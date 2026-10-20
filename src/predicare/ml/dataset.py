"""Construction du dataset ML de détection de fraude (PB-06).

Ce module relie les briques existantes :

* ``predicare.db.ingest.clean_all`` : nettoyage des tables brutes ;
* ``predicare.ml.features.build_features`` : 28 features anti-fuite ;
* ``labels_fraude.csv`` : cible officielle ``est_fraude`` (0/1).

Il produit un dataset prêt pour l'entraînement, avec :

* la cible ``cible`` : ``est_fraude`` par défaut, ou l'ancien proxy
  ``statut == REJETEE`` via ``cible="rejet"`` ;
* l'exclusion des factures invalides (``est_valide = 0``) et des factures
  sans label ;
* une séparation temporelle train / validation / test avec embargo ;
* les features historiques recalculées point-in-time (doublons, fractionnement,
  réutilisation d'ordonnance, numéro déjà vu).

Usage ::

    PYTHONPATH=src python -m predicare.ml.dataset \
        --raw-dir data/raw --labels-dir labels --out-dir data/processed
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from predicare.db.ingest import clean_all
from predicare.ml.features import FEATURE_NAMES, build_features

logger = logging.getLogger("predicare.ml.dataset")

CIBLES = ("fraude", "rejet")
CIBLE_PAR_DEFAUT = "fraude"
PART_TRAIN = 0.70
PART_VALIDATION = 0.15
DELAI_LABEL_FRAUDE_JOURS = 30

# Features historiques recalculées après coup pour garantir le point-in-time.
FEATURES_HISTORIQUES = (
    "f_nb_doublons_anterieurs",
    "f_numero_facture_deja_vu",
    "f_nb_factures_meme_jour_prest",
    "f_nb_prest_meme_ordo_anterieurs",
)

COLONNES_META = (
    "facture_id",
    "assure_id",
    "prestataire_id",
    "contrat_id",
    "date_reception",
    "date_soin",
    "type_facture",
    "montant_total",
    "numero_facture",
    "ordonnance_id",
)

COLONNES_LABELS = (
    "est_fraude",
    "type_fraude",
    "detail_fraude",
    "est_valide",
    "motif_invalidite",
)


def trouver_labels(raw_dir: Path, labels_dir: Path | None = None) -> Path:
    """Localise ``labels_fraude.csv`` (dossier séparé ou à côté du dataset)."""
    candidats: list[Path] = []
    if labels_dir is not None:
        candidats.append(Path(labels_dir) / "labels_fraude.csv")
    raw_dir = Path(raw_dir)
    candidats.extend(
        [
            raw_dir / "labels_fraude.csv",
            raw_dir / "labels" / "labels_fraude.csv",
            raw_dir.parent / "labels" / "labels_fraude.csv",
            raw_dir.parent / "labels_fraude.csv",
            Path.cwd() / "labels" / "labels_fraude.csv",
            Path.cwd() / "data" / "raw" / "labels" / "labels_fraude.csv",
        ]
    )
    for candidat in candidats:
        if candidat.is_file():
            return candidat
    raise FileNotFoundError(
        "labels_fraude.csv introuvable. Déposer le dossier `labels/` fourni "
        "séparément (ou passer --labels-dir). Pour l'ancien proxy, utiliser "
        "`--cible rejet`."
    )


def charger_labels(raw_dir: Path, labels_dir: Path | None = None) -> pd.DataFrame:
    """Charge et normalise les labels de fraude."""
    chemin = trouver_labels(raw_dir, labels_dir)
    labels = pd.read_csv(chemin, low_memory=False)
    if "facture_id" not in labels.columns or "est_fraude" not in labels.columns:
        raise ValueError(f"{chemin} doit contenir `facture_id` et `est_fraude`.")
    labels["facture_id"] = labels["facture_id"].astype(str)
    if labels["facture_id"].duplicated().any():
        doublons = labels.loc[labels["facture_id"].duplicated(), "facture_id"].head(5).tolist()
        raise ValueError(f"facture_id dupliqué dans les labels : {doublons}")
    labels["est_fraude"] = pd.to_numeric(labels["est_fraude"], errors="coerce").astype("Int64")
    if labels["est_fraude"].isna().any() or not labels["est_fraude"].isin([0, 1]).all():
        raise ValueError("est_fraude doit valoir 0 ou 1 pour chaque facture.")
    if "est_valide" in labels.columns:
        labels["est_valide"] = pd.to_numeric(labels["est_valide"], errors="coerce").astype("Int64")
        labels["est_valide"] = labels["est_valide"].fillna(1)
    else:
        labels["est_valide"] = pd.Series(1, index=labels.index, dtype="Int64")
    if not labels["est_valide"].isin([0, 1]).all():
        raise ValueError("est_valide doit valoir 0 ou 1.")
    for colonne in ("type_fraude", "detail_fraude", "motif_invalidite"):
        if colonne not in labels.columns:
            labels[colonne] = pd.NA
        labels[colonne] = labels[colonne].astype("string")
    logger.info("Labels chargés : %d factures (%s)", len(labels), chemin)
    return labels[["facture_id", *COLONNES_LABELS]].reset_index(drop=True)


def _dates(factures: pd.DataFrame) -> pd.DataFrame:
    f = factures.copy()
    for colonne in ("date_soin", "date_facture", "date_reception", "date_traitement"):
        if colonne in f.columns:
            f[colonne] = pd.to_datetime(f[colonne], errors="coerce")
    return f


def construire_cible(
    factures: pd.DataFrame,
    labels: pd.DataFrame | None,
    cible: str = CIBLE_PAR_DEFAUT,
) -> pd.DataFrame:
    """Construit la table ``facture_id`` / ``cible`` / statut de modélisation.

    ``cible="fraude"`` : cible = ``est_fraude`` pour les factures valides.
    ``cible="rejet"`` : cible = 1 si ``statut == REJETEE`` (ancien proxy).
    """
    if cible not in CIBLES:
        raise ValueError(f"cible inconnue : {cible!r} (attendu : {CIBLES}).")
    f = _dates(factures)
    base = f[["facture_id", "statut", "date_reception", "date_traitement"]].copy()
    base["facture_id"] = base["facture_id"].astype(str)

    date_photo = base["date_traitement"].max()
    delai = (base["date_traitement"] - base["date_reception"]).dt.days
    delai_max = int(delai.max()) if delai.notna().any() else 0
    date_maturite = date_photo - pd.Timedelta(days=delai_max) if pd.notna(date_photo) else pd.NaT

    base["date_maturite"] = date_maturite
    base["delai_decision_max_jours"] = delai_max

    if cible == "fraude":
        if labels is None:
            raise ValueError("cible='fraude' nécessite labels_fraude.csv.")
        base = base.merge(labels, on="facture_id", how="left", validate="one_to_one")
        base["est_fraude"] = pd.to_numeric(base["est_fraude"], errors="coerce").astype("Int64")
        base["est_valide"] = (
            pd.to_numeric(base["est_valide"], errors="coerce").astype("Int64").fillna(1)
        )
        label_present = base["est_fraude"].notna()
        valide = base["est_valide"].eq(1)
        base["cible"] = pd.Series(pd.NA, index=base.index, dtype="Int64")
        apprenable = label_present & valide
        base.loc[apprenable, "cible"] = base.loc[apprenable, "est_fraude"]
        base["statut_ml"] = np.select(
            [
                base["est_valide"].eq(0),
                base["statut"].eq("EN_COURS"),
                base["date_reception"].gt(date_maturite),
                ~label_present,
            ],
            ["exclu_invalide", "exclu_en_cours", "exclu_immature", "exclu_label_inconnu"],
            default="modelisable",
        )
    else:
        base["cible"] = pd.Series(pd.NA, index=base.index, dtype="Int64")
        base.loc[base["statut"].eq("PAYEE"), "cible"] = 0
        base.loc[base["statut"].eq("REJETEE"), "cible"] = 1
        base["statut_ml"] = np.select(
            [
                base["statut"].eq("EN_COURS"),
                base["date_reception"].gt(date_maturite),
            ],
            ["exclu_en_cours", "exclu_immature"],
            default="modelisable",
        )
        for colonne in COLONNES_LABELS:
            if colonne not in base.columns:
                base[colonne] = pd.NA

    incoherentes = base["statut_ml"].eq("modelisable") & ~base["cible"].isin([0, 1])
    if incoherentes.any():
        raise AssertionError(
            f"{int(incoherentes.sum())} factures modelisables sans cible binaire."
        )
    base.attrs["cible_source"] = cible
    base.attrs["date_maturite"] = date_maturite
    base.attrs["delai_decision_max_jours"] = delai_max
    return base


def _historiques_point_in_time(
    feat: pd.DataFrame,
    meta: pd.DataFrame,
) -> pd.DataFrame:
    """Recalcule les features historiques sans aucune donnée postérieure.

    Ordre de référence : réception (``date_reception``), puis ``facture_id``.
    Les compteurs ne portent que sur les factures strictement antérieures dans
    cet ordre ; le label de la ligne courante n'est jamais utilisé.
    """
    h = meta[["facture_id", *COLONNES_META[1:]]].copy()
    h["date_reception"] = pd.to_datetime(h["date_reception"], errors="coerce")
    h["date_soin"] = pd.to_datetime(h["date_soin"], errors="coerce")
    h = h.sort_values(["date_reception", "facture_id"]).reset_index(drop=True)

    cles_jour = ["assure_id", "prestataire_id", "date_soin"]
    cles_doublon = [*cles_jour, "montant_total"]
    h["f_nb_factures_meme_jour_prest"] = (
        h.groupby(cles_jour, dropna=False).cumcount().astype("float64")
    )
    h["f_nb_doublons_anterieurs"] = (
        h.groupby(cles_doublon, dropna=False).cumcount().astype("float64")
    )
    h["f_numero_facture_deja_vu"] = (
        h["numero_facture"].notna() & h["numero_facture"].duplicated(keep="first")
    ).astype("float64")

    h["_premier_couple"] = ~h.duplicated(["ordonnance_id", "prestataire_id"], keep="first")
    h["_cum_ordo"] = h.groupby("ordonnance_id", dropna=True)["_premier_couple"].cumsum()
    h["f_nb_prest_meme_ordo_anterieurs"] = h.groupby("ordonnance_id", dropna=True)[
        "_cum_ordo"
    ].shift(1)
    h.loc[h["ordonnance_id"].isna(), "f_nb_prest_meme_ordo_anterieurs"] = np.nan

    h = h.set_index("facture_id")
    for colonne in FEATURES_HISTORIQUES:
        feat[colonne] = h[colonne].reindex(feat.index).astype("float64")
    return feat


def separer_temporellement(
    dataset: pd.DataFrame,
    embargo_jours: int = DELAI_LABEL_FRAUDE_JOURS,
) -> pd.DataFrame:
    """Ajoute ``split`` (train/validation/test) avec embargo temporel.

    Les dates de coupure sont les quantiles 70 % et 85 % de ``date_reception``.
    Un embargo est appliqué après chaque coupure ; si l'embargo vide un
    ensemble, la coupure est conservée sans embargo (avec un avertissement).
    """
    d = dataset.sort_values(["date_reception", "facture_id"]).reset_index(drop=True).copy()
    d["date_reception"] = pd.to_datetime(d["date_reception"], errors="coerce")
    dates = d["date_reception"]
    q_train = dates.quantile(PART_TRAIN)
    q_val = dates.quantile(PART_TRAIN + PART_VALIDATION)
    embargo = pd.Timedelta(days=max(int(embargo_jours), 0))

    train = dates.le(q_train)
    val = dates.gt(q_train + embargo) & dates.le(q_val)
    test = dates.gt(q_val + embargo)

    if not val.any():
        logger.warning("Embargo trop long pour la validation : repli sans embargo.")
        val = dates.gt(q_train) & dates.le(q_val)
    if not test.any():
        logger.warning("Embargo trop long pour le test : repli sans embargo.")
        test = dates.gt(q_val)

    d["split"] = np.select([train, val, test], ["train", "validation", "test"], default="hors_modele")
    if (d["split"] == "hors_modele").any():
        logger.warning(
            "%d factures non affectées (dates manquantes).", int((d["split"] == "hors_modele").sum())
        )
    d["fold_cv"] = pd.Series(pd.NA, index=d.index, dtype="Int64")
    return d


def construire_dataset(
    raw_dir: str | Path = "data/raw",
    labels_dir: str | Path | None = None,
    cible: str = CIBLE_PAR_DEFAUT,
    out_dir: str | Path = "data/processed",
    sample_n: int | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Construit, sépare et écrit le dataset ML de fraude."""
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tables, rapport_nettoyage = clean_all(raw_dir, sample_n=sample_n, seed=seed)
    if "factures" not in tables:
        raise FileNotFoundError(f"factures.csv introuvable dans {raw_dir}.")
    factures = tables["factures"].copy()
    factures["facture_id"] = factures["facture_id"].astype(str)

    labels = tables.get("labels_fraude")
    if labels is None and cible == "fraude":
        labels = charger_labels(raw_dir, labels_dir)
    cible_df = construire_cible(factures, labels, cible=cible)
    date_maturite = cible_df.attrs["date_maturite"]
    delai_max = int(cible_df.attrs["delai_decision_max_jours"])

    # Les features ne doivent jamais voir les colonnes de décision ni les labels.
    interdites = {
        "statut",
        "motif_rejet",
        "montant_pris_en_charge",
        "date_traitement",
        *COLONNES_LABELS,
    }
    factures_features = factures.drop(columns=[c for c in interdites if c in factures.columns])
    ref_tables = {
        k: v
        for k, v in tables.items()
        if k not in {"factures", "labels_fraude", "labels_prestataires", "identites_pii"}
    }

    features = build_features(factures_features, ref_tables, history=pd.DataFrame())
    features = _historiques_point_in_time(features, factures)

    meta = factures[[c for c in COLONNES_META if c in factures.columns]].copy()
    meta["facture_id"] = meta["facture_id"].astype(str)
    dataset = meta.merge(features, left_on="facture_id", right_index=True, how="left")
    dataset = dataset.merge(
        cible_df[
            [
                "facture_id",
                "cible",
                "statut_ml",
                "est_fraude",
                "type_fraude",
                "detail_fraude",
                "est_valide",
                "motif_invalidite",
            ]
        ],
        on="facture_id",
        how="left",
        validate="one_to_one",
    )

    dataset_ml = dataset[dataset["statut_ml"].eq("modelisable")].copy()
    dataset_ml["cible"] = dataset_ml["cible"].astype(int)
    dataset_ml = separer_temporellement(
        dataset_ml,
        embargo_jours=max(delai_max, DELAI_LABEL_FRAUDE_JOURS if cible == "fraude" else 0),
    )
    dataset_ml = dataset_ml[dataset_ml["split"].isin(["train", "validation", "test"])].copy()
    dataset_ml = dataset_ml.sort_values(["date_reception", "facture_id"]).reset_index(drop=True)

    hors_modele = dataset[~dataset["statut_ml"].eq("modelisable")].copy()

    prevalence = {
        split: {
            "factures": int(len(d)),
            "positifs": int(d["cible"].sum()),
            "prevalence": float(d["cible"].mean()) if len(d) else None,
        }
        for split, d in dataset_ml.groupby("split")
    }
    metadata = {
        "cible": cible,
        "definition": (
            "est_fraude (labels_fraude.csv)" if cible == "fraude" else "statut == REJETEE (proxy)"
        ),
        "date_maturite": str(date_maturite.date()) if pd.notna(date_maturite) else None,
        "delai_decision_max_jours": delai_max,
        "features": FEATURE_NAMES,
        "nb_features": len(FEATURE_NAMES),
        "prevalence": prevalence,
        "nb_factures_source": int(len(factures)),
        "nb_factures_modelisables": int(len(dataset_ml)),
        "nb_hors_modele": int(len(hors_modele)),
        "hors_modele_par_raison": hors_modele["statut_ml"].value_counts().to_dict(),
        "nettoyage": rapport_nettoyage,
    }

    dataset_ml.to_csv(out_dir / "dataset_ml.csv", index=False, encoding="utf-8")
    hors_modele.to_csv(out_dir / "factures_hors_modele.csv", index=False, encoding="utf-8")
    (out_dir / "metadata_dataset.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    logger.info(
        "Dataset ML : %d factures × %d features | prévalence %s",
        len(dataset_ml),
        len(FEATURE_NAMES),
        {k: round(v["prevalence"], 4) if v["prevalence"] is not None else None for k, v in prevalence.items()},
    )
    return {
        "dataset": dataset_ml,
        "hors_modele": hors_modele,
        "metadata": metadata,
        "features": FEATURE_NAMES,
    }


def _cli() -> None:  # pragma: no cover
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="Dataset ML fraude – PrediCare TPA (PB-06)")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--labels-dir", default=None)
    p.add_argument("--out-dir", default="data/processed")
    p.add_argument("--cible", choices=CIBLES, default=CIBLE_PAR_DEFAUT)
    p.add_argument("--sample", type=int, default=None)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    construire_dataset(
        raw_dir=args.raw_dir,
        labels_dir=args.labels_dir,
        cible=args.cible,
        out_dir=args.out_dir,
        sample_n=args.sample,
        seed=args.seed,
    )


if __name__ == "__main__":  # pragma: no cover
    _cli()
