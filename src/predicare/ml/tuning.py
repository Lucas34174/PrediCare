"""Module de tuning d'hyperparamètres (XGBoost & LightGBM) – PrediCare TPA (PB-07).

Responsabilités :
  - Validation croisée stratifiée et groupée par assuré (StratifiedGroupKFold).
  - Optimisation bayésienne Optuna sur la métrique PR-AUC (Average Precision).
  - Gestion explicite du déséquilibre via scale_pos_weight.
  - Prédiction Out-Of-Fold (OOF) pour le calibrage ultérieur du seuil de décision.
  - Garantie anti-fuite : le jeu de test n'est jamais utilisé durant le tuning.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.metrics import average_precision_score, fbeta_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from xgboost import XGBClassifier

from predicare.ml.baseline import (
    FACTURES_PATH,
    FEATURES_PATH,
    LABELS_PATH,
    MODELS_DIR,
    _drop_high_nan,
    check_no_leakage,
    load_dataset,
    split_no_leakage,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Espaces de recherche Optuna
# ---------------------------------------------------------------------------
def sample_xgb_params(trial: optuna.Trial, scale_pos: float) -> dict[str, Any]:
    """Échantillonne les hyperparamètres XGBoost."""
    return {
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 10.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, max(1.0, scale_pos)),
    }


def sample_lgbm_params(trial: optuna.Trial, scale_pos: float) -> dict[str, Any]:
    """Échantillonne les hyperparamètres LightGBM."""
    return {
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 100, 500, step=50),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_samples": trial.suggest_int("min_child_samples", 5, 50),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, max(1.0, scale_pos)),
    }


# ---------------------------------------------------------------------------
# Validation croisée interne et fonction objectif
# ---------------------------------------------------------------------------
def _compute_splits(
    y: pd.Series, groups: pd.Series | np.ndarray, n_splits: int = 5
) -> StratifiedGroupKFold:
    """Instancie un découpage CV stratifié et groupé adapté au volume."""
    n_pos = int(y.sum())
    n_grp = len(np.unique(groups))
    effective_splits = max(2, min(n_splits, n_pos, n_grp))
    return StratifiedGroupKFold(n_splits=effective_splits, shuffle=True, random_state=42)


def evaluate_cv(
    model_type: str,
    params: dict[str, Any],
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series | np.ndarray,
    seed: int = 42,
    n_splits: int = 5,
) -> float:
    """Évalue un jeu d'hyperparamètres par CV groupée sur la PR-AUC moyenne."""
    sgkf = _compute_splits(y, groups, n_splits=n_splits)
    scores: list[float] = []

    for tr_idx, val_idx in sgkf.split(X, y, groups):
        X_tr_f, X_val_f = X.iloc[tr_idx], X.iloc[val_idx]
        y_tr_f, y_val_f = y.iloc[tr_idx], y.iloc[val_idx]

        if model_type == "xgb":
            clf = XGBClassifier(
                **params,
                random_state=seed,
                eval_metric="aucpr",
                early_stopping_rounds=30,
                verbosity=0,
                n_jobs=-1,
            )
            clf.fit(X_tr_f, y_tr_f, eval_set=[(X_val_f, y_val_f)], verbose=False)
        elif model_type == "lgbm":
            clf = LGBMClassifier(
                **params,
                random_state=seed,
                verbosity=-1,
                n_jobs=-1,
            )
            clf.fit(
                X_tr_f,
                y_tr_f,
                eval_set=[(X_val_f, y_val_f)],
                eval_metric="binary_logloss",
                callbacks=[early_stopping(stopping_rounds=30, verbose=False), log_evaluation(0)],
            )
        else:
            raise ValueError(f"Modèle inconnu : {model_type!r}")

        y_prob = clf.predict_proba(X_val_f)[:, 1]
        scores.append(float(average_precision_score(y_val_f, y_prob)))

    return float(np.mean(scores))


# ---------------------------------------------------------------------------
# Optimisation Optuna
# ---------------------------------------------------------------------------
def tune_model(
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: pd.Series | np.ndarray,
    n_trials: int = 30,
    seed: int = 42,
    n_splits: int = 5,
) -> tuple[optuna.Study, dict[str, Any]]:
    """Recherche bayésienne d'hyperparamètres sur le train."""
    check_no_leakage(X_train)
    n_neg = len(y_train) - int(y_train.sum())
    scale_pos = n_neg / max(1, int(y_train.sum()))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    def objective(trial: optuna.Trial) -> float:
        if model_type == "xgb":
            params = sample_xgb_params(trial, scale_pos)
        else:
            params = sample_lgbm_params(trial, scale_pos)
        return evaluate_cv(
            model_type=model_type,
            params=params,
            X=X_train,
            y=y_train,
            groups=groups_train,
            seed=seed,
            n_splits=n_splits,
        )

    logger.info("Début tuning %s (%d trials, CV %d-folds)", model_type.upper(), n_trials, n_splits)
    study.optimize(objective, n_trials=n_trials, n_jobs=1)
    logger.info("Fin tuning %s : Meilleure PR-AUC CV = %.4f", model_type.upper(), study.best_value)
    return study, study.best_params


