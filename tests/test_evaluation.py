"""Tests unitaires du module d'évaluation globale (PB-08)."""

import numpy as np
import pandas as pd
import pytest

from predicare.ml.evaluation import (
    ALL_FRAUD_TYPES,
    compute_calibration,
    compute_confusion_metrics,
    compute_metrics_by_fraud_type,
    compute_naive_baseline,
    compute_pr_roc_curves,
    compute_threshold_grid,
    compute_wilson_ci,
    evaluate_global,
)


def _make_toy_data():
    # 8 négatifs, 2 positifs
    y_true = np.array([0, 0, 0, 0, 0, 0, 0, 0, 1, 1])
    # Scores séparés mais imparfaits
    y_prob = np.array([0.1, 0.2, 0.15, 0.3, 0.4, 0.85, 0.25, 0.05, 0.75, 0.90])
    return y_true, y_prob


def test_compute_confusion_metrics():
    y_true, y_prob = _make_toy_data()
    # Seuil 0.80 : seuls les scores >= 0.80 sont positifs -> y_prob[5] (faux pos), y_prob[9] (vrai pos)
    # y_prob[8] = 0.75 < 0.80 -> faux négatif
    m = compute_confusion_metrics(y_true, y_prob, threshold=0.80)
    assert m["matrice_brute"]["tp"] == 1
    assert m["matrice_brute"]["fp"] == 1
    assert m["matrice_brute"]["fn"] == 1
    assert m["matrice_brute"]["tn"] == 7
    assert m["recall"] == 0.5  # 1 sur 2
    assert m["precision"] == 0.5  # 1 sur 2 alertes
    assert m["nb_alertes"] == 2
    assert m["taux_alerte_pct"] == 20.0


def test_compute_pr_roc_curves():
    y_true, y_prob = _make_toy_data()
    res = compute_pr_roc_curves(y_true, y_prob)
    assert 0.0 <= res["pr_auc"] <= 1.0
    assert res["prevalence_baseline"] == 0.20
    assert 0.0 <= res["roc_auc"] <= 1.0
    assert len(res["pr_points"]) > 0
    assert len(res["roc_points"]) > 0


def test_compute_calibration():
    y_true, y_prob = _make_toy_data()
    cal = compute_calibration(y_true, y_prob, n_bins=3)
    assert 0.0 <= cal["brier_score"] <= 1.0
    assert isinstance(cal["curve_points"], list)


def test_compute_threshold_grid():
    y_true, y_prob = _make_toy_data()
    grid = compute_threshold_grid(y_true, y_prob, thresholds=[0.3, 0.5, 0.8])
    assert len(grid) == 3
    # Le rappel au seuil 0.3 doit être supérieur ou égal à celui au seuil 0.8
    assert grid[0]["recall"] >= grid[2]["recall"]


def test_compute_naive_baseline():
    y_true, _ = _make_toy_data()
    naive = compute_naive_baseline(y_true)
    assert naive["prevalence"] == 0.20
    assert naive["brier_score"] == 0.16  # 0.2 * 0.8


def test_evaluate_global_structure():
    y_true, y_prob = _make_toy_data()
    rep = evaluate_global(y_true, y_prob, production_threshold=0.80, optimal_threshold=0.30)
    assert "metrics_seuil_production" in rep
    assert "metrics_seuil_optimal" in rep
    assert "courbes" in rep
    assert "calibration" in rep
    assert "sensibilite_seuils" in rep


def test_anti_leakage_sur_features_evaluation():
    """Garantit qu'aucune feature interdite n'est transmise à l'évaluation."""
    from predicare.ml.baseline import check_no_leakage

    X_clean = pd.DataFrame({"f_1": [1, 2], "f_2": [3, 4]})
    check_no_leakage(X_clean)

    X_fuite = pd.DataFrame({"f_1": [1, 2], "statut": ["PAYEE", "REJETEE"]})
    with pytest.raises(ValueError, match="Fuite de données détectée"):
        check_no_leakage(X_fuite)


def test_compute_wilson_ci_bornes_et_cas_limites():
    # Cas n = 0
    assert compute_wilson_ci(0, 0) == (0.0, 0.0)
    # 1 succès sur 1 essai : la borne sup doit être 1.0 et inf > 0
    low, high = compute_wilson_ci(1, 1)
    assert 0.0 < low < 1.0
    assert high == 1.0
    # 0 succès sur 4 essais : inf = 0 et sup > 0
    low4, high4 = compute_wilson_ci(0, 4)
    assert low4 == 0.0
    assert 0.0 < high4 < 1.0


def test_compute_metrics_by_fraud_type_exhaustif_14_types():
    """Garantit que les 14 types du CDC sont tous présents sans division par zéro."""
    y_true = np.array([1, 1, 1, 0, 0])
    y_prob = np.array([0.9, 0.2, 0.85, 0.1, 0.4])
    types = np.array(["SURFACTURATION", "DOUBLON", "ACTE_FICTIF", "AUCUNE", "AUCUNE"])

    # Seuil 0.50 : SURFACTURATION (0.9) et ACTE_FICTIF (0.85) détectés. DOUBLON (0.2) raté.
    res = compute_metrics_by_fraud_type(y_true, y_prob, types, threshold=0.50)

    # 14 types présents
    assert len(res) == 14
    for t in ALL_FRAUD_TYPES:
        assert t in res

    # Types présents
    assert res["SURFACTURATION"]["effectif_test"] == 1
    assert res["SURFACTURATION"]["detectes"] == 1
    assert res["SURFACTURATION"]["recall"] == 1.0
    assert res["SURFACTURATION"]["statut"] == "DETECTE_100%"

    assert res["DOUBLON"]["effectif_test"] == 1
    assert res["DOUBLON"]["detectes"] == 0
    assert res["DOUBLON"]["recall"] == 0.0
    assert res["DOUBLON"]["statut"] == "NON_DETECTE"

    # Types absents
    assert res["FRACTIONNEMENT"]["effectif_test"] == 0
    assert res["FRACTIONNEMENT"]["statut"] == "ABSENT_DU_TEST"
    assert res["FRACTIONNEMENT"]["recall"] == 0.0
