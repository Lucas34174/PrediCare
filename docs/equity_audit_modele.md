# Audit d'équité du modèle PrediCare (cible B)

> Cible : `cible_controle_medical` (proxy de suspicion d'abus). Aucun label de fraude confirmée n'existe : cet audit porte sur les **alertes du modèle**, pas sur une vérité terrain de fraude.

Seuil d'alerte appliqué : **0.80** (score de risque normalisé).

Écart de rappel maximal toléré entre groupes : **10%**.

## Synthèse

| Dimension | Groupes | Groupes à faible effectif | Écart TPR | Écart FPR | Alerte |
|---|---:|---:|---:|---:|---|
| sexe | 2 | 0 | 0.073 | 0.003 | ✅ |
| tranche_age | 4 | 0 | 0.158 | 0.023 | ⚠️ écart de rappel 0.158 > 0.1 |
| formule | 3 | 0 | 0.118 | 0.013 | ⚠️ écart de rappel 0.118 > 0.1 |
| ville_assure | 7 | 2 | 0.333 | 0.036 | ⚠️ écart de rappel 0.333 > 0.1 |
| ville_prestataire | 7 | 2 | 0.323 | 0.071 | ⚠️ écart de rappel 0.323 > 0.1 |

## Détail par dimension

Un effectif de moins de 5 positifs rend le rappel instable : ces groupes sont marqués et ne doivent pas fonder de conclusion.

### sexe

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| F | 5202 | 63 | 388 | 7.5% | 0.857 [0.75–0.92] | 0.065 [0.06–0.07] | 0.139 |
| M | 5126 | 65 | 394 | 7.7% | 0.785 [0.67–0.87] | 0.068 [0.06–0.08] | 0.129 |

### tranche_age

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| <25 | 4153 | 51 | 353 | 8.5% | 0.765 [0.63–0.86] | 0.077 [0.07–0.09] | 0.110 |
| 45-60 | 2939 | 37 | 186 | 6.3% | 0.865 [0.72–0.94] | 0.053 [0.05–0.06] | 0.172 |
| 25-45 | 2075 | 27 | 166 | 8.0% | 0.815 [0.63–0.92] | 0.070 [0.06–0.08] | 0.133 |
| 60+ | 1161 | 13 | 77 | 6.6% | 0.923 [0.67–0.99] | 0.057 [0.04–0.07] | 0.156 |

### formule

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| ESSENTIEL | 5728 | 76 | 468 | 8.2% | 0.868 [0.77–0.93] | 0.071 [0.06–0.08] | 0.141 |
| PREMIUM | 2378 | 24 | 155 | 6.5% | 0.750 [0.55–0.88] | 0.058 [0.05–0.07] | 0.116 |
| CONFORT | 2222 | 28 | 159 | 7.2% | 0.750 [0.57–0.87] | 0.063 [0.05–0.07] | 0.132 |

### ville_assure

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| Antananarivo | 7355 | 84 | 548 | 7.5% | 0.798 [0.70–0.87] | 0.066 [0.06–0.07] | 0.122 |
| Toamasina | 862 | 14 | 79 | 9.2% | 0.929 [0.69–0.99] | 0.078 [0.06–0.10] | 0.165 |
| Antsirabe | 681 | 7 | 36 | 5.3% | 0.714 [0.36–0.92] | 0.046 [0.03–0.06] | 0.139 |
| Mahajanga | 490 | 6 | 37 | 7.6% | 0.667 [0.30–0.90] | 0.068 [0.05–0.09] | 0.108 |
| Fianarantsoa | 437 | 11 | 46 | 10.5% | 1.000 [0.74–1.00] | 0.082 [0.06–0.11] | 0.239 |
| Toliara *(effectif faible)* | 356 | 3 | 23 | 6.5% | 1.000 [0.44–1.00] | 0.057 [0.04–0.09] | 0.130 |
| Antsiranana *(effectif faible)* | 147 | 3 | 13 | 8.8% | 0.667 [0.21–0.94] | 0.076 [0.04–0.13] | 0.154 |

### ville_prestataire

| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |
|---|---:|---:|---:|---:|---|---|---:|
| Antananarivo | 7652 | 87 | 568 | 7.4% | 0.816 [0.72–0.88] | 0.066 [0.06–0.07] | 0.125 |
| Toamasina | 771 | 13 | 71 | 9.2% | 0.923 [0.67–0.99] | 0.078 [0.06–0.10] | 0.169 |
| Antsirabe | 673 | 6 | 30 | 4.5% | 0.667 [0.30–0.90] | 0.039 [0.03–0.06] | 0.133 |
| Mahajanga | 492 | 5 | 42 | 8.5% | 0.600 [0.23–0.88] | 0.080 [0.06–0.11] | 0.071 |
| Fianarantsoa | 366 | 12 | 50 | 13.7% | 0.917 [0.65–0.99] | 0.110 [0.08–0.15] | 0.220 |
| Toliara *(effectif faible)* | 318 | 4 | 20 | 6.3% | 1.000 [0.51–1.00] | 0.051 [0.03–0.08] | 0.200 |
| Antsiranana *(effectif faible)* | 56 | 1 | 1 | 1.8% | 0.000 [0.00–0.79] | 0.018 [0.00–0.10] | 0.000 |

## Limites

- Cible = proxy administratif (contrôle médical), pas de la fraude confirmée.
- Test : 128 positifs au total → les sous-groupes restent petits.
- Données synthétiques : les écarts observés peuvent refléter le générateur.
- La ville est jointe hors du jeu d'apprentissage (dimension d'audit, pas variable du modèle).

## Mesures correctives proposées

1. Recalibrer le seuil par sous-groupe uniquement si un écart TPR persiste sur un jeu plus large.
2. Surveiller mensuellement les taux d'alerte par groupe (voir PB-12, dérive).
3. Documenter tout écart résiduel dans la model card (PB-11).