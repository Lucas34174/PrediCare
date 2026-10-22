from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from predicare.api.main import app
from predicare.api.routers.dashboard_public import _db_engine
from predicare.core.security import create_access_token

client = TestClient(app)


def _authorization(role: str) -> dict[str, str]:
    token = create_access_token({"sub": "dashboard-test", "role": role})
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_public_requires_authentication():
    response = client.get("/dashboard/public/kpis")

    assert response.status_code == 401


def test_dashboard_public_forbids_non_manager_roles():
    response = client.get(
        "/dashboard/public/kpis",
        headers=_authorization("assure"),
    )

    assert response.status_code == 403


def test_dashboard_public_allows_manager(monkeypatch):
    engine = MagicMock()
    result = engine.connect.return_value.__enter__.return_value.execute.return_value
    result.scalar.return_value = 1
    result.fetchall.return_value = []
    monkeypatch.setitem(app.dependency_overrides, _db_engine, lambda: engine)

    response = client.get(
        "/dashboard/public/kpis",
        headers=_authorization("gestionnaire"),
    )

    assert response.status_code == 200
    assert "business" in response.json()
