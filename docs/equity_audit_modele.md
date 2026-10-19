# Audit d'équité du modèle PrediCare (cible B)

> Cible : `cible_controle_medical` (proxy de suspicion d'abus). Aucun label de fraude confirmée n'existe : cet audit porte sur les **alertes du modèle**, pas sur une vérité terrain de fraude.

Seuil d'alerte appliqué : **0.80** (score de risque normalisé).

Écart de rappel maximal toléré entre groupes : **10%**.

## Synthèse

| Dimension | Groupes | Groupes à faible effectif | Écart TPR | Écart FPR | Alerte |
|---|---:|---:|---:|---:|---|
| sexe | 2 | 0 | 0.085 | 0.002 | ✅ |
| tranche_age | 4 | 0 | 0.198 | 0.016 | ⚠️ écart de rappel 0.198 > 0.1 |
| formule | 3 | 0 | 0.274 | 0.013 | ⚠️ écart de rappel 0.274 > 0.1 |
| ville_assure | 7 | 2 | 0.242 | 0.033 | ⚠️ écart de rappel 0.242 > 0.1 |
| ville_prestataire | 7 | 2 | 0.161 | 0.073 | ⚠️ écart de rappel 0.161 > 0.1 |

## Détail par dimension

Un effectif de moins de 5 positifs rend le rappel instable : ces groupes sont marqués et ne doivent pas fonder de conclusion.

### sexe

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| F | 5202 | 63 | 361 | 6.9% | 0.746 [0.63–0.84] | 0.061 [0.05–0.07] | 0.130 |
| M | 5126 | 65 | 371 | 7.2% | 0.831 [0.72–0.90] | 0.063 [0.06–0.07] | 0.146 |

### tranche_age

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| <25 | 4153 | 51 | 322 | 7.8% | 0.725 [0.59–0.83] | 0.069 [0.06–0.08] | 0.115 |
| 45-60 | 2939 | 37 | 186 | 6.3% | 0.838 [0.69–0.92] | 0.053 [0.05–0.06] | 0.167 |
| 25-45 | 2075 | 27 | 148 | 7.1% | 0.778 [0.59–0.89] | 0.062 [0.05–0.07] | 0.142 |
| 60+ | 1161 | 13 | 76 | 6.5% | 0.923 [0.67–0.99] | 0.056 [0.04–0.07] | 0.158 |

### formule

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| ESSENTIEL | 5728 | 76 | 442 | 7.7% | 0.803 [0.70–0.88] | 0.067 [0.06–0.07] | 0.138 |
| PREMIUM | 2378 | 24 | 152 | 6.4% | 0.917 [0.74–0.98] | 0.055 [0.05–0.07] | 0.145 |
| CONFORT | 2222 | 28 | 138 | 6.2% | 0.643 [0.46–0.79] | 0.055 [0.05–0.07] | 0.130 |

### ville_assure

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| Antananarivo | 7355 | 84 | 521 | 7.1% | 0.810 [0.71–0.88] | 0.062 [0.06–0.07] | 0.131 |
| Toamasina | 862 | 14 | 69 | 8.0% | 0.714 [0.45–0.88] | 0.070 [0.05–0.09] | 0.145 |
| Antsirabe | 681 | 7 | 35 | 5.1% | 0.714 [0.36–0.92] | 0.045 [0.03–0.06] | 0.143 |
| Mahajanga | 490 | 6 | 32 | 6.5% | 0.667 [0.30–0.90] | 0.058 [0.04–0.08] | 0.125 |
| Fianarantsoa | 437 | 11 | 43 | 9.8% | 0.909 [0.62–0.98] | 0.077 [0.06–0.11] | 0.233 |
| Toliara *(effectif faible)* | 356 | 3 | 22 | 6.2% | 0.667 [0.21–0.94] | 0.057 [0.04–0.09] | 0.091 |
| Antsiranana *(effectif faible)* | 147 | 3 | 10 | 6.8% | 0.667 [0.21–0.94] | 0.056 [0.03–0.11] | 0.200 |

### ville_prestataire

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| Antananarivo | 7652 | 87 | 539 | 7.0% | 0.828 [0.73–0.89] | 0.062 [0.06–0.07] | 0.134 |
| Toamasina | 771 | 13 | 64 | 8.3% | 0.692 [0.42–0.87] | 0.073 [0.06–0.09] | 0.141 |
| Antsirabe | 673 | 6 | 27 | 4.0% | 0.667 [0.30–0.90] | 0.034 [0.02–0.05] | 0.148 |
| Mahajanga | 492 | 5 | 40 | 8.1% | 0.800 [0.38–0.96] | 0.074 [0.05–0.10] | 0.100 |
| Fianarantsoa | 366 | 12 | 47 | 12.8% | 0.750 [0.47–0.91] | 0.107 [0.08–0.14] | 0.191 |
| Toliara *(effectif faible)* | 318 | 4 | 15 | 4.7% | 0.750 [0.30–0.95] | 0.038 [0.02–0.07] | 0.200 |
| Antsiranana *(effectif faible)* | 56 | 1 | 0 | 0.0% | 0.000 [0.00–0.79] | 0.000 [0.00–0.07] | 0.000 |

## Limites

- Cible = proxy administratif (contrôle médical), pas de la fraude confirmée.
- Test : 128 positifs au total → les sous-groupes restent petits.
- Données synthétiques : les écarts observés peuvent refléter le générateur.
- La ville est jointe hors du jeu d'apprentissage (dimension d'audit, pas variable du modèle).

## Mesures correctives proposées

1. Recalibrer le seuil par sous-groupe uniquement si un écart TPR persiste sur un jeu plus large.
2. Surveiller mensuellement les taux d'alerte par groupe (voir PB-12, dérive).
3. Documenter tout écart résiduel dans la model card (PB-11).

Analyse de mitigation (seuils par sous-groupe, évaluée sur le test) : `docs/equity_mitigation.md`.