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
# Référentiel des 14 types de fraude (CDC §6)
# ---------------------------------------------------------------------------
ALL_FRAUD_TYPES: tuple[str, ...] = (
    "SURFACTURATION",
    "QUANTITE_EXCESSIVE",
    "UPCODING",
    "LIGNES_NON_PRESCRITES",
    "SUBSTITUTION_PRODUIT",
    "ORDONNANCE_EXPIREE",
    "SOINS_JOUR_FERME",
    "DOUBLON",
    "FRACTIONNEMENT",
    "SURCONSOMMATION",
    "ACTE_FICTIF",
    "INCOHERENCE_PROFIL",
    "PRESTATAIRE_RADIE",
    "HORS_COUVERTURE",
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


# ---------------------------------------------------------------------------
# Intervalle de confiance de Wilson pour petits effectifs
# ---------------------------------------------------------------------------
def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calcule l'intervalle de confiance de Wilson pour une proportion binomiale (k sur n)."""
    if n <= 0:
        return 0.0, 0.0
    z = 1.95996  # Pour 95% de confiance
    p_hat = k / n
    denominator = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2 * n)) / denominator
    spread = z * np.sqrt((p_hat * (1.0 - p_hat) + (z**2) / (4 * n)) / n) / denominator
    low = max(0.0, float(center - spread))
    high = min(1.0, float(center + spread))
    return round(low, 4), round(high, 4)


# ---------------------------------------------------------------------------
# Métriques détaillées par type de fraude
# ---------------------------------------------------------------------------
def compute_metrics_by_fraud_type(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    types_fraude: pd.Series | np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    """Calcule pour chacun des 14 types de fraude le Recall, Précision et IC Wilson."""
    y_arr = np.asarray(y_true).astype(int)
    prob_arr = np.asarray(y_prob, dtype=float)
    y_pred = (prob_arr >= threshold).astype(int)
    tf_series = pd.Series(types_fraude).fillna("AUCUNE").astype(str)
    total_alertes = int(y_pred.sum())
    results: dict[str, dict[str, Any]] = {}
    for ftype in ALL_FRAUD_TYPES:
        mask_type = (tf_series == ftype) & (y_arr == 1)
        n_cas = int(mask_type.sum())
        if n_cas == 0:
            results[ftype] = {
                "effectif_test": 0,
                "detectes": 0,
                "rates": 0,
                "recall": 0.0,
                "recall_ic_wilson_95": [0.0, 0.0],
                "precision_part_alertes": 0.0,
                "score_moyen": 0.0,
                "statut": "ABSENT_DU_TEST",
            }
            continue
        preds_subset = y_pred[mask_type]
        probs_subset = prob_arr[mask_type]
        detectes = int(preds_subset.sum())
        rates = n_cas - detectes
        rec = float(detectes / n_cas)
        score_moy = float(np.mean(probs_subset))
        part_alertes = float(detectes / total_alertes) if total_alertes > 0 else 0.0
        ci_low, ci_high = compute_wilson_ci(detectes, n_cas)
        if rec == 1.0:
            statut = "DETECTE_100%"
        elif rec == 0.0:
            statut = "NON_DETECTE"
        else:
            statut = "PARTIEL"
        results[ftype] = {
            "effectif_test": n_cas,
            "detectes": detectes,
            "rates": rates,
            "recall": round(rec, 4),
            "recall_ic_wilson_95": [ci_low, ci_high],
            "precision_part_alertes": round(part_alertes, 4),
            "score_moyen": round(score_moy, 4),
            "statut": statut,
        }
    return results




# ---------------------------------------------------------------------------
# Métriques d'évaluation et de calibration v2 / modèle B
# ---------------------------------------------------------------------------
def seuil_pour_recall(y: Any, p: Any, cible: float = 0.80) -> float:
    """Plus petit seuil qui garantit le rappel cible."""
    prec, rec, th = precision_recall_curve(y, p)
    ok = np.where(rec[:-1] >= cible)[0]
    return float(th[ok[-1]]) if len(ok) else float(th[0])


def metriques_seuil(y: Any, p: Any, seuil: float) -> dict[str, Any]:
    """Matrice de confusion et métriques à un seuil donné."""
    y_arr = np.asarray(y)
    pred = np.asarray(p) >= seuil
    tn, fp, fn, tp = confusion_matrix(y_arr, pred, labels=[0, 1]).ravel()
    rec = tp / max(tp + fn, 1)
    pre = tp / max(tp + fp, 1)
    return {
        "seuil": float(seuil),
        "tp": int(tp),
        "fp": int(fp),
        "fn": int(fn),
        "tn": int(tn),
        "recall": float(rec),
        "precision": float(pre),
        "f1": float(2 * pre * rec / (pre + rec)) if (pre + rec) else 0.0,
        "nb_alertes": int(pred.sum()),
        "part_alertee": float(pred.mean()),
        "lift": float(pre / y_arr.mean()) if y_arr.mean() else float("nan"),
    }


def metriques_comparaison(y: Any, p: Any) -> dict[str, Any]:
    """PR-AUC, ROC-AUC et rappels à budget d'alertes fixé."""
    y_arr = np.asarray(y)
    p_arr = np.asarray(p)
    prec, rec, _ = precision_recall_curve(y_arr, p_arr)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-12)
    m80 = metriques_seuil(y_arr, p_arr, seuil_pour_recall(y_arr, p_arr, 0.80))
    out: dict[str, Any] = {
        "pr_auc": float(average_precision_score(y_arr, p_arr)),
        "roc_auc": float(roc_auc_score(y_arr, p_arr)),
        "brier": float(brier_score_loss(y_arr, p_arr)),
        "f1_max": float(f1.max()),
        "precision_a_recall80": float(m80["precision"]),
        "part_alertee_a_recall80": float(m80["part_alertee"]),
    }
    ordre = np.argsort(-p_arr)
    for budget in (0.03, 0.05):
        k = max(1, int(round(budget * len(y_arr))))
        out[f"recall_top{int(budget * 100)}pct"] = float(y_arr[ordre[:k]].sum() / max(y_arr.sum(), 1))
    return out


