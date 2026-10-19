"""Module d'évaluation rigoureuse du modèle de fraude – PrediCare TPA (PB-08).

Fonctions pures et testables, sans effets de bord :
  - compute_confusion_metrics() : matrices aux seuils 0.80 et 0.30 (brutes et normalisées).
  - compute_pr_roc_curves()      : PR-AUC, courbe PR vs prévalence, ROC-AUC.
  - compute_calibration()        : Brier score et courbe de fiabilité.
  - compute_threshold_grid()     : tableau de sensibilité au seuil.
  - compute_naive_baseline()     : baseline naïve basée sur la prévalence.
  - evaluate_global()            : agrégateur de métriques globales.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)


# ---------------------------------------------------------------------------
# 1. Matrice de confusion et métriques au seuil
# ---------------------------------------------------------------------------
def compute_confusion_metrics(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    """Calcule la matrice de confusion (brute et normalisée) et les métriques associées."""
    y_arr = np.asarray(y_true).astype(int)
    y_pred = (np.asarray(y_prob) >= threshold).astype(int)
    n_total = len(y_arr)

    cm = confusion_matrix(y_arr, y_pred, labels=[0, 1])
    tn, fp, fn, tp = [int(v) for v in cm.ravel()]

    rec = float(recall_score(y_arr, y_pred, zero_division=0))
    prec = float(precision_score(y_arr, y_pred, zero_division=0))
    f1 = float(f1_score(y_arr, y_pred, zero_division=0))
    f2 = float(fbeta_score(y_arr, y_pred, beta=2, zero_division=0))
    spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

    nb_alertes = tp + fp
    taux_alerte = float(nb_alertes / n_total) if n_total > 0 else 0.0

    return {
        "seuil": round(threshold, 2),
        "matrice_brute": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "matrice_normalisee_pct": {
            "tp": round(100.0 * tp / n_total, 2) if n_total else 0.0,
            "fp": round(100.0 * fp / n_total, 2) if n_total else 0.0,
            "fn": round(100.0 * fn / n_total, 2) if n_total else 0.0,
            "tn": round(100.0 * tn / n_total, 2) if n_total else 0.0,
        },
        "recall": round(rec, 4),
        "precision": round(prec, 4),
        "f1": round(f1, 4),
        "f2": round(f2, 4),
        "specificite": round(spec, 4),
        "nb_alertes": nb_alertes,
        "taux_alerte_pct": round(100.0 * taux_alerte, 2),
    }


# ---------------------------------------------------------------------------
# 2. Courbes PR et ROC
# ---------------------------------------------------------------------------
def compute_pr_roc_curves(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    n_sample_points: int = 25,
) -> dict[str, Any]:
    """Calcule la PR-AUC, la prévalence baseline et échantillonne les courbes."""
    y_arr = np.asarray(y_true).astype(int)
    prob_arr = np.asarray(y_prob, dtype=float)

    pr_auc = float(average_precision_score(y_arr, prob_arr))
    prevalence = float(np.mean(y_arr))
    roc_auc = float(roc_auc_score(y_arr, prob_arr)) if len(np.unique(y_arr)) > 1 else 0.5

    prec_arr, rec_arr, _ = precision_recall_curve(y_arr, prob_arr)
    step_pr = max(1, len(prec_arr) // n_sample_points)
    pr_points = [
        {"recall": round(float(r), 4), "precision": round(float(p), 4)}
        for p, r in zip(prec_arr[::step_pr], rec_arr[::step_pr], strict=False)
    ]

    fpr_arr, tpr_arr, _ = roc_curve(y_arr, prob_arr)
    step_roc = max(1, len(fpr_arr) // n_sample_points)
    roc_points = [
        {"fpr": round(float(f), 4), "tpr": round(float(t), 4)}
        for f, t in zip(fpr_arr[::step_roc], tpr_arr[::step_roc], strict=False)
    ]

    return {
        "pr_auc": round(pr_auc, 4),
        "prevalence_baseline": round(prevalence, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_points": pr_points,
        "roc_points": roc_points,
    }


# ---------------------------------------------------------------------------
# 3. Calibration et Score de Brier
# ---------------------------------------------------------------------------
def compute_calibration(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 5,
) -> dict[str, Any]:
    """Évalue la calibration probabiliste (Brier score et courbe de fiabilité)."""
    y_arr = np.asarray(y_true).astype(int)
    prob_arr = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)

    brier = float(brier_score_loss(y_arr, prob_arr))

    # Gestion des cas à très faible effectif positif
    try:
        prob_true, prob_pred = calibration_curve(y_arr, prob_arr, n_bins=n_bins, strategy="uniform")
        curve_points = [
            {"prob_predite": round(float(p), 4), "fraction_reelle": round(float(t), 4)}
            for p, t in zip(prob_pred, prob_true, strict=False)
        ]
    except ValueError:
        curve_points = []

    return {
        "brier_score": round(brier, 4),
        "curve_points": curve_points,
    }


# ---------------------------------------------------------------------------
# 4. Grille de sensibilité au seuil
# ---------------------------------------------------------------------------
def compute_threshold_grid(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    thresholds: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Génère la table complète sensibilité seuil -> métriques."""
    if thresholds is None:
        thresholds = [round(t, 2) for t in np.arange(0.05, 0.96, 0.05)]
    return [compute_confusion_metrics(y_true, y_prob, t) for t in thresholds]


# ---------------------------------------------------------------------------
# 5. Baseline naïve (prévalence)
# ---------------------------------------------------------------------------
def compute_naive_baseline(y_true: pd.Series | np.ndarray) -> dict[str, Any]:
    """Baseline naïve prédisant toujours la prévalence a priori."""
    y_arr = np.asarray(y_true).astype(int)
    prev = float(np.mean(y_arr))
    return {
        "type": "NaivePriorClassifier",
        "prevalence": round(prev, 4),
        "brier_score": round(prev * (1.0 - prev), 4),
    }


# ---------------------------------------------------------------------------
# 6. Agrégateur d'évaluation globale
# ---------------------------------------------------------------------------
def evaluate_global(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    production_threshold: float = 0.80,
    optimal_threshold: float = 0.30,
) -> dict[str, Any]:
    """Agrège l'ensemble des métriques d'évaluation globale."""
    return {
        "metrics_seuil_production": compute_confusion_metrics(y_true, y_prob, production_threshold),
        "metrics_seuil_optimal": compute_confusion_metrics(y_true, y_prob, optimal_threshold),
        "courbes": compute_pr_roc_curves(y_true, y_prob),
        "calibration": compute_calibration(y_true, y_prob),
        "baseline_naive": compute_naive_baseline(y_true),
        "sensibilite_seuils": compute_threshold_grid(y_true, y_prob),
    }
