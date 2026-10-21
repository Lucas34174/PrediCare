#!/bin/sh
set -e

echo "  __ Attente de la base de données..."
until python -c "from predicare.core.config import database_url; from sqlalchemy import create_engine; engine = create_engine(database_url()); conn = engine.connect(); conn.close()" > /dev/null 2>&1; do
  sleep 2
done

engine = create_engine(database_url())
for i in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print(' ___ Base de données prête.')
        sys.exit(0)
    except Exception:
        time.sleep(2)
print(' ___ Timeout : la base de données ne répond pas.')
sys.exit(1)
"

echo " ___ Base de données prête. Application des migrations..."
alembic upgrade head

echo " ___ Ingestion du corpus RAG..."
python -m predicare.rag.ingest_all

echo " ___ Initialisation terminée !"