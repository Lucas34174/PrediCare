#!/bin/sh
set -e

echo " ___ Attente de la base de données..."
python -c "
import time
from sqlalchemy import create_engine, text
from predicare.core.config import database_url
import sys

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