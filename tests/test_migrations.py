"""Tests des migrations Alembic, sur une base temporaire (jamais la base de développement)."""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from predicare.core.config import database_url

RACINE = Path(__file__).resolve().parents[1]

TABLES_ATTENDUES = {
    "referentiel_actes",
    "referentiel_medicaments",
    "garanties",
    "prestataires",
    "grille_tarifaire",
    "contrats",
    "assures",
    "identites_pii",
    "ordonnances",
    "ordonnance_lignes",
    "factures",
    "lignes_facture",
    "predictions",
    "explications_shap",
    "decisions_gestionnaire",
    "documents_vectorises",
    "semantic_cache",
    "journal_audit",
    "documents",
    "utilisateurs",
    "ingest_state",
}


def alembic_config() -> Config:
    config = Config(str(RACINE / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE / "migrations"))
    return config


@pytest.fixture
def base_temporaire(monkeypatch):
    """Crée une base vide, y dirige l'application (DB_NAME), puis la supprime."""
    nom = f"predicare_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(database_url().set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connexion:
            connexion.execute(text(f'CREATE DATABASE "{nom}"'))
    except OperationalError:
        admin.dispose()
        if os.environ.get("PREDICARE_REQUIRE_DB"):
            raise
        pytest.skip("PostgreSQL injoignable : tests de migrations ignorés")
    monkeypatch.setenv("DB_NAME", nom)
    yield nom
    with admin.connect() as connexion:
        connexion.execute(text(f'DROP DATABASE "{nom}" WITH (FORCE)'))
    admin.dispose()


def lister_tables() -> set[str]:
    moteur = create_engine(database_url())
    try:
        return set(inspect(moteur).get_table_names())
    finally:
        moteur.dispose()


def test_une_seule_tete_de_migration():
    """Deux branches de migration en parallèle doivent être fusionnées avant la PR."""
    assert len(ScriptDirectory.from_config(alembic_config()).get_heads()) == 1


def test_upgrade_cree_toutes_les_tables(base_temporaire):
    command.upgrade(alembic_config(), "head")

    assert lister_tables() == TABLES_ATTENDUES | {"alembic_version"}


def test_migrations_rejouables(base_temporaire):
    config = alembic_config()

    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert lister_tables() == {"alembic_version"}

    command.upgrade(config, "head")
    assert lister_tables() == TABLES_ATTENDUES | {"alembic_version"}


def test_extensions_vector_et_pgcrypto_installees(base_temporaire):
    command.upgrade(alembic_config(), "head")

    moteur = create_engine(database_url())
    try:
        with moteur.connect() as connexion:
            extensions = {
                row[0] for row in connexion.execute(text("SELECT extname FROM pg_extension"))
            }
    finally:
        moteur.dispose()

    assert {"vector", "pgcrypto"} <= extensions
