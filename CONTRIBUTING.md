# Guide de contribution

## Branches

- `main` : version stable, démontrable. Protégée (PR + CI verte obligatoires).
- `dev` : intégration quotidienne.
- `feat/<PB-xx>-<sujet>`, `fix/<sujet>`, `docs/<sujet>` : branches de travail courtes.

## Workflow

1. `git switch dev && git pull`
2. `git switch -c feat/PB-xx-sujet`
3. Commits atomiques, format : `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`
4. `make lint && make test`
5. Ouvrir une PR vers `dev` ; au moins 1 relecture d'un autre membre ; squash merge.

## Règles

- Style PEP8 appliqué par `ruff` (CI bloquante).
- Aucun secret, aucune donnée (`data/`) ni PII dans Git : utiliser `.env` et `.env.example`.
- Toute fonctionnalité s'accompagne d'au moins un test.
