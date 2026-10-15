"""Script de test : ingestion du barème uniquement."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text

from predicare.core.config import database_url
from predicare.rag.config import RagConfig
from predicare.rag.ingest import Ingestor

logging.basicConfig(level=logging.INFO)


def main() -> None:
    config = RagConfig.from_env()
    engine = create_engine(database_url())

    ingestor = Ingestor(engine, config)

    # Vérifier la santé d'Ollama
    if not ingestor._embedder.healthcheck():
        raise SystemExit("Ollama indisponible ou modèle bge-m3 manquant")

    bareme = Path("/data/raw/Bareme_Reference_Actes.pdf")
    rapport = ingestor.ingest_file(bareme)
    print(rapport)

    # Vérification en base
    with engine.connect() as conn:
        nb = conn.execute(
            text("SELECT count(*) FROM documents_vectorises WHERE actif = true")
        ).scalar()
        print(f"Chunks en base : {nb}")

    ingestor.close()


if __name__ == "__main__":
    main()
