"""Tests de conformité contrat d'interface et compatibilité SHAP (PB-07)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from xgboost import XGBClassifier

from predicare.api.schemas import AdminModelsResponse, ModelVersion
from predicare.ml.registry import (
    CHAMPION_VERSION_ID,
    export_champion_model,
    register_model_version,
)


def test_export_champion_model_et_schemas_contrat(tmp_path):
    """Vérifie que models_metadata.json respecte rigoureusement le schéma AdminModelsResponse."""
    # Création des artefacts minimaux dans tmp_path
    tuning_file = tmp_path / "tuning_results.json"
    report_file = tmp_path / "final_comparison_report.json"
    tuning_file.write_text(
        json.dumps(
            {
                "xgb": {
                    "best_params": {
                        "max_depth": 3,
                        "learning_rate": 0.1,
                        "n_estimators": 10,
                        "scale_pos_weight": 2.0,
                    }
                }
            }
        )
    )
    report_file.write_text(
        json.dumps(
            {
                "xgboost_optimal": {"recall": 0.80, "precision": 0.20, "f1": 0.32},
                "baseline_lr": {"recall": 0.43, "precision": 0.60, "f1": 0.50},
            }
        )
    )

    # Données synthétiques
    feat_path = tmp_path / "features.csv"
    lbl_path = tmp_path / "labels.csv"
    fac_path = tmp_path / "factures.csv"

    pd.DataFrame(
        {"f_1": [1.0] * 20, "f_2": [2.0] * 20},
        index=pd.Index([f"F{i}" for i in range(20)], name="facture_id"),
    ).to_csv(feat_path)
    pd.DataFrame(
        {
            "facture_id": [f"F{i}" for i in range(20)],
            "est_fraude": [0] * 18 + [1] * 2,
            "est_valide": [1] * 20,
        }
    ).to_csv(lbl_path, index=False)
    pd.DataFrame(
        {
            "facture_id": [f"F{i}" for i in range(20)],
            "assure_id": [f"A{i % 4}" for i in range(20)],
            "date_soin": ["2025-01-01"] * 20,
        }
    ).to_csv(fac_path, index=False)

    model_p, meta_p = export_champion_model(
        models_dir=tmp_path,
        features_path=str(feat_path),
        labels_path=str(lbl_path),
        factures_path=str(fac_path),
    )

    assert model_p.exists()
    assert meta_p.exists()

    # Validation directe par le validateur Pydantic de l'API
    parsed = AdminModelsResponse.model_validate_json(meta_p.read_text())
    assert parsed.active_version == CHAMPION_VERSION_ID
    assert len(parsed.available_models) == 2
    assert parsed.available_models[0].statut == "ACTIVE"


def test_champion_model_shap_et_scores():
    """Vérifie la compatibilité SHAP TreeExplainer et l'intervalle des probabilités."""
    model_path = Path("models") / f"fraud_xgb_{CHAMPION_VERSION_ID}.joblib"
    if not model_path.exists():
        # Fallback pour exécution hors présence de fichier disque

        model = XGBClassifier(max_depth=3, n_estimators=10)
        X = pd.DataFrame(np.random.normal(0, 1, (20, 5)), columns=[f"f_{i}" for i in range(5)])
        y = pd.Series([0] * 18 + [1] * 2)
        model.fit(X, y)
    else:
        model = joblib.load(model_path)
        feature_names = json.loads(Path("models/feature_names.json").read_text())
        X = pd.DataFrame(np.random.normal(0, 1, (10, len(feature_names))), columns=feature_names)

    # 1. Scores bornés dans [0, 1]
    probs = model.predict_proba(X)[:, 1]
    assert np.all((probs >= 0.0) & (probs <= 1.0))

    # 2. Compatibilité SHAP TreeExplainer (exigence stricte pour /claims/{id}/prediction)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(X)
    assert shap_values.values.shape == X.shape


def test_register_model_version_standby(tmp_path):
    """Vérifie que l'enregistrement d'une nouvelle version en STANDBY n'écrase pas l'active."""
    meta_p = tmp_path / "models_metadata.json"
    init_meta = AdminModelsResponse(
        active_version="v1.0.0-xgb",
        available_models=[
            ModelVersion(
                version_id="v1.0.0-xgb",
                type="XGBoost",
                recall_test=0.286,
                precision_test=0.333,
                f1_score=0.308,
                date_entrainement=datetime.now(UTC).date(),
                statut="ACTIVE",
            )
        ],
    )
    meta_p.write_text(json.dumps(init_meta.model_dump(mode="json")))
    clf = XGBClassifier(n_estimators=5, max_depth=2)
    X = pd.DataFrame({"f1": [1.0, 2.0], "f2": [3.0, 4.0]})
    y = pd.Series([0, 1])
    clf.fit(X, y)
    model_p, meta_res = register_model_version(
        version_id="v1.1.0-xgb",
        model=clf,
        recall_test=0.4286,
        precision_test=0.4286,
        f1_score=0.4286,
        make_active=False,
        models_dir=tmp_path,
    )
    assert model_p.exists()
    assert model_p.name == "fraud_xgb_v1.1.0-xgb.joblib"
    parsed = AdminModelsResponse.model_validate_json(meta_res.read_text())
    assert parsed.active_version == "v1.0.0-xgb"
    assert len(parsed.available_models) == 2
    v11 = [m for m in parsed.available_models if m.version_id == "v1.1.0-xgb"][0]
    assert v11.statut == "STANDBY"
    assert v11.recall_test == 0.4286
def test_unit_vs_batch_inference_parity():
    """Vérifie que l'inférence unitaire (1 facture) est strictement identique à l'inférence batch."""
    clf = XGBClassifier(n_estimators=10, max_depth=3, random_state=42)
    X = pd.DataFrame(
        np.random.normal(0, 1, (10, 4)),
        columns=[f"feat_{i}" for i in range(4)],
    )
    y = pd.Series([0] * 8 + [1] * 2)
    clf.fit(X, y)
    prob_batch = clf.predict_proba(X)[:, 1]
    for i in range(len(X)):
        row_df = X.iloc[[i]]
        prob_unit = clf.predict_proba(row_df)[0, 1]
        assert abs(prob_batch[i] - prob_unit) < 1e-6
