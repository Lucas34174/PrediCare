# PrediCare TPA

Plateforme intégrée de détection de fraudes à l'assurance santé, d'assistant RAG sur les contrats et de pilotage décisionnel (Capstone Cohorte IA – ODC & Ingedata).

![CI](https://github.com/<org>/predicare-tpa/actions/workflows/ci.yml/badge.svg)

## Démarrage rapide (dev)
```bash
python -m venv .venv && source .venv/bin/activate
cp .env.example .env
make install
make test
make run   # http://localhost:8000/health
```

## Structure
| Dossier | Rôle |
| --- | --- |
| `src/predicare/api` | API FastAPI |
| `src/predicare/ml` | Pipeline de données, modèle fraude, SHAP |
| `src/predicare/rag` | Indexation des contrats, agent RAG |
| `src/predicare/db` | Accès base (PostgreSQL/pgvector) |
| `src/predicare/core` | Configuration, logs, sécurité |
| `migrations/` | Migrations SQL versionnées |
| `infra/n8n/` | Workflows n8n (.json) |
| `web/` | Interface web |
| `data/` | Données locales (non versionnées) |
| `models/` | Modèles versionnés |
| `docs/` | Architecture, guides utilisateur et exploitation |
| `tests/` | Tests pytest |

## Architecture
_À compléter (diagramme des 3 flux : pipeline ML, RAG, BI)._

## Contribution
Voir [CONTRIBUTING.md](CONTRIBUTING.md).
