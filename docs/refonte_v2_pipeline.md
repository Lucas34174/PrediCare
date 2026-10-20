# Refonte v2 — pipeline complet PB-09 → PB-14

## 1. Objectif

Repartir des **12 CSV sources** et du **référentiel métier des 14 types de
fraude** pour reconstruire :

1. les labels de fraude (labels faibles, faute de vérité terrain) ;
2. le dataset d'entraînement ;
3. l'EDA ;
4. les règles PB-09 ;
5. le modèle PB-10 ;
6. le registre PB-11 ;
7. le service et l'explicabilité PB-12 ;
8. l'équité et la robustesse PB-13 ;
9. le monitoring et le lot jury PB-14.

La version précédente (`v1.1.0`, proxy `CONTROLE_MEDICAL`) reste archivée et
restaurable. La nouvelle version est `v2.0.0-weak`.

## 2. Sources et lignage

| Source | Volume | Usage |
|---|---:|---|
| `factures.csv` | 84 593 | Facture, montant, dates, statut |
| `lignes_facture.csv` | 123 270 | Actes, médicaments, quantités, prix |
| `ordonnances.csv` | 47 804 | Prescription, validité, prescripteur |
| `ordonnance_lignes.csv` | 82 175 | Lignes prescrites |
| `assures.csv` | 4 459 | Profil, ville, adhésion, radiation |
| `contrats.csv` | 1 500 | Couverture, formule, dates |
| `prestataires.csv` | 251 | Type, spécialité, convention, jours |
| `garanties.csv` | 27 | Taux de remboursement |
| `grille_tarifaire.csv` | 3 242 | Tarifs pratiqués |
| `referentiel_actes.csv` | 58 | Tarifs max, profil requis |
| `referentiel_medicaments.csv` | 28 | Prix de référence |
| `identites_pii.csv` | — | Identités (non utilisées comme features) |

Le référentiel métier `fraudes_factures.csv` définit les 14 types :
SURFACTURATION, QUANTITE_EXCESSIVE, UPCODING, LIGNES_NON_PRESCRITES,
SUBSTITUTION_PRODUIT, ORDONNANCE_EXPIREE, SOINS_JOUR_FERME, DOUBLON,
FRACTIONNEMENT, SURCONSOMMATION, ACTE_FICTIF, INCOHERENCE_PROFIL,
PRESTATAIRE_RADIE, HORS_COUVERTURE.

## 3. Étape 1 — Labels faibles

Module : `src/predicare/ml/weak_labels.py`
Sorties : `data/raw/labels/labels_fraude.csv`,
`data/raw/labels/weak_labels_manifest.json`,
`data/raw/labels/signaux_faibles.csv`.

- 19 signaux calculés depuis les 12 CSV ;
- 3 niveaux : haute (6 021), moyenne (2 933), faible (27 147 candidats) ;
- calibration à la prévalence connue de l'EDA : **7 347 positifs / 84 593
  (8,69 %)** ;
- 1 326 positifs moyens retenus, 1 507 candidats moyens non retenus ;
- type principal indicatif + `types_fraude` multi-label.

Détail : `docs/weak_labels.md`.

## 4. Étape 2 — Dataset d'entraînement

Module : `src/predicare/ml/dataset_fraude.py`
Sorties : `data/processed/dataset_fraude_v2.csv`,
`data/processed/dataset_fraude_v2_manifest.json`.

- jointure des labels faibles sur le dataset Phase 4 (77 879 factures) ;
- cible `cible = est_fraude` ;
- **39 variables de règles exclues** pour éviter la circularité ;
- 60 features comportementales ;
- poids de supervision faible : 1,0 / 0,8 / 0,3 / 1,0 ;
- splits chronologiques : train 57 573, validation 9 853, test 10 453.

Variables exclues (extrait) : `ecart_tarif_reference`,
`quantite_excedentaire`, `nb_lignes_non_prescrites`,
`surconsommation_ordonnance`, `doublon_potentiel`,
`prestataire_ferme_jour_soin`, `upcoding_majoration_indue`,
`convention_terminee_au_soin`, `nb_alertes_metier`, `score_regles_metier`,
`motif_rejet`, `statut`. La liste complète est dans le manifeste.

## 5. Étape 3 — EDA

