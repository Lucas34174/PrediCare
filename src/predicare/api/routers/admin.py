"""Router administration – /admin."""

import logging
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from predicare.api.deps import require_roles
from predicare.core.config import model_version
from predicare.ml.config import MODELS_ROOT
from predicare.ml.registry import lister_versions, promouvoir, rollback, version_production

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
    UserInfo,
)

router = APIRouter(prefix="/admin", tags=["Administration"])
logger = logging.getLogger(__name__)

_NOW = datetime(2026, 10, 15, 11, 0, tzinfo=UTC)

_CONFIG = AdminConfig(
    fraud_score_threshold=0.80,
    n8n_webhook_url="http://n8n:5678/webhook/fraud-alert",
    semantic_cache_enabled=True,
    semantic_cache_threshold=0.85,
)


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
    """Liste les modèles réellement enregistrés, avec repli sur le catalogue historique."""
    versions = lister_versions()
    if versions:
        available = []
        for entry in versions:
            meta = entry.get("metadonnees") or {}
            metrics = meta.get("metriques_test") or meta.get("test") or {}
            created = str(entry.get("cree", ""))[:10]
            try:
                trained = date.fromisoformat(created)
            except ValueError:
                trained = date.today()
            available.append(
                ModelVersion(
                    version_id=entry["version"],
                    type=str(meta.get("modele", "XGBoost")),
                    recall_test=float(metrics.get("recall", 0.0)),
                    precision_test=float(metrics.get("precision", 0.0)),
                    f1_score=float(metrics.get("f1", 0.0)),
                    date_entrainement=trained,
                    statut={
                        "production": "ACTIVE",
                        "staging": "STANDBY",
                        "archive": "ARCHIVED",
                    }.get(str(entry.get("statut", "staging")), "STANDBY"),
                )
            )
        return AdminModelsResponse(
            active_version=version_production() or model_version(),
            available_models=available,
        )

    metadata_path = MODELS_ROOT / "models_metadata.json"
    if metadata_path.is_file():
        try:
            return AdminModelsResponse.model_validate_json(
                metadata_path.read_text(encoding="utf-8")
            )
        except (ValueError, OSError):
            logger.exception("Catalogue historique des modèles invalide : %s", metadata_path)
    return AdminModelsResponse(active_version=model_version(), available_models=[])


@router.post(
    "/models/{version_id}/activate",
    response_model=ModelActivateResponse,
    responses={404: {"description": "Version de modèle inconnue."}},
)
def activate_model(
    version_id: str,
    _admin: Annotated[UserInfo, Depends(require_roles([Role.ADMINISTRATEUR]))],
) -> ModelActivateResponse:
    """Bascule atomiquement le pointeur vers une version validée."""
    try:
        promouvoir(version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Version {version_id} inconnue.") from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ModelActivateResponse(
        message="Bascule effectuée ; les requêtes en cours terminent sur leur modèle initial.",
        active_version=version_id,
        switched_at=datetime.now(UTC),
    )


@router.post("/models/rollback", response_model=ModelActivateResponse)
def rollback_model(
    _admin: Annotated[UserInfo, Depends(require_roles([Role.ADMINISTRATEUR]))],
    version_id: str | None = Query(default=None),
) -> ModelActivateResponse:
    """Revient à la version précédente (ou à celle explicitement demandée)."""
    try:
        registre = rollback(version_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Version {version_id} inconnue.") from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ModelActivateResponse(
        message="Retour arrière effectué.",
        active_version=registre["production"],
        switched_at=datetime.now(UTC),
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
