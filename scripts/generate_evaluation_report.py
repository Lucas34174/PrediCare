"""Script de génération du rapport d'évaluation et des figures – PrediCare TPA (PB-08).

Exécution :
    PYTHONPATH=src python scripts/generate_evaluation_report.py
    ou via 'make evaluate'
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import joblib
import matplotlib

# Backend non-interactif pour WSL / CI
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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
from predicare.ml.evaluation import (
    ALL_FRAUD_TYPES,
    compute_metrics_by_fraud_type,
    evaluate_global,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("evaluate_report")

DOCS_FIG_DIR = Path("docs/figures")


# ---------------------------------------------------------------------------
# Tracé des figures
# ---------------------------------------------------------------------------
def plot_confusion_matrices(rep: dict, out_path: Path) -> None:
    """Génère la figure des matrices de confusion (seuil 0.80 vs 0.30)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), dpi=150)

    for ax, key, title in [
        (axes[0], "metrics_seuil_production", "Seuil Contractuel (0.80)"),
        (axes[1], "metrics_seuil_optimal", "Seuil Opérationnel Optimal (0.30)"),
    ]:
        m = rep[key]
        raw = m["matrice_brute"]
        pct = m["matrice_normalisee_pct"]
        cm_data = np.array([[raw["tn"], raw["fp"]], [raw["fn"], raw["tp"]]])

        im = ax.imshow(cm_data, cmap="Blues", interpolation="nearest")
        ax.set_title(
            f"{title}\nRecall: {m['recall']:.1%} | Précision: {m['precision']:.1%}",
            fontsize=10,
            fontweight="bold",
        )
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["Non-Fraude (0)", "Fraude (1)"])
        ax.set_yticklabels(["Non-Fraude (0)", "Fraude (1)"])
        ax.set_xlabel("Prédiction Modèle")
        ax.set_ylabel("Vérité Terrain")

        for i in range(2):
            for j in range(2):
                val = cm_data[i, j]
                label_txt = f"{val}\n({pct['tn' if (i, j) == (0, 0) else 'fp' if (i, j) == (0, 1) else 'fn' if (i, j) == (1, 0) else 'tp']:.1f}%)"
                color = "white" if val > cm_data.max() / 2 else "black"
                ax.text(j, i, label_txt, ha="center", va="center", color=color, fontsize=10)

        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    plt.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    logger.info("Figure enregistrée : %s", out_path)


def plot_pr_and_roc(rep: dict, out_path: Path) -> None:
    """Génère la courbe PR avec prévalence baseline et encart ROC."""
    courbes = rep["courbes"]
    pr_pts = courbes["pr_points"]
    roc_pts = courbes["roc_points"]
    prev = courbes["prevalence_baseline"]

    fig, ax = plt.subplots(figsize=(7, 5), dpi=150)

    rec_vals = [p["recall"] for p in pr_pts]
    prec_vals = [p["precision"] for p in pr_pts]
    ax.plot(
        rec_vals,
        prec_vals,
        color="#1f77b4",
        lw=2.5,
        label=f"XGBoost (PR-AUC = {courbes['pr_auc']:.3f})",
    )
    ax.axhline(
        y=prev,
        color="crimson",
        linestyle="--",
        lw=1.5,
        label=f"Baseline Prévalence ({prev:.1%})",
    )

    ax.set_title("Courbe Précision-Rappel (Jeu de Test)", fontsize=11, fontweight="bold")
    ax.set_xlabel("Rappel (Recall)")
    ax.set_ylabel("Précision")
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlim(-0.02, 1.05)
    ax.legend(loc="upper right")
    ax.grid(True, linestyle=":", alpha=0.6)

    # Inset ROC
    ins = ax.inset_axes([0.15, 0.15, 0.35, 0.35])
    fpr_vals = [p["fpr"] for p in roc_pts]
    tpr_vals = [p["tpr"] for p in roc_pts]
    ins.plot(fpr_vals, tpr_vals, color="#2ca02c", lw=1.8)
    ins.plot([0, 1], [0, 1], "k--", lw=1)
    ins.set_title(f"ROC (AUC={courbes['roc_auc']:.2f})", fontsize=8)
    ins.set_xticks([0, 1])
    ins.set_yticks([0, 1])
    ins.tick_params(labelsize=7)

    plt.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    logger.info("Figure enregistrée : %s", out_path)


