"""Tests unitaires et d'intégration pour l'émission des alertes n8n (PB-24)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.api.services.alertes import (
    construire_payload_alerte,
    emettre_alerte_fraude,
)
from predicare.core.security import create_access_token

_GESTIONNAIRE_TOKEN = create_access_token(
    {
        "sub": "gestionnaire1",
        "id": "USR-0012",
        "role": "gestionnaire",
        "nom_complet": "Aina Razafy",
        "assure_id": None,
        "prestataire_id": None,
    }
)
client = TestClient(app, headers={"Authorization": f"Bearer {_GESTIONNAIRE_TOKEN}"})


def test_construire_payload_alerte_conforme_contrat_4():
    """Garantit la présence et le format de tous les champs exigés par le §4."""
    facture = {
        "facture_id": "FAC-00005637",
        "numero_facture": "F-2025-00124",
        "date_soin": "2025-04-12",
        "montant_total": 45000,
        "part_assure": 9000,
        "prestataire_id": "PR-0015",
        "assure_id": "ASS-00421",
    }
    top_facteurs = [
        {"description": "Tarif supérieur de 50 %", "feature": "ecart_tarif"},
        {"description": "Jour de fermeture", "feature": "jour_fermeture"},
    ]

    payload = construire_payload_alerte(
        facture=facture,
        score_fraude=0.87,
        seuil_applique=0.80,
        version_modele="v1.0.0-xgb",
        top_facteurs=top_facteurs,
        dashboard_url_base="http://localhost:3000",
    )

    assert payload["event"] == "FRAUD_ALERT"
    assert "timestamp" in payload
    assert payload["facture"]["facture_id"] == "FAC-00005637"
    assert payload["facture"]["montant_demande"] == 36000
    assert payload["facture"]["prestataire_id"] == "PR-0015"
    assert payload["facture"]["assure_id"] == "ASS-00421"
    assert payload["prediction"]["score_fraude"] == 0.87
    assert payload["prediction"]["seuil_applique"] == 0.80
    assert payload["prediction"]["version_modele"] == "v1.0.0-xgb"
    assert payload["explicabilite_shap"]["facteur_principal"] == "Tarif supérieur de 50 %"
    assert payload["explicabilite_shap"]["facteur_secondaire"] == "Jour de fermeture"
    assert payload["liens_action"]["dashboard_url"] == "http://localhost:3000/claims/FAC-00005637"


def test_emettre_alerte_fraude_succes():
    payload = {"facture": {"facture_id": "FAC-TEST-01"}}
    mock_resp = MagicMock(status_code=200)

    with patch.object(httpx.Client, "post", return_value=mock_resp) as mock_post:
        ok = emettre_alerte_fraude(payload, url="http://test-n8n:5678/webhook/fraud-alert")
        assert ok is True
        mock_post.assert_called_once()


def test_emettre_alerte_fraude_echec_injoignable_sans_crash():
    payload = {"facture": {"facture_id": "FAC-TEST-02"}}

    with patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("Connexion refusée")):
        ok = emettre_alerte_fraude(payload, url="http://test-n8n:5678/webhook/fraud-alert")
        assert ok is False

def test_soumission_facture_declenche_alerte_sur_anomalie():
    """Vérifie que POST /claims déclenche emettre_alerte_fraude si est_anomalie est True."""
    payload_claim = {
        "numero_facture": "F-2026-ALERT-01",
        "assure_id": "ASS-00421",
        "prestataire_id": "PR-0015",
        "date_soin": "2026-10-14",
        "date_emission": "2026-10-15",
        "montant_total": 30000,
        "part_assure": 6000,
        "lignes": [
            {
                "num_ligne": 1,
                "code": "ACT-CS-01",
                "type_ligne": "ACTE",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant_total": 30000,
            }
        ],
    }

    with (
        patch("predicare.api.services.alertes.emettre_alerte_fraude") as mock_alerte,
        patch(
            "predicare.api.routers.claims.predire_facture_en_ligne",
            return_value={
                "score_fraude": 0.95,
                "seuil_applique": 0.30,
                "est_anomalie": True,
                "version_modele": "v1.0.0-xgb",
                "top_facteurs": [{"description": "Anomalie", "feature": "x"}],
                "recommandation": "Contrôle requis",
                "date_prediction": "2026-10-20T10:00:00Z",
            },
        ),
    ):
        resp = client.post("/claims", json=payload_claim)
        assert resp.status_code == 201
        assert resp.json()["est_anomalie"] is True
        mock_alerte.assert_called_once()
        args, _ = mock_alerte.call_args
        assert args[0]["event"] == "FRAUD_ALERT"
        assert args[0]["prediction"]["score_fraude"] == 0.95


def test_soumission_facture_pas_d_alerte_si_sous_le_seuil():
    """Vérifie que POST /claims n'émet AUCUNE alerte si est_anomalie est False."""
    payload_claim = {
        "numero_facture": "F-2026-OK-01",
        "assure_id": "ASS-00421",
        "prestataire_id": "PR-0015",
        "date_soin": "2026-10-14",
        "date_emission": "2026-10-15",
        "montant_total": 10000,
        "part_assure": 2000,
        "lignes": [
            {
                "num_ligne": 1,
                "code": "ACT-CS-01",
                "type_ligne": "ACTE",
                "quantite": 1,
                "prix_unitaire": 10000,
                "montant_total": 10000,
            }
        ],
    }

    with (
        patch("predicare.api.services.alertes.emettre_alerte_fraude") as mock_alerte,
        patch(
            "predicare.api.routers.claims.predire_facture_en_ligne",
            return_value={
                "score_fraude": 0.10,
                "seuil_applique": 0.30,
                "est_anomalie": False,
                "version_modele": "v1.0.0-xgb",
                "top_facteurs": [],
                "recommandation": "Conforme",
                "date_prediction": "2026-10-20T10:00:00Z",
            },
        ),
    ):
        resp = client.post("/claims", json=payload_claim)
        assert resp.status_code == 201
        assert resp.json()["est_anomalie"] is False
        mock_alerte.assert_not_called()
