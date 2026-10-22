"""Tests unitaires et d'intégration pour l'authentification JWT et le RBAC (PB-20)."""

from datetime import timedelta

from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.core.security import create_access_token, decode_access_token

client = TestClient(app)


def test_login_success_returns_valid_jwt():
    """Vérifie que /auth/login émet un JWT valide et décodable."""
    resp = client.post("/auth/login", json={"identifier": "gestionnaire1", "password": "x"})
    assert resp.status_code == 200
    data = resp.json()

    token = data["access_token"]
    payload = decode_access_token(token)
    assert payload["sub"] == "gestionnaire1"
    assert payload["role"] == "gestionnaire"
    assert payload["id"] == "USR-0012"


def test_login_invalid_credentials_rejected():
    """Identifiant inconnu ou mot de passe erroné renvoie 401."""
    resp = client.post("/auth/login", json={"identifier": "utilisateur_fantome", "password": "x"})
    assert resp.status_code == 401

    resp_wrong = client.post(
        "/auth/login", json={"identifier": "admin1", "password": "mauvais_mot_de_passe"}
    )
    assert resp_wrong.status_code == 401


def test_auth_me_with_valid_jwt():
    """GET /auth/me renvoie le profil complet extrait du token."""
    login_resp = client.post("/auth/login", json={"identifier": "assure1", "password": "x"})
    token = login_resp.json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    user = resp.json()
    assert user["identifier"] == "assure1"
    assert user["role"] == "assure"
    assert user["assure_id"] == "ASS-00421"


def test_auth_me_with_expired_token():
    """Un token expiré est systématiquement rejeté avec 401."""
    expired_token = create_access_token(
        {"sub": "admin1", "role": "administrateur", "id": "USR-0001"},
        expires_delta=timedelta(seconds=-10),
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expiré."


def test_auth_me_with_tampered_token():
    """Un token altéré ou malformé renvoie 401."""
    resp = client.get(
        "/auth/me", headers={"Authorization": "Bearer token.invalide.fausse_signature"}
    )
    assert resp.status_code == 401


def test_assure_ne_voit_que_son_propre_dossier():
    """l'assuré titulaire accède au dossier (200), un autre assuré est rejeté (403)."""
    # 1. L'assuré titulaire (ASS-00421) accède à sa facture FAC-00005637
    login_titulaire = client.post("/auth/login", json={"identifier": "assure1", "password": "x"})
    token_titulaire = login_titulaire.json()["access_token"]

    resp_titulaire = client.get(
        "/claims/FAC-00005637", headers={"Authorization": f"Bearer {token_titulaire}"}
    )
    assert resp_titulaire.status_code == 200
    assert resp_titulaire.json()["assure_id"] == "ASS-00421"

    # 2. Un autre assuré tente d'accéder au dossier de ASS-00421 -> 403 Forbidden
    token_autre_assure = create_access_token(
        {
            "sub": "autre_assure",
            "role": "assure",
            "id": "ASS-99999",
            "assure_id": "ASS-99999",
            "nom_complet": "Autre Personne",
        }
    )
    resp_autre = client.get(
        "/claims/FAC-00005637", headers={"Authorization": f"Bearer {token_autre_assure}"}
    )
    assert resp_autre.status_code == 403
    assert "titulaire" in resp_autre.json()["detail"]


def test_assure_liste_filtree():
    """Un assuré ne voit dans la liste que ses factures (total=0 si aucun dossier à son nom)."""
    token_autre_assure = create_access_token(
        {
            "sub": "autre_assure",
            "role": "assure",
            "id": "ASS-99999",
            "assure_id": "ASS-99999",
            "nom_complet": "Autre Personne",
        }
    )
    resp = client.get("/claims", headers={"Authorization": f"Bearer {token_autre_assure}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert len(resp.json()["items"]) == 0
