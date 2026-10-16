#!/usr/bin/env bash
# PrediCare TPA - Script de sauvegarde PostgreSQL (PB-28)

set -euo pipefail

# Chargement des variables d'environnement si .env existe
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

DB_NAME="${POSTGRES_DB:-predicare}"
DB_USER="${POSTGRES_USER:-predicare_admin}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/predicare_${DB_NAME}_${TIMESTAMP}.dump"

echo "=== [PrediCare] Démarrage de la sauvegarde de '${DB_NAME}' ==="

# Détection de l'environnement : Docker Compose ou local
if docker compose ps db --status running -q 2>/dev/null | grep -q .; then
    echo "-> Exécution de pg_dump via le conteneur Docker 'db'..."
    docker compose exec -T db pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_FILE"
elif command -v pg_dump >/dev/null 2>&1; then
    echo "-> Exécution de pg_dump via le client local..."
    export PGPASSWORD="${POSTGRES_PASSWORD:-predicare_secret}"
    pg_dump -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_FILE"
else
    echo "ERREUR : Ni conteneur Docker 'db' actif ni binaire 'pg_dump' local trouvé." >&2
    exit 1
fi

# Vérification que le fichier de backup a bien été créé et n'est pas vide
if [ ! -s "$BACKUP_FILE" ]; then
    echo "ERREUR : Le fichier de sauvegarde généré est vide ou manquant : $BACKUP_FILE" >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi

FILE_SIZE="$(du -h "$BACKUP_FILE" | cut -f1)"
echo "-> Sauvegarde réussie : ${BACKUP_FILE} (${FILE_SIZE})"

# Rétention : suppression des dumps de plus de N jours
echo "-> Nettoyage des sauvegardes datant de plus de ${RETENTION_DAYS} jours..."
find "$BACKUP_DIR" -type f -name "predicare_*.dump" -mtime +"$RETENTION_DAYS" -exec rm -f {} + 2>/dev/null || true

echo "=== [PrediCare] Sauvegarde terminée avec succès ==="
