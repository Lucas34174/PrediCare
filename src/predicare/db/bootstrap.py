"""Bootstrap idempotent de la base PrediCare (PB-19).

Exécuté par le service Docker ``init`` avant le démarrage de l'API :

1. attend PostgreSQL ;
2. prend un verrou advisory pour éviter deux chargements concurrents ;
3. applique les migrations Alembic ;
4. vérifie la clé PII ;
5. charge les 12 CSV métier si le jeu n'est pas déjà chargé ;
6. enregistre le résultat dans ``ingest_state``.

Le module ne journalise jamais de donnée personnelle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from predicare.core import pii
from predicare.core.config import database_url
from predicare.db.ingest import clean_all
from predicare.db.load import (
    delete_all,
    has_existing_data,
    load_all,
)
from predicare.db.schemas import SOURCE_TABLES

logger = logging.getLogger("predicare.db.bootstrap")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_DATASET_KEY = "source_v1"
LOCK_ID = 947_210_019
WAIT_SECONDS = 60


class BootstrapError(RuntimeError):
    """Erreur bloquante du bootstrap."""


def _engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def _now() -> datetime:
    return datetime.now(UTC)


def wait_for_database(engine: Engine, timeout: int = WAIT_SECONDS) -> None:
    """Attend que PostgreSQL accepte une connexion simple."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except SQLAlchemyError as exc:  # pragma: no cover - dépend de l'environnement
            last_error = exc
            time.sleep(2)
    raise BootstrapError(f"PostgreSQL injoignable après {timeout}s") from last_error


def _configure_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    # ``alembic.ini`` utilise ``fileConfig`` qui désactive les loggers déjà
    # créés. On réactive explicitement l'arbre PrediCare après les migrations.
    for name in ("predicare", "predicare.db", "predicare.db.bootstrap"):
        existing = logging.getLogger(name)
        existing.disabled = False
        existing.setLevel(level)


def _alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    return config


def run_migrations() -> None:
    """Applique ``alembic upgrade head``."""
    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        # alembic.ini remplace la configuration de logging (root=WARNING) ; on
        # rétablit les logs du bootstrap pour afficher les counts et les étapes.
        _configure_logging()


# ---------------------------------------------------------------------------
# Comptes de démonstration — seeded automatiquement à chaque `docker compose up`
# ---------------------------------------------------------------------------

_DEMO_USERS = [
    {
        "id": "USR-0001",
        "identifiant": "admin1",
        "mot_de_passe": "admin123",
        "role": "administrateur",
        "assure_id": None,
        "prestataire_id": None,
    },
    {
        "id": "USR-0012",
        "identifiant": "gestionnaire1",
        "mot_de_passe": "gestionnaire123",
        "role": "gestionnaire",
        "assure_id": None,
        "prestataire_id": None,
    },
    {
        "id": "USR-0021",
        "identifiant": "assure1",
        "mot_de_passe": "assure123",
        "role": "assure",
        "assure_id": None,  # sera mis à jour ci-dessous si un assuré existe
        "prestataire_id": None,
    },
    {
        "id": "USR-0050",
        "identifiant": "pro1",
        "mot_de_passe": "pro123",
        "role": "professionnel_sante",
        "assure_id": None,
        "prestataire_id": None,  # sera mis à jour ci-dessous si un prestataire existe
    },
]


