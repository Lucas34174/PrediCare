"""Point d'entrée de l'API PrediCare TPA."""

from functools import cache

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from predicare.api.routers import admin, assistant, auth, claims, dashboard
from predicare.api.schemas import HealthResponse
from predicare.core.config import database_url

API_VERSION = "0.1.0"
app = FastAPI(
    title="PrediCare TPA API",
    version=API_VERSION,
    description="Détection de fraudes médicales, assistant RAG et pilotage opérationnel.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(dashboard.router)
app.include_router(assistant.router)
app.include_router(admin.router)


@cache
def _engine() -> Engine:
    """Moteur SQLAlchemy dédié au ping de santé (timeout court)."""
    return create_engine(database_url(), connect_args={"connect_timeout": 2}, pool_pre_ping=True)


def _database_reachable() -> bool:
    """Vrai si PostgreSQL répond à un SELECT 1."""
    try:
        with _engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


@app.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    responses={503: {"model": HealthResponse, "description": "PostgreSQL injoignable."}},
)
def health(response: Response) -> HealthResponse:
    """Endpoint de supervision (exigence « Supervisable » du CDC)."""
    if _database_reachable():
        return HealthResponse(status="ok", version=API_VERSION, database="connected")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="unhealthy",
        version=API_VERSION,
        database="disconnected",
        detail="Impossible de joindre PostgreSQL",
    )
