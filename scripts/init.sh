#!/bin/sh
set -e

echo "  __ Attente de la base de données..."
until python -c "from predicare.core.config import database_url; from sqlalchemy import create_engine; engine = create_engine(database_url()); conn = engine.connect(); conn.close()" > /dev/null 2>&1; do
  sleep 2
done

echo " ___ Base de données prête. Application des migrations..."
alembic upgrade head

echo " ___ Ingestion du corpus RAG..."
python -m predicare.rag.ingest_all

echo " ___ Initialisation terminée !"