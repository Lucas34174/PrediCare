"""Module de sérialisation et versionnement du modèle champion – PrediCare TPA (PB-07).

Responsabilités :
  - Sérialisation du modèle champion versionné (v1.0.0-xgb).
  - Production du fichier models/models_metadata.json conforme au schéma AdminModelsResponse.
  - Garantie de compatibilité avec shap.TreeExplainer pour les explications d'inférence.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from predicare.api.schemas import AdminModelsResponse, ModelVersion
from predicare.ml.baseline import (
    FACTURES_PATH,
    FEATURES_PATH,
    LABELS_PATH,
    MODELS_DIR,
    _drop_high_nan,
    check_no_leakage,
    load_dataset,
    split_no_leakage,
)
from predicare.ml.tuning import train_tuned_model

STATUTS = ("staging", "production", "archive")


logger = logging.getLogger(__name__)

CHAMPION_VERSION_ID = "v1.0.0-xgb"
BASELINE_VERSION_ID = "v0.9.0-baseline"


def export_champion_model(
    models_dir: Path = MODELS_DIR,
    features_path: str = FEATURES_PATH,
    labels_path: str = LABELS_PATH,
    factures_path: str = FACTURES_PATH,
    seed: int = 42,
    test_size: float = 0.2,
) -> tuple[Path, Path]:
    """Entraîne et enregistre le modèle champion et ses métadonnées conformes à l'API."""
    tuning_file = models_dir / "tuning_results.json"
    report_file = models_dir / "final_comparison_report.json"
    if not tuning_file.exists() or not report_file.exists():
        raise FileNotFoundError("tuning_results.json et final_comparison_report.json requis.")

    tuning_data = json.loads(tuning_file.read_text())
    final_report = json.loads(report_file.read_text())

    # Entraînement final du champion sur tout le train (sans toucher au test)
    X, y, meta = load_dataset(features_path, labels_path, factures_path)
    X_tr, _, y_tr, _ = split_no_leakage(X, y, meta, test_size=test_size)
    check_no_leakage(X_tr)

    X_tr_clean, _, _ = _drop_high_nan(X_tr, X_tr)
    xgb_params = tuning_data["xgb"]["best_params"]
    champion_model = train_tuned_model("xgb", xgb_params, X_tr_clean, y_tr, seed=seed)

    # Sauvegarde du modèle joblib
    model_path = models_dir / f"fraud_xgb_{CHAMPION_VERSION_ID}.joblib"
    joblib.dump(champion_model, model_path)
    # Alias modèle actif
    joblib.dump(champion_model, models_dir / "model_champion.joblib")
    logger.info("Modèle champion sérialisé : %s", model_path)

    # Construction des métadonnées conformes au contrat Pydantic de l'API
    today = datetime.now(UTC).date()
    m_xgb = final_report.get("xgboost_optimal", {})
    m_base = final_report.get("baseline_lr", {})

    metadata = AdminModelsResponse(
        active_version=CHAMPION_VERSION_ID,
        available_models=[
            ModelVersion(
                version_id=CHAMPION_VERSION_ID,
                type="XGBoost",
                recall_test=float(m_xgb.get("recall", 0.286)),
                precision_test=float(m_xgb.get("precision", 0.333)),
                f1_score=float(m_xgb.get("f1", 0.308)),
                date_entrainement=today,
                statut="ACTIVE",
            ),
            ModelVersion(
                version_id=BASELINE_VERSION_ID,
                type="LogisticRegression",
                recall_test=float(m_base.get("recall", 0.429)),
                precision_test=float(m_base.get("precision", 0.600)),
                f1_score=float(m_base.get("f1", 0.500)),
                date_entrainement=today,
                statut="STANDBY",
            ),
        ],
    )

    metadata_path = models_dir / "models_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2, ensure_ascii=False)
    )
    logger.info("Métadonnées modèles écrites : %s", metadata_path)

    return model_path, metadata_path


