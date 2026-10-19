"""PB-11 — Registre de versions du modèle et procédure de rollback.

Chaque version entraînée est enregistrée avec son empreinte SHA-256, ses
métriques et son statut (``staging`` / ``production`` / ``archive``). La
production est un **pointeur** : promouvoir une version revient à déplacer ce
pointeur, et ``rollback`` revient à la version précédemment en production.

Le registre vit à la racine du dossier ``models/`` afin de versionner les
artefacts hors du code applicatif.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from predicare.ml.config import MODELS_ROOT, REGISTRY_PATH

STATUTS = ("staging", "production", "archive")


def hacher_artefact(chemin: Path | str) -> str:
    """Empreinte SHA-256 d'un artefact (intégrité du modèle déployé)."""
    digest = hashlib.sha256()
    with open(chemin, "rb") as fichier:
        for bloc in iter(lambda: fichier.read(1 << 20), b""):
            digest.update(bloc)
    return digest.hexdigest()


def _charger(chemin: Path | str | None = None) -> dict:
    chemin = Path(chemin) if chemin else REGISTRY_PATH
    if not chemin.is_file():
        return {"versions": [], "production": None, "historique_production": []}
    return json.loads(chemin.read_text(encoding="utf-8"))


def _ecrire(registre: dict, chemin: Path | str | None = None) -> Path:
    chemin = Path(chemin) if chemin else REGISTRY_PATH
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(registre, indent=2, ensure_ascii=False), encoding="utf-8")
    return chemin


def lister_versions(chemin: Path | str | None = None) -> list[dict]:
    """Liste les versions enregistrées (la plus récente en premier)."""
    return list(reversed(_charger(chemin)["versions"]))


def version_production(chemin: Path | str | None = None) -> str | None:
    """Version actuellement en production."""
    return _charger(chemin).get("production")


def chemin_version(version: str, racine: Path | str | None = None) -> Path:
    """Dossier d'artefacts d'une version (``models/<version>/``)."""
    racine = Path(racine) if racine else MODELS_ROOT
    return racine / version


def enregistrer_version(
    version: str,
    chemin_modele: Path | str,
    metadonnees: dict | None = None,
    statut: str = "staging",
    promouvoir: bool = False,
    chemin_registre: Path | str | None = None,
) -> dict:
    """Enregistre une version et copie son artefact dans ``models/<version>/``."""
    if statut not in STATUTS:
        raise ValueError(f"Statut invalide : {statut!r} (attendu : {STATUTS}).")

    chemin_modele = Path(chemin_modele)
    if not chemin_modele.is_file():
        raise FileNotFoundError(f"Artefact introuvable : {chemin_modele}")

    destination = chemin_version(version) / "model.joblib"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if chemin_modele.resolve() != destination.resolve():
        shutil.copy2(chemin_modele, destination)

    registre = _charger(chemin_registre)
    entree = {
        "version": version,
        "cree": datetime.now(UTC).isoformat(),
        "artefact": str(destination.relative_to(MODELS_ROOT.parent)),
        "sha256": hacher_artefact(destination),
        "statut": statut,
        "metadonnees": metadonnees or {},
    }
    registre["versions"] = [v for v in registre["versions"] if v["version"] != version]
    registre["versions"].append(entree)

    if promouvoir:
        _basculer_production(registre, version)
    _ecrire(registre, chemin_registre)
    return entree


def _basculer_production(registre: dict, version: str) -> None:
    """Déplace le pointeur de production et met à jour l'historique."""
    for entree in registre["versions"]:
        if entree["version"] == version:
            entree["statut"] = "production"
        elif entree["statut"] == "production":
            entree["statut"] = "archive"
    if registre.get("production") != version:
        registre.setdefault("historique_production", []).append(version)
    registre["production"] = version


def promouvoir(version: str, chemin_registre: Path | str | None = None) -> dict:
    """Promeut une version en production."""
    registre = _charger(chemin_registre)
    if version not in {v["version"] for v in registre["versions"]}:
        raise KeyError(f"Version inconnue : {version}")
    _basculer_production(registre, version)
    _ecrire(registre, chemin_registre)
    return registre


def rollback(version: str | None = None, chemin_registre: Path | str | None = None) -> dict:
    """Reviert la production sur une version cible (par défaut l'antérieure)."""
    registre = _charger(chemin_registre)
    historique = registre.get("historique_production", [])
    if version is None:
        if len(historique) < 2:
            raise ValueError("Aucune version antérieure en production : rollback impossible.")
        version = historique[-2]
    if version not in {v["version"] for v in registre["versions"]}:
        raise KeyError(f"Version inconnue : {version}")
    _basculer_production(registre, version)
    _ecrire(registre, chemin_registre)
    return registre


def charger_production(chemin_registre: Path | str | None = None):
    """Charge le modèle en production via :class:`predicare.ml.scoring.ModeleFraude`."""
    from predicare.ml.scoring import charger_modele

    registre = _charger(chemin_registre)
    version = registre.get("production")
    if not version:
        raise RuntimeError("Aucune version en production dans le registre.")
    chemin = MODELS_ROOT.parent / next(
        v["artefact"] for v in registre["versions"] if v["version"] == version
    )
    return charger_modele(chemin)


def main() -> None:  # pragma: no cover - CLI
    import argparse

    parseur = argparse.ArgumentParser(description="Registre de versions du modèle PrediCare")
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("liste")
    for nom in ("promouvoir", "rollback"):
        p = sous.add_parser(nom)
        p.add_argument("version", nargs="?")
    args = parseur.parse_args()

    if args.commande == "liste":
        registre = _charger()
        print(f"Production : {registre.get('production')}")
        for entree in lister_versions():
            print(f" - {entree['version']:8s} [{entree['statut']}] {entree['sha256'][:12]}…")
    elif args.commande == "promouvoir":
        promouvoir(args.version)
        print(f"Production : {version_production()}")
    elif args.commande == "rollback":
        rollback(args.version)
        print(f"Production : {version_production()}")


if __name__ == "__main__":  # pragma: no cover
    main()
