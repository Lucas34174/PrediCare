# Rapport d'Analyse des Faux Négatifs et Amélioration du Modèle (PB-10)

**Auteur** : Équipe Data Science / ML – PrediCare TPA  
**Date** : 2026-10-20  
**Branche** : `feature/analyse-faux-negatifs`  
**Jeu de test scellé** : 91 factures (91 assurés distincts, 7 fraudes, prévalence 7.69 %)  
**Version de référence (AVANT)** : `v1.0.0-xgb` au seuil 0.30  
**Version améliorée (APRÈS)** : `v1.1.0-xgb` au seuil 0.25 (statut STANDBY)

---

## 1. Contexte & Objectif Métier

Dans le cadre de l'assurance santé à Madagascar (montants en Ariary MGA entiers), la détection de fraude présente une forte asymétrie de coût :

- **Faux Négatif (FN)** : Fraude payée à tort $\rightarrow$ perte financière sèche directe.
- **Faux Positif (FP)** : Facture légitime en revue $\rightarrow$ coût opérationnel modéré d'arbitrage gestionnaire.

L'objectif de PB-10 est de cartographier sans concession les fraudes échappant au modèle champion existant, d'identifier les causes racines (features vs seuil vs données), et de tester et mesurer au moins une amélioration sur le même découpage sans fuite.

---

## 2. Cartographie Complète des Types de Fraude Manqués (Critère 1)

Sur le jeu de test scellé (7 fraudes réelles), le modèle initial au seuil opérationnel (0.30) présentait **5 faux négatifs** cumulant **99 000 MGA** de pertes financières non interceptées :

### Bilan par Type de Fraude (CDC §6)

| Type de Fraude        | Total | Détectés (TP) | Manqués (FN) |   Recall    | Score Moy. FN | Montant Manqué (Ariary) | Statut                        |
| :-------------------- | :---: | :-----------: | :----------: | :---------: | :-----------: | :---------------------: | :---------------------------- |
| **DOUBLON**           |   4   |       0       |    **4**     |  **0.0 %**  |    0.0820     |     **63 000 MGA**      | Échec principal (80 % des FN) |
| **PRESTATAIRE_RADIE** |   1   |       0       |    **1**     |  **0.0 %**  |    0.0021     |     **36 000 MGA**      | Échec unitaire                |
| **ACTE_FICTIF**       |   1   |       1       |      0       | **100.0 %** |       -       |          0 MGA          | Détection parfaite            |
| **SURFACTURATION**    |   1   |       1       |      0       | **100.0 %** |       -       |          0 MGA          | Détection parfaite            |
| **TOTAL**             | **7** |     **2**     |    **5**     | **28.6 %**  |  **0.0660**   |     **99 000 MGA**      | -                             |

### Détail des 5 Faux Négatifs Individuels

1. `FAC-00083354` (`DOUBLON`, 20 000 MGA, Consultation) : Score = **0.2704** (copie de `FAC-00059213`). Proche du seuil 0.30.
2. `FAC-00083087` (`DOUBLON`, 19 500 MGA, Laboratoire) : Score = **0.0191** (copie de `FAC-00066162`).
3. `FAC-00083196` (`DOUBLON`, 11 900 MGA, Pharmacie) : Score = **0.0200** (copie de `FAC-00062958`).
4. `FAC-00083360` (`DOUBLON`, 11 600 MGA, Pharmacie) : Score = **0.0184** (copie de `FAC-00057778`).
5. `FAC-00084677` (`PRESTATAIRE_RADIE`, 36 000 MGA, Consultation) : Score = **0.0021** (Dr RAHARIVONY déconventionné le 2026-04-23, soin le 2026-08-26).

---

## 3. Diagnostic des Causes Racines & Analyse SHAP

1. **Pourquoi les factures DOUBLON sont-elles manquées ?**
   - **Explication SHAP** : Pour chaque doublon, la facture individuelle est **parfaitement conforme au barème** : prix conventionnels respectés (`f_ratio_med_prix_ref_max` SHAP = -3.25), quantité conforme à l'ordonnance (`f_qte_fac_vs_prescrite_max` SHAP = -1.44), âge conforme (`f_age_au_soin` SHAP = -2.18).
   - **Cause technique** : Le filtre `_drop_high_nan(0.95)` a éliminé les 3 variables d'antériorité de réémission (`f_nb_doublons_anterieurs`, `f_numero_facture_deja_vu`, `f_nb_factures_meme_jour_prest`) car elles contenaient des `NaN` faute de profondeur d'historique dans l'échantillon réduit de 500 factures. Privé de son signal temporel, le modèle ne peut pas différencier une réémission d'une consultation normale.

