"""Endpoint POST /assistant/chat — PB-36 (Test sans JWT)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine,Engine,text
from predicare.api.deps import get_db_engine

from predicare.core.config import database_url
from predicare.rag.agent import ReactAgent
from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder
from predicare.rag.retriever import Retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


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


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """Assistant RAG sourcé (Bypass auth pour test)."""

    # Bypass : on force un contrat et un rôle
    contract_id = "CTR-000048"
    # role = "assure"

    # Initialisation à la volée (POC)
    engine = create_engine(database_url())
    config = RagConfig.from_env()
    embedder = Embedder(config)
    retriever = Retriever(engine, embedder, config)
    agent = ReactAgent(engine, retriever, config)

    try:
        result = agent.run(payload.message, contract_id)
    finally:
        agent.close()
        embedder.close()

    return ChatResponse(
        response=result.answer,
        sources=[Source(**s) for s in result.sources],
        abstention=result.abstention,
        conversation_id=payload.conversation_id,
    )

@router.get("/cache/stats")
def cache_stats(engine: Engine = Depends(get_db_engine)):
    """Expose les statistiques du cache sémantique (FinOps)."""
    with engine.connect() as conn:
        total_entries = conn.execute(text("SELECT count(*) FROM semantic_cache")).scalar() or 0
        total_hits = conn.execute(text("SELECT sum(hit_count) FROM semantic_cache")).scalar() or 0
        
        saved_tokens = total_hits * 500
        
        return {
            "entries": total_entries,
            "total_hits": total_hits,
            "estimated_saved_tokens": saved_tokens,
            "message": f"Le cache a permis d'économiser environ {saved_tokens} tokens."
        }
