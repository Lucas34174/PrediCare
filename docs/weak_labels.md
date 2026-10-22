# Labels faibles de fraude — méthodologie et limites

## 1. Pourquoi des labels faibles ?

Les fichiers de vérité terrain `labels_fraude.csv` et `labels_prestataires.csv`
ne sont plus disponibles dans le projet, les sauvegardes ou l'historique Git.
La refonte v2 reconstruit donc une **cible faible** (weak supervision) à partir
des sources métier encore présentes :

- les **12 CSV** du jeu de données PrediCare ;
- le **référentiel métier** des 14 types de fraude facture
  (`rapports_predicare/referentiel_feuilles/fraudes_factures.csv`) ;
- les **précisions mesurées dans l'EDA d'origine**
  (`PrediCare/notebooks/01_eda_exploration_donnees.ipynb`), lorsque les vrais
  labels existaient encore.

> **Avertissement central** : ces labels ne sont **pas** des fraudes
> confirmées. Ce sont des suspicions déterministes, produites par des règles.
> Toute communication doit les présenter comme « labels reconstruits » ou
> « signaux de fraude », jamais comme une vérité terrain.

Le module de référence est `src/predicare/ml/weak_labels.py`.

## 2. Signaux et précision attendue

Les 19 signaux sont calculés facture par facture. Leur précision est celle
mesurée dans l'EDA d'origine (quand les vrais labels existaient).

| Signal | Type visé | Précision EDA | Niveau | Factures |
|---|---|---:|---|---:|
| `qte` | QUANTITE_EXCESSIVE | 1,000 | haute | 564 |
| `non_prescrites` | LIGNES_NON_PRESCRITES | 1,000 | haute | 1 276 |
| `substitution` | SUBSTITUTION_PRODUIT | 1,000 | haute | 531 |
| `expiree` | ORDONNANCE_EXPIREE | 1,000 | haute | 594 |
| `ferme` | SOINS_JOUR_FERME | 0,985 | haute | 474 |
| `doublon_copie` | DOUBLON | 0,847 | haute | 679 |
| `surf_grille` | SURFACTURATION | 0,842 | haute | 1 974 |
| `fictif_autre` | ACTE_FICTIF | 1,000 | haute | 175 |
| `profil` | INCOHERENCE_PROFIL | 1,000 | haute | 382 |
| `radie_fin` | PRESTATAIRE_RADIE | 1,000 | haute | 157 |
| `hors_couv` | HORS_COUVERTURE | 1,000 | haute | 186 |
| `surconso` | SURCONSOMMATION | 0,512 | moyenne | 1 468 |
| `doublon_tous` | DOUBLON | 0,456 | moyenne | 1 350 |
| `surf_acte` | SURFACTURATION | 0,423 | moyenne | 2 202 |
| `fictif_sans_ord` | ACTE_FICTIF | 0,317 | faible | 863 |
| `fraction` | FRACTIONNEMENT | 0,237 | faible | 4 168 |
| `upcoding` | UPCODING | 0,200 | faible | 329 |
| `radie_statut` | PRESTATAIRE_RADIE | 0,134 | faible | 3 063 |
| `surf_med` | SURFACTURATION | 0,110 | faible | 24 697 |

Les règles sont implémentées dans `weak_labels.py` :

1. **Surfacturation** : prix unitaire > tarif max de l'acte, > prix de
   référence du médicament, ou > tarif pratiqué du prestataire.
2. **Quantité excessive** : quantité facturée > quantité prescrite.
3. **Lignes non prescrites** : code facturé absent de l'ordonnance.
4. **Substitution** : médicament hors ordonnance à prix élevé.
5. **Ordonnance expirée** : délai soin − prescription > validité (30 j optique,
   10 j sinon).
6. **Soins jour fermé** : jour de la semaine absent des jours d'ouverture.
7. **Doublon** : même assuré, prestataire, montant et date de soin.
8. **Fractionnement** : plusieurs factures même assuré/prestataire/jour.
9. **Surconsommation** : une ordonnance facturée par plusieurs prestataires.
10. **Acte fictif** : acte à ordonnance requise sans ordonnance, ou ordonnance
    d'un autre assuré.
11. **Incohérence profil** : sexe/âge incompatible avec l'acte.
12. **Prestataire radié** : soin après fin de convention ou statut `RADIE`.
13. **Hors couverture** : soin avant adhésion, après radiation, hors contrat.
14. **Upcoding** : consultation de spécialiste facturée par un généraliste ou
    par un spécialiste d'une autre spécialité.

