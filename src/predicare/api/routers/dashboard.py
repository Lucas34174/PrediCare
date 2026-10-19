"""Router tableau de bord – /dashboard/kpis."""

from typing import Literal

from fastapi import APIRouter

from ..schemas import DashboardKpisResponse, FraudeDistribution, KpiMetrics

router = APIRouter(prefix="/dashboard", tags=["Tableau de bord"])


@router.get("/kpis", response_model=DashboardKpisResponse)
def kpis(periode: Literal["7d", "30d", "all"] = "30d") -> DashboardKpisResponse:
    """Indicateurs de pilotage métier (mock)."""
    return DashboardKpisResponse(
        periode=periode,
        kpis=KpiMetrics(
            total_factures_traitees=15420,
            montant_total_demande=456200000,
            montant_economise_fraude=38400000,
            taux_detection_fraude=0.084,
            dossiers_en_attente_arbitrage=18,
        ),
        distribution_fraudes=[
            FraudeDistribution(type="TARIF_ABUSIF", count=64),
            FraudeDistribution(type="ACTE_FICTIF", count=32),
            FraudeDistribution(type="DOUBLON", count=18),
            FraudeDistribution(type="PRESCRIPTION_NON_CONFORME", count=12),
        ],
    )


from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Engine
from predicare.api.deps import get_db_engine

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/kpis")
def get_kpis(periode: str = "30d", engine: Engine = Depends(get_db_engine)):
    """Renvoie les KPIs décisionnels."""
    # (Ajouter un filtre de date selon 'periode')
    with engine.connect() as conn:
        total_factures = conn.execute(text("SELECT count(*) FROM factures")).scalar()
        montant_total = conn.execute(text("SELECT sum(montant_total) FROM factures")).scalar() or 0
        anomalies = conn.execute(text("SELECT count(*) FROM factures WHERE statut = 'REJETEE'")).scalar()
        
        return {
            "periode": periode,
            "kpis": {
                "total_factures_traitees": total_factures,
                "montant_total_demande": montant_total,
                "dossiers_en_attente_arbitrage": anomalies,
                "taux_detection_fraude": round(anomalies / total_factures, 4) if total_factures else 0
            }
        }