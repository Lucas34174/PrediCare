"""Tests unitaires pour l'analyse des faux négatifs – PrediCare TPA (PB-10)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from predicare.ml.error_analysis import (
    compute_detail_fraude_breakdown,
    compute_fraud_type_breakdown,
    compute_transversal_analysis,
    explain_fn_with_shap,
    extract_error_cases,
)


@pytest.fixture
def mock_eval_data() -> pd.DataFrame:
    meta = pd.DataFrame(
        {
            "facture_id": ["F1", "F2", "F3", "F4", "F5"],
            "assure_id": ["A1", "A2", "A3", "A4", "A5"],
            "date_soin": ["2026-01-01"] * 5,
        }
    )
    y_true = np.array([1, 1, 0, 0, 1])
    y_prob = np.array([0.85, 0.15, 0.10, 0.40, 0.20])
    threshold = 0.30

    factures = pd.DataFrame(
        {
            "facture_id": ["F1", "F2", "F3", "F4", "F5"],
            "montant_total": [10000, 25000, 5000, 8000, 50000],
            "type_facture": ["CONSULTATION", "PHARMACIE", "CONSULTATION", "PHARMACIE", "PHARMACIE"],
            "prestataire_id": ["P1", "P2", "P1", "P3", "P2"],
            "contrat_id": ["C1", "C2", "C1", "C3", "C2"],
        }
    )

    labels = pd.DataFrame(
        {
            "facture_id": ["F1", "F2", "F3", "F4", "F5"],
            "type_fraude": ["SURFACTURATION", "DOUBLON", None, None, "DOUBLON"],
            "detail_fraude": ["PRIX_ELEVE", "IDENTIQUE", None, None, "IDENTIQUE"],
        }
    )

    return extract_error_cases(
        y_true=y_true,
        y_prob=y_prob,
        threshold=threshold,
        meta=meta,
        factures=factures,
        labels=labels,
    )


def test_extract_error_cases(mock_eval_data: pd.DataFrame) -> None:
    df = mock_eval_data
    assert len(df) == 5
    assert set(df["statut_prediction"]) == {"TP", "FN", "TN", "FP"}
    # F1 : y_true=1, prob=0.85 >= 0.30 -> TP
    assert df.loc[df["facture_id"] == "F1", "statut_prediction"].iloc[0] == "TP"
    # F2 : y_true=1, prob=0.15 < 0.30 -> FN
    assert df.loc[df["facture_id"] == "F2", "statut_prediction"].iloc[0] == "FN"
    # F3 : y_true=0, prob=0.10 < 0.30 -> TN
    assert df.loc[df["facture_id"] == "F3", "statut_prediction"].iloc[0] == "TN"
    # F4 : y_true=0, prob=0.40 >= 0.30 -> FP
    assert df.loc[df["facture_id"] == "F4", "statut_prediction"].iloc[0] == "FP"
    # F5 : y_true=1, prob=0.20 < 0.30 -> FN
    assert df.loc[df["facture_id"] == "F5", "statut_prediction"].iloc[0] == "FN"


def test_compute_fraud_type_breakdown(mock_eval_data: pd.DataFrame) -> None:
    breakdown = compute_fraud_type_breakdown(mock_eval_data)
    assert len(breakdown) == 2
    # Tri par recall croissant : DOUBLON (recall 0.0) doit être premier
    first = breakdown[0]
    assert first["type_fraude"] == "DOUBLON"
    assert first["total_fraudes"] == 2
    assert first["detectes_tp"] == 0
    assert first["manques_fn"] == 2
    assert first["recall"] == 0.0
    assert first["montant_manque_ariary"] == 75000  # 25000 + 50000


def test_compute_detail_fraude_breakdown(mock_eval_data: pd.DataFrame) -> None:
    res = compute_detail_fraude_breakdown(mock_eval_data, weak_types=["DOUBLON"])
    assert len(res) == 1
    assert res[0]["detail_fraude"] == "IDENTIQUE"
    assert res[0]["nb_manques"] == 2
    assert res[0]["montant_manque_ariary"] == 75000


def test_compute_transversal_analysis(mock_eval_data: pd.DataFrame) -> None:
    trans = compute_transversal_analysis(mock_eval_data)
    assert trans["nb_fn"] == 2
    assert trans["nb_tp"] == 1
    assert trans["montants_fn"]["total_ariary"] == 75000
    assert trans["repartition_type_facture_fn"]["PHARMACIE"] == 2


def test_explain_fn_with_shap() -> None:
    from sklearn.ensemble import RandomForestClassifier

    X = pd.DataFrame(
        {
            "f_a": [1.0, 2.0, 3.0, 4.0, 5.0],
            "f_b": [10.0, 20.0, 30.0, 40.0, 50.0],
        },
        index=["F1", "F2", "F3", "F4", "F5"],
    )
    y = np.array([0, 1, 0, 1, 1])
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X, y)

    X_fn = X.loc[["F2", "F5"]]
    exps = explain_fn_with_shap(clf, X_fn, top_k=2)
    assert len(exps) == 2
    assert exps[0]["facture_id"] == "F2"
    assert "top_features_negatives" in exps[0]
    assert "top_features_positives" in exps[0]
