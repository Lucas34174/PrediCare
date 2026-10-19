# Model card — PrediCare modèle de risque de contrôle médical (v1.1.0)

> **Statut** : **production** (registre `models/registry.json`).
> **Prédécesseur** : v1.0.0 archivée, rollback disponible.
> **Équipe** : M1 (Data Science / ML) — PB-11, PB-14, évaluation métier.

## 1. Vue d'ensemble

| Élément | Valeur |
|---|---|
| Nom | `predicare-modele-controle-medical` |
| Version | **v1.1.0** |
| Artefact | `models/v1.1.0/model.joblib` |
| Métadonnées | `models/v1.1.0/metadata.json` |
| Registre | `models/registry.json` (statut : `production`) |
| Algorithme | **LightGBM** régularisé (9 feuilles, 91 échantillons min./feuille) |
| Déséquilibre | **aucun** traitement (poids et SMOTE testés, moins bons) |
| Calibration | **Platt** (régression logistique sur le score brut), validation |
| Sélection | **Validation croisée 5 plis × 3 graines sur le train** |
| Évaluation | Holdout test unique (jamais utilisé pour choisir) |
| Cible | `cible_controle_medical` (proxy administratif) |

### Pourquoi une v1.1.0 ?

La v1.0.0 avait été sélectionnée sur la validation (120 positifs) puis évaluée
sur le test. Ce protocole est instable : avec 128 positifs, l'écart-type de la
PR-AUC dépasse 0,015. La v1.1.0 applique une sélection par **validation croisée
sur le train** (699 positifs, 15 plis) et un modèle plus régularisé.

## 2. Sélection

Comparaison par validation croisée (5 plis × 3 graines, `reports/ml/v11/comparaison_cv.csv`) :

| Modèle | CV PR-AUC moyenne | Écart-type |
|---|---:|---:|
| v1.0.0 (LightGBM, 31 feuilles) | 0,1446 | 0,0156 |
| **v1.1.0 (LightGBM, 9 feuilles)** | **0,1461** | **0,0143** |
| XGBoost (poids) | 0,1428 | 0,0120 |
| Ensemble LightGBM + XGBoost | 0,1455 | 0,0119 |

**Lecture honnête** : les quatre modèles sont **statistiquement
indiscernables** (écarts < 1 écart-type). La v1.1.0 est retenue pour sa
**variance plus faible** et sa régularisation plus forte, pas pour un gain de
performance prouvé.

## 3. Performance (holdout test — 10 328 factures, 128 positifs)

| Métrique | v1.1.0 | v1.0.0 | Lecture |
|---|---:|---:|---|
| PR-AUC (AP) | **0,1555** (IC95 0,122–0,207) | 0,1412 | +10 %, IC qui se recouvrent |
| ROC-AUC | **0,9552** | 0,9530 | séparation globale équivalente |
| Rappel (seuil calibré 0,0182) | **0,789** | 0,820 | 101 / 128 positifs |
| Précision | **0,138** | 0,134 | 732 alertes (7,1 %) |
| Lift | **11,1×** | 10,8× | enrichissement vs hasard |
| Brier | 0,0118 | 0,0114 | calibration proche |
| ECE | 0,018 | 0,001 | Platt moins fin qu'isotonique |

> **Ne pas conclure d'une supériorité forte** : l'intervalle de confiance de la
> PR-AUC (0,122–0,207) recouvre largement celle de la v1.0.0. Le gain test
> (+0,014) est cohérent avec la CV (+0,0015) mais reste dans le bruit.
>
> **Note méthodologique** : la PR-AUC est calculée sur le **classement brut**.
> L'ancienne calibration isotonique produisait 9 paliers et écrasait le
> classement (0,1330 mesuré) ; la calibration de Platt est strictement
> croissante et préserve la PR-AUC réelle (0,1555).

## 4. Évaluation métier (le vrai critère d'usage)

Le modèle **priorise un budget de contrôle**. À budget égal, comparaison au
moteur de règles (`reports/ml/v11/evaluation_metier.csv`) :

| Budget | Rappel modèle | Rappel règles | Précision modèle | Précision règles |
|---:|---:|---:|---:|---:|
| 1 % | 0,125 | 0,102 | 0,155 | 0,126 |
| 2 % | 0,273 | 0,172 | 0,169 | 0,106 |
| 3 % | 0,383 | 0,289 | 0,158 | 0,119 |
| 5 % | 0,562 | 0,477 | 0,140 | 0,118 |
| 10 % | **0,969** | 0,688 | 0,120 | 0,085 |

