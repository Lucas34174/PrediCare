# Model card — PrediCare modèle de risque de contrôle médical (v1.0.0)

> **Statut** : version candidate transmise à M2 (intégration plateforme).
> **Équipe** : M1 (Data Science / ML).
> **Cible du backlog** : PB-11 (figer le modèle v1 et rédiger la model card).

## 1. Vue d'ensemble

| Élément | Valeur |
|---|---|
| Nom | `predicare-modele-controle-medical` |
| Version | **v1.0.0** |
| Empreinte SHA-256 | `9940b9ff6d1c9b28fe8b71c6e39336f980f8e3bbede46f5e942310d1d2ab7510` |
| Artefact | `models/v1.0.0/model.joblib` |
| Métadonnées | `models/v1.0.0/metadata.json` |
| Registre | `models/registry.json` (statut : `production`) |
| Algorithme | **LightGBM** (gradient boosting) + sur-échantillonnage **SMOTE** |
| Calibration | Régression isotonique (validation) |
| Type de tâche | Classification binaire supervisée, population déséquilibrée |
| Cadre réglementaire | Module 3 (CDC), AI Act — système d'IA à **risque élevé** (voir `docs/eu_ai_act_classification.md`) |

## 2. Usage prévu

**Finalité** : **prioriser les factures à contrôler** pour suspicion d'abus ou de
fraude, en amont de l'arbitrage par un gestionnaire. Le modèle produit un **score
de risque normalisé** ∈ [0, 1] et une explication SHAP par alerte.

**Utilisateurs** : gestionnaires de prestations (contrôle), équipe conformité.

**Hors périmètre** :
- le modèle **ne décide pas** du rejet d'une facture ; la décision reste humaine ;
- il ne fournit **aucune preuve de fraude** ;
- il n'est pas conçu pour un usage rétroactif contre un assuré.

**Seuil produit** : **0,80** (paramétrable via `PREDICARE_SEUIL_ALERTE`). Le score
exposé est normalisé de sorte que le point de fonctionnement métier (seuil calibré)
vaut 0,80 — la probabilité calibrée brute reste disponible dans l'artefact.

## 3. Données

| Élément | Valeur |
|---|---|
| Source | 12 CSV synthétiques `CohorteAI_datagen/dataset/` |
| Table de variables | `rapports_predicare/phase4_ml/dataset_ml.csv` (77 879 × 107) |
| Population d'apprentissage | **76 936** factures (rejets purement administratifs exclus) |
| Positifs | **947** (1,231 %) |
| Découpage | Temporel avec embargo 15 j : train 2024-10-02→2026-02-28 · validation 2026-03-16→2026-05-31 · test 2026-06-16→2026-09-18 |
| Effectifs | train 56 875 (699 pos.) · validation 9 733 (120 pos.) · test 10 328 (128 pos.) |
| Variables | **100** = 89 numériques + 11 catégorielles |
| Prétraitement | Imputation médiane + indicateurs de manquant ; OneHotEncoder (modalité rare = 20) |

### ⚠️ Cible : proxy, pas de la fraude confirmée

Le CDC annonçait « des labels de fraude dans un fichier séparé ». **Ce fichier
n'existe pas** dans les livrables (vérification exhaustive des 12 CSV, archives,
notebooks et uploads). La cible retenue est donc un **proxy** :

```
cible_cm = 1  si le motif de rejet est CONTROLE_MEDICAL
cible_cm = 0  si la facture est payée
(exclus)      les 943 autres rejets (PIECE_MANQUANTE_ATTESTATION,
              ORDONNANCE_PERIMEE, DELAI_DE_CARENCE, HORS_PERIODE_COUVERTURE,
              PLAFOND_ATTEINT, ENTENTE_PREALABLE_ABSENTE, PRODUIT_NON_REMBOURSABLE)
```

`CONTROLE_MEDICAL` est le seul motif relevant d'un **jugement clinique** ; il est
le meilleur substitut disponible. **Toute performance rapportée mesure la
détection du contrôle médical, pas de la fraude avérée.**

## 4. Performance (jeu de test, 10 328 factures, 128 positifs)

| Métrique | Modèle v1.0.0 | Baseline règles seules | Lecture |
|---|---:|---:|---|
| **PR-AUC (AP)** | **0,1412** (IC95 0,109–0,163) | 0,093 | +52 % vs règles |
| ROC-AUC | **0,9530** (IC95 0,941–0,961) | 0,893 | Bonne séparation globale |
| Brier | 0,0114 | — | Calibration correcte |
| ECE | 0,0013 | — | Très bonne calibration |
| **Rappel** (seuil calibré) | **0,820** | 0,906 | 105 / 128 positifs détectés |
| Précision | 0,134 | 0,070 | 782 alertes (7,6 % du flux) |
| Lift | **10,8×** | — | Enrichissement vs hasard |

**Point de fonctionnement** : seuil calibré 0,1356 → 782 alertes, 105 vrais
positifs, 677 faux positifs, 23 manqués. La table `reports/ml/courbe_seuils_test.csv`
donne le compromis pour tout budget d'alertes.

