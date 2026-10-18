"""Endpoint POST /assistant/chat — PB-36.

Expose l'agent ReAct via l'API FastAPI.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import Engine

from predicare.api.deps import get_current_user, get_db_engine
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


# ─── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    engine: Engine = Depends(get_db_engine),
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    """Assistant RAG sourcé.

    Sécurité :
    - L'utilisateur doit être authentifié (`assure`, `gestionnaire` ou `admin`).
    - Le `contract_id` est extrait du JWT, jamais du corps de la requête.
    - Si l'utilisateur n'a pas de contrat (ex: admin), l'agent RAG fonctionne
      mais sans accès aux factures.
    """
    role = current_user.get("role")
    if role not in ("assure", "gestionnaire", "administrateur"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rôle non autorisé pour l'assistant.",
        )

    contract_id = current_user.get("contract_id") or ""

    # Instancier les composants (en prod : via cache/singleton)
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