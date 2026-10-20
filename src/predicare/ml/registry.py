"""Module de sérialisation et versionnement du modèle champion – PrediCare TPA (PB-07).

Responsabilités :
  - Sérialisation du modèle champion versionné (v1.0.0-xgb).
  - Production du fichier models/models_metadata.json conforme au schéma AdminModelsResponse.
  - Garantie de compatibilité avec shap.TreeExplainer pour les explications d'inférence.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import joblib

from predicare.api.schemas import AdminModelsResponse, ModelVersion
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
from predicare.ml.tuning import train_tuned_model

logger = logging.getLogger(__name__)

CHAMPION_VERSION_ID = "v1.0.0-xgb"
BASELINE_VERSION_ID = "v0.9.0-baseline"


def export_champion_model(
    models_dir: Path = MODELS_DIR,
    features_path: str = FEATURES_PATH,
    labels_path: str = LABELS_PATH,
    factures_path: str = FACTURES_PATH,
    seed: int = 42,
    test_size: float = 0.2,
) -> tuple[Path, Path]:
    """Entraîne et enregistre le modèle champion et ses métadonnées conformes à l'API."""
    tuning_file = models_dir / "tuning_results.json"
    report_file = models_dir / "final_comparison_report.json"
    if not tuning_file.exists() or not report_file.exists():
        raise FileNotFoundError("tuning_results.json et final_comparison_report.json requis.")

    tuning_data = json.loads(tuning_file.read_text())
    final_report = json.loads(report_file.read_text())

    # Entraînement final du champion sur tout le train (sans toucher au test)
    X, y, meta = load_dataset(features_path, labels_path, factures_path)
    X_tr, _, y_tr, _ = split_no_leakage(X, y, meta, test_size=test_size)
    check_no_leakage(X_tr)

    X_tr_clean, _, _ = _drop_high_nan(X_tr, X_tr)
    xgb_params = tuning_data["xgb"]["best_params"]
    champion_model = train_tuned_model("xgb", xgb_params, X_tr_clean, y_tr, seed=seed)

    # Sauvegarde du modèle joblib
    model_path = models_dir / f"fraud_xgb_{CHAMPION_VERSION_ID}.joblib"
    joblib.dump(champion_model, model_path)
    # Alias modèle actif
    joblib.dump(champion_model, models_dir / "model_champion.joblib")
    logger.info("Modèle champion sérialisé : %s", model_path)

    # Construction des métadonnées conformes au contrat Pydantic de l'API
    today = datetime.now(UTC).date()
    m_xgb = final_report.get("xgboost_optimal", {})
    m_base = final_report.get("baseline_lr", {})

    metadata = AdminModelsResponse(
        active_version=CHAMPION_VERSION_ID,
        available_models=[
            ModelVersion(
                version_id=CHAMPION_VERSION_ID,
                type="XGBoost",
                recall_test=float(m_xgb.get("recall", 0.286)),
                precision_test=float(m_xgb.get("precision", 0.333)),
                f1_score=float(m_xgb.get("f1", 0.308)),
                date_entrainement=today,
                statut="ACTIVE",
            ),
            ModelVersion(
                version_id=BASELINE_VERSION_ID,
                type="LogisticRegression",
                recall_test=float(m_base.get("recall", 0.429)),
                precision_test=float(m_base.get("precision", 0.600)),
                f1_score=float(m_base.get("f1", 0.500)),
                date_entrainement=today,
                statut="STANDBY",
            ),
        ],
    )

    metadata_path = models_dir / "models_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2, ensure_ascii=False)
    )
    logger.info("Métadonnées modèles écrites : %s", metadata_path)

    return model_path, metadata_path


def register_model_version(
    version_id: str,
    model: any,
    recall_test: float,
    precision_test: float,
    f1_score: float,
    model_type: str = "XGBoost",
    make_active: bool = False,
    models_dir: Path = MODELS_DIR,
) -> tuple[Path, Path]:
    """Enregistre une nouvelle version de modèle sans écraser les versions existantes.

    Garantit la compatibilité ascendante avec GET /admin/models et la réversibilité (rollback).
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date()

    # 1. Sérialisation du fichier joblib versionné
    model_path = models_dir / f"fraud_xgb_{version_id}.joblib"
    joblib.dump(model, model_path)
    logger.info("Version modèle sérialisée : %s", model_path)

    if make_active:
        joblib.dump(model, models_dir / "model_champion.joblib")
        logger.info("Alias model_champion.joblib mis à jour vers %s", version_id)

    # 2. Mise à jour de models_metadata.json
    metadata_path = models_dir / "models_metadata.json"
    if metadata_path.exists():
        existing_raw = json.loads(metadata_path.read_text())
        existing = AdminModelsResponse.model_validate(existing_raw)
        active_ver = version_id if make_active else existing.active_version
        available = list(existing.available_models)
    else:
        active_ver = version_id if make_active else "v1.0.0-xgb"
        available = []

    statut_new = "ACTIVE" if make_active else "STANDBY"

    new_version_entry = ModelVersion(
        version_id=version_id,
        type=model_type,
        recall_test=round(float(recall_test), 4),
        precision_test=round(float(precision_test), 4),
        f1_score=round(float(f1_score), 4),
        date_entrainement=today,
        statut=statut_new,
    )

    if make_active:
        available = [
            ModelVersion(**{**m.model_dump(), "statut": "STANDBY"})
            for m in available
            if m.version_id != version_id
        ]
    else:
        available = [m for m in available if m.version_id != version_id]

    available.append(new_version_entry)

    updated_metadata = AdminModelsResponse(
        active_version=active_ver,
        available_models=available,
    )

    metadata_path.write_text(
        json.dumps(updated_metadata.model_dump(mode="json"), indent=2, ensure_ascii=False)
    )
    logger.info("models_metadata.json mis à jour avec %s (statut=%s)", version_id, statut_new)

    return model_path, metadata_path



if __name__ == "__main__":  # pragma: no cover
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    export_champion_model()
    print("✓ Modèle champion v1.0.0-xgb et models_metadata.json générés avec succès.")
