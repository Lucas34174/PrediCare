"""Tests d'intégration et de validation RBAC / schémas pour /admin/config (PB-25)."""

import pytest
from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.core.config_service import invalidate_config_cache
from predicare.core.security import create_access_token

_ADMIN_TOKEN = create_access_token(
    {"sub": "admin1", "id": "USR-0001", "role": "administrateur", "nom_complet": "Admin Test"}
)
_GESTIONNAIRE_TOKEN = create_access_token(
    {"sub": "gest1", "id": "USR-0012", "role": "gestionnaire", "nom_complet": "Gest Test"}
)
_ASSURE_TOKEN = create_access_token(
    {"sub": "assure1", "id": "USR-0021", "role": "assure", "nom_complet": "Assuré Test"}
)
_PRO_TOKEN = create_access_token(
    {"sub": "pro1", "id": "USR-0031", "role": "professionnel_sante", "nom_complet": "Dr Test"}
)

_unauth_client = TestClient(app)
_admin_client = TestClient(app, headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"})
_gest_client = TestClient(app, headers={"Authorization": f"Bearer {_GESTIONNAIRE_TOKEN}"})
_assure_client = TestClient(app, headers={"Authorization": f"Bearer {_ASSURE_TOKEN}"})
_pro_client = TestClient(app, headers={"Authorization": f"Bearer {_PRO_TOKEN}"})


@pytest.fixture(autouse=True)
def reset_cache():
    """Invalide le cache avant chaque test pour éviter les interférences."""
    invalidate_config_cache(clear_overrides=True)
    yield
    invalidate_config_cache(clear_overrides=True)


# ---------------------------------------------------------------------------
# Matrice de contrôle d'accès (RBAC)
# ---------------------------------------------------------------------------


def test_get_config_unauthenticated_rejected():
    """GET /admin/config sans token est rejeté avec 401."""
    resp = _unauth_client.get("/admin/config")
    assert resp.status_code == 401


@pytest.mark.parametrize("client_fixture", [_gest_client, _assure_client, _pro_client])
def test_get_config_non_admin_forbidden(client_fixture):
    """GET /admin/config avec un rôle non-administrateur est rejeté avec 403."""
    resp = client_fixture.get("/admin/config")
    assert resp.status_code == 403


def test_get_config_admin_success():
    """GET /admin/config avec rôle administrateur renvoie 200 avec la configuration."""
    resp = _admin_client.get("/admin/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "fraud_score_threshold" in data
    assert "n8n_webhook_url" in data
    assert "semantic_cache_enabled" in data
    assert "semantic_cache_threshold" in data
    assert 0.0 <= data["fraud_score_threshold"] <= 1.0


def test_put_config_unauthenticated_rejected():
    """PUT /admin/config sans token est rejeté avec 401."""
    resp = _unauth_client.put("/admin/config", json={"fraud_score_threshold": 0.70})
    assert resp.status_code == 401


@pytest.mark.parametrize("client_fixture", [_gest_client, _assure_client, _pro_client])
def test_put_config_non_admin_forbidden(client_fixture):
    """PUT /admin/config avec un rôle non-administrateur est rejeté avec 403."""
    resp = client_fixture.put("/admin/config", json={"fraud_score_threshold": 0.70})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Validation stricte des schémas (422)
# ---------------------------------------------------------------------------


def test_put_config_rejects_unknown_fields():
    """Un champ inconnu dans le corps est strictement refusé avec 422 (extra='forbid')."""
    resp = _admin_client.put(
        "/admin/config",
        json={"fraud_score_threshold": 0.75, "parametre_pirate": "injection"},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("bad_threshold", [-0.01, 1.01, 2.5, -5.0])
def test_put_config_rejects_out_of_bounds_fraud_threshold(bad_threshold):
    """Un seuil de fraude en dehors de [0.0, 1.0] est rejeté avec 422."""
    resp = _admin_client.put(
        "/admin/config",
        json={"fraud_score_threshold": bad_threshold},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("bad_threshold", [-0.1, 1.2])
def test_put_config_rejects_out_of_bounds_semantic_cache_threshold(bad_threshold):
    """Un seuil de cache sémantique en dehors de [0.0, 1.0] est rejeté avec 422."""
    resp = _admin_client.put(
        "/admin/config",
        json={"semantic_cache_threshold": bad_threshold},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "bad_url",
    [
        "ftp://n8n:5678/webhook",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data",
        "http://metadata.google.internal/computeMetadata/v1",
        "",
        "   ",
    ],
)
def test_put_config_rejects_invalid_webhook_urls(bad_url):
    """Une URL non HTTP(S) ou ciblant les métadonnées cloud est rejetée avec 422 (SSRF)."""
    resp = _admin_client.put(
        "/admin/config",
        json={"n8n_webhook_url": bad_url},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Mise à jour partielle et lecture immédiate
# ---------------------------------------------------------------------------


def test_put_config_partial_update_success():
    """PUT /admin/config met à jour les champs fournis sans écraser les autres."""
    resp = _admin_client.put(
        "/admin/config",
        json={"fraud_score_threshold": 0.88},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fraud_score_threshold"] == 0.88
    assert "n8n_webhook_url" in data
    assert "updated_at" in data
    assert data["updated_at"] is not None

    # Lecture immédiate via GET /admin/config
    get_resp = _admin_client.get("/admin/config")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["fraud_score_threshold"] == 0.88


def test_no_secrets_in_responses():
    """Vérifie qu'aucun secret (clé JWT, mot de passe base, etc.) n'est exposé."""
    resp = _admin_client.get("/admin/config")
    text = resp.text.lower()
    assert "secret" not in text
    assert "password" not in text
    assert "change_me" not in text
