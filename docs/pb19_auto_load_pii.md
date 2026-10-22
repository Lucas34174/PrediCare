# PB-19 — Chargement automatique et PII chiffrées

## 1. Objectif

Au premier démarrage de la plateforme :

1. le schéma PostgreSQL est migré automatiquement ;
2. les 12 CSV métier sont chargés une seule fois ;
3. les identités sont isolées dans `identites_pii` et chiffrées avec `pgcrypto` ;
4. les démarrages suivants ne rechargent pas les données.

Le service Docker `init` exécute ce bootstrap avant le démarrage de l'API.

## 2. Séquence de démarrage

```text
db (healthy)
  └── init (one-shot)
        ├── attente PostgreSQL
        ├── verrou advisory
        ├── alembic upgrade head
        ├── test canari de PII_ENCRYPTION_KEY
        ├── lecture de ingest_state
        ├── clean_all() sur /data/source
        ├── chargement ordonné (FK)
        ├── chiffrement des identités
        └── ingest_state.status = completed
              └── api (healthy)
                    └── front
```

`init` est idempotent : si `ingest_state.status = completed` et que le checksum
des CSV n'a pas changé, il sort en succès sans recharger.

## 3. Sources de données

Le service `init` monte :

```text
../CohorteAI_datagen/dataset  →  /data/source  (lecture seule)
```

Il attend les 12 fichiers suivants :

```text
referentiel_actes.csv
referentiel_medicaments.csv
garanties.csv
prestataires.csv
grille_tarifaire.csv
contrats.csv
assures.csv
identites_pii.csv
ordonnances.csv
ordonnance_lignes.csv
factures.csv
lignes_facture.csv
```

Les labels (`labels_fraude.csv`, `labels_prestataires.csv`) ne sont pas chargés
en base : ils restent dans `data/raw/labels` pour l'entraînement ML.

## 4. Chiffrement des PII

La table `identites_pii` ne contient que :

- `assure_id` (clé étrangère) ;
- `nom_chiffre`, `prenoms_chiffre`, `date_naissance_chiffre` ;
- `telephone_chiffre`, `email_chiffre`, `adresse_chiffre`, `numero_cin_chiffre` ;
- `pii_key_version`.

Le chiffrement utilise :

```sql
pgp_sym_encrypt(valeur, clé, 'cipher-algo=aes256')
```

La clé est lue dans `PII_ENCRYPTION_KEY`. Elle doit contenir au moins
32 caractères. En production, les valeurs `change_me_*` sont refusées.

Au premier chargement, une valeur canari est chiffrée et stockée dans
`ingest_state.pii_canary`. Aux démarrages suivants, le bootstrap la déchiffre
avec la clé fournie : une clé différente est donc détectée avant tout
rechargement.

Le module central est `src/predicare/core/pii.py`. Aucun autre module ne doit
appeler `pgp_sym_encrypt` ou `pgp_sym_decrypt` directement.

## 5. Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `PII_ENCRYPTION_KEY` | Clé de chiffrement PII | obligatoire |
| `PII_KEY_VERSION` | Version de clé | `1` |
| `SOURCE_DATA_DIR` | Dossier des 12 CSV | `data/raw` |
| `AUTO_LOAD_DATA` | Active le chargement | `true` |
| `FORCE_RELOAD` | Vide et recharge | `false` |

Génération d'une clé :

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 6. Commandes

```bash
# Premier démarrage complet
docker compose up --build -d

# État du bootstrap
make db-status
# ou
docker compose run --rm init python -m predicare.db.bootstrap --status

# Rechargement destructif
make reload-data

# Migrations seules
make migrate
```

## 7. Vérifications

```bash
# Les 12 tables et ingest_state
docker compose exec db psql -U predicare -d predicare -c "\dt"

# État du chargement
docker compose exec db psql -U predicare -d predicare \
  -c "SELECT dataset_key, status, rows_loaded, finished_at FROM ingest_state;"

# Les PII sont bien des bytea
docker compose exec db psql -U predicare -d predicare \
  -c "SELECT assure_id, nom_chiffre FROM identites_pii LIMIT 1;"

# Vérifier le nombre de factures
docker compose exec db psql -U predicare -d predicare \
  -c "SELECT count(*) FROM factures;"
```

Le résultat attendu pour le jeu de référence est :

| Table | Lignes |
|---|---:|
| `factures` | 84 593 |
| `lignes_facture` | 123 270 |
| `assures` | 4 459 |
| `identites_pii` | 4 459 |
| `ordonnances` | 47 804 |
| `ordonnance_lignes` | 82 175 |

## 8. Échecs et reprise

- **CSV manquant** : `init` échoue avec la liste des fichiers absents ; l'API ne démarre pas.
- **Clé PII absente ou invalide** : échec du test canari ; aucun chargement.
- **Erreur pendant le chargement** : transaction annulée ; `ingest_state.status = failed`.
- **Redémarrage après échec** : `init` retente le chargement.
- **Données existantes sans marqueur** : aucun écrasement automatique ; utiliser `FORCE_RELOAD=1`.
- **Checksum différent** : rechargement ignoré par défaut ; utiliser `FORCE_RELOAD=1`.

## 9. Sauvegarde et restauration

`pg_dump` contient les PII sous forme chiffrée. La clé doit être sauvegardée
séparément, sinon les identités sont définitivement illisibles.

```bash
make backup
# La clé PII doit être conservée dans un coffre-fort de secrets.
```

Après restauration, vérifier :

```sql
SELECT count(*) FROM identites_pii;
```

Puis déchiffrer un échantillon avec la clé sauvegardée.

## 10. Limites actuelles

- Le rôle PostgreSQL applicatif reste `predicare` (superutilisateur du compose).
  La séparation `loader` / `app` / `pii_reader` est documentée comme évolution.
- `utilisateurs.nom_complet` et `contrats.souscripteur_nom` restent en clair :
  leur périmètre PII doit être validé avec le DPO.
- La rotation de clé est préparée par `pii_key_version` mais n'est pas encore
  automatisée.
