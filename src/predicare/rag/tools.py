"""Outils exposés à l'agent ReAct.

RÈGLE CRITIQUE : search_my_claims ne retourne JAMAIS de données
d'un autre assuré que celui du JWT.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine, text

from predicare.rag.retriever import Retriever

logger = logging.getLogger(__name__)


class Tools:
    """Outils exposés au LLM."""

    def __init__(
        self,
        engine: Engine,
        retriever: Retriever,
    ) -> None:
        self._engine = engine
        self._retriever = retriever

    def search_documents(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Recherche RAG sur le corpus public (barème, CG, guides).

        Retourne une liste de chunks avec leur source.
        """
        results = self._retriever.search(query, top_k=top_k)

        out: list[dict[str, Any]] = []
        for r in results:
            out.append(
                {
                    "contenu": r.contenu,
                    "chunk_type": r.chunk_type,
                    "metadata": r.metadata,
                    "similarity": r.score_vector,
                    "source": self._extraire_source(r),
                }
            )
        return out

    def search_my_claims(
        self,
        contract_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Liste les factures de l'assuré connecté (contrat spécifique).

        ⚠️ Le contract_id vient du JWT, JAMAIS du LLM.
        """
        if not contract_id:
            logger.warning("search_my_claims appelé sans contract_id")
            return []

        sql = text("""
            SELECT
                f.facture_id,
                f.numero_facture,
                f.date_soin,
                f.montant_total,
                f.statut,
                f.motif_rejet
            FROM factures f
            WHERE f.contrat_id = :cid
            ORDER BY f.date_soin DESC
            LIMIT :limit
        """)

        with self._engine.connect() as conn:
            rows = conn.execute(sql, {"cid": contract_id, "limit": limit}).fetchall()

        return [
            {
                "facture_id": r.facture_id,
                "numero_facture": r.numero_facture,
                "date_soin": str(r.date_soin) if r.date_soin else None,
                "montant_total": r.montant_total,
                "statut": r.statut,
                "motif_rejet": r.motif_rejet,
            }
            for r in rows
        ]

    @staticmethod
    def _extraire_source(result) -> dict[str, str]:
        """Extrait une source lisible depuis les métadonnées d'un chunk."""
        md = result.metadata
        doc_type = md.get("doc_type") or result.chunk_type

        if result.chunk_type == "ligne_bareme":
            return {
                "document": "Barème de référence",
                "section": (
                    f"{md.get('categorie', '?')} — "
                    f"{md.get('code_acte') or md.get('code_medicament', '?')}"
                ),
            }
        if result.chunk_type in ("article", "article_partie"):
            return {
                "document": f"Conditions Générales {md.get('formule', '')}".strip(),
                "section": f"Article {md.get('article_num', '?')} — {md.get('article_titre', '')}",
            }
        if result.chunk_type == "contrat_metadata":
            return {
                "document": f"Contrat {md.get('contract_id', '?')}",
                "section": f"Formule {md.get('formule', '?')}",
            }
        if result.chunk_type == "prestataire":
            return {
                "document": "Guide Réseau",
                "section": f"{md.get('categorie', '?')} — {md.get('prestataire_nom', '?')}",
            }
        if result.chunk_type == "beneficiaire":
            return {
                "document": f"Contrat {md.get('contract_id', '?')}",
                "section": f"Bénéficiaire {md.get('beneficiaire_id', '?')}",
            }
        return {"document": doc_type, "section": ""}
