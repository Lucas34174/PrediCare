# PrediCare TPA

Plateforme intégrée de détection de fraudes à l'assurance santé, d'assistant RAG sur les contrats et de pilotage décisionnel (Capstone Cohorte IA – ODC & Ingedata).

## Démarrage rapide (dev)

```bash
python -m venv .venv && source .venv/bin/activate
cp .env.example .env
make install
make test
make run   # http://localhost:8000/health
```

### Démarrage Docker avec chargement automatique

```bash
cp .env.example .env
# Remplacer PII_ENCRYPTION_KEY (>= 32 caractères) et les autres secrets.
docker compose up --build -d
docker compose ps   # init doit être "exited (0)"
```

Le service `init` applique les migrations et charge les 12 CSV métier au
premier démarrage. Les identités sont chiffrées dans `identites_pii`
(`pgcrypto`). Voir [`docs/pb19_auto_load_pii.md`](docs/pb19_auto_load_pii.md).

## Structure

| Dossier              | Rôle                                             |
| -------------------- | ------------------------------------------------ |
| `src/predicare/api`  | API FastAPI                                      |
| `src/predicare/ml`   | Pipeline de données, modèle fraude, SHAP         |
| `src/predicare/rag`  | Indexation des contrats, agent RAG               |
| `src/predicare/db`   | Accès base (PostgreSQL/pgvector)                 |
| `src/predicare/core` | Configuration, logs, sécurité                    |
| `migrations/`        | Migrations SQL versionnées                       |
| `infra/n8n/`         | Workflows n8n (.json)                            |
| `web/`               | Interface web                                    |
| `data/`              | Données locales (non versionnées)                |
| `models/`            | Modèles versionnés                               |
| `docs/`              | Architecture, guides utilisateur et exploitation |
| `tests/`             | Tests pytest                                     |

## Architecture

_À compléter (diagramme des 3 flux : pipeline ML, RAG, BI)._

## Contribution

Voir [CONTRIBUTING.md](CONTRIBUTING.md).
