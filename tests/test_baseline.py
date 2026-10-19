"""Tests unitaires – predicare.ml.baseline (PB-06)."""

import numpy as np
import pandas as pd

from predicare.ml.baseline import split_no_leakage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_data(n: int = 100, n_assures: int = 20, seed: int = 42) -> tuple:
    """Génère un jeu synthétique : factures réparties sur n_assures assurés."""
    rng = np.random.default_rng(seed)
    facture_ids = [f"F{i:04d}" for i in range(n)]
    assure_col = [f"A{i % n_assures:03d}" for i in range(n)]
    base = pd.Timestamp("2024-01-01")
    dates = [(base + pd.Timedelta(days=i * 3)).strftime("%Y-%m-%d") for i in range(n)]

    X = pd.DataFrame(
        {"f_ecart": rng.normal(0, 1, n), "f_ratio": rng.uniform(0.5, 2, n)},
        index=pd.Index(facture_ids, name="facture_id"),
    )
    y = pd.Series(rng.integers(0, 2, n), index=X.index, name="est_fraude")
    meta = pd.DataFrame({"facture_id": facture_ids, "assure_id": assure_col, "date_soin": dates})
    return X, y, meta


# ---------------------------------------------------------------------------
# Tests split_no_leakage
# ---------------------------------------------------------------------------
def test_split_pas_de_fuite_assure():
    """Aucun assuré ne doit apparaître dans train ET test."""
    X, y, meta = _make_data()
    X_tr, X_te, _, _ = split_no_leakage(X, y, meta, test_size=0.2)

    meta_idx = meta.set_index("facture_id")
    assures_train = set(meta_idx.loc[X_tr.index, "assure_id"])
    assures_test = set(meta_idx.loc[X_te.index, "assure_id"])

    assert assures_train.isdisjoint(assures_test), "Fuite : un assuré est dans train ET test"


def test_split_ordre_chronologique_groupes():
    """Les assurés du train sont ceux avec les premières visites les plus anciennes."""
    X, y, meta = _make_data()
    X_tr, _, _, _ = split_no_leakage(X, y, meta, test_size=0.2)

    meta_idx = meta.set_index("facture_id").copy()
    meta_idx["_dt"] = pd.to_datetime(meta_idx["date_soin"])
    first_dates = meta_idx.groupby("assure_id")["_dt"].min().sort_values()
    n_train = max(1, int(len(first_dates) * 0.8))
    expected_train_assures = set(first_dates.index[:n_train])

    actual_train_assures = set(meta_idx.loc[X_tr.index, "assure_id"])
    assert actual_train_assures == expected_train_assures


def test_split_partition_complete():
    """Train + Test = dataset complet, sans doublons."""
    X, y, meta = _make_data()
    X_tr, X_te, y_tr, y_te = split_no_leakage(X, y, meta, test_size=0.2)

    all_ids = set(X_tr.index) | set(X_te.index)
    assert all_ids == set(X.index), "Des factures ont disparu du split"
    assert len(set(X_tr.index) & set(X_te.index)) == 0, "Des factures sont dans les deux sets"


def test_split_index_x_y_coherents():
    """Les index de X et y doivent être identiques dans train et test."""
    X, y, meta = _make_data()
    X_tr, X_te, y_tr, y_te = split_no_leakage(X, y, meta, test_size=0.2)

    assert list(X_tr.index) == list(y_tr.index)
    assert list(X_te.index) == list(y_te.index)


def test_split_taille_test_proportion_assures():
    """~20 % des assurés vont en test (entre 15 % et 30 % accepté)."""
    X, y, meta = _make_data(n=200, n_assures=20)
    _, X_te, _, _ = split_no_leakage(X, y, meta, test_size=0.2)

    meta_idx = meta.set_index("facture_id")
    n_test_assures = meta_idx.loc[X_te.index, "assure_id"].nunique()
    n_total = meta["assure_id"].nunique()

    assert 0.15 <= n_test_assures / n_total <= 0.30
