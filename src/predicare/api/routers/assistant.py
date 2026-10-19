"""Endpoint POST /assistant/chat — PB-36 (Test sans JWT)."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import create_engine

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
