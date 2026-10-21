"""Endpoint POST /assistant/chat — PB-36 (Version Sécurisée JWT)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Engine, text

from predicare.api.deps import _db_engine, get_current_user
from predicare.rag.agent import ReactAgent
from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder
from predicare.rag.retriever import Retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


# ─── Schémas ───────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None


class Source(BaseModel):
    document: str
    section: str


class ChatResponse(BaseModel):
    response: str
    sources: list[Source]
    abstention: bool
    conversation_id: str | None = None
    provenance_cache_semantique: bool = False


# ─── Endpoint ──────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    engine: Engine = Depends(_db_engine),
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Assistant RAG sourcé avec sécurité JWT."""
    # 1. Vérification du rôle
    role = current_user.role
    if role not in ("assure", "gestionnaire", "administrateur"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rôle non autorisé pour l'assistant.",
        )

    # 2. Récupération du contract_id (uniquement pour les assurés)
    contract_id = ""
    if role == "assure":
        assure_id = current_user.id
        # On va chercher le contrat de l'assuré en base
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT contrat_id FROM assures WHERE assure_id = :aid"), {"aid": assure_id}
            ).fetchone()
        if row:
            contract_id = row[0]
        else:
            contract_id = ""

    # 3. Instanciation de l'agent
    config = RagConfig.from_env()
    embedder = Embedder(config)
    retriever = Retriever(engine, embedder, config)
    agent = ReactAgent(engine, retriever, config)

    try:
        # L'agent reçoit le contract_id extrait de la base (via le JWT)
        result = agent.run(payload.message, contract_id=contract_id)
    finally:
        agent.close()
        embedder.close()

    return ChatResponse(
        response=result.answer,
        sources=[Source(**s) for s in result.sources],
        abstention=result.abstention,
        conversation_id=payload.conversation_id,
        provenance_cache_semantique=False,  # À lier avec le cache plus tard
    )


@router.get("/cache/stats")
def cache_stats(engine: Engine = Depends(_db_engine)):
    """Expose les statistiques du cache sémantique (FinOps)."""
    with engine.connect() as conn:
        total_entries = conn.execute(text("SELECT count(*) FROM semantic_cache")).scalar() or 0
        total_hits = conn.execute(text("SELECT sum(hit_count) FROM semantic_cache")).scalar() or 0

        # Estimation : 1 hit évite ~500 tokens (prompt + contexte)
        saved_tokens = total_hits * 500

        return {
            "entries": total_entries,
            "total_hits": total_hits,
            "estimated_saved_tokens": saved_tokens,
            "message": f"Le cache a permis d'économiser environ {saved_tokens} tokens.",
        }
