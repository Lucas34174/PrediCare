"""Tests unitaires du module de sélection de seuil (PB-07)."""

import numpy as np

from predicare.ml.threshold import (
    compute_pr_curve_data,
    compute_threshold_table,
    select_optimal_threshold,
)


def _make_dummy_probs(n: int = 100, seed: int = 42):
    rng = np.random.default_rng(seed)
    y_true = np.array([0] * 80 + [1] * 20)
    # Les positifs ont des probas plus hautes en moyenne
    probs = np.concatenate([rng.uniform(0.1, 0.6, 80), rng.uniform(0.4, 0.9, 20)])
    return y_true, probs


def test_compute_threshold_table_structure():
    y_true, probs = _make_dummy_probs()
    table = compute_threshold_table(y_true, probs, thresholds=[0.2, 0.5, 0.8])
    assert len(table) == 3
    assert set(table.columns) >= {"seuil", "recall", "precision", "f1", "f2", "nb_alertes"}
    # Le recall décroît avec l'augmentation du seuil
    assert table.loc[0, "recall"] >= table.loc[2, "recall"]


def test_select_optimal_threshold_avec_contrainte_recall():
    y_true, probs = _make_dummy_probs()
    table = compute_threshold_table(y_true, probs)
    opt = select_optimal_threshold(table, min_recall=0.80)

    assert opt["recall"] >= 0.80
    assert 0.0 < opt["seuil_optimal"] < 1.0
    assert "regle_decision" in opt
    assert opt["nb_alertes"] > 0


def test_select_optimal_threshold_fallback():
    """Si la contrainte n'est pas atteignable, sélectionne le seuil max recall."""
    y_true = np.array([0] * 90 + [1] * 10)
    probs = np.full(100, 0.3)  # Probas plates
    table = compute_threshold_table(y_true, probs, thresholds=[0.5, 0.8])
    opt = select_optimal_threshold(table, min_recall=0.99)
    assert "seuil_optimal" in opt


def test_compute_pr_curve_data():
    y_true, probs = _make_dummy_probs()
    data = compute_pr_curve_data(y_true, probs)
    assert "precision" in data and "recall" in data
    assert len(data["precision"]) == len(data["recall"])
    assert len(data["precision"]) > 0


def test_select_optimal_threshold_cost_utility():
    y_true, probs = _make_dummy_probs()
    table = compute_threshold_table(y_true, probs)
    opt = select_optimal_threshold(table, criterion="cost_utility", cost_fn=10.0, cost_fp=1.0)
    assert 0.0 < opt["seuil_optimal"] < 1.0
    assert "Coût métier" in opt["regle_decision"]


def test_select_optimal_threshold_max_f2():
    y_true, probs = _make_dummy_probs()
    table = compute_threshold_table(y_true, probs)
    opt = select_optimal_threshold(table, criterion="max_f2")
    assert 0.0 < opt["seuil_optimal"] < 1.0
    assert "F2-score" in opt["regle_decision"]
