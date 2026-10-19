"""Tests unitaires du module de tuning ML (PB-07)."""

import numpy as np
import optuna
import pandas as pd
import pytest
import shap

from predicare.ml.tuning import (
    evaluate_cv,
    evaluate_out_of_fold,
    sample_lgbm_params,
    sample_xgb_params,
    train_tuned_model,
    tune_model,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_dataset(n: int = 120, n_assures: int = 15, n_fraud: int = 15, seed: int = 42):
    rng = np.random.default_rng(seed)
    fids = [f"F{i:04d}" for i in range(n)]
    assures = np.array([f"A{i % n_assures:03d}" for i in range(n)])
    X = pd.DataFrame(
        {
            "f_ratio": rng.uniform(0.5, 2.0, n),
            "f_ecart": rng.normal(0, 1, n),
            "f_age": rng.integers(18, 70, n),
        },
        index=pd.Index(fids, name="facture_id"),
    )
    y = pd.Series([0] * (n - n_fraud) + [1] * n_fraud, index=X.index, name="est_fraude")
    return X, y, assures


# ---------------------------------------------------------------------------
# Tests espaces d'échantillonnage
# ---------------------------------------------------------------------------
def test_sample_xgb_params():
    study = optuna.create_study()
    trial = study.ask()
    params = sample_xgb_params(trial, scale_pos=10.0)
    for key in ("max_depth", "learning_rate", "n_estimators", "subsample", "scale_pos_weight"):
        assert key in params
    assert 3 <= params["max_depth"] <= 8
    assert 1.0 <= params["scale_pos_weight"] <= 10.0


def test_sample_lgbm_params():
    study = optuna.create_study()
    trial = study.ask()
    params = sample_lgbm_params(trial, scale_pos=10.0)
    for key in ("num_leaves", "learning_rate", "min_child_samples", "scale_pos_weight"):
        assert key in params
    assert 15 <= params["num_leaves"] <= 127


# ---------------------------------------------------------------------------
# Tests CV et Tuning (sur jeu synthétique rapide)
# ---------------------------------------------------------------------------
def test_evaluate_cv_xgb():
    X, y, groups = _make_dataset()
    params = {
        "max_depth": 3,
        "learning_rate": 0.1,
        "n_estimators": 10,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 1.0,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "scale_pos_weight": 2.0,
    }
    score = evaluate_cv("xgb", params, X, y, groups, n_splits=3)
    assert 0.0 <= score <= 1.0


def test_evaluate_cv_lgbm():
    X, y, groups = _make_dataset()
    params = {
        "max_depth": 3,
        "num_leaves": 15,
        "learning_rate": 0.1,
        "n_estimators": 10,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_samples": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "scale_pos_weight": 2.0,
    }
    score = evaluate_cv("lgbm", params, X, y, groups, n_splits=3)
    assert 0.0 <= score <= 1.0


def test_tune_model_xgb_et_lgbm_court():
    """Tuning court (2 trials, 2 splits) pour valider l'orchestrateur Optuna."""
    X, y, groups = _make_dataset(n=60, n_assures=10, n_fraud=10)
    study_xgb, best_p_xgb = tune_model("xgb", X, y, groups, n_trials=2, n_splits=2)
    assert len(study_xgb.trials) == 2
    assert "max_depth" in best_p_xgb

    study_lgb, best_p_lgb = tune_model("lgbm", X, y, groups, n_trials=2, n_splits=2)
    assert len(study_lgb.trials) == 2
    assert "num_leaves" in best_p_lgb


# ---------------------------------------------------------------------------
# Tests Out-Of-Fold et Compatibilité SHAP
# ---------------------------------------------------------------------------
def test_evaluate_out_of_fold():
    X, y, groups = _make_dataset(n=60, n_assures=10, n_fraud=10)
    params = {
        "max_depth": 3,
        "learning_rate": 0.1,
        "n_estimators": 10,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 1.0,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "scale_pos_weight": 2.0,
    }
    oof_probs, metrics = evaluate_out_of_fold("xgb", params, X, y, groups, n_splits=3)
    assert len(oof_probs) == len(y)
    assert np.all((oof_probs >= 0.0) & (oof_probs <= 1.0))
    assert "oof_pr_auc" in metrics
    assert "oof_recall_0.5" in metrics


def test_train_tuned_model_et_shap_compatibility():
    """Vérifie que les modèles entraînés sont compatibles avec shap.TreeExplainer."""
    X, y, _ = _make_dataset(n=50, n_fraud=8)
    params_xgb = {
        "max_depth": 3,
        "learning_rate": 0.1,
        "n_estimators": 15,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 1.0,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "scale_pos_weight": 2.0,
    }
    xgb_mod = train_tuned_model("xgb", params_xgb, X, y)
    explainer_xgb = shap.TreeExplainer(xgb_mod)
    shap_vals_xgb = explainer_xgb(X)
    assert shap_vals_xgb.values.shape == X.shape

    params_lgb = {
        "max_depth": 3,
        "num_leaves": 15,
        "learning_rate": 0.1,
        "n_estimators": 15,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_samples": 5,
        "reg_alpha": 0.1,
        "reg_lambda": 0.1,
        "scale_pos_weight": 2.0,
    }
    lgb_mod = train_tuned_model("lgbm", params_lgb, X, y)
    explainer_lgb = shap.TreeExplainer(lgb_mod)
    shap_vals_lgb = explainer_lgb(X)
    assert shap_vals_lgb.values.shape == X.shape


def test_tuning_refuse_fuite():
    """tune_model doit refuser tout X contenant une variable interdite."""
    X, y, groups = _make_dataset()
    X["statut"] = "PAYEE"
    with pytest.raises(ValueError, match="Fuite de données détectée"):
        tune_model("xgb", X, y, groups, n_trials=1)
