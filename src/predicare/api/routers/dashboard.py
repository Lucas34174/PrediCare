"""Routeur pour le Dashboard décisionnel (PB-39) - BI & FinOps."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicare.api.deps import _db_engine, get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/kpis")
def get_kpis(
    periode: str = "30d",
    engine: Engine = Depends(_db_engine),
    current_user=Depends(get_current_user),
):
    """KPIs Métier et FinOps pour le tableau de bord."""
    if current_user.role not in ("gestionnaire", "administrateur"):
        raise HTTPException(status_code=403, detail="Accès réservé aux gestionnaires.")

    with engine.connect() as conn:
        # --- 1. KPIs MÉTIER (Base de données) ---
        total_factures = conn.execute(text("SELECT count(*) FROM factures")).scalar() or 0
        montant_total = (
            conn.execute(text("SELECT coalesce(sum(montant_total), 0) FROM factures")).scalar() or 0
        )
        montant_economise = (
            conn.execute(
                text(
                    "SELECT coalesce(sum(montant_total), 0) FROM factures WHERE statut = 'REJETEE'"
                )
            ).scalar()
            or 0
        )
        rejetees = (
            conn.execute(text("SELECT count(*) FROM factures WHERE statut = 'REJETEE'")).scalar()
            or 0
        )
        en_attente = (
            conn.execute(text("SELECT count(*) FROM factures WHERE statut = 'EN_COURS'")).scalar()
            or 0
        )

        taux_detection = round((rejetees / total_factures), 4) if total_factures > 0 else 0.0
        # Motifs de fraude
        rows_motifs = conn.execute(
            text(
                "SELECT motif_rejet, count(*) as count FROM factures WHERE statut = 'REJETEE' AND motif_rejet IS NOT NULL GROUP BY motif_rejet ORDER BY count DESC LIMIT 4"
            )
        ).fetchall()
        distribution = [{"type": r.motif_rejet, "count": r.count} for r in rows_motifs]

        # --- 2. KPIs FINOPS (Cache sémantique) ---
        cache_entries = conn.execute(text("SELECT count(*) FROM semantic_cache")).scalar() or 0
        cache_hits = (
            conn.execute(text("SELECT coalesce(sum(hit_count), 0) FROM semantic_cache")).scalar()
            or 0
        )
        # Estimation : 1 hit = ~500 tokens économisés
        tokens_economises = cache_hits * 500
        # Si on estime 1 token = 0.00001 € (ou 50 Ar), on peut chiffrer l'économie
        economie_estimee = tokens_economises * 50  # en Ariary (exemple)

    return {
        "periode": periode,
        "kpis_metier": {
            "total_factures": total_factures,
            "montant_total_demande": montant_total,
            "montant_economise": montant_economise,
            "taux_detection_fraude": taux_detection,
            "en_attente": en_attente,
        },
        "kpis_finops": {
            "cache_entries": cache_entries,
            "cache_hits": cache_hits,
            "tokens_economises": tokens_economises,
            "economie_estimee_ar": economie_estimee,
        },
        "distribution_fraudes": distribution,
    }