### Ancres 100 % fraude

Quatre motifs de rejet étaient associés à 100 % de fraude dans l'EDA :

| Motif de rejet | Type associé | Volume |
|---|---|---:|
| `CONTROLE_MEDICAL` | CONTROLE_MEDICAL | 998 |
| `ORDONNANCE_PERIMEE` | ORDONNANCE_EXPIREE | 246 |
| `HORS_PERIODE_COUVERTURE` | HORS_COUVERTURE | 69 |
| `PRODUIT_NON_REMBOURSABLE` | HORS_COUVERTURE | 3 |

`motif_rejet` reste **exclu des variables du modèle** : il ne doit jamais
servir de feature.

## 3. Construction des labels

### 3.1 Trois niveaux

- **Haute confiance** : au moins un signal de précision ≥ 0,80, ou une ancre
  100 % fraude. Volume : **6 021** factures.
- **Moyenne confiance** : aucun signal haute, mais au moins un signal moyen
  (`surconso`, `doublon_tous`, `surf_acte`). Volume : **2 933** factures.
- **Faible confiance** : uniquement des signaux faibles. Volume : **27 147**
  factures. Ces factures sont des **candidats**, pas des positifs.
- **Aucun signal** : 48 592 factures.

### 3.2 Calibration à la prévalence connue

L'EDA d'origine comptait **7 347 fraudes sur 84 593 factures (8,69 %)**. La
base haute confiance (6 021) est conservée intégralement. Pour atteindre la
prévalence connue, **1 326** factures moyennes sont retenues par ordre
décroissant de :

1. précision attendue du meilleur signal ;
2. nombre de signaux moyens ;
3. nombre de signaux faibles.

Les 1 507 autres factures moyennes restent des **candidates** (`candidat=1`,
`est_fraude=0`). Cette calibration est explicitement **supervisée par la
prévalence** : elle ne prouve pas que les 1 326 factures sont frauduleuses,
elle aligne seulement le volume sur ce que l'EDA indiquait.

### 3.3 Résultat

| Niveau | Factures | Part |
|---|---:|---:|
| Positifs haute confiance | 6 021 | 7,12 % |
| Positifs moyenne retenus | 1 326 | 1,57 % |
| **Total positifs** | **7 347** | **8,69 %** |
| Candidats (dont positifs) | 36 001 | 42,56 % |
| Aucun signal | 48 592 | 57,44 % |

## 4. Schéma de sortie

`data/raw/labels/labels_fraude.csv` contient 84 593 lignes et 15 colonnes :

| Colonne | Description |
|---|---|
| `facture_id` | Clé facture |
| `est_fraude` | 1 = retenu comme fraude probable, 0 sinon |
| `type_fraude` | Type principal indicatif (ou `AUCUN`) |
| `detail_fraude` | Signaux déclenchés, séparés par `;` |
| `est_valide` | 1 pour toutes les lignes |
| `motif_invalidite` | Vide |
| `confiance` | `haute`, `moyenne`, `faible`, `aucune` |
| `candidat` | 1 si au moins un signal (positif ou non) |
| `types_fraude` | Tous les types déclenchés, séparés par `;` |
| `precision_attendue` | Précision du meilleur signal déclenché |
| `tier` | `haute`, `moyenne_retenue`, `candidate_moyenne`, `candidate_faible`, `aucune` |
| `n_haute`, `n_moyenne`, `n_faible` | Nombre de signaux par niveau |
| `source` | `weak_labels_v1` |

Le manifeste `data/raw/labels/weak_labels_manifest.json` documente les
volumes, les règles, les précisions, la calibration et les limites.

## 5. Distribution des types

| Type | Labels faibles (positifs) | EDA d'origine | Écart |
|---|---:|---:|---:|
| SURFACTURATION | 1 644 | 1 272 | +372 |
| SURCONSOMMATION | 1 123 | 469 | +654 |
| DOUBLON | 957 | 909 | +48 |
| LIGNES_NON_PRESCRITES | 570 | 733 | −163 |
| QUANTITE_EXCESSIVE | 564 | 568 | −4 |
| SUBSTITUTION_PRODUIT | 531 | 368 | +163 |
| ORDONNANCE_EXPIREE | 499 | 502 | −3 |
| INCOHERENCE_PROFIL | 379 | 379 | 0 |
| SOINS_JOUR_FERME | 346 | 227 | +119 |
| ACTE_FICTIF | 214 | 496 | −282 |
| HORS_COUVERTURE | 180 | 195 | −15 |
| PRESTATAIRE_RADIE | 159 | 147 | +12 |
| CONTROLE_MEDICAL | 111 | — | — |
| UPCODING | 36 | 742 | −706 |
| FRACTIONNEMENT | 34 | 340 | −306 |

