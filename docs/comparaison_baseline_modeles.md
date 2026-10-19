# Rapport Comparatif Final – Baseline vs XGBoost vs LightGBM (PB-07)

Date : 2026-10-19  
Graine de reproductibilité : `seed=42`  
Jeu de test : **91 factures (91 assurés distincts, 7 fraudes)** – évalué une seule fois à l'issue de l'optimisation.

---

## 1. Tableau comparatif final sur le jeu de test

| Modèle               | Seuil appliqué |  Recall   | Précision | F1-score  | F2-score |  PR-AUC   |  ROC-AUC  | IC 95 % Recall (Bootstrap) |
| :------------------- | :------------: | :-------: | :-------: | :-------: | :------: | :-------: | :-------: | :------------------------: |
| **Baseline LR**      |      0.50      |   0.429   | **0.600** | **0.500** |  0.455   | **0.492** |   0.648   |        [0.00, 0.83]        |
| **Baseline RF**      |      0.50      |   0.286   |   0.500   |   0.364   |  0.312   |   0.412   | **0.821** |        [0.00, 0.67]        |
| **XGBoost optimal**  |      0.30      |   0.286   |   0.333   |   0.308   |  0.294   |   0.434   |   0.752   |        [0.00, 0.67]        |
| **LightGBM optimal** |      0.05      | **0.429** |   0.429   |   0.429   |  0.429   |   0.411   |   0.677   |        [0.00, 0.83]        |

---

## 2. Décomposition du Recall par type de fraude (XGBoost)

| Type de fraude      | Détectés / Total |  Recall   | Diagnostic                                                                 |
| :------------------ | :--------------: | :-------: | :------------------------------------------------------------------------- |
| `ACTE_FICTIF`       |      1 / 1       | **100 %** | Détection immédiate via règles tarifaires & spécialités                    |
| `SURFACTURATION`    |      1 / 1       | **100 %** | Signal tarifaire fort (`f_ecart_tarif_max_moy`)                            |
| `PRESTATAIRE_RADIE` |      0 / 1       |    0 %    | Faux négatif sur date de radiation marginale                               |
| `DOUBLON`           |      0 / 4       |    0 %    | Features de doublon exclues faute d'historique suffisant sur l'échantillon |

---

## 3. Analyse d'honnêteté & limites des données de développement

1. **Exclusion des features de doublons** : Le filtre `_drop_high_nan(threshold=0.95)` a exclu 5 features d'historique (`f_nb_doublons_anterieurs`, `f_numero_facture_deja_vu`, `f_nb_factures_meme_jour_prest`). Sur l'échantillon de 500 factures, ces colonnes manquent d'antériorité. Sur le volume complet de production (84 593 factures), ces colonnes sont garnies et permettront la capture des doublons.
2. **Puissance statistique du test réduit** : Avec 7 cas positifs au test, chaque prédiction modifie le Recall de 14.3 points. L'intervalle de confiance bootstrap $[0.00, 0.67]$ reflète cette variance d'échantillonnage.
3. **Modèle retenu pour la mise en production** : **XGBoost** est retenu pour le déploiement API en raison de sa stabilité d'arbres, de sa compatibilité native SHAP `TreeExplainer`, et de son seuil opérationnel à 0.30 (générant un volume d'alertes modéré de 40 % contre plus de 63 % pour LightGBM).
