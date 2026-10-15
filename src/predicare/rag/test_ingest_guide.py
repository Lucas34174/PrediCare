"""Test d'ingestion : Guides Réseau."""

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
        raise SystemExit("Ollama indisponible")

    fichiers = sorted(Path("/data/raw").glob("Guide_Reseau_Soins_*.pdf"))
    print(f"→ {len(fichiers)} guides détectés\n")

    for chemin in fichiers:
        rapport = ingestor.ingest_file(chemin)
        print(f"  {chemin.name} → {rapport}")

    # Vérification par catégorie
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT metadonnees->>'categorie' AS categorie, count(*)
            FROM documents_vectorises
            WHERE chunk_type = 'prestataire' AND actif = true
            GROUP BY 1 ORDER BY 2 DESC
        """)).fetchall()
        print("\nPrestataires par catégorie :")
        for r in rows:
            print(f"  {r.categorie}: {r.count}")

        rows = conn.execute(text("""
            SELECT metadonnees->>'ville' AS ville, count(*)
            FROM documents_vectorises
            WHERE chunk_type = 'prestataire' AND actif = true
            GROUP BY 1 ORDER BY 2 DESC
        """)).fetchall()
        print("\nPrestataires par ville :")
        for r in rows:
            print(f"  {r.ville or 'non précisée'}: {r.count}")

    ingestor.close()


if __name__ == "__main__":
    main()