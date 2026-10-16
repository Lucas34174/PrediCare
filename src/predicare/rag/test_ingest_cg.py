"""Test d'ingestion : Conditions Générales (3 formules)."""

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

    if not ingestor._embedder.healthcheck():
        raise SystemExit("Ollama indisponible ou modèle bge-m3 manquant")

    fichiers = [
        "Conditions_Generales_CONFORT.pdf",
        "Conditions_Generales_ESSENTIEL.pdf",
        "Conditions_Generales_PREMIUM.pdf",
    ]

    for nom in fichiers:
        chemin = Path(f"/data/raw/{nom}")
        if not chemin.exists():
            print(f"⚠️  Introuvable : {nom}")
            continue
        rapport = ingestor.ingest_file(chemin)
        print(f"{nom} → {rapport}")

    # Vérification
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT metadonnees->>'formule' AS formule, count(*)
                FROM documents_vectorises
                WHERE chunk_type IN ('article', 'article_partie')
                  AND actif = true
                GROUP BY metadonnees->>'formule'
            """)
        ).fetchall()
        print("\nChunks par formule :")
        for r in rows:
            print(f"  {r.formule}: {r.count}")

    ingestor.close()


if __name__ == "__main__":
    main()
