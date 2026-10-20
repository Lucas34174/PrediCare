"""Module d'analyse approfondie des faux négatifs – PrediCare TPA (PB-10).

Responsabilités :
  - Extraction et caractérisation des faux négatifs (FN) sur le jeu de test.
  - Décomposition par type_fraude et detail_fraude avec montants financiers en Ariary.
  - Analyse transverse (type de facture, prestataires suspects, formule contrat).
  - Explicabilité locale SHAP (top features réduisant le score de risque).
  - Production d'un rapport structuré pour orienter les améliorations de features.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import shap

logger = logging.getLogger(__name__)


def extract_error_cases(
    y_true: pd.Series | np.ndarray,
    y_prob: np.ndarray,
    threshold: float,
    meta: pd.DataFrame,
    factures: pd.DataFrame | None = None,
    labels: pd.DataFrame | None = None,
    prestataires: pd.DataFrame | None = None,
    labels_prest: pd.DataFrame | None = None,
    contrats: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Construit un DataFrame enrichi associant prédictions, métadonnées et contexte métier.

    Garantit l'absence de colonnes de fuite dans l'analyse.
    """
    y_arr = np.asarray(y_true).astype(int)
    prob_arr = np.asarray(y_prob, dtype=float)
    y_pred = (prob_arr >= threshold).astype(int)

    df = meta.copy()
    df["y_true"] = y_arr
    df["score_fraude"] = np.round(prob_arr, 4)
    df["y_pred"] = y_pred

    # Qualification du statut de prédiction
    conditions = [
        (df["y_true"] == 1) & (df["y_pred"] == 1),
        (df["y_true"] == 0) & (df["y_pred"] == 1),
        (df["y_true"] == 1) & (df["y_pred"] == 0),
        (df["y_true"] == 0) & (df["y_pred"] == 0),
    ]
    statuts = ["TP", "FP", "FN", "TN"]
    df["statut_prediction"] = np.select(conditions, statuts, default="INCONNU")

    # Jointures contextuelles si fournies
    if factures is not None:
        cols_fac = [
            c
            for c in [
                "facture_id",
                "numero_facture",
                "prestataire_id",
                "contrat_id",
                "type_facture",
                "montant_total",
            ]
            if c in factures.columns
        ]
        df = df.merge(factures[cols_fac], on="facture_id", how="left")

    if labels is not None:
        cols_lbl = [
            c for c in ["facture_id", "type_fraude", "detail_fraude"] if c in labels.columns
        ]
        # Évite le dédoublement de type_fraude si déjà dans meta
        df = df.drop(columns=[c for c in cols_lbl if c in df.columns and c != "facture_id"])
        df = df.merge(labels[cols_lbl], on="facture_id", how="left")

    if prestataires is not None and "prestataire_id" in df.columns:
        cols_prest = [
            c
            for c in ["prestataire_id", "nom", "type_prestataire", "conventionne"]
            if c in prestataires.columns
        ]
        df = df.merge(prestataires[cols_prest], on="prestataire_id", how="left")

    if labels_prest is not None and "prestataire_id" in df.columns:
        cols_lp = [c for c in ["prestataire_id", "est_suspect"] if c in labels_prest.columns]
        df = df.merge(labels_prest[cols_lp], on="prestataire_id", how="left")
        if "est_suspect" in df.columns:
            df["est_suspect"] = df["est_suspect"].fillna(0).astype(int)

    if contrats is not None and "contrat_id" in df.columns:
        cols_ctr = [c for c in ["contrat_id", "formule"] if c in contrats.columns]
        df = df.merge(contrats[cols_ctr], on="contrat_id", how="left")

    return df


def compute_fraud_type_breakdown(df_eval: pd.DataFrame) -> list[dict[str, Any]]:
    """Génère le tableau par type_fraude trié par rappel croissant puis montant manqué."""
    df_frauds = df_eval[df_eval["y_true"] == 1].copy()
    if df_frauds.empty:
        return []

    if "type_fraude" not in df_frauds.columns:
        df_frauds["type_fraude"] = "INCONNU"
    else:
        df_frauds["type_fraude"] = df_frauds["type_fraude"].fillna("NON_DEFINI")

    results: list[dict[str, Any]] = []
    for ftype, group in df_frauds.groupby("type_fraude"):
        total = len(group)
        tp_mask = group["statut_prediction"] == "TP"
        fn_mask = group["statut_prediction"] == "FN"

        detectes = int(tp_mask.sum())
        manques = int(fn_mask.sum())
        recall = round(float(detectes / total), 4) if total > 0 else 0.0

        fn_group = group[fn_mask]
        scores_fn = fn_group["score_fraude"].tolist()
        score_moyen_fn = round(float(np.mean(scores_fn)), 4) if scores_fn else 0.0
        score_med_fn = round(float(np.median(scores_fn)), 4) if scores_fn else 0.0

        montant_total = int(group["montant_total"].sum()) if "montant_total" in group else 0
        montant_fn = int(fn_group["montant_total"].sum()) if "montant_total" in fn_group else 0

        results.append(
            {
                "type_fraude": str(ftype),
                "total_fraudes": total,
                "detectes_tp": detectes,
                "manques_fn": manques,
                "recall": recall,
                "score_moyen_fn": score_moyen_fn,
                "score_median_fn": score_med_fn,
                "montant_total_ariary": montant_total,
                "montant_manque_ariary": montant_fn,
            }
        )

    # Tri par rappel croissant, puis par montant manqué décroissant
    results.sort(key=lambda x: (x["recall"], -x["montant_manque_ariary"]))
    return results


