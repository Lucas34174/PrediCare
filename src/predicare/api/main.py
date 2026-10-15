"""Point d'entrée de l'API PrediCare TPA."""

from fastapi import FastAPI

from predicare.api.routers import admin, assistant, auth, claims, dashboard
from predicare.api.schemas import HealthResponse

app = FastAPI(
    title="PrediCare TPA API",
    version="0.1.0",
    description="Détection de fraudes médicales, assistant RAG et pilotage opérationnel.",
)

app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(dashboard.router)
app.include_router(assistant.router)
app.include_router(admin.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Endpoint de supervision (exigence « Supervisable » du CDC)."""
    return HealthResponse(status="ok", version="0.1.0", database="connected")
