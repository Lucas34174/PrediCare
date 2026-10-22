"""Tests d'intégration du bootstrap PostgreSQL et du chiffrement PII (PB-19)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from predicare.core import pii
from predicare.core.config import database_url
from predicare.db.bootstrap import bootstrap

RACINE = Path(__file__).resolve().parents[1]
SOURCE = Path(
    os.environ.get(
        "PREDICARE_SOURCE",
        "/mnt/sda1/CAPSTONINGEDATA/CohorteAI_datagen/dataset",
    )
)
KEY = "k" * 64

pytestmark = pytest.mark.skipif(
    not SOURCE.is_dir(),
    reason="Les 12 CSV sources ne sont pas disponibles.",
)


def _migrate() -> None:
    config = Config(str(RACINE / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE / "migrations"))
    command.upgrade(config, "head")


def test_bootstrap_loads_all_tables_and_encrypts_pii(db_temporaire, monkeypatch, caplog):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", KEY)
    monkeypatch.setenv("PII_KEY_VERSION", "1")
    monkeypatch.setenv("APP_ENV", "dev")
    caplog.set_level(logging.INFO)
    _migrate()

    counts = bootstrap(
        source_dir=SOURCE,
        dataset_key="test_pb19",
        apply_migrations=False,
        key=KEY,
    )

    assert counts is not None
    assert counts["factures"] == 83_938
    assert counts["lignes_facture"] == 122_035
    assert counts["identites_pii"] == 4_459

    moteur = create_engine(database_url())
    try:
        with moteur.connect() as conn:
            state = (
                conn.execute(
                    text(
                        "SELECT status, rows_loaded FROM ingest_state "
                        "WHERE dataset_key = 'test_pb19'"
                    )
                )
                .mappings()
                .one()
            )
            assert state["status"] == "completed"
            assert state["rows_loaded"]["factures"] == 83_938

            nom_chiffre = conn.execute(
                text("SELECT nom_chiffre FROM identites_pii WHERE assure_id = 'ASS-9CAA1484E0'")
            ).scalar_one()
            assert isinstance(nom_chiffre, bytes)
            assert b"RANDRIASOLOFO" not in nom_chiffre

            identity = pii.decrypt_identity(conn, "ASS-9CAA1484E0", KEY)
            assert identity is not None
            assert identity["nom"] == "RANDRIASOLOFO"
            assert identity["prenoms"] == "Thierry Ny Aina"
    finally:
        moteur.dispose()

    assert "RANDRIASOLOFO" not in caplog.text

    # Deuxième exécution : aucun rechargement, aucun doublon.
    assert (
        bootstrap(
            source_dir=SOURCE,
            dataset_key="test_pb19",
            apply_migrations=False,
            key=KEY,
        )
        is None
    )
    moteur = create_engine(database_url())
    try:
        with moteur.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM factures")).scalar_one() == 84_593
            assert (
                conn.execute(
                    text("SELECT count(*) FROM ingest_state WHERE dataset_key = 'test_pb19'")
                ).scalar_one()
                == 1
            )
    finally:
        moteur.dispose()

    # Une mauvaise clé ne doit ni recharger ni invalider un état completed.
    with pytest.raises(pii.PIIError):
        bootstrap(
            source_dir=SOURCE,
            dataset_key="test_pb19",
            apply_migrations=False,
            key="x" * 64,
        )
    moteur = create_engine(database_url())
    try:
        with moteur.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT status FROM ingest_state WHERE dataset_key = 'test_pb19'")
                ).scalar_one()
                == "completed"
            )
    finally:
        moteur.dispose()
    assert (
        bootstrap(
            source_dir=SOURCE,
            dataset_key="test_pb19",
            apply_migrations=False,
            key=KEY,
        )
        is None
    )


def test_wrong_key_is_rejected_by_stored_canary(db_temporaire, monkeypatch):
    monkeypatch.setenv("PII_ENCRYPTION_KEY", KEY)
    _migrate()
    moteur = create_engine(database_url())
    try:
        with moteur.connect() as conn:
            canary = pii.encrypt_canary(conn, KEY)
            pii.verify_canary(conn, KEY, canary)
            with pytest.raises(pii.PIIError):
                pii.verify_canary(conn, "x" * 64, canary)
    finally:
        moteur.dispose()
