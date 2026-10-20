# Model card — PrediCare v2.0.0-weak

## 1. Identification

| Champ | Valeur |
|---|---|
| Version | `v2.0.0-weak` |
| Statut | Production (registre PB-11) |
| Modèle | XGBoost (gradient boosting) |
| Cible | `est_fraude` — label faible reconstruit |
| Date d'entraînement | 2026-10-20 |
| Jeu d'entraînement | `data/processed/dataset_fraude_v2.csv` |
| Artefact | `models/v2.0.0-weak/model.joblib` |
| Métadonnées | `models/v2.0.0-weak/metadata.json` |
| Version précédente | `v1.1.0` (archivée, proxy `CONTROLE_MEDICAL`) |

> **Avertissement** : la cible est un **label faible reconstruit par règles**,
> pas une fraude confirmée. Les métriques ci-dessous mesurent la reproduction
> des règles et des signaux comportementaux, pas la fraude réelle. Voir
> `docs/weak_labels.md`.

## 2. Usage prévu

**Utilisation prévue**

- Prioriser les factures à contrôler par l'équipe fraude.
- Fournir un score de risque et des facteurs explicatifs SHAP par alerte.
- Tester des scénarios de budget d'alertes (1 %, 2 %, 3 %, 5 %, 10 %).
- Alimenter le tableau de bord de dérive et l'audit d'équité.

**Hors périmètre**

- Décision automatique de rejet ou de sanction.
- Preuve de fraude ou de culpabilité d'un prestataire ou d'un assuré.
- Utilisation sur des données réelles sans audit humain préalable.
- Prédiction sur des types non couverts par les règles (UPCODING,
  FRACTIONNEMENT) sans validation dédiée.

## 3. Données

### 3.1 Sources

Les 12 CSV du jeu PrediCare :

`factures`, `lignes_facture`, `ordonnances`, `ordonnance_lignes`, `assures`,
`contrats`, `prestataires`, `garanties`, `grille_tarifaire`,
`referentiel_actes`, `referentiel_medicaments`, `identites_pii`.

### 3.2 Périmètre

| Élément | Valeur |
|---|---:|
| Factures sources | 84 593 |
| Factures avec label faible | 84 593 |
| Positifs faibles | 7 347 (8,69 %) |
| Factures modélisables | 77 879 |
| Positifs modélisables | 6 762 (8,68 %) |
| Features | 60 |
| Train | 57 573 (5 055 positifs, 8,78 %) |
| Validation | 9 853 (814 positifs, 8,26 %) |
| Test | 10 453 (893 positifs, 8,54 %) |

Les 6 714 factures non modélisables (dates manquantes, doublons de clé,
embargo temporel) sont exclues. Le split est chronologique : le test est
postérieur au train et à la validation.

### 3.3 Features

Les 60 variables sont **comportementales** :

- montants, volumes, nombre de lignes, quantités ;
- délais soin → facture → réception ;
- ancienneté, âge, sexe, formule, contrat, secteur ;
- type de prestataire, spécialité, niveau tarifaire, note qualité ;
- historique prestataire/assuré (taux de rejet lissé, volumes, ratios) ;
- jour de semaine, week-end, horaires, canal de réception ;
- présence d'ordonnance, d'attestation, d'entente.

**Variables exclues** (39) : toutes les variables qui encodent directement une
règle de labellisation ou une fuite, par exemple `ecart_tarif_reference`,
`quantite_excedentaire`, `nb_lignes_non_prescrites`,
`surconsommation_ordonnance`, `doublon_potentiel`,
`prestataire_ferme_jour_soin`, `upcoding_majoration_indue`,
`convention_terminee_au_soin`, `nb_alertes_metier`, `score_regles_metier`,
`motif_rejet`, `statut`. La liste complète est dans
`data/processed/dataset_fraude_v2_manifest.json`.

> **Circularité résiduelle** : même sans les variables de règles, les variables
> comportementales (montants, historique de rejet) restent corrélées aux
> règles. Le modèle est donc en partie un **distillateur de règles**, pas un
> détecteur indépendant.

## 4. Entraînement

### 4.1 Pondération des labels faibles

| Cas | Poids |
|---|---:|
| Positif haute confiance | 1,0 |
| Positif moyenne confiance | 0,8 |
| Négatif candidat (règle faible) | 0,3 |
| Négatif sans signal | 1,0 |

