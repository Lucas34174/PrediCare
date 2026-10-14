# Lancement de la plateforme (Docker Compose)

## Démarrage

```bash
cp .env.example .env          # une seule fois ; .env n'est jamais commité
docker compose up --build -d
docker compose ps             # 4 services "healthy" au bout d'environ 30 s
```

| Service | URL | Rôle |
| --- | --- | --- |
| front | http://localhost:3000 | Interface React (nginx) ; appelle l'API via `/api/` |
| api | http://localhost:8000/health | API FastAPI (documentation : `/docs`) |
| n8n | http://localhost:5678 | Workflows d'alerte |
| db | 127.0.0.1:5432 | PostgreSQL 16 + pgvector + pgcrypto |

Ordre de démarrage (healthchecks) : db, puis api et n8n, puis front. Les ports se changent dans `.env` (`DB_PORT`, `API_PORT`, `FRONT_PORT`, `N8N_PORT`).

## Commandes utiles

| Besoin | Commande |
| --- | --- |
| Journaux d'un service | `docker compose logs -f api` |
| Arrêt (données conservées) | `docker compose down` |
| Remise à zéro (SUPPRIME les données) | `docker compose down -v` |
| Console SQL | `docker compose exec db psql -U predicare -d predicare` |
| Reconstruire après une modification | `docker compose up --build -d` |

## Vérifications

```bash
curl -s localhost:3000/api/health     # {"status":"ok"} : le front atteint l'API via nginx
docker compose exec db psql -U predicare -d predicare -c "\dx"   # vector, pgcrypto
docker compose exec db psql -U predicare -c "\l"                  # bases predicare et n8n
```

Les données (volumes `pgdata` et `n8n_data`) survivent à `docker compose down` et à un redémarrage.
