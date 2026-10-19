"""Module d'évaluation finale sur le jeu de test – PrediCare TPA (PB-07).

Responsabilités :
  - Évaluation unique et comparative sur le test inviolé (Baseline vs XGBoost vs LightGBM).
  - Calcul du Recall, Précision, F1, F2, PR-AUC, ROC-AUC et matrice de confusion.
  - Décomposition du Recall par type de fraude (type_fraude).
  - Intervalles de confiance à 95 % par bootstrap sur le Recall.
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
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from predicare.ml.baseline import (
    FACTURES_PATH,
    FEATURES_PATH,
    LABELS_PATH,
    MODELS_DIR,
    _drop_high_nan,
    check_no_leakage,
    load_dataset,
    make_pipeline,
    split_no_leakage,
)
from predicare.ml.tuning import train_tuned_model

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bootstrap pour intervalle de confiance du Recall
# ---------------------------------------------------------------------------
def compute_recall_bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bootstraps: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Calcule l'intervalle de confiance (1-alpha) du Recall par bootstrap empirique."""
    rng = np.random.default_rng(seed)
    n = len(y_true)
    recalls: list[float] = []

    for _ in range(n_bootstraps):
        idx = rng.integers(0, n, n)
        y_t_b = y_true[idx]
        y_p_b = y_pred[idx]
        if y_t_b.sum() > 0:
            rec = float(recall_score(y_t_b, y_p_b, zero_division=0))
            recalls.append(rec)

    if not recalls:
        return 0.0, 0.0

    low = float(np.percentile(recalls, 100 * (alpha / 2)))
    high = float(np.percentile(recalls, 100 * (1 - alpha / 2)))
    return round(low, 4), round(high, 4)


# ---------------------------------------------------------------------------
# Décomposition du Recall par type de fraude
# ---------------------------------------------------------------------------
def compute_recall_by_fraud_type(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    types_fraude: pd.Series | np.ndarray,
) -> dict[str, dict[str, Any]]:
    """Mesure le taux de détection spécifique pour chaque type de fraude."""
    tf_series = pd.Series(types_fraude).fillna("NON_DEFINI")
    fraud_mask = np.asarray(y_true) == 1
    tf_frauds = tf_series[fraud_mask]
    preds_frauds = np.asarray(y_pred)[fraud_mask]

    result: dict[str, dict[str, Any]] = {}
    for ftype in sorted(tf_frauds.unique()):
        mask = tf_frauds == ftype
        total = int(mask.sum())
        detected = int(preds_frauds[mask].sum())
        rec = float(detected / total) if total > 0 else 0.0
        result[str(ftype)] = {
            "total_cas": total,
            "detectes": detected,
            "rates": total - detected,
            "recall": round(rec, 4),
        }
    return result


