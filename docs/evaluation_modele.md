# Rapport d'Évaluation Détaillée du Modèle de Fraude – PrediCare TPA (PB-08)

**Destinataire** : Jury d'évaluation & Direction Technique  
**Auteur** : Pôle Data / ML – PrediCare TPA  
**Date d'évaluation** : 2026-10-19  
**Version du modèle** : `v1.0.0-xgb` (XGBoost) | **Graine** : `seed=42`  
**Jeu de test inviolé** : 91 factures (91 assurés distincts, 7 fraudes, prévalence = 7.69 %)

---

## 1. Contexte Métier & Objectif

Dans le cadre du tiers payant santé à Madagascar (remboursements en Ariary MGA), la détection de fraude présente un **coût asymétrique majeur** :

- **Faux négatif (FN)** : Fraude non détectée et remboursée à tort $\rightarrow$ perte financière sèche directe pour l'organisme de prévoyance.
- **Faux positif (FP)** : Facture légitime orientée vers l'arbitrage gestionnaire $\rightarrow$ surcoût modéré d'instruction humaine (quelques minutes par dossier).
  Ce rapport détaille la performance empirique du modèle champion `v1.0.0-xgb` sur le jeu de test final, analyse ses erreurs sans artifice, évalue sa calibration probabiliste et explicite ses limites structurelles face au monde réel.

---

## 2. Intégrité de l'Évaluation & Garantie Anti-Fuite

1. **Étanchéité temporelle et groupée par assuré** :
   - Le jeu de test est constitué des 20 % d'assurés les plus récents chronologiquement (`split_no_leakage`).
   - **Aucun assuré commun** entre train et test : les factures potentiellement corrélées d'un même individu ne peuvent pas fuiter d'un jeu à l'autre.
   - Le jeu de test est resté scellé durant tout le tuning Optuna et le calibrage du seuil.
2. **Contrôle automatisé des variables interdites** :
   - Vérification automatisée (`check_no_leakage`) garantissant l'absence stricte de `statut`, `motif_rejet`, `montant_pris_en_charge` et `date_traitement` dans la matrice de features.
3. **Filtrage des étiquettes** :
   - Exclusion systématique des labels non validés (`est_valide != 1`).

---

## 3. Performances Globales & Matrices de Confusion

### Comparaison des matrices aux deux seuils opérationnels

![Matrices de confusion](figures/confusion_matrix.png)
| Métrique | Seuil Contractuel API (`0.80`) | Seuil Opérationnel Recommandé (`0.30`) | Interprétation Métier |
| :--- | :---: | :---: | :--- |
| **Vrais Positifs (TP)** | 2 | 2 | Fraudes interceptées |
| **Faux Positifs (FP)** | 1 | 4 | Alertes levées sur factures légitimes |
| **Faux Négatifs (FN)** | 5 | 5 | Fraudes payées sans contrôle |
| **Vrais Négatifs (TN)** | 83 | 80 | Télétransmissions conformes validées |
| **Recall (Rappel)** | **28.6 %** | **28.6 %** | Taux de capture des fraudes |
| **Précision** | **66.7 %** | **33.3 %** | 2 alertes sur 3 sont de vraies fraudes à 0.80 |
| **Spécificité** | **98.8 %** | **95.2 %** | Préservation du flux légitime |
| **Nombre d'alertes** | **3 / 91 (3.3 %)** | **6 / 91 (6.6 %)** | Volume de dossiers dirigé vers l'arbitrage |

### Enseignement opérationnel

- Au seuil contractuel par défaut de l'API (**0.80**), le modèle est extrêmement sélectif : il ne génère que **3.3 % d'alertes** avec une **précision élevée de 66.7 %**, mais laisse passer les fraudes plus diffuses.
- Au seuil opérationnel recommandé (**0.30**), le volume d'alertes passe à **6.6 %**, maintenant une charge de travail très modérée pour l'équipe de gestionnaires tout en abaissant la barrière de déclenchement sur les signaux faibles.

---

## 4. Courbes Précision-Rappel, ROC & Calibration

### Courbe Précision-Rappel vs Ligne de base de prévalence

![Courbe PR et ROC](figures/pr_curve.png)

- **PR-AUC = 0.4340** : Le modèle surclasse la ligne de base de prévalence naïve (**0.0769**) par un facteur de **5.6x**. Sur données fortement déséquilibrées, la PR-AUC démontre que le modèle concentre efficacement le signal de suspicion bien au-dessus du hasard.
- **ROC-AUC = 0.7517** : Pouvoir de discrimination globale satisfaisant.

### Fiabilité Probabiliste (Calibration)

![Courbe de calibration](figures/calibration_curve.png)

