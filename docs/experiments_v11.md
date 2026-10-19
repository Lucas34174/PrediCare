# Expériences v1.1 — ce qui n'a pas marché (et pourquoi)

> Objectif : améliorer la prédiction au-delà de la v1.0.0. **Résultat : aucun
> gain robuste.** Ce document consigne les essais pour éviter de les refaire et
> pour assumer les limites du jeu.

## Protocole

- Découpage temporel existant (train / validation / test).
- Comparaison des jeux de variables sur la **validation** (120 positifs).
- Vérification par **validation croisée 5 plis × 3 graines sur le train**
  (699 positifs) pour les configurations finalistes.
- Le test n'est utilisé qu'une fois, après sélection.

## 1. Variables PB-09 et réseau/vélocité

Variables testées (ajoutées aux 100 de base) :

- **PB-09** (9) : 6 codes d'alerte prescription + nombre d'alertes, gravité
  maximale, montant maximal en jeu ;
- **réseau/vélocité** (11) : assurés distincts par prestataire, prestataires
  distincts par assuré, intensité du couple, concentration, factures sur 7/30
  jours et sur la journée.

Résultats de validation (`reports/ml/v11/experiments_jeux_variables.csv`) :

| Jeu de variables | Variables | Stratégie | PR-AUC validation |
|---|---:|---|---:|
| **base** | **100** | **aucun** | **0,1562** |
| base + PB-09 + réseau | 120 | SMOTE | 0,1410 |
| base + réseau | 111 | aucun | 0,1409 |
| base + PB-09 + réseau | 120 | aucun | 0,1405 |
| base + PB-09 | 109 | SMOTE | 0,1404 |
| base + PB-09 | 109 | aucun | 0,1402 |
| base | 100 | poids | 0,1378 |
| base + réseau | 111 | SMOTE | 0,1328 |
| base | 100 | SMOTE | 0,1305 |
| base + PB-09 | 109 | poids | 0,1265 |
| base + réseau | 111 | poids | 0,1254 |
| base + PB-09 + réseau | 120 | poids | 0,1250 |

**Conclusion** : les nouvelles variables **n'améliorent pas** la PR-AUC de
validation ; elles la dégradent de 0,015 à 0,031. Les alertes PB-09 sont déjà
corrélées à `nb_alertes_metier` / `score_regles_metier`, et les variables réseau
sont majoritairement des compteurs cumulatifs redondants.

## 2. Déséquilibre

- **Poids de classe** (`scale_pos_weight ≈ 80`) : PR-AUC 0,1378 vs 0,1562.
- **SMOTE** (ratio 0,25) : PR-AUC 0,1305 vs 0,1562.

Avec 699 positifs et un signal métier fort, le sur-échantillonnage ajoute du
bruit. La v1.1.0 conserve donc **l'absence de traitement du déséquilibre**.

## 3. Tuning et ensemble

- Recherche Optuna (30 essais, 3 plis) : meilleure config = 9 feuilles,
  91 échantillons/feuille, 350 arbres, `lr = 0,026`.
- Validation croisée 5 plis × 3 graines (`reports/ml/v11/comparaison_cv.csv`) :

| Modèle | CV PR-AUC | Écart-type |
|---|---:|---:|
| v1.0.0 (31 feuilles) | 0,1446 | 0,0156 |
| **v1.1.0 (9 feuilles)** | **0,1461** | **0,0143** |
| XGBoost | 0,1428 | 0,0120 |
| Ensemble LightGBM + XGBoost | 0,1455 | 0,0119 |

**Conclusion** : les écarts (< 0,004) sont très inférieurs à l'écart-type
(≈ 0,014). Aucun modèle n'est significativement meilleur. La v1.1.0 est retenue
pour sa **variance plus faible**, pas pour un gain prouvé.

## 4. Instabilité du holdout

Le même modèle tuné obtient, selon le jeu de variables et le découpage :

- 0,1746 (120 variables, test, classement brut) ;
- 0,1555 (100 variables, test, classement brut).

Une mesure antérieure à 0,1330 était **biaisée par les paliers** de la
calibration isotonique (9 valeurs distinctes), qui écrasait le classement ;
la calibration de Platt, strictement croissante, préserve la PR-AUC réelle.
Avec 128 positifs, l'intervalle de confiance à 95 % de la PR-AUC est
**0,122–0,207** : ces valeurs sont compatibles. Toute communication qui
présenterait 0,175 comme « le » résultat serait du cherry-picking.

## 5. Ce qu'il faudrait pour progresser réellement

1. **Labels de fraude confirmée** (le blocage principal) — sans eux, on mesure
   la détection du contrôle médical, pas de la fraude.
2. **Plus de positifs** (quelques milliers) pour stabiliser les écarts.
3. **Variables de graphe globales** (communautés, centralité, cycles
   prestataire–assuré–ordonnance) plutôt que des compteurs locaux.
4. **Objectif de ranking top-k** (LambdaRank) aligné sur l'usage, à tester avec
   un budget de contrôle réel.
5. **Données de recouvrement** pour remplacer les hypothèses de coût/bénéfice.

## Reproduire

```bash
PYTHONPATH=src python -m predicare.ml.network_features     # construit dataset_cm_v11.csv
PYTHONPATH=src python -m predicare.ml.experiments_v11      # tableau ci-dessus
PYTHONPATH=src python -m predicare.ml.training_v11 --cv    # CV + modèle v1.1.0
```
