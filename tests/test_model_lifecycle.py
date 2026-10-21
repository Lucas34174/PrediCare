"""Lifecycle tests: immutable model versions, atomic promotion and hot rollback."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from predicare.ml import config, registry, service


def _artefact(path, offset: float) -> None:
    X = pd.DataFrame({"f1": [-2.0, -1.0, 1.0, 2.0], "f2": [-1.0, 1.0, -1.0, 1.0]})
    y = np.array([0, 0, 1, 1])
    clf = LogisticRegression(C=1.0 + offset, random_state=42).fit(X, y)
    joblib.dump(
        {
            "pipeline": clf,
            "variables": ["f1", "f2"],
            "version": f"candidate-{offset}",
            "modele": "LogisticRegression",
            "seuil_probabilite_calibree": 0.5,
        },
        path,
    )


@pytest.fixture
def lifecycle_paths(tmp_path, monkeypatch):
    racine = tmp_path / "models"
    racine.mkdir()
    monkeypatch.setattr(config, "MODELS_ROOT", racine)
    monkeypatch.setattr(config, "REGISTRY_PATH", racine / "registry.json")
    monkeypatch.delenv("PREDICARE_MODELE_PATH", raising=False)
    monkeypatch.delenv("PREDICARE_MODELE_VERSION", raising=False)
    service.reset_model_cache()
    yield racine, config.REGISTRY_PATH
    service.reset_model_cache()


def _register(racine, version: str, offset: float):
    source = racine.parent / f"{version}-source.joblib"
    _artefact(source, offset)
    return registry.enregistrer_version(
        version,
        source,
        metadonnees={"modele": "LogisticRegression"},
        racine_modeles=racine,
    )


def test_promotion_et_rollback_changent_le_modele_servi_sans_reset_cache(lifecycle_paths):
    racine, chemin_registre = lifecycle_paths
    _register(racine, "v1-test", 0.0)
    registry.promouvoir("v1-test", chemin_registre)
    service.reset_model_cache()
    ancien = service.get_model()
    assert ancien.version == "v1-test"

    _register(racine, "v2-test", 1.0)
    assert service.get_model().version == "v1-test"  # staging ne change pas le trafic

    registry.promouvoir("v2-test", chemin_registre)
    nouveau = service.get_model()  # aucun redémarrage ni purge de cache requise
    assert nouveau.version == "v2-test"
    assert ancien.version == "v1-test"  # une requête déjà en vol garde son objet
    assert registry.version_production(chemin_registre) == "v2-test"

    registre = registry.rollback(chemin_registre=chemin_registre)
    assert registre["production"] == "v1-test"
    assert service.get_model().version == "v1-test"


def test_modele_actif_integre_doit_avoir_une_empreinte_valide(lifecycle_paths):
    racine, chemin_registre = lifecycle_paths
    _register(racine, "v1-test", 0.0)
    registry.promouvoir("v1-test", chemin_registre)
    _register(racine, "v2-test", 1.0)

    artefact = racine / "v2-test" / "model.joblib"
    artefact.write_bytes(artefact.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA-256"):
        registry.promouvoir("v2-test", chemin_registre)
    assert registry.version_production(chemin_registre) == "v1-test"


def test_artefact_actif_corrompu_maintient_le_dernier_modele_sain(lifecycle_paths):
    racine, chemin_registre = lifecycle_paths
    _register(racine, "v1-test", 0.0)
    registry.promouvoir("v1-test", chemin_registre)
    service.reset_model_cache()
    modele_sain = service.get_model()
    _register(racine, "v2-test", 1.0)
    registry.promouvoir("v2-test", chemin_registre)

    artefact = racine / "v2-test" / "model.joblib"
    artefact.write_bytes(artefact.read_bytes() + b"tamper")
    assert service.get_model() is modele_sain
    assert service.get_model().version == "v1-test"


def test_une_version_ne_peut_pas_ecraser_un_artefact_immuable(lifecycle_paths):
    racine, _ = lifecycle_paths
    _register(racine, "v1-test", 0.0)
    source = racine.parent / "different-source.joblib"
    _artefact(source, 3.0)
    with pytest.raises(FileExistsError, match="immuables"):
        registry.enregistrer_version("v1-test", source, racine_modeles=racine)


def test_bascule_concurrente_ne_produit_ni_erreur_ni_version_inattendue(lifecycle_paths):
    racine, chemin_registre = lifecycle_paths
    _register(racine, "v1-test", 0.0)
    registry.promouvoir("v1-test", chemin_registre)
    service.reset_model_cache()
    _register(racine, "v2-test", 1.0)

    requete_entree = Event()
    terminer_requete_entree = Event()

    def predire_entree():
        model = service.get_model()
        requete_entree.set()
        assert terminer_requete_entree.wait(timeout=20)
        score = model.scorer_unitaire(pd.DataFrame([{"f1": 0.25, "f2": -0.5}]))
        return model.version, score

    def predire_apres_bascule(_: int):
        model = service.get_model()
        score = model.scorer_unitaire(pd.DataFrame([{"f1": 0.25, "f2": -0.5}]))
        return model.version, score

    nombre_requetes = 500
    with ThreadPoolExecutor(max_workers=64) as pool:
        en_cours = pool.submit(predire_entree)
        assert requete_entree.wait(timeout=5)
        registry.promouvoir("v2-test", chemin_registre)
        futures = [pool.submit(predire_apres_bascule, i) for i in range(nombre_requetes - 1)]
        nouvelles_reponses = [future.result(timeout=30) for future in futures]
        terminer_requete_entree.set()
        results = [en_cours.result(timeout=10), *nouvelles_reponses]

    assert len(results) == nombre_requetes
    assert all(version in {"v1-test", "v2-test"} for version, _ in results)
    assert all(np.isfinite(score) and 0 <= score <= 1 for _, score in results)
    assert results[0][0] == "v1-test"
    assert all(version == "v2-test" for version, _ in results[1:])
    assert service.get_model().version == "v2-test"


def test_promotion_d_un_identifiant_inconnu_ne_change_pas_le_registre(lifecycle_paths):
    _, chemin_registre = lifecycle_paths
    with pytest.raises(KeyError, match="inconnue"):
        registry.promouvoir("absente", chemin_registre)
    assert registry.version_production(chemin_registre) is None


def test_api_admin_bascule_et_rollback_le_modele_actif(lifecycle_paths):
    from fastapi.testclient import TestClient

    from predicare.api.main import app
    from predicare.core.security import create_access_token

    racine, _ = lifecycle_paths
    _register(racine, "v1-test", 0.0)
    registry.promouvoir("v1-test")
    _register(racine, "v2-test", 1.0)
    service.reset_model_cache()

    token = create_access_token(
        {
            "sub": "admin1",
            "id": "USR-0001",
            "role": "administrateur",
            "nom_complet": "Administrateur de test",
        }
    )
    client = TestClient(app, headers={"Authorization": f"Bearer {token}"})

    response = client.post("/admin/models/v2-test/activate")
    assert response.status_code == 200
    assert response.json()["active_version"] == "v2-test"
    assert service.get_model().version == "v2-test"
    listed = client.get("/admin/models").json()
    assert listed["active_version"] == "v2-test"
    assert {model["version_id"]: model["statut"] for model in listed["available_models"]} == {
        "v1-test": "ARCHIVED",
        "v2-test": "ACTIVE",
    }

    response = client.post("/admin/models/rollback")
    assert response.status_code == 200
    assert response.json()["active_version"] == "v1-test"
    assert service.get_model().version == "v1-test"
