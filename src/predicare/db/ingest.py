"""Pipeline d'ingestion et de nettoyage des données pour PrediCare TPA (PB-04)."""

import argparse
import json
import logging
import os
from pathlib import Path
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


def check_referential_integrity(
    cleaned_tables: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    """Vérifie l'intégrité des clés étrangères entre les tables nettoyées.
    Règle 4 : Aucune suppression silencieuse. Les éventuels orphelins sont
    enregistrés dans la liste de quarantaine.
    """
    foreign_keys = [
        ("assures", "contrat_id", "contrats", "contrat_id"),
        ("factures", "assure_id", "assures", "assure_id"),
        ("factures", "prestataire_id", "prestataires", "prestataire_id"),
        ("factures", "contrat_id", "contrats", "contrat_id"),
        ("factures", "ordonnance_id", "ordonnances", "ordonnance_id"),
        ("lignes_facture", "facture_id", "factures", "facture_id"),
        ("ordonnances", "assure_id", "assures", "assure_id"),
        ("ordonnances", "prescripteur_id", "prestataires", "prestataire_id"),
        (
            "ordonnance_lignes",
            "ordonnance_id",
            "ordonnances",
            "ordonnance_id",
        ),
        ("grille_tarifaire", "prestataire_id", "prestataires", "prestataire_id"),
        ("identites_pii", "assure_id", "assures", "assure_id"),
        ("labels_fraude", "facture_id", "factures", "facture_id"),
        (
            "labels_prestataires",
            "prestataire_id",
            "prestataires",
            "prestataire_id",
        ),
    ]
    orphan_reports = []
    for f_src, col_src, f_ref, col_ref in foreign_keys:
        if f_src in cleaned_tables and f_ref in cleaned_tables:
            df_src = cleaned_tables[f_src]
            df_ref = cleaned_tables[f_ref]
            # Exclusion des valeurs nulles légitimes (ex: ordonnance_id absent)
            src_series = df_src[col_src].dropna()
            ref_set = set(df_ref[col_ref].dropna())
            orphelins_mask = ~src_series.isin(ref_set)
            if orphelins_mask.any():
                nb_orph = int(orphelins_mask.sum())
                orphan_reports.append(
                    {
                        "table_source": f_src,
                        "colonne_source": col_src,
                        "table_reference": f_ref,
                        "colonne_reference": col_ref,
                        "nombre_orphelins": nb_orph,
                        "motif": "ORPHELIN_CLE_ETRANGERE",
                    }
                )
                logger.warning(
                    "Orphelins détectés : %s.%s -> %s.%s (%d lignes)",
                    f_src,
                    col_src,
                    f_ref,
                    col_ref,
                    nb_orph,
                )
    return orphan_reports


def clean_all(
    raw_dir: Path | str = "data/raw",
    sample_n: int | None = None,
    seed: int = 42,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    path_raw = Path(raw_dir)
    all_table_names = list(TABLE_SCHEMAS.keys())
    # 1. Chargement brut en mémoire
    dfs_raw = {}
    for table in all_table_names:
        csv_file = path_raw / f"{table}.csv"
        if csv_file.exists():
            dfs_raw[table] = pd.read_csv(csv_file, low_memory=False)
    # 2. Nettoyage technique table par table
    cleaned_tables = {}
    all_quarantine = []
    reports = {}
    for table in all_table_names:
        if table in dfs_raw:
            df_c, quar, st = clean_dataframe_base(dfs_raw[table], table)
            cleaned_tables[table] = df_c
            all_quarantine.extend(quar)
            reports[table] = st

    # 3. Échantillonnage cohérent par fermeture transitive (Règle 9)
    if sample_n and "factures" in cleaned_tables:
        df_fac = cleaned_tables["factures"]
        n_sample = min(sample_n, len(df_fac))
        sampled_fac = df_fac.sample(n=n_sample, random_state=seed)
        cleaned_tables["factures"] = sampled_fac

        kept_fac_ids = set(sampled_fac["facture_id"])
        kept_assure_ids = set(sampled_fac["assure_id"].dropna())
        kept_prest_ids = set(sampled_fac["prestataire_id"].dropna())
        kept_contrat_ids = set(sampled_fac["contrat_id"].dropna())
        kept_ordo_ids = set(sampled_fac["ordonnance_id"].dropna())

        # Suivi des ordonnances et extension des prescripteurs et assurés
        if "ordonnances" in cleaned_tables:
            cleaned_tables["ordonnances"] = cleaned_tables["ordonnances"][
                cleaned_tables["ordonnances"]["ordonnance_id"].isin(kept_ordo_ids)
            ]
            kept_assure_ids |= set(cleaned_tables["ordonnances"]["assure_id"].dropna())
            kept_prest_ids |= set(cleaned_tables["ordonnances"]["prescripteur_id"].dropna())

        if "ordonnance_lignes" in cleaned_tables:
            cleaned_tables["ordonnance_lignes"] = cleaned_tables["ordonnance_lignes"][
                cleaned_tables["ordonnance_lignes"]["ordonnance_id"].isin(kept_ordo_ids)
            ]

        # Suivi des assurés et extension des contrats
        if "assures" in cleaned_tables:
            cleaned_tables["assures"] = cleaned_tables["assures"][
                cleaned_tables["assures"]["assure_id"].isin(kept_assure_ids)
            ]
            kept_contrat_ids |= set(cleaned_tables["assures"]["contrat_id"].dropna())

        if "identites_pii" in cleaned_tables:
            cleaned_tables["identites_pii"] = cleaned_tables["identites_pii"][
                cleaned_tables["identites_pii"]["assure_id"].isin(kept_assure_ids)
            ]

        if "contrats" in cleaned_tables:
            cleaned_tables["contrats"] = cleaned_tables["contrats"][
                cleaned_tables["contrats"]["contrat_id"].isin(kept_contrat_ids)
            ]

        if "prestataires" in cleaned_tables:
            cleaned_tables["prestataires"] = cleaned_tables["prestataires"][
                cleaned_tables["prestataires"]["prestataire_id"].isin(kept_prest_ids)
            ]

        if "grille_tarifaire" in cleaned_tables:
            cleaned_tables["grille_tarifaire"] = cleaned_tables["grille_tarifaire"][
                cleaned_tables["grille_tarifaire"]["prestataire_id"].isin(kept_prest_ids)
            ]

        if "lignes_facture" in cleaned_tables:
            cleaned_tables["lignes_facture"] = cleaned_tables["lignes_facture"][
                cleaned_tables["lignes_facture"]["facture_id"].isin(kept_fac_ids)
            ]

        if "labels_fraude" in cleaned_tables:
            cleaned_tables["labels_fraude"] = cleaned_tables["labels_fraude"][
                cleaned_tables["labels_fraude"]["facture_id"].isin(kept_fac_ids)
            ]

        if "labels_prestataires" in cleaned_tables:
            cleaned_tables["labels_prestataires"] = cleaned_tables["labels_prestataires"][
                cleaned_tables["labels_prestataires"]["prestataire_id"].isin(kept_prest_ids)
            ]

    # 4. Contrôle d'intégrité référentielle
    orphan_reports = check_referential_integrity(cleaned_tables)
    quality_report = {
        "tables": {t: reports[t] for t in cleaned_tables if t in reports},
        "total_quarantaine_conflits_pk": len(all_quarantine),
        "quarantaine_details": all_quarantine,
        "anomalies_orphelins": orphan_reports,
    }
    return cleaned_tables, quality_report


def save_dataframe_atomic(df: pd.DataFrame, target_path: Path) -> None:
    """Écrit un DataFrame en CSV de manière atomique et déterministe (Règle 8).
    - Pas d'index.
    - Écriture dans un fichier temporaire .tmp puis renommage atomique.
    - Garantit que deux exécutions successives produisent des octets identiques.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".csv.tmp")
    df.to_csv(temp_path, index=False, encoding="utf-8")
    os.replace(temp_path, target_path)


def run_pipeline(
    raw_dir: Path | str = "data/raw",
    processed_dir: Path | str = "data/processed",
    sample_n: int | None = None,
    seed: int = 42,
    export_pii_unencrypted: bool = False,
) -> dict[str, Any]:
    """Exécute le pipeline de bout en bout :
    1. Nettoyage technique et échantillonnage cohérent.
    2. Écriture atomique des CSV nettoyés dans data/processed/.
    3. Respect PII (identites_pii non exporté par défaut).
    4. Écriture du rapport de qualité JSON dans data/processed/qualite_rapport.json.
    """
    path_raw = Path(raw_dir)
    path_proc = Path(processed_dir)
    path_proc.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Démarrage du pipeline d'ingestion (source=%s, cible=%s, sample=%s)",
        path_raw,
        path_proc,
        sample_n,
    )
    cleaned_tables, quality_report = clean_all(
        raw_dir=path_raw,
        sample_n=sample_n,
        seed=seed,
    )
    # Écriture déterministe de chaque table
    for table_name, df_clean in cleaned_tables.items():
        if table_name == "identites_pii" and not export_pii_unencrypted:
            logger.info(
                "Table 'identites_pii' validée mais NON écrite en clair dans %s (Règle 7 - RGPD).",
                path_proc,
            )
            continue
        target_file = path_proc / f"{table_name}.csv"
        save_dataframe_atomic(df_clean, target_file)
        logger.info("Table '%s' écrite avec succès (%d lignes)", table_name, len(df_clean))
    # Écriture du rapport de qualité JSON (sans PII)
    report_file = path_proc / "qualite_rapport.json"
    temp_report = path_proc / "qualite_rapport.json.tmp"
    with open(temp_report, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2, ensure_ascii=False)
    os.replace(temp_report, report_file)
    logger.info("Rapport de qualité généré dans %s", report_file)
    return quality_report


def main() -> None:
    """CLI du pipeline d'ingestion PrediCare TPA."""
    parser = argparse.ArgumentParser(
        description="Pipeline reproductible d'ingestion et de nettoyage PrediCare TPA (PB-04)"
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw",
        help="Dossier contenant les CSV bruts (défaut: data/raw)",
    )
    parser.add_argument(
        "--processed-dir",
        default="data/processed",
        help="Dossier de destination des tables nettoyées (défaut: data/processed)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="Taille de l'échantillon de factures à extraire avec cohérence référentielle",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Graine aléatoire pour l'échantillonnage (défaut: 42)",
    )
    parser.add_argument(
        "--export-pii-unencrypted",
        action="store_true",
        default=False,
        help="Autorise l'écriture de identites_pii en clair (interdit en prod, réservé débug sécurisé)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Active les logs de niveau DEBUG",
    )
    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    report = run_pipeline(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        sample_n=args.sample,
        seed=args.seed,
        export_pii_unencrypted=args.export_pii_unencrypted,
    )
    print(
        f"Pipeline terminé avec succès. Tables traitées : {len(report['tables'])}, "
        f"Conflits PK : {report['total_quarantaine_conflits_pk']}, "
        f"Orphelins : {len(report['anomalies_orphelins'])}"
    )


if __name__ == "__main__":
    main()
