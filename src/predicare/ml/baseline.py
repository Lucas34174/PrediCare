"""Baseline ML de détection de fraude – PrediCare TPA (PB-06).

Fonctions exposées :
  - load_dataset()     : charge features, labels et métadonnées de split
  - split_no_leakage() : split sans fuite par assuré (groupes) et temps
  - make_pipeline()    : pipeline sklearn
  - evaluate()         : métriques Recall / PR-AUC
  - train_baseline()   : orchestrateur complet
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Constantes
FEATURES_PATH = "data/processed/features.csv"
LABELS_PATH = "data/processed/labels_fraude.csv"
FACTURES_PATH = "data/processed/factures.csv"
MODELS_DIR = Path("models")

# Features exclues avant fitting si taux de NaN > seuil dans le train
NAN_THRESHOLD = 0.95


# Chargement
def load_dataset(
    features_path: str = FEATURES_PATH,
    labels_path: str = LABELS_PATH,
    factures_path: str = FACTURES_PATH,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Charge et joint features, labels (est_fraude) et métadonnées de split."""
    logger.info("Chargement features : %s", features_path)
    feat = pd.read_csv(features_path, index_col="facture_id")

    logger.info("Chargement labels : %s", labels_path)
    lbl = pd.read_csv(labels_path).set_index("facture_id")["est_fraude"].astype(int)

    logger.info("Chargement métadonnées factures : %s", factures_path)
    meta = pd.read_csv(factures_path, usecols=["facture_id", "assure_id", "date_soin"])

    # Intersection des trois sources
    common = feat.index.intersection(lbl.index)
    feat = feat.loc[common]
    lbl = lbl.loc[common]
    meta = meta[meta["facture_id"].isin(common)].reset_index(drop=True)

    logger.info(
        "Dataset : %d factures | %d fraudes (%.1f %%)",
        len(feat),
        int(lbl.sum()),
        100.0 * lbl.mean(),
    )
    return feat, lbl, meta


# Split sans fuite
def split_no_leakage(
    X: pd.DataFrame,
    y: pd.Series,
    meta: pd.DataFrame,
    test_size: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Split sans fuite temporelle par assuré.

    Stratégie :
      1. Calcule la date de première visite par assure_id.
      2. Trie les assurés par cette date (ordre chronologique).
      3. Les (1-test_size)*100 % d'assurés les plus anciens → train.
      4. Les test_size*100 % les plus récents → test.

    Garanties :
      - Aucun assuré n'est dans les deux ensembles.
      - Les assurés du train ont des premières visites antérieures aux assurés du test.
    """
    meta_idx = meta.set_index("facture_id").copy()
    meta_idx["_dt"] = pd.to_datetime(meta_idx["date_soin"], errors="coerce")

    first_date = meta_idx.groupby("assure_id")["_dt"].min().sort_values()
    n_assures = len(first_date)
    n_train_grp = max(1, int(n_assures * (1 - test_size)))

    train_assures = set(first_date.index[:n_train_grp])
    train_ids = meta_idx.index[meta_idx["assure_id"].isin(train_assures)]
    test_ids = meta_idx.index[~meta_idx["assure_id"].isin(train_assures)]

    logger.info(
        "Split : train=%d factures (%d assurés) | test=%d factures (%d assurés)",
        len(train_ids),
        len(train_assures),
        len(test_ids),
        n_assures - len(train_assures),
    )
    return X.loc[train_ids], X.loc[test_ids], y.loc[train_ids], y.loc[test_ids]
