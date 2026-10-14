#!/bin/sh
# Exécuté UNE SEULE FOIS, à la création du volume de données PostgreSQL.
# Le schéma métier est créé par les migrations (dossier migrations/), pas ici.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<EOSQL
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SELECT 'CREATE DATABASE "${N8N_DB_NAME}"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${N8N_DB_NAME}')
\gexec
EOSQL