def plot_recall_by_fraud_type(types_report: dict, out_path: Path) -> None:
    """Génère le diagramme en barres horizontales du Recall par type de fraude avec IC Wilson."""
    types = list(ALL_FRAUD_TYPES)
    recalls = [types_report[t]["recall"] for t in types]
    ci_lows = [types_report[t]["recall_ic_wilson_95"][0] for t in types]
    ci_highs = [types_report[t]["recall_ic_wilson_95"][1] for t in types]
    counts = [types_report[t]["effectif_test"] for t in types]

    y_pos = np.arange(len(types))
    errors = [
        [r - low for r, low in zip(recalls, ci_lows, strict=False)],
        [high - r for r, high in zip(recalls, ci_highs, strict=False)],
    ]

    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    bars = ax.barh(
        y_pos, recalls, xerr=errors, align="center", color="#3b528b", alpha=0.85, capsize=3
    )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(types, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Rappel (Recall) au seuil 0.30")
    ax.set_xlim(-0.05, 1.15)
    ax.set_title(
        "Rappel par Type de Fraude avec Intervalles Wilson 95%", fontsize=11, fontweight="bold"
    )
    ax.grid(axis="x", linestyle=":", alpha=0.6)

    for _i, (bar, c, r) in enumerate(zip(bars, counts, recalls, strict=False)):
        annot = f"N={c} (Recall={r:.0%})" if c > 0 else "Absent (N=0)"
        color = "black" if c > 0 else "gray"
        ax.text(
            max(0.02, bar.get_width() + 0.05),
            bar.get_y() + bar.get_height() / 2,
            annot,
            va="center",
            fontsize=7.5,
            color=color,
        )

    plt.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    logger.info("Figure enregistrée : %s", out_path)


def plot_calibration_curve(rep: dict, out_path: Path) -> None:
    """Génère la courbe de fiabilité probabiliste."""
    cal = rep["calibration"]
    pts = cal["curve_points"]

    fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
    ax.plot([0, 1], [0, 1], "k--", label="Calibration parfaite", lw=1.5)

    if pts:
        p_pred = [p["prob_predite"] for p in pts]
        p_true = [p["fraction_reelle"] for p in pts]
        ax.plot(p_pred, p_true, "s-", color="#e377c2", lw=2, label="XGBoost v1.0.0")

    ax.set_title(
        f"Courbe de Fiabilité (Brier Score = {cal['brier_score']:.4f})",
        fontsize=11,
        fontweight="bold",
    )
    ax.set_xlabel("Probabilité moyenne prédite")
    ax.set_ylabel("Fraction de fraudes réelles")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(loc="upper left")
    ax.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    logger.info("Figure enregistrée : %s", out_path)


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------
def main() -> None:
    DOCS_FIG_DIR.mkdir(parents=True, exist_ok=True)
    models_dir = Path(MODELS_DIR)

    # Modèle champion
    champion_path = models_dir / "model_champion.joblib"
    if not champion_path.exists():
        champion_path = models_dir / "fraud_xgb_v1.0.0-xgb.joblib"
    if not champion_path.exists():
        sys.exit("Modèle champion introuvable dans models/. Lance make tune ou registry.")

    model = joblib.load(champion_path)

    # Chargement dataset
    X, y, meta = load_dataset(FEATURES_PATH, LABELS_PATH, FACTURES_PATH)
    X_tr, X_te, y_tr, y_te = split_no_leakage(X, y, meta, test_size=0.2)
    check_no_leakage(X_tr)
    check_no_leakage(X_te)

    _, X_te_clean, _ = _drop_high_nan(X_tr, X_te)
    meta_te = meta.set_index("facture_id").loc[X_te_clean.index]
    types_te = (
        meta_te["type_fraude"].to_numpy()
        if "type_fraude" in meta_te.columns
        else np.array(["AUCUNE"] * len(X_te_clean))
    )

    y_prob = model.predict_proba(X_te_clean)[:, 1]

    # Calcul métriques globales
    global_report = evaluate_global(y_te, y_prob, production_threshold=0.80, optimal_threshold=0.30)

    # Calcul métriques par type
    types_optimal = compute_metrics_by_fraud_type(y_te, y_prob, types_te, threshold=0.30)
    types_prod = compute_metrics_by_fraud_type(y_te, y_prob, types_te, threshold=0.80)

    full_output = {
        "global": global_report,
        "by_fraud_type_optimal_0_30": types_optimal,
        "by_fraud_type_production_0_80": types_prod,
    }

    # Sauvegarde JSON
    out_json = models_dir / "detailed_evaluation_report.json"
    out_json.write_text(json.dumps(full_output, indent=2, ensure_ascii=False))
    logger.info("Rapport d'évaluation complet sauvegardé dans %s", out_json)

    # Sauvegarde figures
    plot_confusion_matrices(global_report, DOCS_FIG_DIR / "confusion_matrix.png")
    plot_pr_and_roc(global_report, DOCS_FIG_DIR / "pr_curve.png")
    plot_recall_by_fraud_type(types_optimal, DOCS_FIG_DIR / "recall_by_fraud_type.png")
    plot_calibration_curve(global_report, DOCS_FIG_DIR / "calibration_curve.png")

    print("\n✓ Rapport et 4 figures générés avec succès dans docs/figures/ et models/.")


if __name__ == "__main__":
    main()