Module : `src/predicare/ml/eda.py`
Sortie de référence : `reports/eda_fraude_v2/rapport_eda_fraude.md`
(dataset d'entraînement, 77 879 factures). Une EDA complémentaire du dataset
28 features de `dataset.py` est conservée dans `reports/eda_fraude/`.

| Indicateur | Valeur |
|---|---:|
| Factures modélisables | 77 879 |
| Positifs | 6 762 (8,68 %) |
| Prévalence train | 8,78 % |
| Prévalence validation | 8,26 % |
| Prévalence test | 8,54 % |
| Montant moyen positif | 126 488 |
| Montant moyen négatif | 29 807 |
| Montant total positifs | 855,3 M |

Types de facture à fort lift : HOSPITALISATION 7,75, MATERNITE 2,35,
IMAGERIE 2,33, KINÉSITHÉRAPIE 1,57, LABORATOIRE 1,33.

Top prestataires à risque : `PRE-00162` (33,57 % de positifs, lift 3,87),
`PRE-00155` (27,31 %, lift 3,15), `PRE-00037` (35,25 %, lift 4,06).

> Le dataset `dataset_ml.csv` (28 features de règles) sert à l'EDA
> diagnostique et à la traçabilité des règles ; il n'est pas utilisé pour
> entraîner le modèle, car ses features encodent directement les règles de
> labellisation. Le dataset d'entraînement est `dataset_fraude_v2.csv`
> (60 features comportementales).

## 6. Étape 4 — Règles PB-09

Module : `src/predicare/ml/prescription.py`
Sortie : `reports/ml/pb09/alertes_prescription.csv`.

| Code | Factures alertées | Précision | Rappel global | Lift |
|---|---:|---:|---:|---:|
| `DOUBLON_PRESCRIPTION` | 3 938 | 8,81 % | 4,72 % | 1,01 |
| `SURCONSOMMATION` | 1 468 | 100 %* | 19,98 % | 11,51* |
| `LIGNES_NON_PRESCRITES` | 1 276 | 100 %* | 17,37 % | 11,51* |
| `ORDONNANCE_ANTIDATEE` | 113 | 100 % | 1,54 % | 11,51 |
| `PRESCRIPTEUR_INCOMPATIBLE` | 21 | 4,76 % | 0,01 % | 0,55 |
| `PRESCRIPTEUR_RADIE` | 2 | 100 % | 0,03 % | 11,51 |

\* Précision **circulaire** : ces règles ont servi à construire les labels.

Global : 6 449 factures alertées, précision 44,0 %, rappel 38,6 %, lift 5,07,
6,8 % du montant total.

**Audit** : `DOUBLON_PRESCRIPTION` n'apporte aucun lift (1,01) et
`PRESCRIPTEUR_INCOMPATIBLE` est sous la prévalence (0,55). Ces deux règles
doivent être revues ou désactivées.

Détail : `reports/ml/pb09/evaluation_pb09.json`.

## 7. Étape 5 — Modèle PB-10

Module : `src/predicare/ml/training_v2.py`
Sortie : `models/v2.0.0-weak/model.joblib`.

| Modèle | Déséquilibre | PR-AUC validation | PR-AUC test |
|---|---|---:|---:|
| LightGBM | poids faibles | 0,7303 | 0,7221 |
| LightGBM | aucun | 0,7484 | 0,7362 |
| **XGBoost** | **poids faibles** | **0,7677** | **0,7541** |
| LightGBM | SMOTE | 0,6993 | 0,6903 |

Test (seuil calibré 0,0461, rappel cible 80 %) :

| Métrique | Valeur |
|---|---:|
| PR-AUC | 0,7541 (IC95 0,7274–0,7782) |
| ROC-AUC | 0,9032 |
| Rappel | 0,7805 |
| Précision | 0,4199 |
| F1 | 0,5460 |
| Brier | 0,0358 |
| ECE | 0,0092 |
| Alertes | 1 660 (15,88 %) |
| Lift | 4,91 |

À budget égal (710 alertes sur le test) :

| Approche | Précision | Rappel |
|---|---:|---:|
| PB-09 | 0,4197 | 0,3337 |
| **Modèle v2 top 710** | **0,8127** | **0,6461** |
| Modèle v2 seuil | 0,4199 | 0,7805 |

## 8. Étape 6 — Registre PB-11

Module : `src/predicare/ml/registry.py`
Sortie : `models/registry.json`.

| Version | Statut |
|---|---|
| `v2.0.0-weak` | **production** |
| `v1.1.0` | archive |
| `v1.0.0` | archive |

Chaque version est identifiée par un SHA-256 et un artefact. Le rollback est
disponible via `python -m predicare.ml.registry rollback v1.1.0`, avec
restauration du magasin `data/raw/dataset_cm.csv`.

## 9. Étape 7 — Service, SHAP et dérive PB-12

Modules : `service.py`, `explain.py`, `drift.py`.

- service : `predire_facture(facture_id, top_k=5)` renvoie le score, la
  décision, la version et les facteurs SHAP ;
- explicabilité : top 3–5 facteurs avec valeur, impact et description ;
- dérive train → test : 60 variables, 45 `ok`, 0 vigilance, 1 alerte
  (`assure_taux_rejet_hist_lisse`, PSI 0,366), verdict
  `derive_significative` ;
- lot jury : 20 factures, 15 alertes, JSON + Markdown dans
  `reports/ml/pb12/lot_jury_20.*`.

Exemple SHAP (`FAC-00027743`, probabilité 0,9784) :
`ratio_montant_moy_hist_prest` +2,559, `quantite_max_ligne` +2,005,
`type_ordonnance=MEDICAMENTS` +1,110.

## 10. Étape 8 — Équité et robustesse PB-13

Module : `fairness.py`, `robustness.py`
Sorties : `reports/ml/pb14/synthese_equite.json`,
`docs/equity_audit_modele.md`, `tests/fixtures/factures_test_set.json`.

| Dimension | Écart TPR max−min | Alerte |
|---|---:|---|
| Sexe | 0,0003 | Non |
| Âge | 0,0906 | Non |
| Formule | 0,0794 | Non |
| Ville assuré | 0,1061 | **Oui** |
| Ville prestataire | 0,1375 | **Oui** |

Robustesse : 10 factures valides + 10 invalides, 10/10 invalides détectés.

## 11. Étape 9 — Monitoring PB-14

Indicateurs recommandés :

| Indicateur | Fréquence | Seuil |
|---|---|---|
| PSI des variables | mensuel | > 0,25 sur 2 mois |
| Taux d'alerte | hebdomadaire | ±20 % |
| Précision auditée | mensuel | < 30 % |
| Rappel audité | trimestriel | < 70 % |
| Écart TPR ville | mensuel | > 10 points |
| ECE | mensuel | > 0,05 |

Le lot de 20 factures (`reports/ml/pb12/lot_jury_20.md`) sert de support de
démonstration : 5 positifs haute confiance, 5 positifs moyenne, 5 vrais
négatifs, 5 faux positifs, avec explications SHAP.

## 12. Résultats clés

| Indicateur | v1.1.0 (proxy) | v2.0.0-weak |
|---|---:|---:|
| Cible | `CONTROLE_MEDICAL` | label faible 14 types |
| Positifs test | 128 | 893 |
| PR-AUC test | 0,1555 | **0,7541** |
| ROC-AUC test | 0,9552 | 0,9032 |
| Rappel | 0,789 | 0,7805 |
| Précision | 0,138 | **0,4199** |
| Alertes | 732 | 1 660 |

Les deux versions ne sont **pas comparables directement** : la cible, le
périmètre et le nombre de positifs diffèrent. La v2 est plus précise et plus
riche (14 types, SHAP, équité, dérive), mais elle repose sur des labels
reconstruits.

## 13. Limites

1. Pas de vérité terrain ; métriques optimistes.
2. Circularité partielle règles/features.
3. Types UPCODING et FRACTIONNEMENT sous-représentés.
4. Prévalence calibrée à 7 347 positifs.
5. Écarts d'équité par ville.
6. Dérive de `assure_taux_rejet_hist_lisse`.
7. Données synthétiques.
8. Aucun audit humain.

## 14. Artefacts

| Artefact | Chemin |
|---|---|
| Labels faibles | `data/raw/labels/labels_fraude.csv` |
| Manifeste labels | `data/raw/labels/weak_labels_manifest.json` |
| Dataset v2 | `data/processed/dataset_fraude_v2.csv` |
| Manifeste dataset | `data/processed/dataset_fraude_v2_manifest.json` |
| EDA (dataset d'entraînement) | `reports/eda_fraude_v2/rapport_eda_fraude.md` |
| EDA (diagnostic 28 features) | `reports/eda_fraude/rapport_eda_fraude.md` |
| Alertes PB-09 | `reports/ml/pb09/alertes_prescription.csv` |
| Évaluation PB-09 | `reports/ml/pb09/evaluation_pb09.json` |
| Modèle v2 | `models/v2.0.0-weak/model.joblib` |
| Métriques v2 | `reports/ml/v2/metrics.json` |
| Scores test | `reports/ml/v2/scores_test.csv` |
| Registre | `models/registry.json` |
| Équité | `reports/ml/pb14/synthese_equite.json` |
| Dérive | `reports/ml/pb12/synthese_derive.json` |
| Lot jury | `reports/ml/pb12/lot_jury_20.md` |
| Model card | `docs/model_card_v2.md` |
| Labels faibles (doc) | `docs/weak_labels.md` |
