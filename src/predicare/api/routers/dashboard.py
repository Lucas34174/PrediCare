"""Router tableau de bord – /dashboard/kpis."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicare.api.deps import _db_engine, get_current_user

router = APIRouter(prefix="/dashboard", tags=["Tableau de bord"])

"""Routeur pour le Dashboard décisionnel (PB-39)."""

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis")
def get_kpis(
    periode: str = "30d",
    engine: Engine = Depends(_db_engine),
    current_user=Depends(get_current_user),
):
    """Renvoie les KPIs décisionnels pour le tableau de bord.
    Accès : gestionnaire, administrateur.
    """
    # 1. Contrôle d'accès (RBAC)
    if current_user.role not in ("gestionnaire", "administrateur"):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Accès réservé aux gestionnaires.")

    # 2. Calcul des KPIs depuis la base
    with engine.connect() as conn:
        # Nombre total de factures
        total_factures = conn.execute(text("SELECT count(*) FROM factures")).scalar() or 0

        # Montant total demandé
        montant_total = (
            conn.execute(text("SELECT coalesce(sum(montant_total), 0) FROM factures")).scalar() or 0
        )

        # Montant économisé (somme des factures rejetées)
        montant_economise = (
            conn.execute(
                text(
                    "SELECT coalesce(sum(montant_total), 0) FROM factures WHERE statut = 'REJETEE'"
                )
            ).scalar()
            or 0
        )

        # Nombre de factures rejetées (fraudes / anomalies)
        factures_rejetees = (
            conn.execute(text("SELECT count(*) FROM factures WHERE statut = 'REJETEE'")).scalar()
            or 0
        )

        # Dossiers en attente d'arbitrage
        en_attente = (
            conn.execute(text("SELECT count(*) FROM factures WHERE statut = 'EN_COURS'")).scalar()
            or 0
        )

        # Taux de détection de fraude
        taux_detection = (
            round((factures_rejetees / total_factures), 4) if total_factures > 0 else 0.0
        )

        # Répartition des motifs de rejet
        rows_motifs = conn.execute(
            text("""
            SELECT motif_rejet, count(*) as count
            FROM factures
            WHERE statut = 'REJETEE' AND motif_rejet IS NOT NULL
            GROUP BY motif_rejet
            """)
        ).fetchall()

        distribution = [{"type": r.motif_rejet, "count": r.count} for r in rows_motifs]

    return {
        "periode": periode,
        "kpis": {
            "total_factures_traitees": total_factures,
            "montant_total_demande": montant_total,
            "montant_economise_fraude": montant_economise,
            "taux_detection_fraude": taux_detection,
            "dossiers_en_attente_arbitrage": en_attente,
        },
        "distribution_fraudes": distribution,
    }
