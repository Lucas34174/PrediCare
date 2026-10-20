"""Script d'analyse exhaustive des faux négatifs du modèle champion – PB-10.

Exécution :
    PYTHONPATH=src python scripts/analyse_faux_negatifs.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

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
from predicare.ml.error_analysis import (
    compute_detail_fraude_breakdown,
    compute_fraud_type_breakdown,
    compute_transversal_analysis,
    explain_fn_with_shap,
    extract_error_cases,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("analyse_fn")

PRESTATAIRES_PATH = "data/processed/prestataires.csv"
LABELS_PREST_PATH = "data/processed/labels_prestataires.csv"
CONTRATS_PATH = "data/processed/contrats.csv"


def main() -> None:
    models_dir = Path(MODELS_DIR)
    champion_path = models_dir / "model_champion.joblib"
    if not champion_path.exists():
        champion_path = models_dir / "fraud_xgb_v1.0.0-xgb.joblib"

    if not champion_path.exists():
        sys.exit(f"Modèle introuvable dans {models_dir}")

    logger.info("Chargement modèle champion : %s", champion_path)
    model = joblib.load(champion_path)

    # Chargement dataset
    X, y, meta = load_dataset(FEATURES_PATH, LABELS_PATH, FACTURES_PATH)
    X_tr, X_te, y_tr, y_te = split_no_leakage(X, y, meta, test_size=0.2)
    check_no_leakage(X_tr)
    check_no_leakage(X_te)

    # Nettoyage NaN identique à l'entraînement
    _, X_te_clean, _ = _drop_high_nan(X_tr, X_te)

    # Tables contextuelles pour enrichissement
    df_fac = pd.read_csv(FACTURES_PATH)
    df_lbl = pd.read_csv(LABELS_PATH)
    df_prest = pd.read_csv(PRESTATAIRES_PATH) if Path(PRESTATAIRES_PATH).exists() else None
    df_lp = pd.read_csv(LABELS_PREST_PATH) if Path(LABELS_PREST_PATH).exists() else None
    df_ctr = pd.read_csv(CONTRATS_PATH) if Path(CONTRATS_PATH).exists() else None

    # Inférence au seuil opérationnel (0.30)
    seuil_op = 0.30
    y_prob = model.predict_proba(X_te_clean)[:, 1]

    meta_te = meta.set_index("facture_id").loc[X_te_clean.index].reset_index()
    df_eval = extract_error_cases(
        y_true=y_te,
        y_prob=y_prob,
        threshold=seuil_op,
        meta=meta_te,
        factures=df_fac,
        labels=df_lbl,
        prestataires=df_prest,
        labels_prest=df_lp,
        contrats=df_ctr,
    )

    # 1. Bilan par type de fraude
    by_type = compute_fraud_type_breakdown(df_eval)

    # 2. Bilan par détail de fraude
    weak_types = [t["type_fraude"] for t in by_type if t["recall"] < 1.0]
    by_detail = compute_detail_fraude_breakdown(df_eval, weak_types=weak_types)

    # 3. Analyse transverse
    transversal = compute_transversal_analysis(df_eval)

    # 4. SHAP sur les FN
    df_fn = df_eval[df_eval["statut_prediction"] == "FN"]
    X_fn = X_te_clean.loc[df_fn["facture_id"]]
    shap_exps = explain_fn_with_shap(model, X_fn, top_k=3)

    # Affichage terminal clair
    print("\n" + "=" * 95)
    print("ANALYSE DES FAUX NÉGATIFS (PB-10) – MODÈLE CHAMPION AU SEUIL OPTIMAL (0.30)")
    print("=" * 95)

    print("\n[TABLEAU 1 : TAUX DE RAPPEL ET PERTES PAR TYPE DE FRAUDE]")
    hdr_t = (
        f"{'Type Fraude':<24} | {'Total':<5} | {'Détectés':<8} | {'Manqués':<7} | "
        f"{'Recall':<7} | {'Score Moy FN':<12} | {'Montant Manqué (Ariary)'}"
    )
    print(hdr_t)
    print("-" * len(hdr_t))
    for t in by_type:
        print(
            f"{t['type_fraude']:<24} | {t['total_fraudes']:<5} | {t['detectes_tp']:<8} | "
            f"{t['manques_fn']:<7} | {t['recall']:<7.1%} | {t['score_moyen_fn']:<12.4f} | "
            f"{t['montant_manque_ariary']:>15,d} MGA"
        )

    print("\n[TABLEAU 2 : DÉTAIL DES FAUX NÉGATIFS INDIVIDUELS]")
    hdr_fn = (
        f"{'Facture ID':<14} | {'Type Fraude':<18} | {'Score':<6} | "
        f"{'Montant Total':<14} | {'Type Fac':<12} | {'Prestataire ID'}"
    )
    print(hdr_fn)
    print("-" * len(hdr_fn))
    for _, row in df_fn.iterrows():
        print(
            f"{row['facture_id']:<14} | {row['type_fraude']:<18} | {row['score_fraude']:<6.4f} | "
            f"{int(row.get('montant_total', 0)):>10,d} MGA | "
            f"{str(row.get('type_facture', '')): <12} | {str(row.get('prestataire_id', ''))}"
        )

    print("\n[TABLEAU 3 : ANALYSE TRANSVERSE DES FAUX NÉGATIFS]")
    print(f"  • Nombre total de FN : {transversal['nb_fn']} / {len(y_te[y_te == 1])} fraudes")
    print(
        f"  • Montant total manqué : {transversal.get('montants_fn', {}).get('total_ariary', 0):,d} MGA"
    )
    print(
        f"  • Scores FN (min/moy/max) : {transversal['scores_fn']['min']:.4f} / "
        f"{transversal['scores_fn']['mean']:.4f} / {transversal['scores_fn']['max']:.4f}"
    )
    print(
        f"  • Scores TP (min/moy/max) : {transversal['scores_tp']['min']:.4f} / "
        f"{transversal['scores_tp']['mean']:.4f} / {transversal['scores_tp']['max']:.4f}"
    )
    print(
        f"  • Répartition types factures FN : {transversal.get('repartition_type_facture_fn', {})}"
    )
    print(f"  • Répartition formules contrat FN : {transversal.get('repartition_formule_fn', {})}")

    print(
        "\n[TABLEAU 4 : EXPLICATIONS SHAP SUR LES FN (Top variables tirant le score vers le bas)]"
    )
    for item in shap_exps:
        fid = item["facture_id"]
        neg_feats = ", ".join(
            [f"{f['feature']} ({f['shap_value']:+.3f})" for f in item["top_features_negatives"]]
        )
        print(f"  • Facture {fid} : {neg_feats}")

    # Sauvegarde du rapport JSON complet
    rapport_json = models_dir / "rapport_analyse_faux_negatifs.json"
    full_report = {
        "seuil_analyse": seuil_op,
        "par_type_fraude": by_type,
        "par_detail_fraude": by_detail,
        "analyse_transverse": transversal,
        "explications_shap": shap_exps,
        "faux_negatifs_factures": df_fn[
            [
                "facture_id",
                "type_fraude",
                "detail_fraude",
                "score_fraude",
                "montant_total",
                "prestataire_id",
                "type_facture",
            ]
        ].to_dict(orient="records"),
    }
    rapport_json.write_text(json.dumps(full_report, indent=2, ensure_ascii=False))
    logger.info("Rapport complet des faux négatifs sauvegardé dans %s", rapport_json)


if __name__ == "__main__":
    main()
