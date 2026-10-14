"""Point d'entrée de l'API PrediCare TPA."""

from fastapi import FastAPI

app = FastAPI(title="PrediCare TPA API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Endpoint de supervision (exigence « Supervisable » du CDC)."""
    return {"status": "ok"}