Les négatifs candidats sont **incertains** : ils peuvent être des fraudes non
détectées. Les sous-pondérer réduit le biais de les traiter comme des négatifs
certains.

### 4.2 Comparaison des stratégies

Sélection sur la **PR-AUC de validation** ; le test n'a servi qu'une fois.

| Modèle | Déséquilibre | PR-AUC validation | PR-AUC test |
|---|---|---:|---:|
| LightGBM | poids faibles | 0,7303 | 0,7221 |
| LightGBM | aucun | 0,7484 | 0,7362 |
| **XGBoost** | **poids faibles** | **0,7677** | **0,7541** |
| LightGBM | SMOTE (0,5) | 0,6993 | 0,6903 |

SMOTE dégrade les performances : les positifs synthétiques ne respectent pas
la structure des règles. La pondération des labels faibles est retenue.

### 4.3 Hyperparamètres

XGBoost retenu : `n_estimators=500`, `learning_rate=0,03`, `max_depth=5`,
`min_child_weight=5`, `subsample=0,85`, `colsample_bytree=0,7`,
`reg_lambda=1,0`, `tree_method=hist`, `eval_metric=aucpr`, graine 42.
La sélection fine n'a pas été refaite : le volume de positifs faibles et la
nature de la cible ne justifient pas une recherche extensive. Les paramètres
LightGBM comparés sont ceux de la v1.1.0 (9 feuilles, 91 échantillons minimum
par feuille), volontairement régularisés.

## 5. Performances

### 5.1 Validation et test

Seuil calibré : **0,0461** (rappel cible 80 % sur la validation).

| Métrique | Validation | Test |
|---|---:|---:|
| PR-AUC | 0,7677 | **0,7541** (IC95 0,7274–0,7782) |
| ROC-AUC | 0,9168 | 0,9032 |
| Rappel | 0,8010 | **0,7805** |
| Précision | 0,4166 | **0,4199** |
| F1 | 0,5481 | 0,5460 |
| Brier | 0,0339 | 0,0358 |
| ECE (10 bins) | 0,0093 | 0,0092 |
| Alertes | 1 565 (15,88 %) | 1 660 (15,88 %) |
| Lift | 5,04 | 4,91 |
| Précision à rappel 80 % | 0,4166 | 0,3846 |

La prévalence de test est de 8,54 %. La PR-AUC de 0,754 est très supérieure à
la prévalence, mais elle est **optimiste** : la cible est construite par des
règles, et les features comportementales en capturent une partie.

### 5.2 Seuils par budget (validation)

| Budget d'alertes | Seuil de probabilité calibrée |
|---:|---:|
| 1 % | 0,9751 |
| 2 % | 0,9645 |
| 3 % | 0,9350 |
| 5 % | 0,7126 |
| 10 % | 0,0884 |

Le score produit est normalisé pour que le seuil calibré vaille **0,8** :
`score = 1 − exp(−p / τ)`, `τ = −seuil / ln(0,2)`. Le seuil reste
surchargeable par `PREDICARE_SEUIL_ALERTE`.

### 5.3 Comparaison avec les règles PB-09

Sur le test, à **budget égal** (710 alertes) :

| Approche | Alertes | Précision | Rappel | Lift |
|---|---:|---:|---:|---:|
| PB-09 (toutes alertes) | 710 | 0,4197 | 0,3337 | 4,91 |
| **Modèle v2 (top 710)** | 710 | **0,8127** | **0,6461** | **9,51** |
| Modèle v2 (seuil produit) | 1 660 | 0,4199 | 0,7805 | 4,91 |

À budget égal, le modèle double la précision et double presque le rappel. Au
seuil produit, il atteint 78 % de rappel avec 42 % de précision.

### 5.4 Exemples SHAP

**Vrai positif — `FAC-00027743`** (label faible `QUANTITE_EXCESSIVE`,
probabilité 0,9784, score 1,0, alerte) :

| Feature | Valeur | Impact SHAP | Lecture |
|---|---:|---:|---|
| `ratio_montant_moy_hist_prest` | 5,03 | +2,559 | Montant 5× supérieur à l'historique du prestataire |
| `quantite_max_ligne` | 5,00 | +2,005 | Quantité maximale élevée sur une ligne |
| `type_ordonnance` | MEDICAMENTS | +1,110 | Ordonnance de médicaments |
| `montant_total` | 80 700 | +0,544 | Montant total élevé |
| `montant_moyen_ligne` | 40 350 | +0,542 | Montant moyen par ligne élevé |