def intervalle_confiance_bootstrap(
    y: Any, p: Any, metrique: str = "pr_auc", n: int = 500, graine: int = 42
) -> tuple[float, float]:
    """IC à 95 % par bootstrap (utile avec peu de positifs)."""
    y_arr = np.asarray(y)
    p_arr = np.asarray(p)
    rng = np.random.default_rng(graine)
    valeurs = []
    for _ in range(n):
        idx = rng.integers(0, len(y_arr), len(y_arr))
        if len(np.unique(y_arr[idx])) < 2:
            continue
        if metrique == "pr_auc":
            valeurs.append(average_precision_score(y_arr[idx], p_arr[idx]))
        elif metrique == "roc_auc":
            valeurs.append(roc_auc_score(y_arr[idx], p_arr[idx]))
        else:
            raise ValueError(f"Métrique inconnue : {metrique}")
    return float(np.percentile(valeurs, 2.5)), float(np.percentile(valeurs, 97.5))


def courbe_seuils(
    y: Any, p: Any, budgets: tuple[float, ...] = (0.005, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20)
) -> pd.DataFrame:
    """Table de compromis seuil / rappel / précision."""
    lignes = []
    for b in budgets:
        seuil = float(np.quantile(p, 1 - b))
        m = metriques_seuil(y, p, seuil)
        m["budget_alertes"] = b
        lignes.append(m)
    return pd.DataFrame(lignes)[
        [
            "budget_alertes",
            "seuil",
            "nb_alertes",
            "recall",
            "precision",
            "f1",
            "tp",
            "fp",
            "fn",
            "tn",
        ]
    ]


def ece(y: Any, p: Any, bins: int = 10) -> tuple[float, pd.DataFrame]:
    """Erreur de calibration attendue (ECE) et table par décile."""
    q = pd.qcut(p, q=min(bins, len(np.unique(p))), duplicates="drop")
    g = (
        pd.DataFrame({"y": y, "p": p, "q": q})
        .groupby("q", observed=True)
        .agg(n=("y", "size"), obs=("y", "mean"), pred=("p", "mean"))
    )
    valeur = float((g["n"] * (g["obs"] - g["pred"]).abs()).sum() / g["n"].sum())
    return valeur, g.reset_index(drop=True)
