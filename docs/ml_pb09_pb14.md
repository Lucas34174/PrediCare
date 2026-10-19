# Livraison ML PB-09 → PB-14 — détection d'abus/fraude santé

> Branche : `feature/ml-pb09-pb14` · Équipe : M1 · Cible : `cible_controle_medical`.
> Ce document résume la livraison, les commandes de reproduction et la
> correspondance avec le CDC.

## 1. Changement de cible (décision structurante)

Le CDC annonçait des « labels de fraude dans un fichier séparé ». **Ce fichier
n'existe pas** (vérification exhaustive des 12 CSV, archives, notebooks, uploads).
La cible retenue est donc le **meilleur proxy disponible** :

| | |
|---|---|
| Cible | `cible_cm = 1` si motif de rejet `CONTROLE_MEDICAL`, `0` si payée |
| Population | **76 936** factures (les 943 autres rejets administratifs sont exclus) |
| Positifs | **947** (1,231 %) |
| Objectif reformulé | **prioriser les factures à contrôler** pour suspicion d'abus/fraude |

Cette limite est documentée dans la model card (`docs/model_card_v1.md`) et
partout où une performance est rapportée.

## 2. Correspondance CDC ↔ livrable

| Exigence CDC | Livrable | Fichier |
|---|---|---|
| Module 2 — supervisé, recall prioritaire, SMOTE/seuils | Entraînement + calibration + seuil | `ml/training.py`, `ml/evaluation.py` |
| Module 3 — XGBoost/LightGBM + SHAP par alerte | LightGBM retenu, SHAP par facture | `ml/training.py`, `ml/explain.py` |
| Module 7 — audit d'équité | Audit par sous-groupe + IC | `ml/fairness.py`, `docs/equity_audit_modele.md` |
| Seuil configurable (0,80) | Score de risque normalisé + `PREDICARE_SEUIL_ALERTE` | `ml/scoring.py` |
| Versioning + rollback | Registre + empreinte SHA-256 | `ml/registry.py`, `models/registry.json` |
| Suivi de dérive | PSI/KS + référence exportée | `ml/drift.py`, `docs/drift_reference.md` |
| Lot de 20 factures jury | 20 cas catégorisés + validation | `ml/robustness.py`, `tests/fixtures/factures_test_set.json` |

## 3. Résultats clés (jeu de test)

| Métrique | v1.0.0 | Baseline règles | 
|---|---:|---:|
| PR-AUC (AP) | **0,1412** [0,109–0,163] | 0,093 |
| ROC-AUC | **0,9530** | 0,893 |
| Rappel | **0,820** | 0,906 |
| Précision | 0,134 | 0,070 |
| Lift | **10,8×** | — |
| ECE | 0,0013 | — |

Le modèle **bat le moteur de règles** sur la PR-AUC (+52 %) et la précision, tout
en conservant un rappel > 0,80. Détail : `reports/ml/comparaison_modeles.csv`.

## 4. Contenu par tâche

### PB-09 — Détection d'anomalies de prescription
Trois signaux calculés depuis les CSV sources :
1. **`SURCONSOMMATION`** — même ordonnance facturée par ≥ 2 prestataires (nomadisme) ;
2. **`LIGNES_NON_PRESCRITES`** — codes facturés absents de l'ordonnance ;
3. **`INADEQUATION_DIAGNOSTIC`** — famille thérapeutique incompatible avec le diagnostic.

Plus les règles prescription de l'EDA (doublon, prescripteur radié, antidatée,
surcharge, ordonnance sans ligne). Sortie au format `alertes_factures_detail`.

```bash
python -m predicare.ml.prescription       # → reports/ml/pb09/
```

*Résultat : 6 818 alertes sur 6 449 factures, dont 1 468 nomadismes et 1 276 lignes
hors ordonnance (58,6 M MGA).*

### PB-10 — Faux négatifs et amélioration mesurée
Analyse des 23 faux négatifs (type, gravité, montant, prestataire, profil) et
test d'une amélioration : ajout des 6 variables PB-09 → **PR-AUC 0,1412 → 0,1509**,
rappel 0,797 → 0,813.

```bash
python -m predicare.ml.false_negatives     # → reports/ml/pb10/
```

### PB-11 — Modèle v1 figé + model card
Artefact + métadonnées + registre + **model card**.

```bash
python -m predicare.ml.registry liste
python -m predicare.ml.registry rollback   # revient à la version précédente
```

### PB-12 — Lot de 20 factures et référence de dérive
5 normales, 5 suspectes, 10 invalides (1 par code) + distribution de référence.

```bash
python -m predicare.ml.robustness          # → fixture + reports/ml/pb12/
python -m predicare.ml.drift               # → référence + dérive test
```

