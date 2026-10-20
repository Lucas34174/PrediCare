# Audit d'équité du modèle PrediCare (cible B)

> Cible : `est_fraude` (label faible reconstruit, 14 types de fraude). Ce n'est pas une vérité terrain : cet audit porte sur les **alertes du modèle**, pas sur une fraude confirmée.

Seuil d'alerte appliqué : **0.80** (score de risque normalisé).

Écart de rappel maximal toléré entre groupes : **10%**.

## Synthèse

| Dimension | Groupes | Groupes à faible effectif | Écart TPR | Écart FPR | Alerte |
|---|---:|---:|---:|---:|---|
| sexe | 2 | 0 | 0.000 | 0.004 | ✅ |
| tranche_age | 4 | 0 | 0.091 | 0.035 | ✅ |
| formule | 3 | 0 | 0.079 | 0.018 | ✅ |
| ville_assure | 7 | 0 | 0.106 | 0.056 | ⚠️ écart de rappel 0.106 > 0.1 |
| ville_prestataire | 7 | 1 | 0.137 | 0.072 | ⚠️ écart de rappel 0.137 > 0.1 |

## Détail par dimension

Un effectif de moins de 5 positifs rend le rappel instable : ces groupes sont marqués et ne doivent pas fonder de conclusion.

### sexe

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| F | 5280 | 465 | 839 | 15.9% | 0.781 [0.74–0.82] | 0.099 [0.09–0.11] | 0.433 |
| M | 5173 | 428 | 821 | 15.9% | 0.780 [0.74–0.82] | 0.103 [0.09–0.11] | 0.407 |

### tranche_age

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| <25 | 4197 | 399 | 753 | 17.9% | 0.812 [0.77–0.85] | 0.113 [0.10–0.12] | 0.430 |
| 45-60 | 2972 | 205 | 400 | 13.5% | 0.737 [0.67–0.79] | 0.090 [0.08–0.10] | 0.378 |
| 25-45 | 2109 | 208 | 355 | 16.8% | 0.745 [0.68–0.80] | 0.105 [0.09–0.12] | 0.437 |
| 60+ | 1175 | 81 | 152 | 12.9% | 0.827 [0.73–0.89] | 0.078 [0.06–0.10] | 0.441 |

### formule

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| ESSENTIEL | 5805 | 515 | 950 | 16.4% | 0.812 [0.78–0.84] | 0.101 [0.09–0.11] | 0.440 |
| PREMIUM | 2400 | 183 | 339 | 14.1% | 0.732 [0.66–0.79] | 0.092 [0.08–0.11] | 0.395 |
| CONFORT | 2248 | 195 | 371 | 16.5% | 0.744 [0.68–0.80] | 0.110 [0.10–0.12] | 0.391 |

### ville_assure

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| Antananarivo | 7449 | 630 | 1168 | 15.7% | 0.778 [0.74–0.81] | 0.099 [0.09–0.11] | 0.420 |
| Toamasina | 868 | 92 | 145 | 16.7% | 0.815 [0.72–0.88] | 0.090 [0.07–0.11] | 0.517 |
| Antsirabe | 691 | 46 | 124 | 17.9% | 0.717 [0.57–0.83] | 0.141 [0.12–0.17] | 0.266 |
| Mahajanga | 499 | 44 | 79 | 15.8% | 0.773 [0.63–0.87] | 0.099 [0.07–0.13] | 0.430 |
| Fianarantsoa | 439 | 44 | 73 | 16.6% | 0.795 [0.65–0.89] | 0.096 [0.07–0.13] | 0.479 |
| Toliara | 359 | 20 | 45 | 12.5% | 0.800 [0.58–0.92] | 0.086 [0.06–0.12] | 0.356 |
| Antsiranana | 148 | 17 | 26 | 17.6% | 0.824 [0.59–0.94] | 0.092 [0.05–0.15] | 0.538 |

### ville_prestataire

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| Antananarivo | 7747 | 661 | 1217 | 15.7% | 0.787 [0.75–0.82] | 0.098 [0.09–0.11] | 0.427 |
| Toamasina | 774 | 80 | 122 | 15.8% | 0.688 [0.58–0.78] | 0.097 [0.08–0.12] | 0.451 |
| Antsirabe | 682 | 40 | 129 | 18.9% | 0.825 [0.68–0.91] | 0.150 [0.12–0.18] | 0.256 |
| Mahajanga | 504 | 39 | 81 | 16.1% | 0.795 [0.64–0.89] | 0.108 [0.08–0.14] | 0.383 |
| Fianarantsoa | 370 | 48 | 69 | 18.6% | 0.812 [0.68–0.90] | 0.093 [0.07–0.13] | 0.565 |
| Toliara | 320 | 23 | 40 | 12.5% | 0.739 [0.54–0.87] | 0.077 [0.05–0.11] | 0.425 |
| Antsiranana *(effectif faible)* | 56 | 2 | 2 | 3.6% | 1.000 [0.34–1.00] | 0.000 [0.00–0.07] | 1.000 |

## Limites

- Cible = label faible reconstruit par règles, pas de la fraude confirmée.
- Test : 893 positifs faibles → les sous-groupes restent petits.
- Données synthétiques : les écarts observés peuvent refléter le générateur.
- La ville est jointe hors du jeu d'apprentissage (dimension d'audit, pas variable du modèle).

## Mesures correctives proposées

1. Recalibrer le seuil par sous-groupe uniquement si un écart TPR persiste sur un jeu plus large.
2. Surveiller mensuellement les taux d'alerte par groupe (voir PB-12, dérive).
3. Documenter tout écart résiduel dans la model card (PB-11).

Analyse de mitigation (seuils par sous-groupe, évaluée sur le test) : `docs/equity_mitigation.md`.