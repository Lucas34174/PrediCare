"""Pipeline d'ingestion et de nettoyage des données pour PrediCare TPA (PB-04)."""

import logging
from typing import Any

import pandas as pd

from predicare.db.schemas import (
    DATE_COLUMNS,
    MONEY_COLUMNS,
    TABLE_PRIMARY_KEYS,
    TABLE_SCHEMAS,
)

logger = logging.getLogger("predicare.db.ingest")


def clean_dataframe_base(
    df: pd.DataFrame,
    table_name: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, int]]:
    df_clean = df.copy()
    expected_cols = TABLE_SCHEMAS[table_name]
    pk_cols = TABLE_PRIMARY_KEYS[table_name]

    # Vérification et sélection des colonnes attendues
    missing_cols = [c for c in expected_cols if c not in df_clean.columns]
    if missing_cols:
        logger.warning("Colonnes manquantes dans %s : %s", table_name, missing_cols)
        for c in missing_cols:
            df_clean[c] = None

    df_clean = df_clean[expected_cols]

    # Nettoyage des chaînes de caractères (strip)
    for c in df_clean.columns:
        if df_clean[c].dtype == object or pd.api.types.is_string_dtype(df_clean[c]):
            df_clean[c] = df_clean[c].apply(lambda v: v.strip() if isinstance(v, str) else v)
            # Remplacement des chaînes vides par None
            df_clean[c] = df_clean[c].apply(lambda v: None if v == "" or pd.isna(v) else v)

    # Typage des montants monétaires et entiers stricts
    for c in df_clean.columns:
        if c in MONEY_COLUMNS or c in {
            "num_ligne",
            "quantite",
            "nb_lignes",
            "nb_beneficiaires",
            "annee_naissance",
            "validite_jours",
            "nif",
            "jours_ouverture",
            "heure_ouverture",
            "heure_fermeture",
            "note_qualite",
            "conventionne",
            "tarif_pratique",
            "chronique",
            "remboursable",
            "ordonnance_requise",
            "entente_prealable",
            "age_min",
            "age_max",
            "est_fraude",
            "est_valide",
            "est_suspect",
        }:
            df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce").astype("Int64")

    # Normalisation des dates (format AAAA-MM-JJ)
    for c in df_clean.columns:
        if c in DATE_COLUMNS:
            df_clean[c] = pd.to_datetime(df_clean[c], errors="coerce").dt.strftime("%Y-%m-%d")
            # Remplacement des 'NaT' par None
            df_clean[c] = df_clean[c].where(df_clean[c].notna(), None)

    # 1. Élimination des doublons strictement identiques
    nb_init = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    nb_doublons_parfaits = nb_init - len(df_clean)

    # 2. Détection et quarantaine des conflits de clés primaires
    quarantine: list[dict[str, Any]] = []
    conflits_pk = df_clean.duplicated(subset=pk_cols, keep=False)
    if conflits_pk.any():
        conflit_rows = df_clean[conflits_pk]
        for _, row in conflit_rows.iterrows():
            quarantine.append(
                {
                    "table": table_name,
                    "motif": "CONFLIT_CLE_PRIMAIRE",
                    "cle": {k: row[k] for k in pk_cols},
                }
            )
        # On ne conserve que la première occurrence en cas de conflit
        df_clean = df_clean.drop_duplicates(subset=pk_cols, keep="first")

    stats = {
        "lignes_initiales": nb_init,
        "lignes_nettoyees": len(df_clean),
        "doublons_parfaits_supprimes": nb_doublons_parfaits,
        "conflits_pk_quarantaine": len(quarantine),
        "valeurs_manquantes_par_colonne": {
            c: int(df_clean[c].isna().sum()) for c in df_clean.columns
        },
    }

    return df_clean, quarantine, stats


def clean_referentiels_and_providers(
    dfs_raw: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], dict[str, Any]]:
    """Nettoie les 5 tables de référentiels et prestataires."""
    cleaned = {}
    all_quarantine = []
    reports = {}

    target_tables = [
        "referentiel_actes",
        "referentiel_medicaments",
        "garanties",
        "prestataires",
        "grille_tarifaire",
    ]

    for table in target_tables:
        raw_key = f"{table}.csv" if f"{table}.csv" in dfs_raw else table
        if raw_key in dfs_raw:
            df_c, quar, st = clean_dataframe_base(dfs_raw[raw_key], table)
            cleaned[table] = df_c
            all_quarantine.extend(quar)
            reports[table] = st

    return cleaned, all_quarantine, reports
