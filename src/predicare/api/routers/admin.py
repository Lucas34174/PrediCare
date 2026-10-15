"""Router administration – /admin."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from ..schemas import (
    AdminAuditResponse,
    AdminConfig,
    AdminConfigUpdateRequest,
    AdminMetricsResponse,
    AdminModelsResponse,
    ApiMetrics,
    AuditEntry,
    MlDriftInfo,
    ModelActivateResponse,
    ModelVersion,
    Role,
)

router = APIRouter(prefix="/admin", tags=["Administration"])

_NOW = datetime(2026, 10, 15, 11, 0, tzinfo=UTC)

_CONFIG = AdminConfig(
    fraud_score_threshold=0.80,
    n8n_webhook_url="http://n8n:5678/webhook/fraud-alert",
    semantic_cache_enabled=True,
    semantic_cache_threshold=0.85,
)

_KNOWN_VERSIONS = {"v1.0.0-xgb", "v0.9.0-baseline"}


@router.get("/config", response_model=AdminConfig)
def get_config() -> AdminConfig:
    """Paramètres opérationnels courants (mock)."""
    return _CONFIG


@router.put("/config", response_model=AdminConfig)
def update_config(body: AdminConfigUpdateRequest) -> AdminConfig:
    """Mise à jour des paramètres à chaud (mock)."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = _NOW
    return _CONFIG.model_copy(update=updates)


@router.get("/models", response_model=AdminModelsResponse)
def list_models() -> AdminModelsResponse:
    """Liste des versions de modèles disponibles (mock)."""
    return AdminModelsResponse(
        active_version="v1.0.0-xgb",
        available_models=[
            ModelVersion(
                version_id="v1.0.0-xgb",
                type="XGBoost",
                recall_test=0.912,
                precision_test=0.843,
                f1_score=0.876,
                date_entrainement=date(2026, 10, 14),
                statut="ACTIVE",
            ),
            ModelVersion(
                version_id="v0.9.0-baseline",
                type="RandomForest",
                recall_test=0.835,
                precision_test=0.791,
                f1_score=0.812,
                date_entrainement=date(2026, 10, 13),
                statut="STANDBY",
            ),
        ],
    )


@router.post(
    "/models/{version_id}/activate",
    response_model=ModelActivateResponse,
    responses={404: {"description": "Version de modèle inconnue."}},
)
def activate_model(version_id: str) -> ModelActivateResponse:
    """Bascule vers une version de modèle (mock)."""
    if version_id not in _KNOWN_VERSIONS:
        raise HTTPException(status_code=404, detail=f"Version {version_id} inconnue.")
    return ModelActivateResponse(
        message="Bascule effectuée avec succès.",
        active_version=version_id,
        switched_at=_NOW,
    )


@router.get("/metrics", response_model=AdminMetricsResponse)
def get_metrics() -> AdminMetricsResponse:
    """Métriques API et dérive du modèle (mock)."""
    return AdminMetricsResponse(
        api_metrics=ApiMetrics(
            requests_total=45120,
            error_rate_5xx=0.0012,
            p95_latency_ms=142.5,
        ),
        ml_drift_monitoring=MlDriftInfo(
            metric="PSI",
            psi_score=0.042,
            statut_derive="STABLE",
            alerte_derive=False,
            derniere_evaluation=_NOW,
        ),
    )


@router.get("/audit", response_model=AdminAuditResponse)
def get_audit(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    type_action: str | None = None,
) -> AdminAuditResponse:
    """Journaux d'audit (mock)."""
    return AdminAuditResponse(
        total=1,
        items=[
            AuditEntry(
                id=154,
                type_action=type_action or "DECISION_FRAUDE",
                utilisateur_id="USR-0012",
                role_utilisateur=Role.GESTIONNAIRE,
                ressource_type="facture",
                ressource_id="FAC-00005637",
                details={"decision": "REJETE", "motif": "Dépassement tarifaire"},
                ip_source="172.18.0.1",
                date_action=_NOW,
            )
        ],
    )