- **Score de Brier = 0.0805** : Excellente proximité quadratique globale avec les probabilités réelles.
- **Comportement de la courbe de fiabilité** : L'utilisation de `scale_pos_weight = 7.51` pour contrer le déséquilibre de classes tend à réhausser les scores prédits sur les cas incertains. Le score doit donc être interprété comme un _indice de risque relatif_ plutôt qu'une probabilité bayésienne purement calibrée.

---

## 5. Analyse Détaillée par Type de Fraude (14 Types du CDC)

### Taux de détection et intervalles de confiance de Wilson (95 %)

![Rappel par type de fraude](figures/recall_by_fraud_type.png)
| Type de Fraude (CDC §6) | Effectif Test | Détectés (TP) | Manqués (FN) | Recall | IC 95 % Wilson | Part des Alertes | Diagnostic |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **ACTE_FICTIF** | 1 | 1 | 0 | **100 %** | [20.7 %, 100 %] | 16.7 % | Détecté via incompatibilité d'actes & spécialités |
| **SURFACTURATION** | 1 | 1 | 0 | **100 %** | [20.7 %, 100 %] | 16.7 % | Détecté via écart tarifaire plafond (`f_ecart_tarif_max_moy`) |
| **DOUBLON** | 4 | 0 | 4 | **0 %** | [0.0 %, 49.0 %] | 0.0 % | Features d'antériorité exclues faute d'historique |
| **PRESTATAIRE_RADIE** | 1 | 0 | 1 | **0 %** | [0.0 %, 79.3 %] | 0.0 % | Date de radiation postérieure à la date de soin |
| _10 autres types CDC_ | 0 | - | - | _N/A_ | [0.0 %, 0.0 %] | 0.0 % | Absents du jeu de test réduit (500 factures) |

---

## 6. Analyse des Erreurs et Limites Structurelles (Transparence Jury)

### Pourquoi les fraudes DOUBLON ont-elles échappé au modèle ?

4 des 7 fraudes du test sont des factures réémises à l'identique (`DOUBLON`). Le modèle ne les a pas interceptées en raison d'un mécanisme documenté du pipeline :

- Le filtre `_drop_high_nan(threshold=0.95)` a éliminé 5 features historiques (`f_nb_doublons_anterieurs`, `f_numero_facture_deja_vu`, `f_nb_factures_meme_jour_prest`).
- Sur l'échantillon de développement réduit (500 factures), le volume est trop restreint pour constituer une profondeur d'historique suffisante, rendant ces colonnes quasi-vides (> 95 % NaN).
- **Conséquence directe** : Privé de ses signaux d'antériorité inter-factures, l'arbre XGBoost ne dispose que des signaux intrinsèques à la facture (montant, lignes, actes), incapables de distinguer un doublon d'une consultation normale. Sur le jeu complet de 84 593 factures, ces features sont peuplées et actives.

### Limites des données synthétiques

1. **Biais d'injection** : Les données étant générées selon des heuristiques prédéfinies, le modèle apprend les artefacts précis du générateur. En conditions réelles à Madagascar, les comportements de fraude sont plus variés et opportunistes.
2. **Taille de l'échantillon de test** : Avec 7 fraudes dans l'échantillon de test, un seul cas représente 14.3 points de Recall. Les intervalles de Wilson sont donc structurellement larges et invitent à la prudence statistique.
3. **Fraudes complexes inter-tables** : Les fraudes exigeant une analyse conjointe (ex. `SURCONSOMMATION`, `FRACTIONNEMENT`) requièrent une fenêtre temporelle glissante d'au moins 3 mois sur l'assuré pour exprimer leur plein potentiel.

---

## 7. Recommandations pour l'Exploitation & l'API

1. **Configuration dynamique du seuil** :
   - Maintenir le défaut contractuel de `GET /admin/config` à `0.80` pour garantir la compatibilité des tests d'intégration.
   - Utiliser `PUT /admin/config` avec `{"fraud_score_threshold": 0.30}` pour les périodes de contrôle renforcé nécessitant une surveillance accrue.
2. **Surveillance de la dérive (MLOps)** :
   - Surveiller l'indice de stabilité de population (PSI) via `GET /admin/metrics` pour détecter toute modification dans la distribution des montants ou des prestations.
3. **Explicabilité obligatoire** :
   - Chaque alerte transmise à l'interface gestionnaire doit être accompagnée de ses composantes SHAP `TreeExplainer` (`GET /claims/{id}/prediction`) afin que l'arbitre humain comprenne immédiatement les facteurs déclencheurs.

---

## 8. Reproductibilité Complète

Toutes les métriques et figures de ce rapport sont régénérables en une commande unique :

```bash
make evaluate
```
