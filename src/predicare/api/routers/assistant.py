"""Router assistant RAG – /assistant/chat."""

from fastapi import APIRouter

from ..schemas import ChatRequest, ChatResponse, ChatSource

router = APIRouter(prefix="/assistant", tags=["Assistant RAG"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """Assistant conversationnel RAG (mock)."""
    return ChatResponse(
        response=(
            "Selon l'article 5 des Conditions Générales de votre formule CONFORT, "
            "les soins dentaires de prévention (dont le détartrage) sont pris en charge "
            "à 80 % dans la limite d'un plafond annuel de 80 000 Ariary."
        ),
        sources=[
            ChatSource(
                document="Conditions_Generales_CONFORT.pdf",
                section="Article 5.1 - Soins dentaires",
                page=4,
            )
        ],
        provenance_cache_semantique=False,
    )
