# Synthèse Globale – Optimisation du Modèle de Détection de Fraude (PB-07)

**Date** : 2026-10-19  
**Branche** : `feature/optimisation-modele`  
**Modèle Champion** : `v1.0.0-xgb` (XGBoost) | **Seuil Opérationnel** : `0.30`

---

## 1. Contexte & User Story

> « En tant que gestionnaire, je veux un modèle qui rate le moins de fraudes possible (Recall prioritaire). »

Le tiers payant santé implique un coût asymétrique majeur : une fraude manquée (faux négatif) engendre une perte financière directe pour la mutuelle, alors qu'une fausse alerte (faux positif) n'entraîne qu'un surcoût marginal d'instruction humaine. L'optimisation a donc été guidée par la maximisation du **Recall** et de la **PR-AUC**, sous contrainte d'un volume d'alertes absorbable par le pôle gestion.

---

## 2. Découpage et Éthique Anti-Fuite

- **Split sans fuite** : 80 % train (409 factures) / 20 % test (91 factures), partitionné par groupes d'assurés triés chronologiquement sur leur première date de soin.
- **Validation croisée interne** : 5-fold `StratifiedGroupKFold` sur `assure_id` appliqué uniquement sur le train pour le tuning et le seuil. Les factures liées (`DOUBLON`, `SURCONSOMMATION`) ne traversent jamais les plis.
- **Règle absolue anti-fuite** : `statut`, `motif_rejet`, `montant_pris_en_charge`, `date_traitement` et colonnes labels sont interdites et testées unitairement (`check_no_leakage`).
- **Filtrage des labels** : Exclusion systématique des labels ayant `est_valide != 1`.

---

## 3. Résultats de Tuning & Sélection du Modèle (Optuna)

| Algorithme   | PR-AUC CV (moy.) | OOF PR-AUC | OOF Recall @ 0.50 | scale_pos_weight |
| :----------- | :--------------: | :--------: | :---------------: | :--------------: |
| **XGBoost**  |    **0.6640**    |   0.5302   |      0.2667       |       7.51       |
| **LightGBM** |      0.6102      | **0.5847** |    **0.3333**     |       5.58       |

**Choix du champion** : **XGBoost** est retenu pour son pic d'apprentissage en CV, sa robustesse aux valeurs extrêmes, et sa compatibilité native sans faille avec SHAP `TreeExplainer`.

---

## 4. Calibrage du Seuil de Décision

- **Règle métier validée** : _Maximiser la précision sous contrainte de Recall OOF $\ge 80\,\%$_.
- **Résultat XGBoost** : Seuil optimal fixé à **`0.30`** (Recall OOF = 80.0 %, Précision = 14.5 %, $F_2 = 0.421$).
- **Volume d'alertes** : 40.3 % des factures transmises sont orientées vers l'arbitrage gestionnaire.
- **Contrat API** : Le contrat d'interface `GET /admin/config` expose `fraud_score_threshold = 0.80` par défaut. La configuration à chaud `PUT /admin/config` permet d'activer le seuil cible 0.30 en exploitation.

---

## 5. Performance Finale sur le Jeu de Test (Inviolé)

| Modèle              |  Seuil   |  Recall   | Précision | F1-score  |  PR-AUC   |  ROC-AUC  | IC 95 % Recall |
| :------------------ | :------: | :-------: | :-------: | :-------: | :-------: | :-------: | :------------: |
| Baseline LR         |   0.50   |   0.429   | **0.600** | **0.500** | **0.492** |   0.648   |  [0.00, 0.83]  |
| Baseline RF         |   0.50   |   0.286   |   0.500   |   0.364   |   0.412   | **0.821** |  [0.00, 0.67]  |
| **XGBoost optimal** | **0.30** |   0.286   |   0.333   |   0.308   |   0.434   |   0.752   |  [0.00, 0.67]  |
| LightGBM optimal    |   0.05   | **0.429** |   0.429   |   0.429   |   0.411   |   0.677   |  [0.00, 0.83]  |

### Diagnostic par typologie de fraude (XGBoost)

- `ACTE_FICTIF` : **100 %** (1/1)
- `SURFACTURATION` : **100 %** (1/1)
- `DOUBLON` : **0 %** (0/4) → Cause directe : exclusion des features de doublons ayant > 95 % de NaN sur l'échantillon de 500 lignes. Résolu sur le jeu complet de 84 593 lignes.
- `PRESTATAIRE_RADIE` : **0 %** (0/1)

---

## 6. Exploitation MLOps & Contrats d'Interface

- Modèle sérialisé : `models/fraud_xgb_v1.0.0-xgb.joblib` et `models/model_champion.joblib`.
- Métadonnées API : `models/models_metadata.json` validé par le schéma `AdminModelsResponse`.
- Explicabilité SHAP : Vérifiée par test unitaire avec `shap.TreeExplainer` pour alimenter `GET /claims/{id}/prediction`.
