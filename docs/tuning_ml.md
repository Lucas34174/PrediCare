# Rapport de Tuning d'Hyperparamètres – XGBoost vs LightGBM (PB-07)

Date : 2026-10-19  
Graine de reproductibilité : `seed=42`  
Métrique directrice : **PR-AUC** (Average Precision Score)  
Protocole de validation : **StratifiedGroupKFold (5 folds)** groupé par `assure_id` sur le jeu d'entraînement (409 factures). Le jeu de test (91 factures) reste strictement inviolé.

---

## 1. Synthèse comparative des performances

| Modèle       | PR-AUC CV (moyenne) | OOF PR-AUC | OOF Recall @ 0.50 | OOF F2 @ 0.50 | scale_pos_weight retenu |
| :----------- | :-----------------: | :--------: | :---------------: | :-----------: | :---------------------: |
| **XGBoost**  |     **0.6640**      |   0.5302   |      0.2667       |    0.3030     |          7.51           |
| **LightGBM** |       0.6102        | **0.5847** |    **0.3333**     |  **0.3846**   |          5.58           |

### Observations clés

1. **Pondération des classes (`scale_pos_weight`)** : Dans les deux algorithmes, l'optimiseur bayésien Optuna a sélectionné un `scale_pos_weight` élevé (> 5.5), confirmant qu'une forte pénalité sur les faux négatifs améliore le classement des fraudes rares.
2. **Comparaison des modèles** :
   - XGBoost affiche la capacité d'apprentissage locale la plus élevée (PR-AUC fold moyen à 0.6640 vs 0.6102 pour LightGBM).
   - LightGBM offre une régularisation out-of-fold globale supérieure (OOF PR-AUC 0.5847 vs 0.5302).
3. **Limitation du seuil standard 0.50** : Avec un Recall @ 0.50 plafonnant entre 26.7 % et 33.3 %, l'ajustement du seuil de décision est indispensable pour atteindre l'objectif métier de détection maximale des fraudes.

---

## 2. Meilleurs hyperparamètres (Optuna TPE - 20 trials)

### XGBoost (`xgb`)

- `max_depth`: 5
- `learning_rate`: 0.0754
- `n_estimators`: 500
- `subsample`: 0.8873
- `colsample_bytree`: 0.6928
- `min_child_weight`: 3.1815
- `reg_alpha`: 0.0207
- `reg_lambda`: 0.0034
- `scale_pos_weight`: 7.5115

### LightGBM (`lgbm`)

- `max_depth`: 7
- `num_leaves`: 99
- `learning_rate`: 0.0549
- `n_estimators`: 450
- `subsample`: 0.8735
- `colsample_bytree`: 0.9788
- `min_child_samples`: 5
- `reg_alpha`: 0.0189
- `reg_lambda`: 0.0022
- `scale_pos_weight`: 5.5753

---

## 3. Artefacts générés

- `models/tuning_results.json` : sauvegarde structurée des scores et hyperparamètres.
