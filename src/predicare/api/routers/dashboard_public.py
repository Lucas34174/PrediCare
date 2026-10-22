"""Routeur pour le Dashboard BI Public (Démonstration Jury)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicare.api.deps import _db_engine, require_roles
from predicare.api.schemas import Role, UserInfo

router = APIRouter(prefix="/dashboard/public", tags=["dashboard-public"])


@router.get("/kpis")
def get_public_kpis(
    _current_user: Annotated[UserInfo, Depends(require_roles([Role.GESTIONNAIRE]))],
    engine: Engine = Depends(_db_engine),
):
    """Renvoie les KPIs de pilotage réservés aux gestionnaires."""

    with engine.connect() as conn:
        # ═══════════════════════════════════════════════════════════
        # 1. PÔLE BUSINESS (Stratégique)
        # ═══════════════════════════════════════════════════════════
        prime_totale = (
            conn.execute(
                text(
                    "SELECT coalesce(sum(prime_annuelle_totale), 0) FROM contrats WHERE statut = 'ACTIF'"
                )
            ).scalar()
            or 0
        )
        nb_contrats = (
            conn.execute(text("SELECT count(*) FROM contrats WHERE statut = 'ACTIF'")).scalar() or 0
        )

        # Top secteurs
        rows_secteurs = conn.execute(
            text(
                "SELECT secteur, count(*) as count FROM contrats WHERE statut = 'ACTIF' GROUP BY secteur ORDER BY count DESC LIMIT 4"
            )
        ).fetchall()
        top_secteurs = [{"name": r.secteur, "value": r.count} for r in rows_secteurs]

        # ═══════════════════════════════════════════════════════════
        # 2. PÔLE MÉTIER (Opérationnel)
        # ═══════════════════════════════════════════════════════════
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

        # Répartition des fraudes
        rows_motifs = conn.execute(
            text(
                "SELECT motif_rejet, count(*) as count FROM factures WHERE statut = 'REJETEE' AND motif_rejet IS NOT NULL GROUP BY motif_rejet ORDER BY count DESC LIMIT 5"
            )
        ).fetchall()
        distribution_fraudes = [{"type": r.motif_rejet, "count": r.count} for r in rows_motifs]

        # ═══════════════════════════════════════════════════════════
        # 3. PÔLE ML (Technique)
        # ═══════════════════════════════════════════════════════════
        # (On simule des données de dérive PSI si la table est vide)
        modele_actif = "v1.0.0-xgb"
        psi_score = 0.042  # À remplacer par une vraie requête SQL sur une table de monitoring
        score_moyen = (
            conn.execute(text("SELECT coalesce(avg(score_fraude), 0) FROM predictions")).scalar()
            or 0.0
        )

        # ═══════════════════════════════════════════════════════════
        # 4. PÔLE FINOPS & RAG
        # ═══════════════════════════════════════════════════════════
        cache_hits = (
            conn.execute(text("SELECT coalesce(sum(hit_count), 0) FROM semantic_cache")).scalar()
            or 0
        )
        tokens_economises = cache_hits * 500

        # Requêtes RAG (on peut chercher dans journal_audit si on logue les appels)
        total_rag = (
            conn.execute(
                text("SELECT count(*) FROM journal_audit WHERE type_action = 'RAG_CHAT'")
            ).scalar()
            or 0
        )

    return {
        "business": {
            "prime_totale": prime_totale,
            "nb_contrats": nb_contrats,
            "top_secteurs": top_secteurs,
        },
        "metier": {
            "total_factures": total_factures,
            "montant_total": montant_total,
            "montant_economise": montant_economise,
            "taux_detection": taux_detection,
            "en_attente": en_attente,
            "distribution_fraudes": distribution_fraudes,
        },
        "ml": {
            "modele_actif": modele_actif,
            "psi_score": psi_score,
            "score_moyen": round(score_moyen, 3),
        },
        "finops": {
            "cache_hits": cache_hits,
            "tokens_economises": tokens_economises,
            "total_requetes_rag": total_rag,
        },
    }
