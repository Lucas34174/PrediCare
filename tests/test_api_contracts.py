"""Tests de contrats de l'API PrediCare TPA."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.core.security import create_access_token
from predicare.rag.agent import AgentResult

# Token gestionnaire valide pour tous les tests de contrats (logique métier, pas auth)
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
_ADMIN_TOKEN = create_access_token(
    {
        "sub": "admin1",
        "id": "USR-0001",
        "role": "administrateur",
        "nom_complet": "Administrateur de test",
        "assure_id": None,
        "prestataire_id": None,
    }
)

client = TestClient(app, headers={"Authorization": f"Bearer {_GESTIONNAIRE_TOKEN}"})
_admin_client = TestClient(app, headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"})
# Client non authentifié pour les tests de rejet sans token
_unauth_client = TestClient(app)


# 3.1 Supervision & Santé


# def test_health_structure():
#     data = client.get("/health").json()
#     assert data["status"] == "ok"
#     assert "version" in data
#     assert "database" in data


# 3.2 Authentification & Profil


def test_login_returns_token():
    resp = client.post("/auth/login", json={"identifier": "gestionnaire1", "password": "x"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "gestionnaire"


def test_login_unknown_user_rejected():
    resp = client.post("/auth/login", json={"identifier": "inconnu", "password": "x"})
    assert resp.status_code == 401


def test_login_token_identifie_le_role():
    resp = client.post("/auth/login", json={"identifier": "assure1", "password": "x"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "assure"


def test_me_returns_user_info():
    token = client.post("/auth/login", json={"identifier": "assure1", "password": "x"}).json()[
        "access_token"
    ]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "assure"
    assert "id" in data
    assert "nom_complet" in data


def test_me_sans_token_rejete():
    # Utilise un client sans header d'auth pour vérifier le rejet
    assert _unauth_client.get("/auth/me").status_code == 401


def test_me_token_invalide_rejete():
    resp = client.get("/auth/me", headers={"Authorization": "Bearer n-importe-quoi"})
    assert resp.status_code == 401


# 3.3 Gestion des Factures & Télétransmissions


def test_list_claims_paginated():
    data = client.get("/claims").json()
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["items"], list)


def test_list_claims_query_params():
    data = client.get("/claims?page=2&page_size=10&statut=EN_COURS").json()
    assert data["page"] == 2
    assert data["page_size"] == 10


def test_get_claim_detail():
    data = client.get("/claims/FAC-00005637").json()
    assert "facture_id" in data
    assert isinstance(data["lignes"], list)


def test_create_claim_returns_201():
    payload = {
        "numero_facture": "F-2026-99999",
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
    resp = client.post("/claims", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "facture_id" in data
    assert "score_fraude" in data
    assert "statut" in data


def test_create_claim_incoherent_montant_rejected():
    """montant_total de la ligne incohérent → 422."""
    payload = {
        "numero_facture": "F-2026-BAD",
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
                "montant_total": 99999,  # incohérent : 1 × 30000 ≠ 99999
            }
        ],
    }
    assert client.post("/claims", json=payload).status_code == 422


# 3.4 Détection de Fraude & Arbitrage Métier


def test_get_prediction_structure():
    data = client.get("/claims/FAC-00005637/prediction").json()
    assert "prediction" in data
    assert "explicabilite" in data
    assert 0.0 <= data["prediction"]["score_fraude"] <= 1.0
    assert "version_modele" in data["prediction"]


def test_decision_valide_met_statut_payee():
    payload = {"decision": "VALIDE", "motif": "Dossier conforme", "montant_accorde": 36000}
    data = client.post("/claims/FAC-00005637/decision", json=payload).json()
    assert data["decision"] == "VALIDE"
    assert data["statut"] == "PAYEE"


def test_decision_rejete_met_statut_rejetee():
    payload = {"decision": "REJETE", "motif": "Fraude confirmée", "montant_accorde": 0}
    data = client.post("/claims/FAC-00005637/decision", json=payload).json()
    assert data["statut"] == "REJETEE"


# 3.5 Tableau de Bord Décisionnel & FinOps


@pytest.mark.skip(reason="En attente de configuration de la DB et du token")
def test_dashboard_kpis_structure():
    data = client.get("/dashboard/kpis").json()
    assert "kpis" in data
    assert "distribution_fraudes" in data
    assert "taux_detection_fraude" in data["kpis"]


@pytest.mark.skip(reason="En attente de configuration de la DB et du token")
def test_dashboard_kpis_periode_transmise():
    for periode in ("7d", "30d", "all"):
        assert client.get(f"/dashboard/kpis?periode={periode}").json()["periode"] == periode


# 3.6 Assistant RAG Sécurisé & Agentique


@pytest.mark.skip(reason="En attente de configuration de la DB et du token")
def test_assistant_chat_structure():
    payload = {"message": "Quel est mon plafond dentaire ?", "conversation_id": "conv-test"}
    fake_result = AgentResult(
        answer="Votre plafond dentaire est de 80 000 Ar.",
        abstention=False,
        sources=[{"document": "Conditions Générales", "section": "Article 5"}],
        steps=[],
    )
    with patch("predicare.api.routers.assistant.ReactAgent.run", return_value=fake_result):
        data = client.post("/assistant/chat", json=payload).json()
    assert "response" in data
    assert isinstance(data["sources"], list)
    # assert "provenance_cache_semantique" in data


@pytest.mark.skip(reason="En attente de configuration de la DB et du token")
def test_assistant_message_vide_rejete():
    assert client.post("/assistant/chat", json={"message": ""}).status_code == 422


# 3.7 Administration, MLOps & Exploitation


def test_get_admin_config_structure():
    data = _admin_client.get("/admin/config").json()
    assert "fraud_score_threshold" in data
    assert "n8n_webhook_url" in data
    assert 0.0 <= data["fraud_score_threshold"] <= 1.0


def test_update_admin_config():
    data = _admin_client.put("/admin/config", json={"fraud_score_threshold": 0.75}).json()
    assert data["fraud_score_threshold"] == 0.75


def test_list_models_structure():
    data = client.get("/admin/models").json()
    assert "active_version" in data
    assert len(data["available_models"]) > 0


def test_activate_model(monkeypatch):
    from predicare.api.routers import admin

    monkeypatch.setattr(admin, "promouvoir", lambda version: {"production": version})
    data = _admin_client.post("/admin/models/v0.9.0-baseline/activate").json()
    assert data["active_version"] == "v0.9.0-baseline"
    assert "switched_at" in data


def test_activate_model_refuse_gestionnaire():
    assert client.post("/admin/models/v0.9.0-baseline/activate").status_code == 403


def test_get_metrics_structure():
    data = client.get("/admin/metrics").json()
    assert "api_metrics" in data
    assert data["ml_drift_monitoring"]["metric"] == "PSI"


def test_get_audit_default():
    data = client.get("/admin/audit").json()
    assert "total" in data
    assert isinstance(data["items"], list)


def test_get_audit_filtre_type_action():
    data = client.get("/admin/audit?type_action=DECISION_FRAUDE").json()
    assert "items" in data
    assert len(data["items"]) > 0
    assert data["items"][0]["type_action"] == "DECISION_FRAUDE"


# Erreurs et paramètres (contrat §3.3 à §3.7)

_DECISION_OK = {"decision": "VALIDE", "motif": "Dossier conforme", "montant_accorde": 36000}


def test_get_claim_inconnue_404():
    assert client.get("/claims/FAC-99999999").status_code == 404


def test_get_claim_id_renvoye_par_post_accessible():
    resp = client.get("/claims/FAC-00084700")
    assert resp.status_code == 200
    assert resp.json()["facture_id"] == "FAC-00084700"


def test_prediction_facture_inconnue_404():
    assert client.get("/claims/FAC-99999999/prediction").status_code == 404


def test_decision_facture_inconnue_404():
    assert client.post("/claims/FAC-99999999/decision", json=_DECISION_OK).status_code == 404


def test_decision_valeur_invalide_422():
    payload = {**_DECISION_OK, "decision": "PEUT_ETRE"}
    assert client.post("/claims/FAC-00005637/decision", json=payload).status_code == 422


def test_list_claims_page_size_max_100():
    assert client.get("/claims?page_size=101").status_code == 422
    assert client.get("/claims?page=0").status_code == 422


def test_list_claims_statut_invalide_422():
    assert client.get("/claims?statut=INCONNU").status_code == 422


def test_list_claims_filtres_dates():
    resp = client.get("/claims?date_debut=2025-01-01&date_fin=2025-12-31")
    assert resp.status_code == 200


@pytest.mark.skip(reason="En attente de configuration de la DB et du token")
def test_dashboard_periode_invalide_422():
    assert client.get("/dashboard/kpis?periode=1an").status_code == 422


def test_activate_model_inconnu_404():
    assert _admin_client.post("/admin/models/v9.9.9/activate").status_code == 404


def test_audit_page_invalide_422():
    assert client.get("/admin/audit?page=0").status_code == 422
