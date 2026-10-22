"""Router pour les prédictions globales – /predictions/latest."""

import json
from typing import Any

from fastapi import APIRouter
from sqlalchemy import create_engine, text

from predicare.core.config import database_url

router = APIRouter(prefix="/predictions", tags=["Prédictions"])


@router.get("/latest")
def get_latest_prediction() -> dict[str, Any] | None:
    """Renvoie la dernière prédiction majeure pour le tableau de bord gestionnaire."""
    try:
        engine = create_engine(database_url())
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text("""
                    SELECT p.id, p.facture_id, p.score_fraude, p.est_anomalie,
                           p.seuil_applique, p.version_modele, p.date_prediction,
                           s.top_features
                    FROM predictions p
                    LEFT JOIN explications_shap s ON s.prediction_id = p.id
                    WHERE p.score_fraude IS NOT NULL
                    ORDER BY p.date_prediction DESC
                    LIMIT 1
                """)
                )
                .mappings()
                .first()
            )

            if not row:
                return None

            top_features_raw = row["top_features"]
            if isinstance(top_features_raw, str):
                try:
                    top_facteurs = json.loads(top_features_raw)
                except Exception:
                    top_facteurs = []
            elif isinstance(top_features_raw, list):
                top_facteurs = top_features_raw
            else:
                top_facteurs = []

            return {
                "claim_id": row["facture_id"],
                "fraud_probability": float(row["score_fraude"]),
                "model_version": str(row["version_modele"] or "v1.0.0-xgb"),
                "explanation": {
                    "top_factors": [
                        {
                            "feature": f.get("feature", ""),
                            "shap_value": float(f.get("impact_shap", 0.0)),
                            "description": f.get("description", ""),
                        }
                        for f in top_facteurs
                    ]
                },
            }
    except Exception:
        return None