def compute_detail_fraude_breakdown(
    df_eval: pd.DataFrame, weak_types: list[str] | None = None
) -> list[dict[str, Any]]:
    """Décompose les faux négatifs par detail_fraude pour les types les plus faibles."""
    df_fn = df_eval[df_eval["statut_prediction"] == "FN"].copy()
    if df_fn.empty:
        return []

    if weak_types:
        df_fn = df_fn[df_fn["type_fraude"].isin(weak_types)]

    if "detail_fraude" not in df_fn.columns:
        df_fn["detail_fraude"] = "NON_RENSEIGNE"
    else:
        df_fn["detail_fraude"] = df_fn["detail_fraude"].fillna("NON_RENSEIGNE")

    results: list[dict[str, Any]] = []
    for (ftype, fdetail), grp in df_fn.groupby(["type_fraude", "detail_fraude"]):
        cnt = len(grp)
        montant = int(grp["montant_total"].sum()) if "montant_total" in grp else 0
        score_moy = round(float(grp["score_fraude"].mean()), 4)
        results.append(
            {
                "type_fraude": str(ftype),
                "detail_fraude": str(fdetail),
                "nb_manques": cnt,
                "montant_manque_ariary": montant,
                "score_moyen": score_moy,
            }
        )
    results.sort(key=lambda x: -x["montant_manque_ariary"])
    return results


def compute_transversal_analysis(df_eval: pd.DataFrame) -> dict[str, Any]:
    """Analyse transverse des FN vs TP (montants, factures, prestataires, contrats)."""
    df_fn = df_eval[df_eval["statut_prediction"] == "FN"]
    df_tp = df_eval[df_eval["statut_prediction"] == "TP"]

    res: dict[str, Any] = {
        "nb_fn": len(df_fn),
        "nb_tp": len(df_tp),
        "scores_fn": {
            "min": round(float(df_fn["score_fraude"].min()), 4) if not df_fn.empty else 0.0,
            "mean": round(float(df_fn["score_fraude"].mean()), 4) if not df_fn.empty else 0.0,
            "median": round(float(df_fn["score_fraude"].median()), 4) if not df_fn.empty else 0.0,
            "max": round(float(df_fn["score_fraude"].max()), 4) if not df_fn.empty else 0.0,
        },
        "scores_tp": {
            "min": round(float(df_tp["score_fraude"].min()), 4) if not df_tp.empty else 0.0,
            "mean": round(float(df_tp["score_fraude"].mean()), 4) if not df_tp.empty else 0.0,
            "median": round(float(df_tp["score_fraude"].median()), 4) if not df_tp.empty else 0.0,
            "max": round(float(df_tp["score_fraude"].max()), 4) if not df_tp.empty else 0.0,
        },
    }

    if "montant_total" in df_eval.columns:
        res["montants_fn"] = {
            "total_ariary": int(df_fn["montant_total"].sum()) if not df_fn.empty else 0,
            "mean_ariary": int(df_fn["montant_total"].mean()) if not df_fn.empty else 0,
            "median_ariary": int(df_fn["montant_total"].median()) if not df_fn.empty else 0,
        }

    if "type_facture" in df_fn.columns:
        res["repartition_type_facture_fn"] = df_fn["type_facture"].value_counts().to_dict()

    if "est_suspect" in df_fn.columns:
        res["prestataires_suspects_fn"] = {
            "nb_suspects": int((df_fn["est_suspect"] == 1).sum()),
            "nb_non_suspects": int((df_fn["est_suspect"] == 0).sum()),
        }

    if "formule" in df_fn.columns:
        res["repartition_formule_fn"] = df_fn["formule"].value_counts().to_dict()

    return res


def explain_fn_with_shap(
    model: Any,
    X_fn: pd.DataFrame,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Extrait les features SHAP qui tirent le score vers le bas pour chaque FN."""
    if X_fn.empty:
        return []

    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X_fn)
    if isinstance(sv, list):
        sv = sv[1]

    # Gestion robuste 2D vs 3D (ex: RandomForest retourne shape (N, features, classes))
    sv_arr = np.asarray(sv)
    if sv_arr.ndim == 3 and sv_arr.shape[-1] >= 2:
        sv_arr = sv_arr[:, :, 1]
    elif sv_arr.ndim == 3 and sv_arr.shape[-1] == 1:
        sv_arr = sv_arr[:, :, 0]

    feature_cols = list(X_fn.columns)
    results: list[dict[str, Any]] = []

    for idx, (facture_id, row) in enumerate(X_fn.iterrows()):
        shap_row = sv_arr[idx]
        contributions = [
            {"feature": col, "shap_value": round(float(shap_row[j]), 4), "valeur": row[col]}
            for j, col in enumerate(feature_cols)
        ]
        # Features négatives (tirent le score vers le bas)
        neg_contribs = sorted(
            [c for c in contributions if c["shap_value"] < 0],
            key=lambda x: x["shap_value"],
        )[:top_k]

        # Features positives (tirent le score vers le haut)
        pos_contribs = sorted(
            [c for c in contributions if c["shap_value"] > 0],
            key=lambda x: -x["shap_value"],
        )[:top_k]

        results.append(
            {
                "facture_id": str(facture_id),
                "top_features_negatives": neg_contribs,
                "top_features_positives": pos_contribs,
            }
        )

    return results
