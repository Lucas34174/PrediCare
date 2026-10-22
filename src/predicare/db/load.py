"""Chargement PostgreSQL des tables métier nettoyées (PB-19).

Le module transforme les DataFrames issus de :func:`predicare.db.ingest.clean_all`
en lignes PostgreSQL typées, dans un ordre compatible avec les clés étrangères.

Les identités ne passent jamais par une insertion en clair : elles sont
déléguées à :mod:`predicare.core.pii`, qui utilise ``pgcrypto``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import Connection, text

from predicare.core import pii
from predicare.db.schemas import (
    DATE_COLUMNS,
    SOURCE_TABLES,
    TABLE_SCHEMAS,
)

logger = logging.getLogger(__name__)

#: Ordre de chargement respectant les dépendances FK.
LOAD_ORDER: tuple[str, ...] = SOURCE_TABLES

#: Ordre inverse pour un rechargement forcé.
DELETE_ORDER: tuple[str, ...] = (
    "decisions_gestionnaire",
    "predictions",
    "lignes_facture",
    "factures",
    "ordonnance_lignes",
    "ordonnances",
    "identites_pii",
    "assures",
    "contrats",
    "grille_tarifaire",
    "prestataires",
    "garanties",
    "referentiel_medicaments",
    "referentiel_actes",
)

BOOLEAN_COLUMNS: dict[str, set[str]] = {
    "referentiel_actes": {"ordonnance_requise", "entente_prealable"},
    "referentiel_medicaments": {"remboursable", "chronique"},
    "garanties": {"attestation_requise"},
    "prestataires": {"conventionne"},
}

TIME_COLUMNS: dict[str, set[str]] = {
    "factures": {"heure_soin"},
}


class LoadError(RuntimeError):
    """Erreur de chargement PostgreSQL."""


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _as_date(value: Any) -> date | None:
    if _is_null(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_time(value: Any) -> time | None:
    if _is_null(value):
        return None
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _as_int(value: Any) -> int | None:
    if _is_null(value):
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return int(value)
    return int(str(value))


def _as_bool(value: Any) -> bool | None:
    if _is_null(value):
        return None
    if isinstance(value, bool):
        return value
    return bool(int(value))


def _as_string_int(value: Any) -> str | None:
    if _is_null(value):
        return None
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def _as_array(value: Any, separator: str) -> list[str] | None:
    if _is_null(value):
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(separator) if item.strip()]


def _as_opening_days(value: Any) -> list[int] | None:
    """Convertit ``12345`` (CSV) en ``[1, 2, 3, 4, 5]`` (ARRAY PostgreSQL)."""
    if _is_null(value):
        return None
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        raw = str(int(value))
    else:
        raw = str(value).strip()
    return [int(char) for char in raw if char.isdigit()]


def _normalise_value(table: str, column: str, value: Any) -> Any:
    if _is_null(value):
        return None

    if column in DATE_COLUMNS:
        return _as_date(value)
    if column in TIME_COLUMNS.get(table, set()):
        return _as_time(value)
    if column in BOOLEAN_COLUMNS.get(table, set()):
        return _as_bool(value)
    if column == "actes_exclus":
        return _as_array(value, "|")
    if column == "jours_ouverture":
        return _as_opening_days(value)
    if column == "nif":
        return _as_string_int(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)) and float(value).is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _rows_for_table(table: str, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    columns = TABLE_SCHEMAS[table]
    rows: list[dict[str, Any]] = []
    for record in dataframe.to_dict("records"):
        rows.append(
            {column: _normalise_value(table, column, record.get(column)) for column in columns}
        )
    return rows


def _insert_rows(
    conn: Connection,
    table: str,
    rows: list[dict[str, Any]],
    chunk_size: int = 2_000,
) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join(f":{column}" for column in columns)
    sql = text(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})")
    try:
        for start in range(0, len(rows), chunk_size):
            conn.execute(sql, rows[start : start + chunk_size])
    except Exception as exc:  # noqa: BLE001 - on ne journalise pas les valeurs
        sqlstate = getattr(exc, "sqlstate", None)
        raise LoadError(
            f"Chargement de la table {table} impossible"
            + (f" (SQLSTATE {sqlstate})" if sqlstate else "")
        ) from None


def load_all(
    conn: Connection,
    tables: dict[str, pd.DataFrame],
    pii_key: str,
    key_version: int = 1,
) -> dict[str, int]:
    """Charge les 12 tables métier dans une transaction déjà ouverte.

    Les labels ne sont volontairement pas chargés : ils restent dans
    ``data/raw/labels`` pour l'entraînement ML.
    """
    counts: dict[str, int] = {}
    for table in LOAD_ORDER:
        dataframe = tables.get(table)
        if dataframe is None:
            raise LoadError(f"Table source absente : {table}")

        if table == "identites_pii":
            counts[table] = pii.insert_identities(conn, dataframe, pii_key, key_version)
        else:
            rows = _rows_for_table(table, dataframe)
            _insert_rows(conn, table, rows)
            counts[table] = len(rows)
        logger.info("Table %s chargée (%d lignes)", table, counts[table])

    verify_counts(conn, tables)
    for table in LOAD_ORDER:
        conn.execute(text(f"ANALYZE {table}"))
    return counts


def verify_counts(conn: Connection, tables: dict[str, pd.DataFrame]) -> None:
    """Vérifie que chaque table contient exactement le nombre de lignes attendu."""
    for table in LOAD_ORDER:
        expected = len(tables[table])
        actual = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        if int(actual) != expected:
            raise LoadError(
                f"Vérification échouée pour {table} : attendu={expected}, chargé={actual}"
            )


def table_counts(conn: Connection) -> dict[str, int]:
    """Retourne les counts des tables métier, sans données personnelles."""
    return {
        table: int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in LOAD_ORDER
    }


def has_existing_data(conn: Connection) -> bool:
    """Vrai si au moins une table métier contient déjà des lignes."""
    return any(count > 0 for count in table_counts(conn).values())


def delete_all(conn: Connection) -> None:
    """Supprime les données métier dans l'ordre inverse des FK.

    Les tables de prédiction/décision sont incluses pour permettre un
    rechargement forcé sans violer les clés étrangères.
    """
    for table in DELETE_ORDER:
        conn.execute(text(f"DELETE FROM {table}"))
