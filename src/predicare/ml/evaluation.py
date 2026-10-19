"""Métriques d'évaluation du modèle B (contrôle médical)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
)


def seuil_pour_recall(y, p, cible: float = 0.80) -> float:
    """Plus petit seuil qui garantit le rappel cible."""
    prec, rec, th = precision_recall_curve(y, p)
    ok = np.where(rec[:-1] >= cible)[0]
    return float(th[ok[-1]]) if len(ok) else float(th[0])


def metriques_seuil(y, p, seuil: float) -> dict:
    """Matrice de confusion et métriques à un seuil donné."""
    pred = np.asarray(p) >= seuil
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
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
        "lift": float(pre / y.mean()) if y.mean() else float("nan"),
    }


def metriques_comparaison(y, p) -> dict:
    """PR-AUC, ROC-AUC et rappels à budget d'alertes fixé."""
    y = np.asarray(y)
    p = np.asarray(p)
    prec, rec, _ = precision_recall_curve(y, p)
    f1 = 2 * prec * rec / np.maximum(prec + rec, 1e-12)
    m80 = metriques_seuil(y, p, seuil_pour_recall(y, p, 0.80))
    out = {
        "pr_auc": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "f1_max": float(f1.max()),
        "precision_a_recall80": float(m80["precision"]),
        "part_alertee_a_recall80": float(m80["part_alertee"]),
    }
    ordre = np.argsort(-p)
    for budget in (0.03, 0.05):
        k = max(1, int(round(budget * len(y))))
        out[f"recall_top{int(budget * 100)}pct"] = float(y[ordre[:k]].sum() / max(y.sum(), 1))
    return out


def intervalle_confiance_bootstrap(
    y, p, metrique: str = "pr_auc", n: int = 500, graine: int = 42
) -> tuple[float, float]:
    """IC à 95 % par bootstrap (utile avec peu de positifs)."""
    y = np.asarray(y)
    p = np.asarray(p)
    rng = np.random.default_rng(graine)
    valeurs = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        if metrique == "pr_auc":
            valeurs.append(average_precision_score(y[idx], p[idx]))
        elif metrique == "roc_auc":
            valeurs.append(roc_auc_score(y[idx], p[idx]))
        else:
            raise ValueError(f"Métrique inconnue : {metrique}")
    return float(np.percentile(valeurs, 2.5)), float(np.percentile(valeurs, 97.5))


def courbe_seuils(y, p, budgets=(0.005, 0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20)) -> pd.DataFrame:
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


def ece(y, p, bins: int = 10) -> tuple[float, pd.DataFrame]:
    """Erreur de calibration attendue (ECE) et table par décile."""
    q = pd.qcut(p, q=min(bins, len(np.unique(p))), duplicates="drop")
    g = (
        pd.DataFrame({"y": y, "p": p, "q": q})
        .groupby("q", observed=True)
        .agg(n=("y", "size"), obs=("y", "mean"), pred=("p", "mean"))
    )
    valeur = float((g["n"] * (g["obs"] - g["pred"]).abs()).sum() / g["n"].sum())
    return valeur, g.reset_index(drop=True)
