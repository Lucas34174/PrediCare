"""Tests unitaires du module d'évaluation finale (PB-07)."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from predicare.ml.evaluate_final import (
    compute_recall_bootstrap_ci,
    compute_recall_by_fraud_type,
    evaluate_model_on_test,
)


def test_compute_recall_bootstrap_ci():
    y_true = np.array([0] * 80 + [1] * 20)
    y_pred = np.array([0] * 85 + [1] * 15)
    ci_low, ci_high = compute_recall_bootstrap_ci(y_true, y_pred, n_bootstraps=200)
    assert 0.0 <= ci_low <= ci_high <= 1.0


def test_compute_recall_by_fraud_type():
    y_true = np.array([1, 1, 1, 0, 0])
    y_pred = np.array([1, 0, 1, 0, 1])
    types = np.array(["SURFACTURATION", "DOUBLON", "SURFACTURATION", "AUCUNE", "AUCUNE"])
    res = compute_recall_by_fraud_type(y_true, y_pred, types)

    assert "SURFACTURATION" in res
    assert "DOUBLON" in res
    assert res["SURFACTURATION"]["total_cas"] == 2
    assert res["SURFACTURATION"]["detectes"] == 2
    assert res["SURFACTURATION"]["recall"] == 1.0
    assert res["DOUBLON"]["recall"] == 0.0


def test_evaluate_model_on_test():
    X = pd.DataFrame({"f_1": [1.0, 2.0, 3.0, 4.0], "f_2": [0.1, 0.2, 0.3, 0.4]})
    y = pd.Series([0, 0, 1, 1])
    clf = LogisticRegression()
    clf.fit(X, y)

    res = evaluate_model_on_test(clf, X, y, threshold=0.5)
    for key in ("recall", "precision", "f1", "f2", "pr_auc", "roc_auc", "confusion_matrix"):
        assert key in res
    assert 0.0 <= res["recall"] <= 1.0