2. **Pourquoi `PRESTATAIRE_RADIE` est-il manqué ?**
   - La variable `f_soin_apres_fin_convention` vaut bien `1.0` sur la facture `FAC-00084677`.
   - Cependant, la radiation datant du 2026-04-23 et le split étant chronologique, la période d'entraînement antérieure ne comportait qu'un seul cas similaire : l'arbre n'a pas appris à lui affecter un split prioritaire face aux tarifs bas du praticien.

---

## 4. Amélioration Testée et Mesurée (Critère 2)

### Hypothèse & Justification

En raison de l'asymétrie financière défavorable aux faux négatifs, l'optimisation bayésienne et le calibrage de seuil sur la validation croisée Out-Of-Fold (OOF) ont été réévalués en relevant la contrainte de rappel opérationnel à $\text{Recall}_{\text{CV}} \ge 85 \%$ (au lieu de $80 \%$).
Sur validation, cette règle sélectionne le seuil **0.25** (Recall OOF = 90.0 % vs 80.0 %).

### Résultats AVANT / APRÈS sur le jeu de test scellé (91 factures)

| Métrique                | AVANT (`v1.0.0-xgb` @ 0.30) | APRÈS (`v1.1.0-xgb` @ 0.25) |       Écart mesuré        |
| :---------------------- | :-------------------------: | :-------------------------: | :-----------------------: |
| **Recall global**       |        28.57 % (2/7)        |      **42.86 % (3/7)**      |      **+14.29 pts**       |
| **Précision**           |        33.33 % (2/6)        |      **42.86 % (3/7)**      |       **+9.53 pts**       |
| **F1-score**            |           0.3077            |         **0.4286**          |      **+12.09 pts**       |
| **F2-score**            |           0.2941            |         **0.4286**          |      **+13.45 pts**       |
| **Vrais Positifs (TP)** |              2              |            **3**            |          **+1**           |
| **Faux Positifs (FP)**  |              4              |            **4**            | **+0 (aucun FP ajouté)**  |
| **Faux Négatifs (FN)**  |              5              |            **4**            |          **-1**           |
| **Taux d'alerte**       |        6.59 % (6/91)        |      **7.69 % (7/91)**      |        +1 dossier         |
| **Pertes financières**  |         99 000 MGA          |       **79 000 MGA**        | **-20 000 MGA récupérés** |

### Contrôle de Non-Régression par Type

- `ACTE_FICTIF` : **100 %** $\rightarrow$ **100 %** (INTACT)
- `SURFACTURATION` : **100 %** $\rightarrow$ **100 %** (INTACT)
- `DOUBLON` : 0 % $\rightarrow$ **25 %** (**AMÉLIORÉ**, capture de `FAC-00083354`)
- `PRESTATAIRE_RADIE` : 0 % $\rightarrow$ 0 % (INTACT)

---

## 5. Contrôle de Parité d'Inférence & Versionnement

1. **Parité Inférence Unitaire vs Batch (`POST /claims`)** :
   - Vérification systématique sur les 91 factures de test.
   - Écart maximal : $\max |p_{\text{batch}} - p_{\text{unitaire}}| = \mathbf{0.00 \times 10^0} < 10^{-6}$.
2. **Versionnement et Gouvernance API (`GET /admin/models`)** :
   - La version `v1.1.0-xgb` est sérialisée dans `models/fraud_xgb_v1.1.0-xgb.joblib`.
   - `models/models_metadata.json` intègre la version avec `statut: "STANDBY"`.
   - `active_version` reste rigoureusement fixée à **`v1.0.0-xgb`** (pas d'activation sans accord).
   - Rollback immédiat disponible en réactivant l'alias si nécessaire.

---

## 6. Limites & Prochaines Pistes

1. **Alimentation de l'antériorité glissante** : Sur le jeu complet de 84 593 factures, alimenter systématiquement le paramètre `history` lors de l'ingestion permettra de conserver les 3 features de réémission sans filtre NaN.
2. **Feature d'interaction conventionnement** : Introduire une feature combinée pénalisant lourdement tout soin post-radiation sans dilution tarifaire.
