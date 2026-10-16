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

Les tables métier reprennent exactement les colonnes des CSV fournis, noms compris, pour que le chargement () soit direct. Choix liés aux données :

- montants en ariary : entiers (`BIGINT`) ;
- pas de clé étrangère sur `code` dans `lignes_facture`, `ordonnance_lignes` et `grille_tarifaire` : un code désigne un acte ou un médicament (deux référentiels) ; le chargement doit vérifier l'absence d'orphelins (0 constaté) ;
- `factures.numero_facture` n'est pas unique : 553 numéros apparaissent en double (fraude DOUBLON) ;
- aucune contrainte métier (dates, prix) : le jeu contient des fraudes injectées qu'il faut pouvoir charger ; seules des contraintes d'intégrité et des valeurs fermées observées (statuts, rangs, sexes, types de ligne) sont posées ;
- `statut`, `motif_rejet`, `montant_pris_en_charge` et `date_traitement` (factures) portent un commentaire PostgreSQL « fuite de données » : à exclure des variables du modèle ;
- `jours_ouverture` (prestataires) et `actes_exclus` (garanties) sont des tableaux PostgreSQL ; le chargement convertit `12345` en `{1,2,3,4,5}` et sépare `actes_exclus` sur `|`.

Données personnelles : `identites_pii` contient uniquement nom, prénoms, date de naissance, téléphone, e-mail, adresse et numéro CIN, en binaire chiffré (`pgcrypto`, `pgp_sym_encrypt`, clé `PII_ENCRYPTION_KEY`). Le sexe et la ville restent dans `assures` ; le reste du système n'utilise que `assure_id`.

Choix en suspens :

- les fichiers de labels (`labels_fraude.csv`, `labels_prestataires.csv`) ne sont pas chargés en base : ils servent à l'entraînement et sont lus depuis les CSV ;
- `decisions_gestionnaire.gestionnaire_id` et `journal_audit.utilisateur_id` n'ont pas de clé étrangère : la table des utilisateurs arrive avec ;
- `vector(1024)` (e5-large / bge-m3) : dimension à confirmer avec le choix du modèle d'embedding ; la changer impose de recréer les colonnes.

Tests : `tests/test_migrations.py` rejoue `upgrade` / `downgrade` / `upgrade` sur une base temporaire (jamais la base de développement) ; la CI fournit une base PostgreSQL pgvector, et `PREDICARE_REQUIRE_DB=1` fait échouer le test si la base est absente.

### API FastAPI – Squelette et mocks :

Les 16 endpoints de `docs/contrats_interface.md` sont implémentés dans `src/predicare/api/routers/` (auth, claims, dashboard, assistant, admin). Les schémas Pydantic v2 (`schemas.py`) valident les requêtes et les réponses. Les réponses sont simulées (mock) : elles seront remplacées par la vraie logique dans les tâches suivantes (authentification , soumission de facture , modèle et SHAP , configuration , versionnement ).

Comportement des mocks, à connaître pour le front :

- `/health` interroge réellement PostgreSQL (`SELECT 1`, timeout de 2 s) : 200 si la base répond, 503 avec `database: "disconnected"` sinon.
- `POST /auth/login` accepte les identifiants `gestionnaire1`, `assure1`, `admin1` et `pro1` avec n'importe quel mot de passe non vide ; tout autre identifiant renvoie 401. Le jeton mock a la forme `mock-token-<identifiant>`, et `GET /auth/me` le relit (401 s'il manque ou s'il est invalide).
- `GET /claims/{id}`, `/prediction` et `/decision` renvoient 404 pour tout id hors `FAC-00005637` et `FAC-00084700` ; `POST /admin/models/{id}/activate` renvoie 404 pour une version inconnue.
- Les paramètres sont validés (422) : `page ≥ 1`, `page_size` entre 1 et 100, `statut` limité aux trois valeurs fermées, `periode` parmi `7d`, `30d`, `all`.

Limites connues, volontairement reportées :

- Les rôles ne sont pas appliqués : n'importe qui peut appeler `/admin/*`, y compris sans jeton. Ne pas exposer cette API hors d'un poste de développement tant que n'est pas fait.
- `PUT /admin/config` et `POST /admin/models/{id}/activate` ne persistent rien : un `GET` ultérieur renvoie les valeurs d'origine
- Le validator `montant_coherent` ne contrôle que `quantite × prix_unitaire` par ligne. Les contrôles de la facture entière (somme des lignes, part assuré, dates) relèvent de .

Incohérences à traiter dans des PR `docs/` séparées : `distribution_fraudes` du contrat cite des types (`TARIF_ABUSIF`, `PRESCRIPTION_NON_CONFORME`) absents des 14 types de fraude du dictionnaire de données, et le document « Choix technologiques » mentionne Streamlit alors que le front est en React.

### Authentification, rôles et isolation des assurés (PB-20) :

L'authentification de l'API repose sur des tokens JWT signés avec l'algorithme HS256 (`PyJWT`), dont la clé secrète provient de la variable d'environnement `JWT_SECRET`. Les mots de passe sont hachés avec `bcrypt`.

La table `utilisateurs` versionnée par la migration Alembic `b20_utilisateurs` stocke les comptes avec contrainte de rôle fermée (`assure`, `professionnel_sante`, `gestionnaire`, `administrateur`), reliés optionnellement à `assures(assure_id)` ou `prestataires(prestataire_id)`.

Le contrôle d'accès (RBAC) s'opère via les dépendances FastAPI `get_current_user` et `require_roles`. Conformément au CDC et aux contrats d'interface, un assuré (`Role.ASSURE`) ne peut consulter et lister que les factures correspondant strictement à son `assure_id` ; toute tentative d'accès à un dossier tiers renvoie une erreur 403 Forbidden.

### Soumission de factures et validation stricte (PB-21) :

L'endpoint `POST /claims` applique une validation Pydantic v2 stricte (`ClaimCreateRequest`) pour garantir la robustesse des données entrantes (CDC §2) :

- Vérification temporelle : la date d'émission ne peut pas précéder la date de soin (`date_emission >= date_soin`).
- Cohérence financière : `montant_total` doit correspondre exactement à la somme des montants des lignes, `part_assure` ne peut pas excéder `montant_total`, et chaque ligne vérifie `montant_total == quantite * prix_unitaire` avec `quantite >= 1`.
- Toute anomalie de structure ou de calcul déclenche un rejet propre HTTP 422 (Unprocessable Entity) avec message d'erreur explicite.

Les factures soumises sont persistées pour permettre leur relecture fidèle avec leurs lignes d'actes et de médicaments via `GET /claims/{id}`.
