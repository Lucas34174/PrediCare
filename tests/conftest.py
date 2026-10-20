"""Fixtures partagées pour les tests d'intégration PostgreSQL."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from predicare.core.config import database_url


@pytest.fixture
def db_temporaire(monkeypatch):
    """Crée une base vide isolée, puis la supprime après le test."""
    nom = f"predicare_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(
        database_url().set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin.connect() as connexion:
            connexion.execute(text(f'CREATE DATABASE "{nom}"'))
    except OperationalError:
        admin.dispose()
        if os.environ.get("PREDICARE_REQUIRE_DB"):
            raise
        pytest.skip("PostgreSQL injoignable : test d'intégration ignoré")
    monkeypatch.setenv("DB_NAME", nom)
    yield nom
    with admin.connect() as connexion:
        connexion.execute(text(f'DROP DATABASE "{nom}" WITH (FORCE)'))
    admin.dispose()
