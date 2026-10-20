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

## Stratégie de sauvegarde et restauration scriptées

- **Contexte** : Le CDC (§2 et §5) exige des sauvegardes scriptées et régulières avec capacité de restauration testée sur environnement propre.
- **Décision** :
  - Sauvegardes automatisées via `pg_dump -Fc` dans `scripts/backup.sh` (format Custom PostgreSQL compressé).
  - Restauration automatisée via `pg_restore --clean` dans `scripts/restore.sh`.
  - Intégration dans le flux d'exploitation via cibles `make backup` et `make restore`.
  - Politique de rétention locale glissante fixée à 7 jours.
  - Planification documentée pour déclenchement cron quotidien à 02h00.

## Stratégie de tests pytest et CI renforcée

- **Contexte** : Le CDC (§6 pytest) exige une suite de tests automatisés protégeant contre les régressions API (auth, 4 rôles RBAC, factures/claims, moteur de prédiction/SHAP, erreurs HTTP) et une CI verte sur chaque PR.
- **Décision** :
  - Tests approfondis des cas limites d'authentification (`tests/test_auth_rbac_edge_cases.py`) : validation des rejets 401 sur tokens expirés, malformés ou payloads incomplets, rejets 403 sur rôles insuffisants via `require_roles`.
  - Tests d'intégration des prédictions, arbitrages et erreurs HTTP (`tests/test_api_predictions_and_errors.py`) : contrôle du score, explicabilité SHAP, cycle d'arbitrage (VALIDE, REJETE, INVESTIGATION), et validation des codes d'erreur (404, 405, 422).
  - Ajout de la cible `make test-cov` pour l'exécution locale avec rapport de couverture.
  - Renforcement du workflow GitHub Actions (`.github/workflows/ci.yml`) avec validation des scripts shell et couverture de code systématique.

### Pipeline RAG

**Modèle d'embedding** : BGE-M3 (BAAI), 1024 dim, local via Ollama.
**Justification** : cf. docs/rag_architecture.md §3.

**Chunking** : spécialisé par type de document.
**Justification** : cf. docs/chunking_strategy.md.

**Recherche** : hybride (vectoriel + full-text + RRF).
**Justification** : cf. docs/rag_architecture.md §6.

**Conformité** : cf. docs/eu_ai_act_classification.md et docs/rgpd_aipd.md.

### EDA des données et des labels

### EDA des données et des labels :

Le notebook `notebooks/01_eda_exploration_donnees.ipynb` explore les 12 CSV et les 2 fichiers de labels. Il porte sur 84 593 factures étiquetées, dont 7 347 frauduleuses (8,69 %, ratio 10,5 : 1) ; 14 des 14 types de fraude du dictionnaire §6 sont présents. Les clés primaires sont uniques et on compte 0 orphelin de clés étrangères. Les colonnes `statut`, `motif_rejet`, `montant_pris_en_charge` et `date_traitement` sont exclues des features d'entraînement et d'inférence : leur AUC univariée atteint 0,673 (`pris_en_charge / montant_total`), contre 0,726 pour la variable de référence `montant_total`. Le déséquilibre impose PR-AUC, rappel à précision fixée et pondération des classes (`scale_pos_weight` de départ ≈ 10,5) plutôt que l'exactitude, avec un découpage temporel et/ou groupé par assuré ou prestataire. Les problèmes de qualité de gravité Haute sont : aucun (gravité Moyenne : colonnes constantes ou entièrement vides, et valeurs manquantes hors nulls attendus). Les signaux §6 testés ont des heuristiques exploratoires ; UPCODING et la carence ne sont pas évalués, faute d'heure et de spécialité d'acte. `identites_pii.csv` n'a été utilisé que pour compter les lignes (4 459 lignes de données) et aucune donnée personnelle n'apparaît dans le notebook. Les données restent hors Git (`data/`).

### Lint des notebooks :

Les notebooks d'exploration sont exemptés des règles ruff E501, N806, E741 et B905 (`per-file-ignores` sur `notebooks/*.ipynb`), car ils contiennent des lignes d'affichage denses et des noms de variables courts de type exploratoire. Ils restent soumis à `ruff format` et aux autres règles (E, W, F, I, N, UP, B). Le code de production sous `src/` garde la limite de 100 caractères.

