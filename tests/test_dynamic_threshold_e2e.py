"""Tests de bout en bout pour l'effet immédiat du seuil dynamique et des alertes (PB-25).

Vérifie l'absence de redémarrage nécessaire, la persistance du seuil appliqué
et la mise à jour à chaud de l'URL du webhook n8n.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.core.config_service import (
    get_current_fraud_threshold,
    get_current_n8n_webhook_url,
    invalidate_config_cache,
)
from predicare.core.security import create_access_token

_ADMIN_TOKEN = create_access_token(
    {"sub": "admin1", "id": "USR-0001", "role": "administrateur", "nom_complet": "Admin Test"}
)
_GESTIONNAIRE_TOKEN = create_access_token(
    {"sub": "gest1", "id": "USR-0012", "role": "gestionnaire", "nom_complet": "Gest Test"}
)

_admin_client = TestClient(app, headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"})
_gest_client = TestClient(app, headers={"Authorization": f"Bearer {_GESTIONNAIRE_TOKEN}"})


@pytest.fixture(autouse=True)
def clean_config():
    """Réinitialise le cache et restaure la configuration nominale avant et après chaque test."""
    invalidate_config_cache(clear_overrides=True)
    yield
    invalidate_config_cache(clear_overrides=True)


def _facture_payload(numero: str) -> dict:
    return {
        "numero_facture": numero,
        "assure_id": "ASS-00421",
        "prestataire_id": "PR-0015",
        "ordonnance_id": "ORD-0003289",
        "date_soin": "2026-10-14",
        "date_emission": "2026-10-15",
        "montant_total": 45000,
        "part_assure": 9000,
        "lignes": [
            {
                "num_ligne": 1,
                "code": "ACT-CS-01",
                "type_ligne": "ACTE",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant_total": 30000,
            },
            {
                "num_ligne": 2,
                "code": "MED-CIP-0045",
                "type_ligne": "MEDICAMENT",
                "quantite": 2,
                "prix_unitaire": 7500,
                "montant_total": 15000,
            },
        ],
    }


def test_effet_immediat_modification_seuil_sans_redemarrage():
    """TEST CLÉ PB-25 : Vérifie l'effet immédiat sans redémarrage sur POST /claims.

    1. Seuil initial = 0.80. Facture avec score contrôlé à 0.85 -> est_anomalie: true, seuil_applique: 0.80
    2. PUT /admin/config -> seuil = 0.90
    3. Même facture avec même score (0.85) -> est_anomalie: false, seuil_applique: 0.90
    """
    # 1. Configuration initiale à 0.80
    resp_init = _admin_client.put("/admin/config", json={"fraud_score_threshold": 0.80})
    assert resp_init.status_code == 200
    assert resp_init.json()["fraud_score_threshold"] == 0.80
    assert get_current_fraud_threshold() == 0.80

    mock_model = MagicMock()
    mock_model.version = "v-test-controlled"
    # Le modèle retourne toujours un score fixe de 0.85
    mock_model.scorer_unitaire.return_value = 0.85

    with (
        patch("predicare.ml.service.get_model", return_value=mock_model),
        patch(
            "predicare.ml.service.expliquer_facture",
            return_value=([{"description": "Score élevé", "feature": "montant"}], "Contrôle"),
        ),
    ):
        # Première soumission sous seuil 0.80
        resp1 = _gest_client.post("/claims", json=_facture_payload("F-E2E-001"))
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["score_fraude"] == 0.85
        assert data1["seuil_applique"] == 0.80
        assert data1["est_anomalie"] is True

        # 2. Modification EN DIRECT via l'API vers 0.90
        resp_update = _admin_client.put("/admin/config", json={"fraud_score_threshold": 0.90})
        assert resp_update.status_code == 200
        assert resp_update.json()["fraud_score_threshold"] == 0.90
        assert get_current_fraud_threshold() == 0.90

        # 3. Deuxième soumission immédiate sous seuil 0.90 (SANS redémarrage ni recréation d'app)
        resp2 = _gest_client.post("/claims", json=_facture_payload("F-E2E-002"))
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["score_fraude"] == 0.85
        assert data2["seuil_applique"] == 0.90
        assert data2["est_anomalie"] is False


def test_relecture_prediction_preserve_seuil_applique():
    """Vérifie que le seuil_applique est fidèlement conservé lors de la consultation."""
    _admin_client.put("/admin/config", json={"fraud_score_threshold": 0.77})

    mock_model = MagicMock()
    mock_model.version = "v-test-controlled"
    mock_model.scorer_unitaire.return_value = 0.82

    with (
        patch("predicare.ml.service.get_model", return_value=mock_model),
        patch(
            "predicare.ml.service.expliquer_facture",
            return_value=(
                [
                    {
                        "feature": "montant",
                        "valeur": 45000,
                        "impact_shap": 0.42,
                        "description": "Score élevé",
                    }
                ],
                "Contrôle",
            ),
        ),
    ):
        resp_create = _gest_client.post("/claims", json=_facture_payload("F-E2E-PRESERVE"))
        assert resp_create.status_code == 201
        facture_id = resp_create.json()["facture_id"]

        # Consultation de la prédiction associée
        resp_pred = _gest_client.get(f"/claims/{facture_id}/prediction")
        assert resp_pred.status_code == 200
        pred_data = resp_pred.json()["prediction"]
        assert pred_data["seuil_applique"] == 0.77
        assert pred_data["score_fraude"] == 0.82
        assert pred_data["est_anomalie"] is True


def test_emission_alerte_n8n_utilise_url_dynamique_a_chaud():
    """Vérifie que l'URL du webhook n8n modifiée en direct est immédiatement utilisée."""
    target_url = "http://n8n-dynamique.local:5678/webhook/alerte-fraude-live"
    resp_cfg = _admin_client.put(
        "/admin/config",
        json={"n8n_webhook_url": target_url, "fraud_score_threshold": 0.50},
    )
    assert resp_cfg.status_code == 200
    assert get_current_n8n_webhook_url() == target_url

    mock_model = MagicMock()
    mock_model.version = "v-test-n8n"
    mock_model.scorer_unitaire.return_value = 0.92

    with (
        patch("predicare.ml.service.get_model", return_value=mock_model),
        patch(
            "predicare.ml.service.expliquer_facture",
            return_value=(
                [
                    {
                        "feature": "montant",
                        "valeur": 45000,
                        "impact_shap": 0.42,
                        "description": "Score élevé",
                    }
                ],
                "Contrôle",
            ),
        ),
    ):
        with patch("predicare.api.services.alertes.httpx.Client") as mock_httpx:
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__.return_value = mock_client_instance
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client_instance.post.return_value = mock_resp
            mock_httpx.return_value = mock_client_instance

            resp = _gest_client.post("/claims", json=_facture_payload("F-E2E-N8N"))
            assert resp.status_code == 201
            assert resp.json()["est_anomalie"] is True

            # Vérifie que httpx.Client.post a bien été appelé avec l'URL dynamique
            mock_client_instance.post.assert_called_once()
            args, _ = mock_client_instance.post.call_args
            assert args[0] == target_url