def seed_users(conn: Connection) -> None:
    """Insère les comptes de démonstration s'ils n'existent pas encore (idempotent)."""
    from predicare.core.security import hash_password

    # Résoudre un vrai assure_id et prestataire_id depuis les données chargées
    first_assure = conn.execute(text("SELECT assure_id FROM assures LIMIT 1")).scalar()
    first_prestataire = conn.execute(
        text("SELECT prestataire_id FROM prestataires LIMIT 1")
    ).scalar()

    users_inserted = 0
    for user in _DEMO_USERS:
        assure_id = first_assure if user["role"] == "assure" else user["assure_id"]
        prestataire_id = (
            first_prestataire if user["role"] == "professionnel_sante" else user["prestataire_id"]
        )
        conn.execute(
            text("""
                INSERT INTO utilisateurs (
                    id, identifiant, mot_de_passe_hash, role, assure_id, prestataire_id, actif
                )
                VALUES (
                    :id, :identifiant, :hash, :role, :assure_id, :prestataire_id, TRUE
                )
                ON CONFLICT (id) DO NOTHING
            """),
            {
                "id": user["id"],
                "identifiant": user["identifiant"],
                "hash": hash_password(user["mot_de_passe"]),
                "role": user["role"],
                "assure_id": assure_id,
                "prestataire_id": prestataire_id,
            },
        )
        users_inserted += 1
    logger.info("seed_users : %d comptes de démonstration vérifiés/insérés.", users_inserted)