Le type principal est **indicatif** : les règles se chevauchent et une facture
peut déclencher plusieurs types (`types_fraude`). Les écarts reflètent la
difficulté à reproduire certains types :

- **UPCODING** et **FRACTIONNEMENT** sont sous-représentés faute de signaux
  fiables ;
- **SURCONSOMMATION** et **SURFACTURATION** sont sur-représentés car leurs
  règles sont plus larges ;
- **ACTE_FICTIF** est sous-représenté car le signal `fictif_sans_ord` est
  imprécis et le signal `fictif_autre` est rare.

## 6. Limites méthodologiques

1. **Pas de vérité terrain.** Les métriques du modèle mesurent la capacité à
   reproduire les règles, pas la fraude réelle.
2. **Circularité.** Les règles PB-09 (`SURCONSOMMATION`,
   `LIGNES_NON_PRESCRITES`) ont servi à construire les labels. Leur précision
   apparente est donc circulaire. Les variables de règles sont exclues des
   features du modèle (voir `dataset_fraude.py`), mais les variables
   comportementales restent corrélées aux règles.
3. **Calibration à la prévalence.** Le nombre de positifs est fixé à 7 347
   d'après l'EDA. Une prévalence réelle différente changerait le seuil et les
   métriques.
4. **Type principal.** L'attribution d'un type unique est arbitraire lorsque
   plusieurs règles se déclenchent. `types_fraude` conserve l'information
   multi-label.
5. **Couverture.** Les 14 types ne sont pas également détectables. Les types
   non couverts (UPCODING, FRACTIONNEMENT) doivent être traités par des règles
   dédiées ou des données supplémentaires.
6. **Données synthétiques.** Le jeu de données est généré ; les résultats
   reflètent le générateur et ne se généralisent pas nécessairement à des
   données réelles.
7. **Pas de validation humaine.** Aucun expert n'a confirmé les labels. Un
   échantillon stratifié devrait être audité avant toute décision métier.

## 7. Utilisation dans le pipeline

```bash
# 1. Reconstruire les labels faibles
PYTHONPATH=src python -m predicare.ml.weak_labels \
  --raw-dir ../CohorteAI_datagen/dataset \
  --out-dir data/raw/labels \
  --target-positifs 7347

# 2. Construire le dataset d'entraînement (features comportementales,
#    variables de règles exclues)
PYTHONPATH=src python -m predicare.ml.dataset_fraude

# 3. EDA
PYTHONPATH=src python -m predicare.ml.eda \
  --dataset data/processed/dataset_ml.csv \
  --hors-modele data/processed/factures_hors_modele.csv \
  --out-dir reports/eda_fraude

# 4. Entraînement
PYTHONPATH=src python -m predicare.ml.training

# 5. Évaluation des règles PB-09
PYTHONPATH=src python -m predicare.ml.eval_rules

# 6. Audits
PYTHONPATH=src python -m predicare.ml.drift
PYTHONPATH=src python -m predicare.ml.fairness
PYTHONPATH=src python -m predicare.ml.robustness

# 7. Lot de 20 factures pour le jury
PYTHONPATH=src python -m predicare.ml.batch_jury
```

## 8. Recommandations

- **Ne pas** présenter les 7 347 positifs comme des fraudes confirmées.
- **Auditer** un échantillon de 100 à 200 factures (strates haute/moyenne/
  candidate) avec des experts métier.
- **Prioriser** les types à forte précision et fort enjeu financier
  (SURFACTURATION, LIGNES_NON_PRESCRITES, SUBSTITUTION_PRODUIT).
- **Compléter** les règles UPCODING et FRACTIONNEMENT.
- **Revoir** la règle PB-09 `DOUBLON_PRESCRIPTION` : 3 938 factures alertées
  pour une précision de 8,8 % et un lift de 1,01 (aucun gain).
- **Surveiller** la dérive de `assure_taux_rejet_hist_lisse` (PSI 0,366) et
  les écarts de rappel par ville.
- **Documenter** toute utilisation dans la model card et le rapport de jury.