**Comparaison des candidats** (`reports/ml/comparaison_modeles.csv`) :

| Modèle | Déséquilibre | PR-AUC (val.) |
|---|---|---:|
| **LightGBM** | **SMOTE** | **0,1562** ✅ retenu |
| LightGBM | poids de classe | 0,1378 |
| XGBoost | poids de classe | 0,1273 |

**Amélioration testée (PB-10)** : ajouter les 6 variables d'alerte prescription
PB-09 fait passer la PR-AUC de **0,1412 → 0,1509** et le rappel de 0,797 → 0,813
(`reports/ml/pb10/amelioration.csv`). Piste retenue pour la v1.1.

## 5. Explicabilité (PB-13)

Chaque alerte est accompagnée des **5 facteurs SHAP** les plus influents, traduits
en libellés métier (`predicare.ml.config.FEATURE_LABELS`), au format du contrat
`ShapFactor{feature, valeur, impact_shap, description}`. Les règles métier
(`nb_alertes_metier`, `score_regles_metier`) figurent parmi les facteurs
dominants : le modèle **complète** le moteur de règles, il ne le remplace pas.

Exemple (facture `FAC-00005637`) : `score_fraude = 0,011`, principal facteur
`nb_alertes_metier = 1` (impact +2,05).

## 6. Équité (PB-14)

Audit détaillé : `docs/equity_audit_modele.md` et `reports/ml/pb14/`.

| Dimension | Écart de rappel max–min | Verdict |
|---|---:|---|
| Sexe | 0,073 | ✅ < 10 pts |
| Tranche d'âge | 0,158 | ⚠️ au-delà du seuil |
| Formule | 0,118 | ⚠️ au-delà du seuil |
| Ville de l'assuré | 0,333 | ⚠️ groupes à faible effectif |
| Ville du prestataire | 0,323 | ⚠️ groupes à faible effectif |

Ces écarts portent sur de **très petits effectifs** (128 positifs au total) : ils
sont signalés avec intervalles de Wilson, mais ne permettent pas de conclure à un
biais systématique. Mesures : suivi mensuel par groupe, recalibration conditionnelle
si l'écart persiste sur un jeu plus large.

## 7. Suivi de dérive (PB-12)

Référence : `reports/ml/pb12/reference_distribution.json` (train). Détection PSI/KS
sur le test : **83 variables stables**, 2 en vigilance, **1 en alerte**
(`assure_taux_rejet_hist_lisse`, PSI 0,363). 14 compteurs cumulatifs sont exclus du
verdict (croissance structurelle attendue). Voir `docs/drift_reference.md`.

## 8. Robustesse (PB-12 / PB-30)

Lot de 20 factures : `tests/fixtures/factures_test_set.json` — 5 normales,
5 suspectes, 10 invalides (1 par code d'invalidité métier). Les factures invalides
sont **rejetées avec un code explicite** par `predicare.ml.robustness.valider_facture`
avant tout scoring. Voir `docs/model_card_v1.md` §8 et le test `tests/test_ml_pb12.py`.

## 9. Limites connues

1. **Pas de vérité terrain de fraude** : la cible est un proxy administratif.
2. **Données synthétiques** : les distributions et écarts reflètent le générateur.
3. **Faible prévalence** (1,23 %) : la précision reste modeste ; c'est un outil de
   **priorisation**, pas de décision automatique.
4. **Calibration isotonique discrète** : la validation ne contient que 120 positifs,
   d'où des probabilités par paliers (29 valeurs distinctes sur le test).
5. **Recouvrement des entités** train/test élevé (split temporel non groupé) :
   les performances sont optimistes pour les prestataires déjà vus.
6. **Écarts d'équité** sur l'âge, la formule et la ville à surveiller.
7. Le modèle ne remplace pas le moteur de règles, qui reste une variable majeure.

## 10. Utilisation technique

```python
from predicare.ml.registry import charger_production

modele = charger_production()          # v1.0.0 en production
alertes = modele.alerter(factures)     # score_risque + alerte
```

API : `GET /claims/{facture_id}/prediction` renvoie le score de risque, le seuil
appliqué, la version et les facteurs SHAP (`predicare.ml.service`).

Registre : `python -m predicare.ml.registry liste | promouvoir <version> | rollback`.

## 11. Reproduire la version

```bash
# 1. Construire la cible B
python -m predicare.ml.targets          # (ou via training, chargement automatique)
# 2. Entraîner, calibrer, évaluer
python -m predicare.ml.training
# 3. Figer la version
python -c "import json; from predicare.ml import registry as R; from predicare.ml.config import MODELS_DIR; \
R.enregistrer_version('v1.0.0', MODELS_DIR/'model.joblib', \
  metadonnees=json.loads((MODELS_DIR/'metadata.json').read_text()), promouvoir=True)"
```

Graine `42`, Python 3.12, dépendances : scikit-learn, lightgbm 4.x, imbalanced-learn,
shap, pandas.