def source_checksum(source_dir: Path) -> str:
    """Calcule un SHA-256 stable des 12 CSV métier attendus."""
    expected = [f"{table}.csv" for table in SOURCE_TABLES]
    missing = [name for name in expected if not (source_dir / name).is_file()]
    if missing:
        raise BootstrapError(f"Fichiers sources manquants dans {source_dir} : {', '.join(missing)}")

    digest = hashlib.sha256()
    for name in expected:
        digest.update(name.encode("utf-8"))
        with (source_dir / name).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _state(conn: Connection, dataset_key: str) -> dict[str, Any] | None:
    row = (
        conn.execute(
            text(
                """
                SELECT dataset_key, dataset_checksum, status, rows_loaded,
                       started_at, finished_at, source_dir, error, pii_canary
                FROM ingest_state
                WHERE dataset_key = :dataset_key
                """
            ),
            {"dataset_key": dataset_key},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _upsert_state(
    conn: Connection,
    *,
    dataset_key: str,
    checksum: str,
    status: str,
    rows_loaded: dict[str, int] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    source_dir: Path | None = None,
    error: str | None = None,
    pii_canary: bytes | None = None,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO ingest_state (
                dataset_key, dataset_checksum, status, rows_loaded,
                started_at, finished_at, source_dir, error, pii_canary
            )
            VALUES (
                :dataset_key, :dataset_checksum, :status,
                CAST(:rows_loaded AS jsonb),
                :started_at, :finished_at, :source_dir, :error, :pii_canary
            )
            ON CONFLICT (dataset_key) DO UPDATE SET
                dataset_checksum = EXCLUDED.dataset_checksum,
                status = EXCLUDED.status,
                rows_loaded = EXCLUDED.rows_loaded,
                started_at = EXCLUDED.started_at,
                finished_at = EXCLUDED.finished_at,
                source_dir = EXCLUDED.source_dir,
                error = EXCLUDED.error,
                pii_canary = COALESCE(EXCLUDED.pii_canary, ingest_state.pii_canary)
            """
        ),
        {
            "dataset_key": dataset_key,
            "dataset_checksum": checksum,
            "status": status,
            "rows_loaded": json.dumps(rows_loaded or {}),
            "started_at": started_at,
            "finished_at": finished_at,
            "source_dir": str(source_dir) if source_dir else None,
            "error": error,
            "pii_canary": pii_canary,
        },
    )


def _lock(conn: Connection) -> None:
    conn.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": LOCK_ID})


def _unlock(conn: Connection) -> None:
    conn.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": LOCK_ID})


def _mark_failed(
    conn: Connection,
    *,
    dataset_key: str,
    checksum: str,
    source_dir: Path,
    started_at: datetime,
    exc: Exception,
) -> None:
    """Enregistre un échec sans exposer de valeur métier."""
    try:
        with conn.begin():
            _upsert_state(
                conn,
                dataset_key=dataset_key,
                checksum=checksum,
                status="failed",
                started_at=started_at,
                finished_at=_now(),
                source_dir=source_dir,
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
    except SQLAlchemyError:
        logger.exception("Impossible d'enregistrer l'état d'échec du bootstrap.")


def bootstrap(
    *,
    source_dir: Path | str | None = None,
    dataset_key: str | None = None,
    force: bool = False,
    auto_load: bool = True,
    apply_migrations: bool = True,
    key: str | None = None,
    key_version: int | None = None,
) -> dict[str, int] | None:
    """Exécute le bootstrap. Retourne les counts chargés ou ``None`` si skip."""
    raw_dir = Path(
        source_dir or os.environ.get("SOURCE_DATA_DIR", str(DEFAULT_SOURCE_DIR))
    ).resolve()
    resolved_key = dataset_key or os.environ.get("DATASET_KEY", DEFAULT_DATASET_KEY)
    started_at = _now()
    checksum = ""
    state: dict[str, Any] | None = None
    load_started = False
    engine = _engine()
    wait_for_database(engine)

    with engine.connect() as conn:
        _lock(conn)
        conn.commit()
        try:
            if apply_migrations:
                run_migrations()

            # Seed idempotent des comptes de démonstration (toujours exécuté)
            with conn.begin():
                seed_users(conn)

            if not auto_load:
                logger.info("AUTO_LOAD_DATA désactivé : chargement ignoré.")
                return None

            pii_key = pii.validate_pii_key(key, os.environ.get("APP_ENV"))
            version = key_version if key_version is not None else pii.pii_key_version()
            pii.canary_check(conn, pii_key)
            checksum = source_checksum(raw_dir)
            state = _state(conn, resolved_key)
            if state and state.get("pii_canary"):
                pii.verify_canary(conn, pii_key, state["pii_canary"])
            canary = pii.encrypt_canary(conn, pii_key)
            conn.commit()

            if (
                state
                and state["status"] == "completed"
                and state["dataset_checksum"] == checksum
                and not force
            ):
                logger.info(
                    "Dataset %s déjà chargé (checksum %s) : bootstrap ignoré.",
                    resolved_key,
                    checksum[:12],
                )
                return None

            if state and state["status"] == "skipped" and not force:
                existing = has_existing_data(conn)
                conn.commit()
                if existing:
                    logger.info("Données déjà présentes : bootstrap ignoré.")
                    return None

            if state is None:
                existing = has_existing_data(conn)
                conn.commit()
                if existing and not force:
                    logger.warning(
                        "Des données métier existent sans marqueur ingest_state. "
                        "Aucun écrasement automatique ; utilisez FORCE_RELOAD=1."
                    )
                    with conn.begin():
                        _upsert_state(
                            conn,
                            dataset_key=resolved_key,
                            checksum=checksum,
                            status="skipped",
                            started_at=started_at,
                            finished_at=_now(),
                            source_dir=raw_dir,
                            error="Données existantes sans marqueur ; rechargement non forcé.",
                            pii_canary=canary,
                        )
                    return None

            if state and state["status"] in {"failed", "running"} and not force:
                existing = has_existing_data(conn)
                conn.commit()
                if existing:
                    logger.warning(
                        "Le bootstrap précédent est %s mais des données existent. "
                        "Aucun rechargement automatique ; utilisez FORCE_RELOAD=1.",
                        state["status"],
                    )
                    return None

            if state and state["status"] == "completed" and not force:
                logger.warning(
                    "Le dataset %s a changé (checksum %s -> %s). "
                    "Rechargement ignoré ; utilisez FORCE_RELOAD=1.",
                    resolved_key,
                    str(state["dataset_checksum"])[:12],
                    checksum[:12],
                )
                return None

            # Les lectures de contrôle ci-dessus ont ouvert une transaction
            # implicite ; on la referme avant le prochain ``conn.begin()``.
            conn.commit()

            if force:
                logger.warning("FORCE_RELOAD actif : suppression puis rechargement.")
                with conn.begin():
                    delete_all(conn)
                    _upsert_state(
                        conn,
                        dataset_key=resolved_key,
                        checksum=checksum,
                        status="running",
                        started_at=started_at,
                        source_dir=raw_dir,
                        pii_canary=canary,
                    )
            else:
                with conn.begin():
                    _upsert_state(
                        conn,
                        dataset_key=resolved_key,
                        checksum=checksum,
                        status="running",
                        started_at=started_at,
                        source_dir=raw_dir,
                        pii_canary=canary,
                    )
            # À partir d'ici, un échec doit être tracé dans ingest_state.
            load_started = True

            logger.info("Nettoyage des 12 CSV sources depuis %s", raw_dir)
            tables, report = clean_all(raw_dir)
            logger.info(
                "Nettoyage terminé : %d tables, %d conflits PK, %d anomalies FK.",
                len(tables),
                report.get("total_quarantaine_conflits_pk", 0),
                len(report.get("anomalies_orphelins", [])),
            )

            with conn.begin():
                counts = load_all(conn, tables, pii_key, version)
                _upsert_state(
                    conn,
                    dataset_key=resolved_key,
                    checksum=checksum,
                    status="completed",
                    rows_loaded=counts,
                    started_at=started_at,
                    finished_at=_now(),
                    source_dir=raw_dir,
                    pii_canary=canary,
                )
            logger.info("Bootstrap terminé : %s", json.dumps(counts, sort_keys=True))
            return counts
        except Exception as exc:  # noqa: BLE001 - on journalise sans PII
            conn.rollback()
            logger.error("Bootstrap échoué : %s", exc)
            if load_started or not (state and state["status"] == "completed"):
                _mark_failed(
                    conn,
                    dataset_key=resolved_key,
                    checksum=checksum or "0" * 64,
                    source_dir=raw_dir,
                    started_at=started_at,
                    exc=exc,
                )
            else:
                logger.error(
                    "Le statut completed est conservé : aucune donnée n'a été "
                    "supprimée ni rechargée."
                )
            raise
        finally:
            _unlock(conn)
            conn.commit()


def status() -> int:
    """Affiche l'état du bootstrap sans charger de données."""
    engine = _engine()
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                        SELECT dataset_key, dataset_checksum, status, rows_loaded,
                               started_at, finished_at, source_dir, error
                        FROM ingest_state
                        ORDER BY dataset_key
                        """
                    )
                )
                .mappings()
                .all()
            )
    except SQLAlchemyError as exc:
        print(f"ingest_state indisponible : {exc}")
        return 1

    if not rows:
        print("Aucun bootstrap enregistré.")
        return 0
    for row in rows:
        print(json.dumps(dict(row), default=str, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap idempotent PrediCare (PB-19).")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Dossier des 12 CSV métier (défaut : SOURCE_DATA_DIR ou data/raw).",
    )
    parser.add_argument("--dataset-key", default=None, help="Clé du jeu de données.")
    parser.add_argument(
        "--force", action="store_true", help="Force la suppression puis le rechargement."
    )
    parser.add_argument(
        "--no-auto-load",
        action="store_true",
        help="Applique les migrations sans charger les données.",
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Ne pas appliquer Alembic (tests ou migration déjà faite).",
    )
    parser.add_argument("--status", action="store_true", help="Affiche ingest_state et quitte.")
    args = parser.parse_args()

    _configure_logging()

    if args.status:
        return status()

    force = args.force or os.environ.get("FORCE_RELOAD", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    auto_load = not args.no_auto_load and os.environ.get("AUTO_LOAD_DATA", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }

    try:
        bootstrap(
            source_dir=args.source_dir,
            dataset_key=args.dataset_key,
            force=force,
            auto_load=auto_load,
            apply_migrations=not args.skip_migrations,
        )
    except Exception as exc:  # noqa: BLE001 - CLI
        logger.error("Échec du bootstrap : %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