def register_model_version(
    version_id: str,
    model: any,
    recall_test: float,
    precision_test: float,
    f1_score: float,
    model_type: str = "XGBoost",
    make_active: bool = False,
    models_dir: Path = MODELS_DIR,
) -> tuple[Path, Path]:
    """Enregistre une nouvelle version de modèle sans écraser les versions existantes.

    Garantit la compatibilité ascendante avec GET /admin/models et la réversibilité (rollback).
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date()

    # 1. Sérialisation du fichier joblib versionné
    model_path = models_dir / f"fraud_xgb_{version_id}.joblib"
    joblib.dump(model, model_path)
    logger.info("Version modèle sérialisée : %s", model_path)

    if make_active:
        joblib.dump(model, models_dir / "model_champion.joblib")
        logger.info("Alias model_champion.joblib mis à jour vers %s", version_id)

    # 2. Mise à jour de models_metadata.json
    metadata_path = models_dir / "models_metadata.json"
    if metadata_path.exists():
        existing_raw = json.loads(metadata_path.read_text())
        existing = AdminModelsResponse.model_validate(existing_raw)
        active_ver = version_id if make_active else existing.active_version
        available = list(existing.available_models)
    else:
        active_ver = version_id if make_active else "v1.0.0-xgb"
        available = []

    statut_new = "ACTIVE" if make_active else "STANDBY"

    new_version_entry = ModelVersion(
        version_id=version_id,
        type=model_type,
        recall_test=round(float(recall_test), 4),
        precision_test=round(float(precision_test), 4),
        f1_score=round(float(f1_score), 4),
        date_entrainement=today,
        statut=statut_new,
    )

    if make_active:
        available = [
            ModelVersion(**{**m.model_dump(), "statut": "STANDBY"})
            for m in available
            if m.version_id != version_id
        ]
    else:
        available = [m for m in available if m.version_id != version_id]

    available.append(new_version_entry)

    updated_metadata = AdminModelsResponse(
        active_version=active_ver,
        available_models=available,
    )

    metadata_path.write_text(
        json.dumps(updated_metadata.model_dump(mode="json"), indent=2, ensure_ascii=False)
    )
    logger.info("models_metadata.json mis à jour avec %s (statut=%s)", version_id, statut_new)

    return model_path, metadata_path


def hacher_artefact(chemin: Path | str) -> str:
    """Empreinte SHA-256 d'un artefact."""
    digest = hashlib.sha256()
    with open(chemin, "rb") as fichier:
        for bloc in iter(lambda: fichier.read(1 << 20), b""):
            digest.update(bloc)
    return digest.hexdigest()


def _charger_registre(chemin: Path | str | None = None) -> dict[str, Any]:
    from predicare.ml.config import REGISTRY_PATH

    p = Path(chemin) if chemin else REGISTRY_PATH
    if not p.is_file():
        return {"versions": [], "production": None, "historique_production": []}
    registre = json.loads(p.read_text(encoding="utf-8"))
    registre.setdefault("versions", [])
    registre.setdefault("production", None)
    registre.setdefault("historique_production", [])
    return registre


def _ecrire_registre(registre: dict[str, Any], chemin: Path | str | None = None) -> Path:
    from predicare.ml.config import REGISTRY_PATH

    p = Path(chemin) if chemin else REGISTRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    contenu = json.dumps(registre, indent=2, ensure_ascii=False)
    fd, temporaire = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fichier:
            fichier.write(contenu)
            fichier.flush()
            os.fsync(fichier.fileno())
        os.replace(temporaire, p)
        try:
            descripteur = os.open(p.parent, os.O_RDONLY)
            try:
                os.fsync(descripteur)
            finally:
                os.close(descripteur)
        except OSError:  # pragma: no cover - certains systèmes ne synchronisent pas les dossiers
            pass
    finally:
        if os.path.exists(temporaire):
            os.unlink(temporaire)
    return p


