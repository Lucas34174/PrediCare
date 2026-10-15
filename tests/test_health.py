"""Tests de l'endpoint /health."""

import pytest
from fastapi.testclient import TestClient

from predicare.api import main
from predicare.api.main import app

client = TestClient(app)


def test_health_ok_quand_base_joignable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "_database_reachable", lambda: True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": main.API_VERSION,
        "database": "connected",
    }


def test_health_503_quand_base_injoignable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "_database_reachable", lambda: False)
    response = client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["database"] == "disconnected"
    assert data["detail"] == "Impossible de joindre PostgreSQL"


def test_database_reachable_false_si_base_absente(monkeypatch: pytest.MonkeyPatch):
    """Sans mock : un port fermé doit donner False, sans exception."""
    monkeypatch.setenv("DB_HOST", "127.0.0.1")
    monkeypatch.setenv("DB_PORT", "1")
    main._engine.cache_clear()
    try:
        assert main._database_reachable() is False
    finally:
        main._engine.cache_clear()
