# Évaluation métier du modèle B

> Source des scores : `reports/ml/v11/scores_test.csv`. Cible = `cible_controle_medical` (proxy de suspicion d'abus). Aucun label de fraude confirmée.

## Point de fonctionnement (seuil calibré au rappel 0,80)

- Factures analysées : **10328**
- Positifs (contrôle médical) : **128** (1.24%)
- Alertes : **732** (7.09% des factures)
- Rappel : **0.789** | Précision : **0.138** | Lift : **11.1×**

## Modèle vs moteur de règles, à budget égal

| Approche | Budget | Alertes | Rappel | Précision | Lift |
|---|---:|---:|---:|---:|---:|
| modèle | 1% | 103 | 0.125 | 0.155 | 12.5× |
| modèle | 2% | 207 | 0.273 | 0.169 | 13.6× |
| modèle | 3% | 310 | 0.383 | 0.158 | 12.8× |
| modèle | 5% | 516 | 0.562 | 0.140 | 11.3× |
| modèle | 10% | 1033 | 0.969 | 0.120 | 9.7× |
| règles | 1% | 103 | 0.102 | 0.126 | 10.2× |
| règles | 2% | 207 | 0.172 | 0.106 | 8.6× |
| règles | 3% | 310 | 0.289 | 0.119 | 9.6× |
| règles | 5% | 516 | 0.477 | 0.118 | 9.5× |
| règles | 10% | 1033 | 0.688 | 0.085 | 6.9× |

Lecture : le modèle améliore le rappel à budget égal, surtout quand le budget s'élargit (à 10 %, 97 % des positifs contre 69 % pour les règles). À 1–5 %, le gain est réel (2 à 9 points de rappel) mais reste modeste : le moteur de règles capte déjà l'essentiel du signal facile.

## Scénario de coût/bénéfice (hypothèses explicites)

Coût d'un contrôle : **2 000 MGA** par dossier. Le « montant en jeu » est le montant **facturé** des vrais positifs, pas le montant indûment perçu : les scénarios ci-dessous sont des ordres de grandeur, pas une mesure d'économies réalisées.

| Budget | Alertes | TP | Coût / TP | Montant moyen TP | Taux d'équilibre | Bénéfice net (30 %) |
|---:|---:|---:|---:|---:|---:|---:|
| 1% | 103 | 16 | 12 875 | 54 219 | 23.7% | 54 250 |
| 2% | 207 | 35 | 11 829 | 49 220 | 24.0% | 102 810 |
| 3% | 310 | 49 | 12 653 | 47 147 | 26.8% | 73 060 |
| 5% | 516 | 72 | 14 333 | 44 017 | 32.6% | -81 240 |
| 10% | 1033 | 124 | 16 661 | 45 892 | 36.3% | -358 805 |

Lecture : le contrôle est rentable si le taux de redressement dépasse le **taux d'équilibre** de la colonne (≈ 24–36 % selon le budget). À 30 % de redressement, les budgets 1–3 % sont bénéficiaires ; les budgets 5–10 % ne le sont pas. En dessous du seuil d'équilibre, le contrôle reste justifié par la conformité et la dissuasion, mais il coûte plus qu'il ne rapporte.

## Recommandation opérationnelle

1. Démarrer sur le budget **1–3 %** : précision maximale (≈ 0,16), coût contenu, et les factures contrôlées servent à mesurer le taux de redressement réel.
2. Utiliser le budget **5–10 %** uniquement en campagne ciblée ou pour les prestataires signalés : c'est là que le modèle creuse l'écart avec les règles.
3. Remplacer les hypothèses (coût, redressement) par les données de recouvrement dès qu'elles sont disponibles.

## Limites

- La cible est un **proxy administratif** : un dossier orienté contrôle médical n'est pas une fraude confirmée.
- Le montant facturé n'est pas le montant indû ; le taux de redressement est une hypothèse à remplacer par les données de recouvrement réelles.
- Les montants sont fortement asymétriques (quelques factures très élevées) : la précision en nombre et la part de montant peuvent diverger.
- Le budget d'alertes est une décision de gestion : le seuil doit être choisi avec les équipes contrôle, pas uniquement optimisé hors ligne.