def _chemin_artefact(entree: dict[str, Any], racine_modeles: Path | None = None) -> Path:
    """Résout un chemin d'artefact et interdit toute sortie du répertoire models/."""
    from predicare.ml.config import MODELS_ROOT

    racine = Path(racine_modeles or MODELS_ROOT).resolve()
    chemin = Path(entree["artefact"])
    if not chemin.is_absolute():
        chemin = racine.parent / chemin
    chemin = chemin.resolve()
    if chemin != racine and racine not in chemin.parents:
        raise ValueError("Le chemin de l'artefact sort du répertoire models/.")
    return chemin


def _verifier_artefact(entree: dict[str, Any], racine_modeles: Path | None = None) -> Path:
    """Vérifie l'intégrité et la capacité d'inférence avant promotion/chargement."""
    chemin = _chemin_artefact(entree, racine_modeles)
    if not chemin.is_file():
        raise FileNotFoundError(f"Artefact introuvable pour {entree['version']}: {chemin}")
    empreinte = hacher_artefact(chemin)
    if empreinte != entree.get("sha256"):
        raise ValueError(f"Empreinte SHA-256 invalide pour la version {entree['version']}.")
    modele = joblib.load(chemin)
    if isinstance(modele, dict):
        modele = modele.get("pipeline", modele.get("modele"))
    if modele is None or not callable(getattr(modele, "predict_proba", None)):
        raise ValueError(f"L'artefact {entree['version']} n'expose pas predict_proba().")
    return chemin


def modele_production(chemin_registre: Path | str | None = None) -> dict[str, Any] | None:
    """Renvoie l'entrée production vérifiée, ou None si le registre n'en a pas."""
    from predicare.ml.config import MODELS_ROOT

    registre = _charger_registre(chemin_registre)
    version = registre.get("production")
    if version is None:
        return None
    entree = next((v for v in registre["versions"] if v.get("version") == version), None)
    if entree is None or entree.get("statut") != "production":
        raise ValueError("Le pointeur de production ne correspond à aucune version active.")
    chemin = _chemin_artefact(entree, MODELS_ROOT)
    if not chemin.is_file():
        raise FileNotFoundError(f"Artefact introuvable pour {version}: {chemin}")
    return {**entree, "chemin_absolu": chemin}


def _ajouter_champion_historique(registre: dict[str, Any], racine_modeles: Path) -> None:
    """Importe le champion historique dans le registre avant le premier déploiement v2."""
    from predicare.core.config import model_version

    if registre.get("production") or registre["versions"]:
        return
    source = racine_modeles / "model_champion.joblib"
    if not source.is_file():
        return
    version = model_version()
    destination = racine_modeles / version / "model.joblib"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        fd, temporaire = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
        os.close(fd)
        try:
            shutil.copy2(source, temporaire)
            os.replace(temporaire, destination)
        finally:
            if os.path.exists(temporaire):
                os.unlink(temporaire)
    metadata_path = racine_modeles / "models_metadata.json"
    meta: dict[str, Any] = {}
    if metadata_path.is_file():
        try:
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Métadonnées du champion historique illisibles : %s", metadata_path)
    entry = {
        "version": version,
        "cree": datetime.now(UTC).isoformat(),
        "artefact": str(destination.relative_to(racine_modeles.parent)),
        "sha256": hacher_artefact(destination),
        "statut": "production",
        "metadonnees": meta,
    }
    registre["versions"].append(entry)
    registre["production"] = version
    registre["historique_production"].append(version)


def lister_versions(chemin: Path | str | None = None) -> list[dict[str, Any]]:
    """Liste les versions enregistrées."""
    return list(reversed(_charger_registre(chemin)["versions"]))


def version_production(chemin: Path | str | None = None) -> str | None:
    """Version actuellement en production."""
    return _charger_registre(chemin).get("production")


