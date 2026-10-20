"""Tests d'intégration pour les prédictions, arbitrages et erreurs HTTP (PB-29)."""

from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.api.routers.claims import _SUBMITTED_CLAIMS
from predicare.api.schemas import ClaimDetail, StatutFacture
from predicare.core.security import create_access_token

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


def test_prediction_rbac_permissions():
    """Vérifie que seuls gestionnaire et administrateur peuvent consulter la prédiction (PB-22)."""
    token_assure = create_access_token({"sub": "assure1", "role": "assure"})
    token_pro = create_access_token({"sub": "pro1", "role": "professionnel_sante"})
    token_gest = create_access_token({"sub": "gest1", "role": "gestionnaire"})
    token_admin = create_access_token({"sub": "admin1", "role": "administrateur"})

    # 1. Assuré et Professionnel de santé -> 403 Forbidden
    resp_assure = client.get(
        f"/claims/{_EXISTING_CLAIM}/prediction",
        headers={"Authorization": f"Bearer {token_assure}"},
    )
    assert resp_assure.status_code == 403

    resp_pro = client.get(
        f"/claims/{_EXISTING_CLAIM}/prediction",
        headers={"Authorization": f"Bearer {token_pro}"},
    )
    assert resp_pro.status_code == 403

    # 2. Gestionnaire et Administrateur -> 200 OK
    resp_gest = client.get(
        f"/claims/{_EXISTING_CLAIM}/prediction",
        headers={"Authorization": f"Bearer {token_gest}"},
    )
    assert resp_gest.status_code == 200

    resp_admin = client.get(
        f"/claims/{_EXISTING_CLAIM}/prediction",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp_admin.status_code == 200


def test_prediction_persisted_from_submission():
    """Vérifie la relecture de la prédiction persistée lors d'une soumission réelle (PB-22)."""
    payload = {
        "numero_facture": "F-2026-PERSIST-01",
        "assure_id": "ASS-00421",
        "prestataire_id": "PR-0015",
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
    resp_post = client.post("/claims", json=payload)
    assert resp_post.status_code == 201
    facture_id = resp_post.json()["facture_id"]
    score_soumis = resp_post.json()["score_fraude"]

    # Relecture via GET /claims/{id}/prediction
    resp_pred = client.get(f"/claims/{facture_id}/prediction")
    assert resp_pred.status_code == 200
    data = resp_pred.json()

    assert data["facture_id"] == facture_id
    assert data["prediction"]["score_fraude"] == score_soumis
    assert data["prediction"]["version_modele"] == "v1.0.0-xgb"
    assert len(data["explicabilite"]["top_facteurs"]) > 0


def test_prediction_distinct_404_no_prediction_available():
    """Vérifie la distinction entre facture inconnue et facture sans prédiction (PB-22)."""
    # Facture enregistrée sans prédiction associée
    claim_sans_pred = "FAC-00099991"
    _SUBMITTED_CLAIMS[claim_sans_pred] = ClaimDetail(
        facture_id=claim_sans_pred,
        numero_facture="F-SANS-PRED",
        assure_id="ASS-00421",
        prestataire_id="PR-0015",
        nom_etablissement="Clinique",
        ordonnance_id=None,
        date_soin="2026-10-14",
        date_emission="2026-10-15",
        montant_total=10000,
        part_assure=2000,
        montant_demande=8000,
        statut=StatutFacture.EN_COURS,
        lignes=[],
    )

    resp = client.get(f"/claims/{claim_sans_pred}/prediction")
    assert resp.status_code == 404
    assert "Aucune prédiction disponible" in resp.json()["detail"]


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
