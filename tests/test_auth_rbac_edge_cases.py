"""Tests approfondis de sécurité, tokens JWT et contrôle d'accès RBAC (PB-29)."""

from datetime import timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.testclient import TestClient

from predicare.api.deps import require_roles
from predicare.api.main import app
from predicare.api.schemas import Role, UserInfo
from predicare.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)

client = TestClient(app)

_require_admin = require_roles([Role.ADMINISTRATEUR])


# Route temporaire de test pour valider require_roles de manière isolée
@app.get("/_test/admin-only")
def _admin_only_endpoint(
    user: Annotated[UserInfo, Depends(_require_admin)],
):
    return {"message": f"Bienvenue admin {user.identifier}"}


def test_verify_password_resilience():
    """Vérifie que la comparaison bcrypt gère les mauvais mots de passe et hash corrompus."""
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed) is True
    assert verify_password("mauvais_pwd", hashed) is False
    assert verify_password("secret123", "hash_totalement_invalide") is False


def test_expired_token_returns_401_expired_detail():
    """Vérifie qu'un token JWT expiré renvoie 401 avec le message explicite 'Token expiré.'."""
    expired_token = create_access_token(
        {"sub": "assure1", "role": "assure"},
        expires_delta=timedelta(seconds=-10),  # Déjà expiré
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "Token expiré" in resp.json()["detail"]


def test_malformed_authorization_header():
    """Vérifie le rejet 401 si le header Authorization n'est pas au format Bearer."""
    # Pas de préfixe Bearer
    resp1 = client.get("/auth/me", headers={"Authorization": "Basic 12345"})
    assert resp1.status_code == 401
    assert resp1.json()["detail"] == "Token manquant ou invalide."

    # Bearer sans token
    resp2 = client.get("/auth/me", headers={"Authorization": "Bearer "})
    assert resp2.status_code == 401


def test_token_missing_required_payload_fields():
    """Vérifie le rejet 401 si le token ne contient pas 'sub' ou 'role'."""
    # Manque 'role'
    token_no_role = create_access_token({"sub": "user_sans_role"})
    resp1 = client.get("/auth/me", headers={"Authorization": f"Bearer {token_no_role}"})
    assert resp1.status_code == 401
    assert "payload incomplet" in resp1.json()["detail"]

    # Manque 'sub'
    token_no_sub = create_access_token({"role": "assure"})
    resp2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token_no_sub}"})
    assert resp2.status_code == 401
    assert "payload incomplet" in resp2.json()["detail"]


def test_token_with_invalid_role():
    """Vérifie le rejet 401 si la valeur du rôle dans le JWT est inconnue."""
    token_bad_role = create_access_token({"sub": "hacker", "role": "super_admin_inconnu"})
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token_bad_role}"})
    assert resp.status_code == 401
    assert "Rôle utilisateur inconnu" in resp.json()["detail"]


def test_require_roles_allows_authorized_role():
    """Vérifie que require_roles autorise un utilisateur ayant le rôle attendu."""
    admin_token = create_access_token({"sub": "admin1", "role": "administrateur"})
    resp = client.get("/_test/admin-only", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert "Bienvenue admin admin1" in resp.json()["message"]


def test_require_roles_forbids_unauthorized_role_403():
    """Vérifie que require_roles renvoie 403 Forbidden si l'utilisateur n'a pas le bon rôle."""
    assure_token = create_access_token({"sub": "assure1", "role": "assure"})
    resp = client.get(
        "/_test/admin-only",
        headers={"Authorization": f"Bearer {assure_token}"},
    )
    assert resp.status_code == 403
    assert "Accès refusé pour le rôle" in resp.json()["detail"]