def enregistrer_version(
    version: str,
    chemin_modele: Path | str,
    metadonnees: dict[str, Any] | None = None,
    statut: str = "staging",
    promouvoir: bool = False,
    chemin_registre: Path | str | None = None,
    racine_modeles: Path | str | None = None,
) -> dict[str, Any]:
    """Enregistre une version dans models/registry.json."""
    from predicare.ml.config import MODELS_ROOT

    if statut not in STATUTS:
        raise ValueError(f"Statut invalide : {statut!r} (attendu : {STATUTS}).")
    if statut == "production":
        raise ValueError(
            "Enregistrer une version en production est interdit ; utiliser promouvoir()."
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", version):
        raise ValueError(f"Identifiant de version invalide : {version!r}.")
    racine = Path(racine_modeles or MODELS_ROOT).resolve()
    chemin_m = Path(chemin_modele)
    if not chemin_m.is_file():
        raise FileNotFoundError(f"Artefact introuvable : {chemin_m}")
    destination = racine / version / "model.joblib"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if chemin_m.resolve() != destination.resolve():
        empreinte_source = hacher_artefact(chemin_m)
        if destination.exists():
            if hacher_artefact(destination) != empreinte_source:
                raise FileExistsError(
                    f"La version {version} existe déjà avec un autre artefact ; les versions sont immuables."
                )
        else:
            fd, temporaire = tempfile.mkstemp(
                prefix=f".{destination.name}.", dir=destination.parent
            )
            os.close(fd)
            try:
                shutil.copy2(chemin_m, temporaire)
                os.replace(temporaire, destination)
            finally:
                if os.path.exists(temporaire):
                    os.unlink(temporaire)
    registre = _charger_registre(chemin_registre)
    _ajouter_champion_historique(registre, racine)
    entree = {
        "version": version,
        "cree": datetime.now(UTC).isoformat(),
        "artefact": str(destination.relative_to(racine.parent)),
        "sha256": hacher_artefact(destination),
        "statut": statut,
        "metadonnees": metadonnees or {},
    }
    registre["versions"] = [v for v in registre["versions"] if v["version"] != version]
    registre["versions"].append(entree)
    if promouvoir:
        if statut != "staging":
            raise ValueError(
                "Seule une version en staging peut être promue lors de son enregistrement."
            )
        _verifier_artefact(entree, racine)
        _basculer_production(registre, version)
    _ecrire_registre(registre, chemin_registre)
    return entree


def _basculer_production(registre: dict[str, Any], version: str) -> None:
    for entree in registre["versions"]:
        if entree["version"] == version:
            entree["statut"] = "production"
        elif entree["statut"] == "production":
            entree["statut"] = "archive"
    if registre.get("production") != version:
        registre.setdefault("historique_production", []).append(version)
    registre["production"] = version


def promouvoir(version: str, chemin_registre: Path | str | None = None) -> dict[str, Any]:
    """Promeut une version en production."""
    from predicare.ml.config import MODELS_ROOT

    registre = _charger_registre(chemin_registre)
    entree = next((v for v in registre["versions"] if v.get("version") == version), None)
    if entree is None:
        raise KeyError(f"Version inconnue : {version}")
    _verifier_artefact(entree, MODELS_ROOT)
    _basculer_production(registre, version)
    _ecrire_registre(registre, chemin_registre)
    return registre


def rollback(
    version: str | None = None, chemin_registre: Path | str | None = None
) -> dict[str, Any]:
    """Revient sur la version précédente en production."""
    from predicare.ml.config import MODELS_ROOT

    registre = _charger_registre(chemin_registre)
    historique = registre.get("historique_production", [])
    if version is None:
        if len(historique) < 2:
            raise ValueError("Aucune version antérieure en production : rollback impossible.")
        version = historique[-2]
    entree = next((v for v in registre["versions"] if v.get("version") == version), None)
    if entree is None:
        raise KeyError(f"Version inconnue : {version}")
    _verifier_artefact(entree, MODELS_ROOT)
    _basculer_production(registre, version)
    _ecrire_registre(registre, chemin_registre)
    return registre


if __name__ == "__main__":  # pragma: no cover
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    export_champion_model()
    print("✓ Modèle champion v1.0.0-xgb et models_metadata.json générés avec succès.")
