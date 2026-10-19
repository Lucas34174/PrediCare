"""Tests PB-11 : registre de versions et rollback."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from predicare.ml import registry


@pytest.fixture()
def registre_isole(monkeypatch):
    """Redirige les artefacts et le registre vers un dossier temporaire.

    On n'utilise pas la fixture ``tmp_path`` de pytest : le contrôle de
    propriété du dossier temporaire échoue sur certains systèmes de fichiers
    montés (tous les fichiers apparaissent appartenir à ``root``).
    """
    base = Path(tempfile.mkdtemp(prefix="predicare-registry-"))
    monkeypatch.setattr(registry, "MODELS_ROOT", base / "models")
    chemin_registre = base / "models" / "registry.json"
    artefacts = []
    for version, contenu in (("v1.0.0", b"modele-v1"), ("v1.0.1", b"modele-v1.1")):
        chemin = base / f"{version}.joblib"
        chemin.write_bytes(contenu)
        artefacts.append((version, chemin))
    yield chemin_registre, artefacts
    shutil.rmtree(base, ignore_errors=True)


def test_enregistrer_et_empreinte(registre_isole):
    chemin_registre, artefacts = registre_isole
    version, chemin = artefacts[0]
    entree = registry.enregistrer_version(
        version, chemin, metadonnees={"modele": "LightGBM"}, promouvoir=True,
        chemin_registre=chemin_registre,
    )
    assert len(entree["sha256"]) == 64
    assert entree["statut"] == "production"
    assert registry.version_production(chemin_registre) == version
    assert (chemin_registre.parent / version / "model.joblib").is_file()


def test_promotion_et_historique(registre_isole):
    chemin_registre, artefacts = registre_isole
    for version, chemin in artefacts:
        registry.enregistrer_version(version, chemin, chemin_registre=chemin_registre)
    registry.promouvoir("v1.0.0", chemin_registre=chemin_registre)
    registry.promouvoir("v1.0.1", chemin_registre=chemin_registre)
    registre = registry._charger(chemin_registre)
    assert registre["production"] == "v1.0.1"
    assert registre["historique_production"] == ["v1.0.0", "v1.0.1"]
    statuts = {v["version"]: v["statut"] for v in registre["versions"]}
    assert statuts == {"v1.0.0": "archive", "v1.0.1": "production"}


def test_rollback_revient_a_la_version_precedente(registre_isole):
    chemin_registre, artefacts = registre_isole
    for version, chemin in artefacts:
        registry.enregistrer_version(version, chemin, chemin_registre=chemin_registre)
    registry.promouvoir("v1.0.0", chemin_registre=chemin_registre)
    registry.promouvoir("v1.0.1", chemin_registre=chemin_registre)
    registry.rollback(chemin_registre=chemin_registre)
    assert registry.version_production(chemin_registre) == "v1.0.0"


def test_rollback_sans_historique_echoue(registre_isole):
    chemin_registre, artefacts = registre_isole
    version, chemin = artefacts[0]
    registry.enregistrer_version(version, chemin, promouvoir=True, chemin_registre=chemin_registre)
    with pytest.raises(ValueError):
        registry.rollback(chemin_registre=chemin_registre)


def test_version_inconnue(registre_isole):
    chemin_registre, _ = registre_isole
    with pytest.raises(KeyError):
        registry.promouvoir("v9.9.9", chemin_registre=chemin_registre)


def test_statut_invalide(registre_isole):
    chemin_registre, artefacts = registre_isole
    version, chemin = artefacts[0]
    with pytest.raises(ValueError):
        registry.enregistrer_version(
            version, chemin, statut="inconnu", chemin_registre=chemin_registre
        )