# ---------------------------------------------------------------------------
# Évaluation complète d'un modèle
# ---------------------------------------------------------------------------
def evaluate_model_on_test(
    model: Any,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    threshold: float = 0.50,
    types_fraude: pd.Series | np.ndarray | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Évalue un modèle sur le test avec métriques continues et métriques au seuil."""
    check_no_leakage(X_test)
    y_true = np.asarray(y_test).astype(int)

    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
    else:
        y_prob = model.predict(X_test)

    y_pred = (y_prob >= threshold).astype(int)

    pr_auc = float(average_precision_score(y_true, y_prob))
    roc_auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.5
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    f2 = float(fbeta_score(y_true, y_pred, beta=2, zero_division=0))
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()

    ci_low, ci_high = compute_recall_bootstrap_ci(y_true, y_pred, seed=seed)

    by_type = {}
    if types_fraude is not None:
        by_type = compute_recall_by_fraud_type(y_true, y_pred, types_fraude)

    return {
        "seuil_applique": round(threshold, 2),
        "recall": round(rec, 4),
        "recall_ci_95": [ci_low, ci_high],
        "precision": round(prec, 4),
        "f1": round(f1, 4),
        "f2": round(f2, 4),
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "confusion_matrix": cm,
        "nb_alertes": int(y_pred.sum()),
        "recall_by_fraud_type": by_type,
    }


# ---------------------------------------------------------------------------
# CLI : python -m predicare.ml.evaluate_final
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import sys

    def _cli() -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        p = argparse.ArgumentParser(description="Évaluation finale sur test – PB-07")
        p.add_argument("--features", default=FEATURES_PATH)
        p.add_argument("--labels", default=LABELS_PATH)
        p.add_argument("--factures", default=FACTURES_PATH)
        p.add_argument("--models-dir", default=str(MODELS_DIR))
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--test-size", type=float, default=0.2)
        args = p.parse_args()

        models_dir = Path(args.models_dir)
        tuning_path = models_dir / "tuning_results.json"
        thresh_path = models_dir / "threshold_analysis.json"
        if not tuning_path.exists() or not thresh_path.exists():
            sys.exit("Erreur : exécute d'abord le tuning et l'analyse de seuil.")

        tuning_data = json.loads(tuning_path.read_text())
        thresh_data = json.loads(thresh_path.read_text())

        # Chargement et split
        X, y, meta = load_dataset(args.features, args.labels, args.factures)
        X_tr, X_te, y_tr, y_te = split_no_leakage(X, y, meta, test_size=args.test_size)
        check_no_leakage(X_tr)
        check_no_leakage(X_te)

        # Nettoyage des NaN identique
        X_tr_clean, X_te_clean, _ = _drop_high_nan(X_tr, X_te)
        meta_te = meta.set_index("facture_id").loc[X_te_clean.index]
        types_fraude_te = (
            meta_te["type_fraude"].to_numpy()
            if "type_fraude" in meta_te.columns
            else np.array(["INCONNU"] * len(X_te_clean))
        )

        final_report: dict[str, Any] = {}

        # 1. Baseline LR
        pipe_lr = make_pipeline("lr", seed=args.seed)
        pipe_lr.fit(X_tr_clean, y_tr)
        final_report["baseline_lr"] = evaluate_model_on_test(
            pipe_lr, X_te_clean, y_te, threshold=0.50, types_fraude=types_fraude_te, seed=args.seed
        )

        # 2. Baseline RF
        pipe_rf = make_pipeline("rf", seed=args.seed)
        pipe_rf.fit(X_tr_clean, y_tr)
        final_report["baseline_rf"] = evaluate_model_on_test(
            pipe_rf, X_te_clean, y_te, threshold=0.50, types_fraude=types_fraude_te, seed=args.seed
        )

        # 3. XGBoost au seuil optimal (0.30)
        xgb_params = tuning_data["xgb"]["best_params"]
        model_xgb = train_tuned_model("xgb", xgb_params, X_tr_clean, y_tr, seed=args.seed)
        seuil_xgb = thresh_data["xgb"]["optimal"]["seuil_optimal"]
        final_report["xgboost_optimal"] = evaluate_model_on_test(
            model_xgb,
            X_te_clean,
            y_te,
            threshold=seuil_xgb,
            types_fraude=types_fraude_te,
            seed=args.seed,
        )

        # 4. LightGBM au seuil optimal (0.05)
        lgbm_params = tuning_data["lgbm"]["best_params"]
        model_lgbm = train_tuned_model("lgbm", lgbm_params, X_tr_clean, y_tr, seed=args.seed)
        seuil_lgbm = thresh_data["lgbm"]["optimal"]["seuil_optimal"]
        final_report["lightgbm_optimal"] = evaluate_model_on_test(
            model_lgbm,
            X_te_clean,
            y_te,
            threshold=seuil_lgbm,
            types_fraude=types_fraude_te,
            seed=args.seed,
        )

        # Affichage comparatif formaté
        print("\n" + "=" * 80)
        print(
            f"TABLEAU FINAL COMPARATIF SUR LE JEU DE TEST (N = {len(y_te)} factures | {int(y_te.sum())} fraudes)"
        )
        print("=" * 80)
        header = f"{'Modèle':<18} | {'Seuil':<5} | {'Recall':<7} | {'Précision':<9} | {'F1':<6} | {'F2':<6} | {'PR-AUC':<6} | {'ROC-AUC':<7} | {'IC 95% Recall'}"
        print(header)
        print("-" * len(header))

        for name, m in final_report.items():
            ic_str = f"[{m['recall_ci_95'][0]:.2f}, {m['recall_ci_95'][1]:.2f}]"
            print(
                f"{name:<18} | {m['seuil_applique']:<5.2f} | {m['recall']:<7.3f} | {m['precision']:<9.3f} | "
                f"{m['f1']:<6.3f} | {m['f2']:<6.3f} | {m['pr_auc']:<6.3f} | {m['roc_auc']:<7.3f} | {ic_str}"
            )

        print("\n--- Décomposition Recall XGBoost optimal par type de fraude ---")
        for ftype, d in final_report["xgboost_optimal"]["recall_by_fraud_type"].items():
            print(
                f"  {ftype:<28} : {d['detectes']}/{d['total_cas']} détectés (Recall = {d['recall']:.2f})"
            )

        out_path = models_dir / "final_comparison_report.json"
        out_path.write_text(json.dumps(final_report, indent=2, ensure_ascii=False))
        logger.info("Rapport comparatif final enregistré dans %s", out_path)

    _cli()