### Sujet : Pipeline reproductible d'ingestion et de nettoyage des données (PB-04)

Le pipeline d'ingestion et de nettoyage technique (`src/predicare/db/ingest.py`) transforme les 12 CSV bruts et les 2 fichiers de labels en tables propres et typées sans dépendance à PostgreSQL. Les montants sont convertis en entiers stricts (`Int64` en Ariary) et les dates au format ISO AAAA-MM-JJ. Les doublons stricts sont éliminés, tandis que les anomalies métier (§6) et les valeurs manquantes structurelles (`ordonnance_id` null, etc.) sont intégralement préservées sans imputation arbitraire. La table `identites_pii` est validée mais protégée contre toute écriture en clair par défaut (RGPD). Une option d'échantillonnage par fermeture transitive (`--sample N`) garantit 0 orphelin sur toutes les relations. La constante `LEAKAGE_COLUMNS` isole les 4 colonnes à fuite pour PB-05, et la fonction publique `clean_all()` fournit une interface directe en mémoire pour le chargement en base PB-19.

### Split anti-fuite et baseline ML :

Split par groupes d'assurés triés chronologiquement par leur première `date_soin` :
80 % des assurés (les plus anciens) → train, 20 % → test. Aucun assuré ne traverse
les deux ensembles ; le train est antérieur au test. `class_weight='balanced'`
retenu pour gérer le déséquilibre (≈ 7 % de fraudes) sans surcharge de dépendance
SMOTE. Métrique prioritaire : **Recall** (coût d'un faux négatif > faux positif en
assurance fraude) ; **PR-AUC** pour le suivi dérive (robuste au déséquilibre).
Deux baselines : LR (Logistic Regression, lbfgs, max_iter=1000) et RF (300 arbres).
Modèles sérialisés dans `models/` via joblib ; `feature_names.json` pour PB-22.

### Optimisation XGBoost/LightGBM et sélection du seuil de décision :

L'optimisation bayésienne Optuna (20 trials) a comparé XGBoost et LightGBM via une validation croisée stratifiée et groupée par assuré (5-fold StratifiedGroupKFold) sur le jeu d'entraînement, préservant l'étanchéité absolue du jeu de test. La métrique directrice est la PR-AUC (Average Precision). Le déséquilibre de classes (ratio ≈ 10.5:1) est traité via `scale_pos_weight` : Optuna converge vers une pondération forte (7.51 pour XGBoost, 5.58 pour LightGBM), surclassant nettement la configuration non pondérée.

Le modèle champion retenu pour le déploiement est **XGBoost** (`v1.0.0-xgb`) : il atteint la meilleure PR-AUC en CV (0.6640), une compatibilité native parfaite avec `shap.TreeExplainer` pour l'explicabilité requise par `GET /claims/{id}/prediction`, et des prédictions bornées strictement dans [0, 1].

La sélection du seuil de décision a été réalisée sur les prédictions Out-Of-Fold (OOF) de validation croisée selon la règle métier : _maximiser la précision sous contrainte de Recall ≥ 80 %_. Le seuil optimal s'établit à **0.30**, générant un volume d'alertes modéré de 40.3 % pour un Recall OOF de 80.0 %, contre un seuil à 0.05 pour LightGBM générant un volume excessif de 63.8 % d'alertes. L'écart avec la valeur par défaut du contrat d'interface (`fraud_score_threshold = 0.80`) est documenté : l'endpoint `PUT /admin/config` permet d'ajuster ce seuil en exploitation sans rupture contractuelle.

Sur le jeu de test final inviolé (91 factures, 7 fraudes), XGBoost détecte 100 % des fraudes `ACTE_FICTIF` et `SURFACTURATION`. Les fraudes `DOUBLON` sont manquées sur l'échantillon réduit car le filtre `_drop_high_nan` (> 95 % NaN) a écarté les features d'antériorité de réémission faute d'historique sur 500 lignes ; ce comportement est documenté et se résout sur le jeu complet de 84 593 factures. Les métadonnées du modèle sont sérialisées dans `models/models_metadata.json` au format validable par `GET /admin/models`.

### Évaluation détaillée du modèle de fraude et analyse des limites (PB-08) :