**Faux positif — `FAC-00007762`** (label faible 0, probabilité 0,9639, score
1,0, alerte) :

| Feature | Valeur | Impact SHAP | Lecture |
|---|---:|---:|---|
| `nb_lignes` | — | +1,661 | Nombre de lignes élevé |
| `ratio_montant_moy_hist_prest` | 17,70 | +1,646 | Montant très supérieur à l'historique |
| `montant_total` | 1 321 000 | +0,948 | Montant total très élevé |

Ce faux positif illustre la limite : un montant hors norme déclenche l'alerte
même si la facture n'est pas dans les règles. L'analyse humaine reste
indispensable.

## 6. Équité

Audit sur le test (`reports/ml/pb14/synthese_equite.json`), seuil produit :

| Dimension | Groupes | Écart TPR max−min | Écart FPR max−min | Alerte |
|---|---:|---:|---:|---|
| Sexe | 2 | 0,0003 | 0,0038 | Non |
| Tranche d'âge | 4 | 0,0906 | 0,0353 | Non |
| Formule | 3 | 0,0794 | 0,0176 | Non |
| Ville assuré | 7 | **0,1061** | 0,0555 | **Oui** |
| Ville prestataire | 7 | **0,1375** | 0,0721 | **Oui** |

Les écarts de rappel par ville dépassent le seuil de 10 points. Une ville
prestataire a moins de 5 positifs : l'estimation est instable. Mesures
recommandées :

1. auditer les villes concernées sur un échantillon plus large ;
2. envisager des seuils par sous-groupe **uniquement** si l'écart persiste ;
3. surveiller mensuellement les taux d'alerte par ville ;
4. documenter tout écart résiduel dans le rapport de conformité.

La ville n'est pas une feature : elle est jointe pour l'audit depuis
`assures.ville` et `prestataires.ville`.

## 7. Dérive

Analyse train → test (`reports/ml/pb12/synthese_derive.json`) :

| Indicateur | Valeur |
|---|---:|
| Variables analysées | 60 |
| Variables stables (`ok`) | 45 |
| Vigilance | 0 |
| Alerte | 1 |
| PSI max hors tendance | 0,366 |
| Verdict | `derive_significative` |

Variable en alerte : `assure_taux_rejet_hist_lisse` (PSI 0,366, KS 0,180).
Cette variable mesure le taux de rejet administratif historique de l'assuré ;
elle dérive entre train et test. Recommandations :

- surveiller la variable mensuellement ;
- réentraîner si le PSI reste > 0,25 sur deux fenêtres consécutives ;
- vérifier que la dérive ne crée pas d'écart d'équité supplémentaire.

## 8. Robustesse

`python -m predicare.ml.robustness` génère **20 factures** (10 valides,
10 invalides) et vérifie les règles de validation :

- montant négatif, total incohérent, devise invalide ;
- code acte inconnu, prestataire inconnu, assuré inconnu ;
- date future, date impossible, champ obligatoire manquant, facture sans ligne.

**Résultat** : 10/10 invalides détectés, 10/10 valides acceptés. Le lot est
dans `tests/fixtures/factures_test_set.json`.

Le lot de démonstration jury (`reports/ml/pb12/lot_jury_20.md`) contient
20 factures contrastées : 5 positifs haute confiance, 5 positifs moyenne
confiance, 5 vrais négatifs, 5 faux positifs. Chaque facture est accompagnée
de ses 3 facteurs SHAP.

## 9. Versioning et rollback

Le registre `models/registry.json` contient :

| Version | Statut | Rôle |
|---|---|---|
| `v2.0.0-weak` | production | Labels faibles, XGBoost, 60 features |
| `v1.1.0` | archive | Proxy `CONTROLE_MEDICAL`, LightGBM, 107 features |
| `v1.0.0` | archive | Première version |

Commandes :

```bash
PYTHONPATH=src python -m predicare.ml.registry liste
PYTHONPATH=src python -m predicare.ml.registry promouvoir v2.0.0-weak
PYTHONPATH=src python -m predicare.ml.registry rollback v1.1.0
```

