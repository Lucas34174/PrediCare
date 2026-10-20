# Référence de dérive et surveillance (PB-12)

> Livrable PB-12 : « distribution de référence des variables exportée pour le
> suivi de dérive ». Cible : `cible_controle_medical` (proxy d'abus).

## 1. Principe

La distribution de chaque variable est figée sur le **train**
(`reports/ml/pb12/reference_distribution.json`) : bornes de déciles et
proportions pour les 89 variables numériques, modalités et proportions pour les
11 variables catégorielles, plus moyenne, écart-type, min, max et taux de
manquants.

La dérive est mesurée par :

- **PSI** (Population Stability Index) sur les mêmes déciles/modalités ;
- **KS** (Kolmogorov–Smirnov) pour les variables numériques.

Seuils d'interprétation : `PSI < 0,10` stable · `0,10 ≤ PSI < 0,25` vigilance ·
`PSI ≥ 0,25` alerte.

## 2. Compteurs cumulatifs à détendanceer

Les variables de type compteur croissent mécaniquement avec le temps : elles
dérivent même en l'absence de tout changement de comportement. Elles sont
marquées `tendance=True` et **exclues du verdict global** :

`prest_nb_decidees_hist`, `prest_nb_rejets_hist`, `prest_nb_factures_hist`,
`prest_nb_decidees_90j`, `prest_nb_factures_90j`, `assure_nb_decidees_hist`,
`assure_nb_rejets_hist`, `assure_nb_factures_hist`, `assure_nb_factures_30j`,
`assure_nb_factures_90j`, `jours_depuis_derniere_facture`,
`anciennete_adhesion_j`, `anciennete_contrat_j`, `anciennete_convention_j`.

En production, ces variables doivent être transformées en **taux par période**
ou en **rangs**, et surveillées séparément.

## 3. Résultat train → test (v1.0.0)

| Indicateur | Valeur |
|---|---:|
| Variables suivies | 100 |
| Exclues (tendance) | 14 |
| Stables (`ok`) | 83 |
| Vigilance | 2 |
| **Alerte** | **1** |
| PSI maximal hors tendance | **0,363** |
| Verdict | **dérive significative** |

Variable en alerte : **`assure_taux_rejet_hist_lisse`** (PSI 0,363, KS 0,180).
Interprétation : le taux de rejet historique de l'assuré, lissé, se déplace entre
train et test. C'est attendu sur un split temporel (l'historique s'enrichit), mais
cette variable étant fortement prédictive, la dérive doit être **surveillée à
chaque rechargement**.

Variables en vigilance : `prest_taux_rejet_90j_lisse` (PSI 0,067) et
`prest_taux_rejet_hist_lisse` (PSI 0,049) — bien qu'en dessous du seuil de
vigilance 0,10, elles sont listées pour information dans
`reports/ml/pb12/derive_test.csv`.

## 4. Procédure de surveillance recommandée

1. Recalculer le PSI/KS sur chaque nouveau lot décisionné (fenêtre glissante 30 j)
   avec `predicare.ml.drift.calculer_derive(reference, dataset, split=...)`.
2. Alerter si `PSI ≥ 0,25` sur une variable non-tendance, ou si le nombre de
   variables en vigilance dépasse 10.
3. Surveiller en parallèle la **performance** (rappel / PR-AUC) sur les dossiers
   décisionnés : `predicare.ml.drift.synthese_derive` fournit le verdict.
4. En cas de dérive confirmée : ré-entraîner, réévaluer la porte G1, enregistrer
   une nouvelle version au registre (PB-11).

## 5. Reproduire

```bash
python -m predicare.ml.drift
```

Produit `reference_distribution.json`, `derive_test.csv` et
`synthese_derive.json` dans `reports/ml/pb12/`.
