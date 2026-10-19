# Pipeline d'ingestion et de nettoyage des données (PB-04)

Ce document décrit le fonctionnement du pipeline d'ingestion et de nettoyage des 12 CSV métiers et des fichiers de labels, conformément aux exigences de **PB-04** et aux besoins des consommateurs **PB-05** (Feature Engineering) et **PB-19** (Chargement automatique idempotent en base PostgreSQL).

---

## 1. Principes et garanties

1. **Rejouabilité et déterminisme** : Aucune donnée aléatoire non contrôlée ni horodatage dans les fichiers de données. Deux exécutions successives produisent des octets identiques.
2. **Écriture atomique** : Écriture dans un fichier temporaire `.tmp` puis renommage atomique via le système de fichiers, évitant les corruptions en cas d'interruption.
3. **Respect strict du RGPD / PII** : La table `identites_pii` est validée en mémoire mais n'est **jamais écrite en clair** dans `data/processed/` sans le drapeau explicite `--export-pii-unencrypted`. Le chiffrement en base relève de PB-19.
4. **Conservation des signaux métier (§6)** : Les anomalies métier (prix hors barème, ordonnances périmées, doublons de facturation, etc.) ne sont **jamais supprimées** car elles constituent les signaux indispensables à la détection de fraude.
5. **Absence d'imputation** : Les valeurs manquantes structurelles (`ordonnance_id` absent pour les soins directs, `motif_rejet` absent pour les factures payées) restent `null`.
6. **Isolation de la fuite de données (Data Leakage)** : Les colonnes `statut`, `motif_rejet`, `montant_pris_en_charge` et `date_traitement` sont conservées dans la table `factures` (requises par l'API) mais sont exportées via la constante `LEAKAGE_COLUMNS` pour être exclues des features par PB-05.

---

## 2. Commandes d'exécution

### Exécution standard (traitement complet des 12 CSV)

```bash
make ingest
# ou directement :
PYTHONPATH=src python -m predicare.db.ingest
```

---

## 3. Interface Python pour les taches futures

Le module `src/predicare/db/ingest.py` expose directement :

```python
from predicare.db.ingest import clean_all
from predicare.db.schemas import LEAKAGE_COLUMNS

# Chargement et nettoyage en mémoire (sans dépendance PostgreSQL)
tables, quality_report = clean_all(raw_dir="data/raw")

# Accès direct aux DataFrames typés
df_factures = tables["factures"]
df_lignes = tables["lignes_facture"]
df_assures = tables["assures"]

# PB-05 : Exclusion immédiate des variables de fuite
features_candidates = [col for col in df_factures.columns if col not in LEAKAGE_COLUMNS]
```

## 4. Schéma des sorties (data/processed/)

- referentiel_actes.csv (58 lignes)
- referentiel_medicaments.csv (28 lignes)
- garanties.csv (27 lignes)
- prestataires.csv (251 lignes)
- grille_tarifaire.csv (3 242 lignes)
- contrats.csv (1 500 lignes)
- assures.csv (4 459 lignes)
- ordonnances.csv (47 804 lignes)
- ordonnance_lignes.csv (82 175 lignes)
- factures.csv (84 593 lignes)
- lignes_facture.csv (123 270 lignes)
- labels_fraude.csv (84 593 lignes - stocké séparément)
- labels_prestataires.csv (251 lignes - stocké séparément)
- qualite_rapport.json (rapport d'intégrité, rejets, doublons et valeurs nulles)
