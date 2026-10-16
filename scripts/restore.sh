#!/usr/bin/env bash

set -euo pipefail

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

DB_NAME="${POSTGRES_DB:-predicare}"
DB_USER="${POSTGRES_USER:-predicare_admin}"
BACKUP_DIR="${BACKUP_DIR:-backups}"

# Si aucun argument n'est fourni, on cherche la sauvegarde la plus récente
if [ $# -ge 1 ]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE="$(ls -t "${BACKUP_DIR}"/predicare_*.dump 2>/dev/null | head -n 1 || true)"
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "ERREUR : Fichier de sauvegarde introuvable : '${BACKUP_FILE}'" >&2
    echo "Usage : $0 [chemin_du_dump.dump]" >&2
    exit 1
fi

echo "=== [PrediCare] Démarrage de la restauration ==="
echo "-> Fichier source : $BACKUP_FILE"
echo "-> Base cible     : $DB_NAME"

if docker compose ps db --status running -q 2>/dev/null | grep -q .; then
    echo "-> Restauration via le conteneur Docker 'db'..."
    docker compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner < "$BACKUP_FILE"
elif command -v pg_restore >/dev/null 2>&1; then
    echo "-> Restauration via le client local 'pg_restore'..."
    export PGPASSWORD="${POSTGRES_PASSWORD:-predicare_secret}"
    pg_restore -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --no-owner "$BACKUP_FILE"
else
    echo "ERREUR : Ni conteneur Docker 'db' actif ni binaire 'pg_restore' local trouvé." >&2
    exit 1
fi

echo "=== [PrediCare] Restauration terminée avec succès ==="
