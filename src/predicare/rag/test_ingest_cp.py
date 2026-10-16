"""Test d'ingestion : toutes les Conditions Particulières du dossier."""

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

    corpus_dir = Path("/data/raw")
    fichiers = sorted(corpus_dir.glob("CP_CTR-*.pdf"))
    print(f"→ {len(fichiers)} fichiers CP détectés\n")

    rapports = {"indexed": 0, "skipped": 0, "erreurs": 0}

    for chemin in fichiers:
        try:
            rapport = ingestor.ingest_file(chemin)
            statut = rapport.get("status", "?")
            rapports[statut] = rapports.get(statut, 0) + 1
            if statut == "indexed":
                print(f"  ✅ {chemin.name} → {rapport['nb_chunks']} chunks")
            elif statut == "skipped":
                print(f"  ⏭  {chemin.name} → déjà indexé")
        except Exception as exc:
            rapports["erreurs"] += 1
            print(f"  ❌ {chemin.name} → ERREUR : {exc}")

    print(f"\nRapport : {rapports}")

    # Vérification SANS colonne inexistante
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT chunk_type, count(*)
                FROM documents_vectorises
                WHERE chunk_type IN (
                    'contrat_metadata', 'beneficiaire', 'section_garanties'
                )
                  AND actif = true
                GROUP BY chunk_type
                ORDER BY chunk_type
            """)
        ).fetchall()
        print("\nChunks CP en base :")
        for r in rows:
            print(f"  {r.chunk_type}: {r.count}")

    ingestor.close()


if __name__ == "__main__":
    main()