- À **1–5 %**, le gain est réel (2 à 9 points de rappel) mais reste modeste :
  les règles captent déjà le signal facile.
- À **10 %**, le modèle retrouve 97 % des positifs contre 69 % pour les règles.
- **Coût par vrai positif** : ≈ 11 800–16 700 MGA (contrôle à 2 000 MGA/dossier).
- **Taux de redressement d'équilibre** : 24 % (budget 1–2 %), 27 % (3 %),
  33 % (5 %), 36 % (10 %). À 30 % de redressement, les budgets 1–3 % sont
  bénéficiaires (+54 k à +103 k MGA), les budgets 5–10 % ne le sont pas.
- Détail : `docs/business_case.md`, `reports/ml/v11/scenarios_cout_benefice.csv`.

## 5. Généralisation par prestataire

`reports/ml/v11/evaluation_groupee_cv.csv` et `docs/evaluation_groupee.md` :

| Protocole | PR-AUC moyenne | Écart-type |
|---|---:|---:|
| GroupKFold par prestataire (train) | 0,1438 | 0,0105 |
| StratifiedKFold aléatoire (référence) | 0,1461 | 0,0143 |

L'écart est faible : le modèle ne dépend pas fortement de l'identité du
prestataire. **Limite** : le test ne contient que 64 factures (0,6 %) de
prestataires jamais vus, et **aucun positif** — le démarrage à froid n'est pas
évaluable sur ce jeu. À titre indicatif, la PR-AUC sur les prestataires vus est
0,1561 (IC95 0,123–0,213).

## 6. Équité (PB-14)

Audit : `docs/equity_audit_modele.md`. Mitigation : `docs/equity_mitigation.md`.

| Dimension | Écart TPR | Mitigation (seuils par groupe) | Verdict |
|---|---:|---:|---|
| Sexe | 0,085 | 0,116 | ❌ dégradé |
| Tranche d'âge | 0,198 | 0,217 | ❌ dégradé |
| Formule | 0,274 | 0,250 | ⚠️ légère amélioration |
| Ville assuré | 0,242 | — (groupes faibles) | ⚠️ |
| Ville prestataire | 0,161 | — (groupes faibles) | ⚠️ |

**La mitigation par seuils ne fonctionne pas de façon fiable** : 2 dimensions
sur 3 se dégradent. Elle n'est **pas déployée**. Les écarts ne sont pas
seulement un problème de seuil ; ils doivent être traités sur une cohorte plus
large et avec les équipes métier.

## 7. Limites

1. **Pas de label de fraude confirmée** : la cible est un proxy administratif.
2. **Données synthétiques** : les distributions reflètent le générateur.
3. **Petit holdout** (128 positifs) : IC larges, classements instables.
4. **Calibration de Platt** (ECE 0,018) : moins fine que l'isotonique, mais
   strictement croissante et compatible avec un seuil par budget.
5. **Démarrage à froid non évaluable** (aucun positif chez les nouveaux
   prestataires du test).
6. **Écarts d'équité** sur l'âge et la formule, partiellement corrigeables.
7. Le modèle **complète** le moteur de règles, il ne le remplace pas.

## 8. Utilisation

```python
from predicare.ml.registry import charger_production

modele = charger_production()            # v1.1.0
alertes = modele.alerter(factures)       # seuil produit 0,80
seuil_3pct = modele.seuil_pour_budget(0.03)
```

API : `GET /claims/{facture_id}/prediction` et
`GET /claims/{facture_id}/prediction?budget=0.03`.

Registre : `python -m predicare.ml.registry liste | promouvoir <version> | rollback`.

## 9. Reproduire

```bash
PYTHONPATH=src python -m predicare.ml.training_v11 --cv   # CV + entraînement + promotion
PYTHONPATH=src python -m predicare.ml.business            # évaluation métier
PYTHONPATH=src python -m predicare.ml.grouped_eval        # généralisation par prestataire
PYTHONPATH=src python -m predicare.ml.fairness            # audit d'équité
PYTHONPATH=src python -m predicare.ml.equity_mitigation   # mitigation
```

Graine `42`, Python 3.12, LightGBM 4.x, scikit-learn, imbalanced-learn, shap,
optuna (pour la recherche d'hyperparamètres).
