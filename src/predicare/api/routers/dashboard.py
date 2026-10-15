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
