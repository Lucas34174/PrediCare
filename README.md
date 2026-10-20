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

## Modèle de fraude v2 (`v2.0.0-weak`)

La refonte v2 reconstruit une cible de fraude à partir des 12 CSV métiers et
du référentiel des 14 types de fraude. Les vrais labels n'étant plus
disponibles, la cible est un **label faible** : elle ne doit pas être
présentée comme une vérité terrain.

- Modèle : XGBoost, 60 variables comportementales ;
- Test : PR-AUC 0,754, ROC-AUC 0,903, rappel 0,781, précision 0,420 ;
- Audit indépendant : **15/20** (détail et limites dans
  [`reports/ml/v2/audit_independant.md`](reports/ml/v2/audit_independant.md)) ;
- Registre : `v2.0.0-weak` en production, `v1.1.0` archivée (rollback) ;
- Documentation : [`docs/model_card_v2.md`](docs/model_card_v2.md),
  [`docs/weak_labels.md`](docs/weak_labels.md),
  [`docs/refonte_v2_pipeline.md`](docs/refonte_v2_pipeline.md).

```bash
# Reconstruire les labels, le dataset et le modèle
PYTHONPATH=src python -m predicare.ml.weak_labels
PYTHONPATH=src python -m predicare.ml.dataset_fraude
PYTHONPATH=src python -m predicare.ml.training_v2
```

## Architecture

_À compléter (diagramme des 3 flux : pipeline ML, RAG, BI)._

## Contribution

Voir [CONTRIBUTING.md](CONTRIBUTING.md).
