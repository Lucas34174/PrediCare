"""Module d'analyse et de sélection du seuil de décision – PrediCare TPA (PB-07).

Responsabilités :
  - Balayage fin des seuils [0.05 à 0.95] sur prédictions Out-Of-Fold (OOF).
  - Calcul pour chaque seuil : Recall, Précision, F1, F2, nombre d'alertes, taux d'alerte.
  - Sélection du seuil optimal selon la règle métier : max Précision avec Recall >= min_recall.
  - Export des courbes et tableaux de décision sans toucher au jeu de test.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)

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
from predicare.ml.tuning import evaluate_out_of_fold

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Balayage des seuils
# ---------------------------------------------------------------------------
def compute_threshold_table(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    thresholds: list[float] | None = None,
) -> pd.DataFrame:
    """Calcule les métriques opérationnelles pour une grille de seuils."""
    if thresholds is None:
        thresholds = [round(t, 2) for t in np.arange(0.05, 0.96, 0.05)]

    y_arr = np.asarray(y_true).astype(int)
    n_total = len(y_arr)
    rows: list[dict[str, Any]] = []

    for t in thresholds:
        y_pred = (y_prob >= t).astype(int)
        cm = confusion_matrix(y_arr, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        rec = float(recall_score(y_arr, y_pred, zero_division=0))
        prec = float(precision_score(y_arr, y_pred, zero_division=0))
        f1 = float(f1_score(y_arr, y_pred, zero_division=0))
        f2 = float(fbeta_score(y_arr, y_pred, beta=2, zero_division=0))
        nb_alertes = int(tp + fp)
        taux_alerte = float(nb_alertes / n_total) if n_total > 0 else 0.0

        rows.append(
            {
                "seuil": t,
                "recall": round(rec, 4),
                "precision": round(prec, 4),
                "f1": round(f1, 4),
                "f2": round(f2, 4),
                "nb_alertes": nb_alertes,
                "taux_alerte": round(taux_alerte, 4),
                "tp": int(tp),
                "fp": int(fp),
                "fn": int(fn),
                "tn": int(tn),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Règle de décision opérationnelle
# ---------------------------------------------------------------------------
def select_optimal_threshold(
    table: pd.DataFrame,
    min_recall: float = 0.80,
    criterion: str = "max_precision",
    cost_fn: float = 5.0,
    cost_fp: float = 1.0,
) -> dict[str, Any]:
    """Sélectionne le seuil optimal selon la règle métier choisie sur validation.

    Critères supportés :
      - "max_precision" : max Précision sous contrainte Recall >= min_recall (défaut)
      - "max_f2"        : max F2-score (pondérant 2x plus le Rappel que la Précision)
      - "cost_utility"  : minimise le coût métier total (cost_fn * FN + cost_fp * FP)
    """
    if criterion == "max_f2":
        best_row = table.sort_values(by=["f2", "recall"], ascending=[False, False]).iloc[0]
        rule_applied = "Max F2-score (validation)"
    elif criterion == "cost_utility":
        t_copy = table.copy()
        t_copy["cout_total"] = t_copy["fn"] * cost_fn + t_copy["fp"] * cost_fp
        best_row = t_copy.sort_values(by=["cout_total", "recall"], ascending=[True, False]).iloc[0]
        rule_applied = f"Min Coût métier (FN x{cost_fn} + FP x{cost_fp})"
    else:
        eligible = table[table["recall"] >= min_recall]
        if not eligible.empty:
            best_row = eligible.sort_values(by=["precision", "f2"], ascending=[False, False]).iloc[
                0
            ]
            rule_applied = f"Max Précision avec Recall >= {min_recall:.2f}"
        else:
            best_row = table.sort_values(by=["recall", "f2"], ascending=[False, False]).iloc[0]
            rule_applied = "Max Recall (contrainte non atteinte)"

    return {
        "seuil_optimal": float(best_row["seuil"]),
        "recall": float(best_row["recall"]),
        "precision": float(best_row["precision"]),
        "f1": float(best_row["f1"]),
        "f2": float(best_row["f2"]),
        "nb_alertes": int(best_row["nb_alertes"]),
        "taux_alerte": float(best_row["taux_alerte"]),
        "tp": int(best_row["tp"]),
        "fp": int(best_row["fp"]),
        "fn": int(best_row["fn"]),
        "tn": int(best_row["tn"]),
        "regle_decision": rule_applied,
    }


# ---------------------------------------------------------------------------
# Données de courbe PR
# ---------------------------------------------------------------------------
def compute_pr_curve_data(y_true: pd.Series | np.ndarray, y_prob: np.ndarray) -> dict[str, Any]:
    """Extrait les points de la courbe Précision-Rappel pour export."""
    prec, rec, thresh = precision_recall_curve(y_true, y_prob)
    return {
        "precision": [round(float(p), 4) for p in prec[:: max(1, len(prec) // 30)]],
        "recall": [round(float(r), 4) for r in rec[:: max(1, len(rec) // 30)]],
    }


# ---------------------------------------------------------------------------
# CLI : python -m predicare.ml.threshold
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    def _cli() -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        p = argparse.ArgumentParser(description="Sélection du seuil – PrediCare TPA (PB-07)")
        p.add_argument("--features", default=FEATURES_PATH)
        p.add_argument("--labels", default=LABELS_PATH)
        p.add_argument("--factures", default=FACTURES_PATH)
        p.add_argument("--models-dir", default=str(MODELS_DIR))
        p.add_argument("--min-recall", type=float, default=0.80)
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--test-size", type=float, default=0.2)
        args = p.parse_args()

        models_dir = Path(args.models_dir)
        tuning_path = models_dir / "tuning_results.json"
        if not tuning_path.exists():
            sys.exit("Erreur : models/tuning_results.json absent. Lance d'abord make tune.")

        tuning_data = json.loads(tuning_path.read_text())

        X, y, meta = load_dataset(args.features, args.labels, args.factures)
        X_tr, _, y_tr, _ = split_no_leakage(X, y, meta, test_size=args.test_size)
        check_no_leakage(X_tr)

        X_tr_clean, _, _ = _drop_high_nan(X_tr, X_tr)
        meta_tr = meta.set_index("facture_id").loc[X_tr_clean.index]
        groups_tr = meta_tr["assure_id"].to_numpy()

        analysis_out: dict[str, Any] = {}
        for mtype in ("xgb", "lgbm"):
            best_params = tuning_data[mtype]["best_params"]
            oof_prob, _ = evaluate_out_of_fold(
                mtype, best_params, X_tr_clean, y_tr, groups_tr, seed=args.seed
            )
            table = compute_threshold_table(y_tr, oof_prob)
            optimal = select_optimal_threshold(table, min_recall=args.min_recall)
            pr_curve = compute_pr_curve_data(y_tr, oof_prob)

            analysis_out[mtype] = {
                "optimal": optimal,
                "table": table.to_dict(orient="records"),
                "pr_curve": pr_curve,
            }

            print(f"\n=== Seuil de décision optimal [{mtype.upper()}] ===")
            print(f"  Règle             : {optimal['regle_decision']}")
            print(f"  Seuil optimal     : {optimal['seuil_optimal']:.2f}")
            print(f"  Recall            : {optimal['recall']:.3f} (prioritaire)")
            print(f"  Précision         : {optimal['precision']:.3f}")
            print(f"  F1-score / F2     : {optimal['f1']:.3f} / {optimal['f2']:.3f}")
            print(
                f"  Alertes générées  : {optimal['nb_alertes']} / {len(y_tr)} ({optimal['taux_alerte'] * 100:.1f} %)"
            )

        out_file = models_dir / "threshold_analysis.json"
        out_file.write_text(json.dumps(analysis_out, indent=2, ensure_ascii=False))
        logger.info("Analyse de seuil enregistrée dans %s", out_file)

    _cli()
