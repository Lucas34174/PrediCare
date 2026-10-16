"""Tests d'intégration pour les prédictions, arbitrages et erreurs HTTP (PB-29)."""

from fastapi.testclient import TestClient

from predicare.api.main import app

client = TestClient(app)

_EXISTING_CLAIM = "FAC-00005637"
_UNKNOWN_CLAIM = "FAC-99999999"


# 1. Tests des Prédictions et Explicabilité SHAP


def test_prediction_schema_and_shap_explainability():
    """Vérifie la présence et la cohérence de tous les champs de prédiction et SHAP."""
    resp = client.get(f"/claims/{_EXISTING_CLAIM}/prediction")
    assert resp.status_code == 200
    data = resp.json()

    # Métadonnées de prédiction
    pred = data["prediction"]
    assert 0.0 <= pred["score_fraude"] <= 1.0
    assert 0.0 <= pred["seuil_applique"] <= 1.0
    assert isinstance(pred["est_anomalie"], bool)
    assert pred["version_modele"]
    assert pred["date_prediction"]

    # Explicabilité SHAP
    expl = data["explicabilite"]
    assert len(expl["top_facteurs"]) > 0
    for factor in expl["top_facteurs"]:
        assert factor["feature"]
        assert isinstance(factor["impact_shap"], (int, float))
        assert factor["description"]
    assert expl["recommandation"]


def test_prediction_not_found_404():
    """Vérifie le rejet 404 lors d'une demande de prédiction pour une facture inexistante."""
    resp = client.get(f"/claims/{_UNKNOWN_CLAIM}/prediction")
    assert resp.status_code == 404
    assert "introuvable" in resp.json()["detail"]


# 2. Tests des Décisions Gestionnaire (Cycle de vie)


def test_decision_investigation_sets_status_en_cours():
    """Vérifie qu'un arbitrage 'INVESTIGATION' place la facture en statut 'EN_COURS'."""
    payload = {
        "decision": "INVESTIGATION",
        "motif": "Demande de pièces justificatives complémentaires",
        "montant_accorde": 0,
    }
    resp = client.post(f"/claims/{_EXISTING_CLAIM}/decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "INVESTIGATION"
    assert data["statut"] == "EN_COURS"


def test_decision_on_unknown_claim_returns_404():
    """Vérifie le rejet 404 lors d'une décision sur une facture inconnue."""
    payload = {
        "decision": "VALIDE",
        "motif": "Conforme",
        "montant_accorde": 10000,
    }
    resp = client.post(f"/claims/{_UNKNOWN_CLAIM}/decision", json=payload)
    assert resp.status_code == 404
    assert "introuvable" in resp.json()["detail"]


def test_decision_invalid_payload_returns_422():
    """Vérifie le rejet 422 si le corps de décision est incomplet ou malformé."""
    # Motif manquant
    resp1 = client.post(f"/claims/{_EXISTING_CLAIM}/decision", json={"decision": "VALIDE"})
    assert resp1.status_code == 422

    # Décision invalide
    resp2 = client.post(
        f"/claims/{_EXISTING_CLAIM}/decision",
        json={"decision": "INCONNUE", "motif": "test"},
    )
    assert resp2.status_code == 422


# 3. Tests des Erreurs HTTP Globales (404, 405, 422)


def test_unknown_endpoint_returns_404():
    """Vérifie le code 404 sur une URL inconnue de l'API."""
    resp = client.get("/api/v1/route-qui-nexiste-absolument-pas")
    assert resp.status_code == 404


def test_method_not_allowed_returns_405():
    """Vérifie le code 405 lors de l'appel d'une méthode HTTP non autorisée."""
    # DELETE non supporté sur /claims
    resp1 = client.delete("/claims")
    assert resp1.status_code == 405

    # POST non supporté sur /health
    resp2 = client.post("/health")
    assert resp2.status_code == 405


def test_query_params_validation_errors_422():
    """Vérifie le code 422 sur des paramètres de requête de types incompatibles."""
    # page non numérique
    resp1 = client.get("/claims?page=premiere_page")
    assert resp1.status_code == 422

    # page_size négatif
    resp2 = client.get("/claims?page_size=-10")
    assert resp2.status_code == 422
