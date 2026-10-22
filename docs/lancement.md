# Lancement de la plateforme (Docker Compose)

## Démarrage

```bash
cp .env.example .env          # une seule fois ; .env n'est jamais commité
# Remplacer les secrets de démonstration, notamment PII_ENCRYPTION_KEY.
docker compose up --build -d
docker compose ps             # init doit être "exited (0)" ; les autres "healthy"
```

| Service | URL                          | Rôle                                                |
| ------- | ---------------------------- | --------------------------------------------------- |
| init    | —                            | Migrations + chargement automatique des 12 CSV      |
| front   | http://localhost:3000        | Interface React (nginx) ; appelle l'API via `/api/` |
| api     | http://localhost:8000/health | API FastAPI (documentation : `/docs`)               |
| n8n     | http://localhost:5678        | Workflows d'alerte                                  |
| db      | 127.0.0.1:5432               | PostgreSQL 16 + pgvector + pgcrypto                 |

Ordre de démarrage : db, puis init, puis api et n8n, puis front. Le service
`init` applique les migrations et charge les données au premier démarrage. Les
démarrages suivants sont idempotents. Les ports se changent dans `.env`
(`DB_PORT`, `API_PORT`, `FRONT_PORT`, `N8N_PORT`).

## Commandes utiles

| Besoin                               | Commande                                                |
| ------------------------------------ | ------------------------------------------------------- |
| Journaux d'un service                | `docker compose logs -f api`                            |
| Arrêt (données conservées)           | `docker compose down`                                   |
| Remise à zéro (SUPPRIME les données) | `docker compose down -v`                                |
| Console SQL                          | `docker compose exec db psql -U predicare -d predicare` |
| Reconstruire après une modification  | `docker compose up --build -d`                          |

## Vérifications

```bash
curl -s localhost:3000/api/health     # {"status":"ok"} : le front atteint l'API via nginx
docker compose exec db psql -U predicare -d predicare -c "\dx"   # vector, pgcrypto
docker compose exec db psql -U predicare -c "\l"                  # bases predicare et n8n
```

Les données (volumes `pgdata` et `n8n_data`) survivent à `docker compose down` et à un redémarrage.

## Base de données et migrations

Le schéma PostgreSQL est créé par des migrations Alembic versionnées (dossier `migrations/versions/`). Le service `init` les applique automatiquement avant de charger les données.

| Besoin                                        | Commande                                                                               |
| --------------------------------------------- | -------------------------------------------------------------------------------------- |
| Créer / mettre à jour le schéma               | `docker compose up -d db` puis `make migrate`                                          |
| État du chargement automatique                | `make db-status`                                                                       |
| Recharger les 12 CSV                          | `make reload-data` (destructif)                                                        |
| Revenir à une base vide                       | `docker compose run --rm api alembic downgrade base`                                   |
| Voir la version appliquée                     | `docker compose run --rm api alembic current`                                          |
| Créer une nouvelle migration                  | `alembic revision -m "sujet"`, écrire `upgrade()` et `downgrade()`, puis `make format` |
| Remise à zéro complète (SUPPRIME les données) | `docker compose down -v`                                                               |

Après avoir ajouté une migration, reconstruire l'image (`make migrate` le fait) : les migrations sont copiées dans l'image `api`.

Tests avec la base du compose (ils créent une base temporaire, jamais la base de développement) :

    docker compose up -d db
    set -a; . ./.env; set +a
    DB_PASSWORD="$POSTGRES_PASSWORD" make test
