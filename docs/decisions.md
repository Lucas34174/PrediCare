### N8N:

Le choix du tag: n8n:2.43.4 vient du fait que c'est la dernière version stable

### PostgreSQL / pgvector :

Image `pgvector/pgvector:pg16` : PostgreSQL 16 avec l'extension `vector` (RAG, cache sémantique) déjà compilée. `pgcrypto` (chiffrement des PII) est activée avec `vector` par le script `infra/db/init/01-extensions.sh`. Ce script ne s'exécute qu'à la création du volume `pgdata` ; pour le rejouer : `docker compose down -v`.

### Base de n8n :

n8n stocke ses données dans une base `n8n` de la même instance PostgreSQL (créée par le script d'init) : une seule base à sauvegarder, un conteneur de moins.

### Front (React) :

Le front est construit avec pnpm 10 / Node 22, puis servi par nginx. L'image est construite avec `pnpm install --frozen-lockfile` pour que deux builds donnent le même résultat : tout ajout de dépendance dans `web/package.json` doit s'accompagner du `pnpm-lock.yaml` mis à jour.

nginx relaie `/api/` vers le service `api` : le navigateur n'appelle qu'une seule origine, donc pas de CORS à configurer. `VITE_API_URL` est lue **au build** (fixée à `/api` dans le compose), pas au démarrage du conteneur.

`VITE_USE_MOCK` reste à `true` dans le compose tant que les endpoints de connexion de l'API n'existent pas.

### Secrets et configuration :

Les secrets viennent de `.env` (jamais commité, modèle dans `.env.example`). Le compose refuse de démarrer si `POSTGRES_PASSWORD`, `JWT_SECRET`, `PII_ENCRYPTION_KEY` ou `N8N_ENCRYPTION_KEY` manquent. Les valeurs de `.env.example` sont des valeurs de démo, à remplacer hors environnement local.

### Schéma de données et migrations (Alembic) :

Le schéma PostgreSQL est géré par des migrations versionnées via Alembic et appliqué dans l'environnement conteneurisé.

- Les tables couvrent l'intégralité du cycle métier : référentiels d'actes et médicaments, prestataires conventionnés, grilles tarifaires, contrats et garanties, assurés, ordonnances, factures et lignes de facturation.
- Conformité RGPD et sécurité : les PII (nom, prénom, téléphone, numéro de sécurité sociale, etc.) sont isolées dans la table `identites_pii` au format binaire chiffré (`pgcrypto`), le reste du système ne manipulant que l'identifiant pseudonymisé `assure_id`.
- Modèle ML et explicabilité : les tables `predictions` et `explications_shap` stockent les scores de risque, les seuils appliqués et les contributions SHAP au format JSON. Les arbitrages manuels sont tracés dans `decisions_gestionnaire`.
- RAG et cache sémantique : la table `documents_vectorises` stocke les sections des contrats d'assurance et leurs embeddings vectoriels (`vector(1024)` via `pgvector`). La table `semantic_cache` permet d'éviter les appels LLM redondants.
- Gouvernance : un `journal_audit` enregistre toutes les actions sensibles avec horodatage et rôle utilisateur.
- Des index stratégiques sont posés sur `factures` (`assure_id`, `prestataire_id`, `ordonnance_id`, `date_soin`) pour permettre la détection rapide des anomalies (doublons, réutilisations d'ordonnances).
