"""Retriever hybride : recherche vectorielle + full-text avec fusion RRF.

Choix techniques :
- pgvector pour la similarité cosinus (modèle BGE-M3, 1024 dim).
- Full-text PostgreSQL avec dictionnaire 'french' (GIN index) pour les
  requêtes exactes (codes d'actes, numéros de contrat, noms de prestataires).
- Fusion RRF (Reciprocal Rank Fusion) : combine les deux classements sans
  nécessiter de pondération manuelle. Formule standard k=60.
- Filtres JSONB sur les métadonnées pour restreindre par formule, catégorie,
  type de chunk, contract_id, etc.

Ce module est central : il est utilisé par les tests d'équité, l'API
/assistant/chat, et le futur endpoint RAG.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Engine, bindparam, text

from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder

logger = logging.getLogger(__name__)


# ─── Constantes ────────────────────────────────────────────────────────────────

RRF_K = 60  # constante standard de la formule RRF
DEFAULT_TOP_K = 5
DEFAULT_MIN_SIMILARITY = 0.40
DEFAULT_CANDIDATES_MULTIPLIER = 4  # on récupère top_k * 4 par méthode avant fusion


# ─── Structures ────────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """Un résultat de recherche unifié."""

    chunk_id: int
    chunk_type: str
    contenu: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score_vector: float | None = None  # similarité cosinus (0-1)
    score_fulltext: float | None = None  # ts_rank (généralement 0-1)
    score_rrf: float = 0.0  # score de fusion final


# ─── Retriever ─────────────────────────────────────────────────────────────────


class Retriever:
    """Retriever hybride pour le corpus RAG PrediCare."""

    def __init__(
        self,
        engine: Engine,
        embedder: Embedder,
        config: RagConfig,
    ) -> None:
        self._engine = engine
        self._embedder = embedder
        self._config = config

    # ─── API publique ──────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        filters: dict[str, Any] | None = None,
        mode: str = "hybrid",
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> list[SearchResult]:
        """Recherche dans le corpus.

        Args:
            query: la question en langage naturel.
            top_k: nombre de résultats finaux.
            filters: dict de filtres sur les métadonnées. Ex :
                     {"formule": "CONFORT", "chunk_type": "article"}
            mode: "vector" | "fulltext" | "hybrid".
            min_similarity: seuil minimum de similarité cosinus (mode vector).

        Returns:
            Liste de SearchResult triés par score RRF décroissant.
        """
        if mode not in ("vector", "fulltext", "hybrid"):
            raise ValueError(f"mode invalide : {mode}")

        if mode == "vector":
            return self._search_vector(query, top_k, filters, min_similarity)
        if mode == "fulltext":
            return self._search_fulltext(query, top_k, filters)

        # hybride : récupérer plus de candidats puis fusionner
        candidates_k = top_k * DEFAULT_CANDIDATES_MULTIPLIER
        vec_results = self._search_vector(query, candidates_k, filters, min_similarity)
        ft_results = self._search_fulltext(query, candidates_k, filters)

        fused = self._fuse_rrf(vec_results, ft_results, top_k)
        return fused

    # ─── Recherche vectorielle ─────────────────────────────────────────────────

    def _search_vector(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
        min_similarity: float,
    ) -> list[SearchResult]:
        """Recherche par similarité cosinus avec pgvector."""
        query_vec = self._embedder.embed_one(query)

        where_clauses, params = self._build_where(filters)
        params["vec"] = query_vec
        params["min_sim"] = min_similarity
        params["k"] = top_k

        sql = text(f"""
            SELECT
                id AS chunk_id,
                chunk_type,
                contenu_enrichi AS contenu,
                metadonnees AS metadata,
                1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM documents_vectorises
            WHERE actif = true
              AND 1 - (embedding <=> CAST(:vec AS vector)) >= :min_sim
              {where_clauses}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
        """).bindparams(bindparam("vec", type_=Vector(self._config.embedding_dim)))

        with self._engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            SearchResult(
                chunk_id=r.chunk_id,
                chunk_type=r.chunk_type,
                contenu=r.contenu,
                metadata=r.metadata or {},
                score_vector=float(r.similarity),
            )
            for r in rows
        ]

    # ─── Recherche full-text ───────────────────────────────────────────────────

    def _search_fulltext(
        self,
        query: str,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Recherche full-text en français (tsvector + GIN)."""
        where_clauses, params = self._build_where(filters)
        params["query"] = query
        params["k"] = top_k

        sql = text(f"""
            SELECT
                id AS chunk_id,
                chunk_type,
                contenu_enrichi AS contenu,
                metadonnees AS metadata,
                ts_rank(to_tsvector('french', contenu_enrichi),
                        plainto_tsquery('french', :query)) AS rank
            FROM documents_vectorises
            WHERE actif = true
              AND to_tsvector('french', contenu_enrichi) @@
                  plainto_tsquery('french', :query)
              {where_clauses}
            ORDER BY rank DESC
            LIMIT :k
        """)

        with self._engine.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            SearchResult(
                chunk_id=r.chunk_id,
                chunk_type=r.chunk_type,
                contenu=r.contenu,
                metadata=r.metadata or {},
                score_fulltext=float(r.rank),
            )
            for r in rows
        ]

    # ─── Fusion RRF ────────────────────────────────────────────────────────────

    @staticmethod
    def _fuse_rrf(
        vec_results: list[SearchResult],
        ft_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Fusion Reciprocal Rank Fusion.

        RRF(d) = Σ (1 / (k + rank_i(d)))
        où rank_i(d) est le rang du document d dans la liste i (1-indexé).
        """
        scores: dict[int, float] = {}
        results_by_id: dict[int, SearchResult] = {}

        for rank, r in enumerate(vec_results, start=1):
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            results_by_id[r.chunk_id] = r

        for rank, r in enumerate(ft_results, start=1):
            scores[r.chunk_id] = scores.get(r.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            # Si on a déjà le chunk via vector, on complète juste le score fulltext
            if r.chunk_id in results_by_id:
                results_by_id[r.chunk_id].score_fulltext = r.score_fulltext
            else:
                results_by_id[r.chunk_id] = r

        # Tri par score RRF décroissant
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        fused: list[SearchResult] = []
        for cid in sorted_ids[:top_k]:
            r = results_by_id[cid]
            r.score_rrf = scores[cid]
            fused.append(r)
        return fused

    # ─── Construction des filtres ──────────────────────────────────────────────

    @staticmethod
    def _build_where(filters: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
        """Construit la clause WHERE à partir des filtres métadonnées.

        Filtres supportés :
        - chunk_type : "article" | "prestataire" | "beneficiaire" | ...
        - formule    : "CONFORT" | "ESSENTIEL" | "PREMIUM"
        - categorie  : "PHARMACIES" | "CONSULTATION" | ...
        - contract_id: "CTR-000048"
        - ville      : "Antananarivo"
        - code_acte  : "CONS-CARDIO"

        Les valeurs sont stockées dans metadonnees (JSONB).
        """
        if not filters:
            return "", {}

        clauses: list[str] = []
        params: dict[str, Any] = {}

        # chunk_type est une colonne directe
        if ct := filters.get("chunk_type"):
            clauses.append("AND chunk_type = :f_chunk_type")
            params["f_chunk_type"] = ct

        # Colonnes JSONB
        jsonb_mapping = {
            "formule": "formule",
            "categorie": "categorie",
            "contract_id": "contract_id",
            "ville": "ville",
            "code_acte": "code_acte",
        }
        for key, jsonb_key in jsonb_mapping.items():
            if value := filters.get(key):
                param_name = f"f_{key}"
                clauses.append(f"AND metadonnees->>'{jsonb_key}' = :{param_name}")
                params[param_name] = value

        return "\n              ".join(clauses), params
