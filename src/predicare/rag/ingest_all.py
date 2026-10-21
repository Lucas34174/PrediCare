"""Ingère tout le corpus de data/raw/ (utilisé par le service init)."""

import logging
from pathlib import Path

from sqlalchemy import create_engine

from predicare.core.config import database_url
from predicare.rag.config import RagConfig
from predicare.rag.ingest import Ingestor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    config = RagConfig.from_env()
    engine = create_engine(database_url())
    ingestor = Ingestor(engine, config)

    corpus = Path("/data/raw")
    if not corpus.exists():
        print(f"  __Corpus {corpus} absent — skip.")
        return

    pdfs = sorted(corpus.glob("*.pdf"))
    print(f"→ {len(pdfs)} PDFs à ingérer")

    for pdf in pdfs:
        try:
            rapport = ingestor.ingest_file(pdf)
            print(f"  {pdf.name} → {rapport}")
        except Exception as exc:
            print(f"  ___{pdf.name} : {exc}")

    ingestor.close()
    logger.info("Ingestion terminée.")


if __name__ == "__main__":
    main()
