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

Alembic a été retenu (document des choix technologiques) : migrations versionnées, rejouables (`upgrade` / `downgrade`), sans modèles ORM (chaque migration décrit le schéma explicitement). La connexion vient des variables `DB_*` (`predicare/core/config.py`), jamais d'`alembic.ini`. Les migrations s'exécutent dans l'image `api` (`make migrate`).

Le schéma est découpé en trois révisions : (1) référentiels et prestataires, (2) données métier, (3) plateforme IA (prédictions, SHAP, décisions, vecteurs, audit).

Les tables métier reprennent exactement les colonnes des CSV fournis, noms compris, pour que le chargement (PB-19) soit direct. Choix liés aux données :

- montants en ariary : entiers (`BIGINT`) ;
- pas de clé étrangère sur `code` dans `lignes_facture`, `ordonnance_lignes` et `grille_tarifaire` : un code désigne un acte ou un médicament (deux référentiels) ; le chargement doit vérifier l'absence d'orphelins (0 constaté) ;
- `factures.numero_facture` n'est pas unique : 553 numéros apparaissent en double (fraude DOUBLON) ;
- aucune contrainte métier (dates, prix) : le jeu contient des fraudes injectées qu'il faut pouvoir charger ; seules des contraintes d'intégrité et des valeurs fermées observées (statuts, rangs, sexes, types de ligne) sont posées ;
- `statut`, `motif_rejet`, `montant_pris_en_charge` et `date_traitement` (factures) portent un commentaire PostgreSQL « fuite de données » : à exclure des variables du modèle ;
- `jours_ouverture` (prestataires) et `actes_exclus` (garanties) sont des tableaux PostgreSQL ; le chargement convertit `12345` en `{1,2,3,4,5}` et sépare `actes_exclus` sur `|`.

Données personnelles : `identites_pii` contient uniquement nom, prénoms, date de naissance, téléphone, e-mail, adresse et numéro CIN, en binaire chiffré (`pgcrypto`, `pgp_sym_encrypt`, clé `PII_ENCRYPTION_KEY`). Le sexe et la ville restent dans `assures` ; le reste du système n'utilise que `assure_id`.

Choix en suspens :

- les fichiers de labels (`labels_fraude.csv`, `labels_prestataires.csv`) ne sont pas chargés en base : ils servent à l'entraînement et sont lus depuis les CSV ;
- `decisions_gestionnaire.gestionnaire_id` et `journal_audit.utilisateur_id` n'ont pas de clé étrangère : la table des utilisateurs arrive avec PB-20 ;
- `vector(1024)` (e5-large / bge-m3) : dimension à confirmer avec le choix du modèle d'embedding ; la changer impose de recréer les colonnes.

Tests : `tests/test_migrations.py` rejoue `upgrade` / `downgrade` / `upgrade` sur une base temporaire (jamais la base de développement) ; la CI fournit une base PostgreSQL pgvector, et `PREDICARE_REQUIRE_DB=1` fait échouer le test si la base est absente.