# ---------------------------------------------------------------------------
# Entraînement final du modèle tuné
# ---------------------------------------------------------------------------
def train_tuned_model(
    model_type: str,
    best_params: dict[str, Any],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    seed: int = 42,
) -> XGBClassifier | LGBMClassifier:
    """Entraîne le modèle avec les meilleurs paramètres sur tout le train."""
    check_no_leakage(X_train)
    if model_type == "xgb":
        model = XGBClassifier(
            **best_params,
            random_state=seed,
            verbosity=0,
            n_jobs=-1,
        )
    elif model_type == "lgbm":
        model = LGBMClassifier(
            **best_params,
            random_state=seed,
            verbosity=-1,
            n_jobs=-1,
        )
    else:
        raise ValueError(f"Modèle inconnu : {model_type!r}")

    model.fit(X_train, y_train)
    return model


# ---------------------------------------------------------------------------
# Prédictions Out-Of-Fold (pour sélection du seuil sans fuite)
# ---------------------------------------------------------------------------
def evaluate_out_of_fold(
    model_type: str,
    best_params: dict[str, Any],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    groups_train: pd.Series | np.ndarray,
    seed: int = 42,
    n_splits: int = 5,
) -> tuple[np.ndarray, dict[str, float]]:
    """Génère les probabilités Out-Of-Fold pour calibrer le seuil de décision."""
    sgkf = _compute_splits(y_train, groups_train, n_splits=n_splits)
    oof_probs = np.zeros(len(y_train), dtype=float)

    for tr_idx, val_idx in sgkf.split(X_train, y_train, groups_train):
        X_tr_f, X_val_f = X_train.iloc[tr_idx], X_train.iloc[val_idx]
        y_tr_f, y_val_f = y_train.iloc[tr_idx], y_train.iloc[val_idx]

        if model_type == "xgb":
            clf = XGBClassifier(
                **best_params,
                random_state=seed,
                eval_metric="aucpr",
                early_stopping_rounds=30,
                verbosity=0,
                n_jobs=-1,
            )
            clf.fit(X_tr_f, y_tr_f, eval_set=[(X_val_f, y_val_f)], verbose=False)
        else:
            clf = LGBMClassifier(
                **best_params,
                random_state=seed,
                verbosity=-1,
                n_jobs=-1,
            )
            clf.fit(
                X_tr_f,
                y_tr_f,
                eval_set=[(X_val_f, y_val_f)],
                eval_metric="binary_logloss",
                callbacks=[early_stopping(stopping_rounds=30, verbose=False), log_evaluation(0)],
            )

        oof_probs[val_idx] = clf.predict_proba(X_val_f)[:, 1]

    pr_auc = float(average_precision_score(y_train, oof_probs))
    y_pred_def = (oof_probs >= 0.5).astype(int)
    recall = float(recall_score(y_train, y_pred_def, zero_division=0))
    f2 = float(fbeta_score(y_train, y_pred_def, beta=2, zero_division=0))

    metrics = {"oof_pr_auc": pr_auc, "oof_recall_0.5": recall, "oof_f2_0.5": f2}
    return oof_probs, metrics


# ---------------------------------------------------------------------------
# CLI : python -m predicare.ml.tuning
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    def _cli() -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        p = argparse.ArgumentParser(description="Tuning XGBoost / LightGBM – PrediCare TPA (PB-07)")
        p.add_argument("--features", default=FEATURES_PATH)
        p.add_argument("--labels", default=LABELS_PATH)
        p.add_argument("--factures", default=FACTURES_PATH)
        p.add_argument("--models-dir", default=str(MODELS_DIR))
        p.add_argument("--n-trials", type=int, default=20)
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--test-size", type=float, default=0.2)
        p.add_argument("--cv-splits", type=int, default=5)
        args = p.parse_args()

        models_dir = Path(args.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)

        X, y, meta = load_dataset(args.features, args.labels, args.factures)
        X_tr, _, y_tr, _ = split_no_leakage(X, y, meta, test_size=args.test_size)

        # Exclusion features > 95% NaN sur le train
        X_tr_clean, _, dropped = _drop_high_nan(X_tr, X_tr)
        meta_tr = meta.set_index("facture_id").loc[X_tr_clean.index]
        groups_tr = meta_tr["assure_id"].to_numpy()

        results: dict[str, Any] = {}
        for mtype in ("xgb", "lgbm"):
            study, best_p = tune_model(
                mtype,
                X_tr_clean,
                y_tr,
                groups_tr,
                n_trials=args.n_trials,
                seed=args.seed,
                n_splits=args.cv_splits,
            )
            oof_p, oof_m = evaluate_out_of_fold(
                mtype,
                best_p,
                X_tr_clean,
                y_tr,
                groups_tr,
                seed=args.seed,
                n_splits=args.cv_splits,
            )
            results[mtype] = {
                "best_value_pr_auc": study.best_value,
                "best_params": best_p,
                "oof_metrics": oof_m,
            }
            print(f"\n[{mtype.upper()} - Tuning CV]")
            print(f"  PR-AUC CV moy. : {study.best_value:.4f}")
            print(f"  OOF PR-AUC     : {oof_m['oof_pr_auc']:.4f}")
            print(f"  OOF Recall@0.5 : {oof_m['oof_recall_0.5']:.4f}")
            print(f"  OOF F2@0.5     : {oof_m['oof_f2_0.5']:.4f}")

        out_report = models_dir / "tuning_results.json"
        out_report.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        logger.info("Résultats de tuning enregistrés dans %s", out_report)

    _cli()