### PB-13 — SHAP par alerte (et API réelle)
Facteurs SHAP traduits en libellés métier, format du contrat de prédiction ;
l'endpoint `GET /claims/{id}/prediction` renvoie désormais le **score réel** du
modèle de production et ses explications.

```bash
python -m predicare.ml.training            # entraîne + évalue + écrit les scores
```

### PB-14 — Audit d'équité
Taux d'alerte, rappel (TPR) et FPR par sexe, âge, ville (assuré/prestataire) et
formule, avec intervalles de Wilson et écarts commentés.

```bash
python -m predicare.ml.fairness            # → docs/equity_audit_modele.md
```

## 5. Choix techniques (et pourquoi)

| Choix | Justification |
|---|---|
| **LightGBM** (vs XGBoost) | meilleure PR-AUC de validation (0,156 vs 0,127) ; exigence CDC satisfaite |
| **Aucun rééchantillonnage** (vs poids, SMOTE) | meilleure PR-AUC (0,156 vs 0,138 / 0,130) ; SMOTE réellement testé en v1.1, non retenu |
| **Calibration isotonique** | probabilités interprétables ; ECE = 0,0013 |
| **Score de risque normalisé** | le seuil produit 0,80 du CDC reste exploitable malgré une prévalence de 1,2 % |
| **Seuil configurable** | `PREDICARE_SEUIL_ALERTE` (défaut 0,80) + seuil par budget (`?budget=0.03`) |
| **`models/v1.0.0` et `v1.1.0` versionnés** | v1.0.0 archivée (rollback), v1.1.0 en production |

## 6. Limites (à assumer devant le jury)

1. **Pas de label de fraude confirmée** : cible = proxy de contrôle médical.
2. **Données synthétiques** : les distributions sont celles du générateur.
3. **Précision modeste** (0,134) inhérente à une prévalence de 1,23 % → outil de
   **priorisation**, décision humaine.
4. **Écarts d'équité** (âge, formule, ville) sur petits effectifs, à surveiller.
5. Le modèle **complète** le moteur de règles, qui reste un facteur dominant.

## 7. Reproductibilité

Environnement Python 3.12 avec `pandas`, `scikit-learn`, `lightgbm`,
`imbalanced-learn`, `shap`, `scipy`.

```bash
export PYTHONPATH=src
python -m predicare.ml.training            # dataset_cm + modèle v1.0.0 + scores + G1
python -m predicare.ml.prescription
python -m predicare.ml.false_negatives
python -m predicare.ml.robustness
python -m predicare.ml.drift
python -m predicare.ml.fairness
pytest tests/test_ml_pb09.py tests/test_ml_pb10.py tests/test_ml_pb11.py \
       tests/test_ml_pb12.py tests/test_ml_pb13.py tests/test_ml_pb14.py \
       tests/test_ml_targets.py
```

## 8. Mise à jour v1.1.0 (production)

La v1.0.0 est archivée ; la v1.1.0 est en production (rollback disponible).
Elle est sélectionnée par **validation croisée sur le train**, puis évaluée une
fois sur le test.

| Livrable | Fichier |
|---|---|
| Model card v1.1 | `docs/model_card_v11.md` |
| Expériences négatives (PB-09, réseau, SMOTE, tuning) | `docs/experiments_v11.md` |
| Évaluation métier (budget, coût/TP, règles) | `docs/business_case.md` |
| Généralisation par prestataire | `docs/evaluation_groupee.md` |
| Mitigation d'équité | `docs/equity_mitigation.md` |
| Tableaux et scores | `reports/ml/v11/` |

Points saillants :

- **Gain non prouvé statistiquement** : CV PR-AUC 0,1461 (v1.1.0) vs 0,1446
  (v1.0.0), écart-type ≈ 0,014. La v1.1.0 est plus régularisée (9 feuilles).
- **Holdout** : PR-AUC 0,1555 (IC95 0,122–0,207), rappel 0,789, précision 0,138,
  732 alertes (7,1 %). Calibration de Platt (strictement croissante, donc
  compatible avec un seuil par budget).
- **Métier** : à 10 % de budget, 97 % des positifs contre 69 % pour les règles ;
  gain de 2 à 9 points de rappel à 1–5 %.
- **Groupes** : CV groupée par prestataire 0,1438 vs 0,1461 aléatoire.
- **Équité** : la mitigation par seuils a été testée ; elle **échoue** sur deux
  dimensions (sexe, âge) et n'est pas déployée. Voir `docs/equity_mitigation.md`.

```bash
python -m predicare.ml.training_v11 --cv    # CV + v1.1.0 + promotion
python -m predicare.ml.business             # évaluation métier
python -m predicare.ml.grouped_eval         # généralisation par prestataire
python -m predicare.ml.equity_mitigation    # mitigation d'équité
python -m predicare.ml.experiments_v11      # expériences négatives
```