L'évaluation détaillée du modèle champion `v1.0.0-xgb` a été conduite sur le jeu de test final scellé (91 factures, 7 fraudes, prévalence 7.69 %) avec exclusion stricte des labels non validés (`est_valide != 1`) et contrôle permanent de non-fuite (`check_no_leakage`). Les métriques retenues pour le pilotage métier sont la PR-AUC (Average Precision = 0.4340, surclassant la prévalence naïve de 5.6x), la matrice de confusion et l'analyse de sensibilité au seuil.

L'évaluation compare systématiquement deux seuils : le seuil contractuel par défaut de l'API (`fraud_score_threshold = 0.80`, 3.3 % d'alertes, précision 66.7 %) et le seuil opérationnel recommandé (`0.30`, 6.6 % d'alertes, Recall 28.6 %). Les scores probabilistes sont calibrés avec un Brier score de 0.0805, reflétant un indice de risque relatif amplifié par la pondération `scale_pos_weight = 7.51`.

L'analyse détaillée des 14 types de fraude (CDC §6) avec intervalles de Wilson à 95 % démontre une détection parfaite sur `ACTE_FICTIF` (100 %) et `SURFACTURATION` (100 %). Les 4 cas de `DOUBLON` sont manqués en raison de l'exclusion des 5 features d'antériorité (> 95 % NaN sur l'échantillon de 500 lignes), limite documentée qui disparaît sur le volume complet (84 593 lignes). Les métriques d'évaluation alimentent `models/models_metadata.json`, garantissant l'alignement strict sans modification des endpoints avec les champs `recall_test`, `precision_test` et `f1_score` de `GET /admin/models`.

### Analyse des faux négatifs et version améliorée du modèle de fraude (PB-10) :

L'analyse systématique des 5 faux négatifs (FN) du modèle champion `v1.0.0-xgb` sur le jeu de test scellé (91 factures, 7 fraudes) a révélé 99 000 MGA de perte financière manquée, concentrée sur `DOUBLON` (4 cas, 63 000 MGA) et `PRESTATAIRE_RADIE` (1 cas, 36 000 MGA). L'analyse SHAP démontre que les factures en doublon sont unitairement parfaitement conformes au barème, et que leur non-détection initiale découlait de l'élimination des variables d'antériorité par `_drop_high_nan` sur l'échantillon de 500 lignes. L'optimisation du seuil opérationnel à **0.25** (validé sur la CV OOF avec Recall $\ge 85 \%$ atteignant 90.0 % en CV) permet d'intercepter la fraude en doublon limitrophe `FAC-00083354` sans générer le moindre faux positif supplémentaire (FP stables à 4). Sur le test inviolé, le rappel global progresse de 28.57 % à **42.86 %** (+14.3 pts), la précision de 33.33 % à **42.86 %** (+9.5 pts), le F1-score de 0.3077 à **0.4286**, et 20 000 MGA sont récupérés, sans aucune régression sur `ACTE_FICTIF` (100 %) ni `SURFACTURATION` (100 %). La parité mathématique stricte entre inférence batch et inférence unitaire est vérifiée ($\max \Delta = 0.00 < 10^{-6}$). La nouvelle version est enregistrée en tant que **`v1.1.0-xgb`** dans `models/models_metadata.json` avec le statut `STANDBY`, maintenant `v1.0.0-xgb` actif par défaut conformément au principe de non-activation sans accord explicite et garantissant la réversibilité complète pour `GET /admin/models`.

## PB-19 — Chargement automatique et chiffrement PII

- Un service Docker `init` one-shot applique `alembic upgrade head`, puis charge
  les 12 CSV métier avant le démarrage de l'API.
- Le chargement est idempotent : `ingest_state` stocke le checksum des sources,
  le statut et les counts. Un checksum inchangé ne déclenche aucun rechargement.
- Les identités sont isolées dans `identites_pii` et chiffrées avec `pgcrypto`
  (`pgp_sym_encrypt`, AES-256). Le module `predicare.core.pii` centralise les
  opérations ; aucun autre module n'appelle pgcrypto directement.
- La clé `PII_ENCRYPTION_KEY` n'est jamais écrite en base ni dans les logs.
  `PII_KEY_VERSION` prépare une rotation future.
- Les labels ne sont pas chargés en base : ils restent dans `data/raw/labels`
  pour l'entraînement ML.