Le rollback vers `v1.1.0` exige de restaurer son magasin de variables :

```bash
# 1. Basculer le pointeur de production
PYTHONPATH=src python -m predicare.ml.registry rollback v1.1.0

# 2. Utiliser le magasin v1.1.0 (107 features) pour le service
PREDICARE_DATASET_CM=data/raw/dataset_cm.csv \
  PYTHONPATH=src python -c \
  "from predicare.ml.service import predire_facture; print(predire_facture('FAC-00027743', top_k=3))"
```

Le magasin par défaut est `data/processed/dataset_cm_v2.csv` (v2). Le magasin
v1.1.0 reste `data/raw/dataset_cm.csv`. Sans la variable
`PREDICARE_DATASET_CM`, le service utiliserait le magasin v2 avec le modèle
v1.1.0, ce qui provoquerait une incompatibilité de features.

## 10. Monitoring en production

| Indicateur | Fréquence | Seuil d'action |
|---|---|---|
| PSI des 60 variables | mensuel | > 0,25 sur 2 mois |
| Taux d'alerte global | hebdomadaire | ±20 % vs référence |
| Précision estimée (audit) | mensuel | < 30 % |
| Rappel estimé (audit) | trimestriel | < 70 % |
| Écart TPR par ville | mensuel | > 10 points |
| ECE | mensuel | > 0,05 |
| Dérive de `assure_taux_rejet_hist_lisse` | mensuel | PSI > 0,25 |

## 11. Limites et risques

1. **Labels faibles** : pas de vérité terrain, métriques optimistes.
2. **Circularité** : les features comportementales corrèlent avec les règles.
3. **Types sous-représentés** : UPCODING, FRACTIONNEMENT, ACTE_FICTIF.
4. **Calibration de prévalence** : le nombre de positifs est fixé à 7 347.
5. **Données synthétiques** : les résultats reflètent le générateur.
6. **Équité** : écarts de rappel par ville à surveiller.
7. **Dérive** : `assure_taux_rejet_hist_lisse` en alerte.
8. **Pas d'audit humain** : aucun expert n'a validé les labels.
9. **Pas de causalité** : SHAP explique le modèle, pas la fraude.
10. **Usage** : le score est une aide à la priorisation, pas une preuve.
11. **Audit indépendant (20/10/2026)** : 15/20 ; rappel faible sur
    `PRESTATAIRE_RADIE`, `ORDONNANCE_EXPIREE`, `DOUBLON` et `FRACTIONNEMENT`.

## 12. Reproduction

```bash
cd PrediCare

# Labels faibles
PYTHONPATH=src python -m predicare.ml.weak_labels \
  --raw-dir ../CohorteAI_datagen/dataset \
  --out-dir data/raw/labels \
  --target-positifs 7347

# Dataset v2
PYTHONPATH=src python -m predicare.ml.dataset_fraude

# EDA
PYTHONPATH=src python -m predicare.ml.eda \
  --dataset data/processed/dataset_ml.csv \
  --hors-modele data/processed/factures_hors_modele.csv \
  --out-dir reports/eda_fraude

# Entraînement + registre (promotion par défaut)
PYTHONPATH=src python -m predicare.ml.training_v2

# Évaluation des règles
PYTHONPATH=src python -m predicare.ml.eval_rules

# Audits
PYTHONPATH=src python -m predicare.ml.drift
PYTHONPATH=src python -m predicare.ml.fairness
PYTHONPATH=src python -m predicare.ml.robustness
PYTHONPATH=src python -m predicare.ml.batch_jury

# Audit indépendant (métriques recalculées, robustesse, note /20)
PYTHONPATH=src python -m predicare.ml.audit_v2

# Tests
PYTHONPATH=src python -m pytest -q tests/test_ml_v2.py
```

## 13. Contacts et validation

| Rôle | Responsabilité |
|---|---|
| Data science | Entraînement, évaluation, model card |
| Équipe fraude | Audit des labels, validation des alertes |
| Conformité / DPO | Équité, explicabilité, minimisation |
| Informatique | Déploiement, monitoring, rollback |

**Prochaine étape recommandée** : audit humain d'un échantillon stratifié de
100 à 200 factures (haute, moyenne, candidate) avant toute utilisation
opérationnelle.
