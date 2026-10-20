# Lot de 20 factures — démonstration jury

> **Avertissement** : les labels sont des labels faibles reconstruits par règles, pas des fraudes confirmées. Ce lot illustre le comportement du modèle et son explicabilité.

Modèle : `v2.0.0-weak` — 15 alertes sur 20 factures.

| # | Facture | Label faible | Confiance | Type faible | Proba | Score | Alerte |
|---|---------|--------------|-----------|-------------|-------|-------|--------|
| 1 | `FAC-00027743` | 1 | haute | QUANTITE_EXCESSIVE | 0.9784 | 1.0000 | OUI |
| 2 | `FAC-00082612` | 1 | haute | SOINS_JOUR_FERME | 0.9783 | 1.0000 | OUI |
| 3 | `FAC-00071257` | 1 | haute | LIGNES_NON_PRESCRITES | 0.9783 | 1.0000 | OUI |
| 4 | `FAC-00034124` | 1 | haute | SUBSTITUTION_PRODUIT | 0.9782 | 1.0000 | OUI |
| 5 | `FAC-00084705` | 1 | haute | PRESTATAIRE_RADIE | 0.9779 | 1.0000 | OUI |
| 6 | `FAC-00082615` | 1 | moyenne | SURCONSOMMATION | 0.9781 | 1.0000 | OUI |
| 7 | `FAC-00026744` | 1 | moyenne | DOUBLON | 0.2075 | 0.9993 | OUI |
| 8 | `FAC-00082425` | 1 | moyenne | SURCONSOMMATION | 0.9781 | 1.0000 | OUI |
| 9 | `FAC-00082422` | 1 | moyenne | SURCONSOMMATION | 0.9766 | 1.0000 | OUI |
| 10 | `FAC-00082184` | 1 | moyenne | SURCONSOMMATION | 0.9767 | 1.0000 | OUI |
| 11 | `FAC-00055892` | 0 | aucune | AUCUN | 0.0173 | 0.4534 | non |
| 12 | `FAC-00006161` | 0 | aucune | AUCUN | 0.0173 | 0.4534 | non |
| 13 | `FAC-00059741` | 0 | aucune | AUCUN | 0.0173 | 0.4539 | non |
| 14 | `FAC-00070082` | 0 | aucune | AUCUN | 0.0174 | 0.4546 | non |
| 15 | `FAC-00031493` | 0 | aucune | AUCUN | 0.0174 | 0.4554 | non |
| 16 | `FAC-00007762` | 0 | aucune | AUCUN | 0.9639 | 1.0000 | OUI |
| 17 | `FAC-00083283` | 0 | aucune | AUCUN | 0.9532 | 1.0000 | OUI |
| 18 | `FAC-00083167` | 0 | aucune | AUCUN | 0.9508 | 1.0000 | OUI |
| 19 | `FAC-00083518` | 0 | aucune | AUCUN | 0.9497 | 1.0000 | OUI |
| 20 | `FAC-00083360` | 0 | faible | SURFACTURATION | 0.9484 | 1.0000 | OUI |

## Explications SHAP (top 3)

### `FAC-00027743`
- **ratio_montant_moy_hist_prest** = `5.033423068173201` (impact +2.559) — Ratio au montant moyen historique du prestataire = 5.03
- **quantite_max_ligne** = `5.0` (impact +2.005) — Quantité maximale sur une ligne = 5.00
- **type_ordonnance** = `MEDICAMENTS` (impact +1.110) — Type d'ordonnance = MEDICAMENTS

### `FAC-00082612`
- **ratio_montant_moy_hist_prest** = `4.97303187142468` (impact +2.216) — Ratio au montant moyen historique du prestataire = 4.97
- **soin_hors_horaires** = `1.0` (impact +1.057) — Soin hors horaires d'ouverture = 1
- **montant_total** = `67200.0` (impact +0.871) — Montant total de la facture = 67200.00

### `FAC-00071257`
- **nb_lignes** = `4.0` (impact +2.601) — Nombre de lignes de la facture = 4
- **ratio_montant_moy_hist_prest** = `1.8503377859665289` (impact +0.986) — Ratio au montant moyen historique du prestataire = 1.85
- **nb_codes_distincts** = `4.0` (impact +0.962) — Nombre de codes distincts = 4

### `FAC-00034124`
- **ratio_montant_moy_hist_prest** = `5.005722203689923` (impact +2.113) — Ratio au montant moyen historique du prestataire = 5.01
- **nb_lignes** = `5.0` (impact +1.900) — Nombre de lignes de la facture = 5
- **montant_total** = `73200.0` (impact +1.045) — Montant total de la facture = 73200.00

### `FAC-00084705`
- **ratio_montant_moy_hist_prest** = `3.5587188612099645` (impact +1.963) — Ratio au montant moyen historique du prestataire = 3.56
- **nb_lignes_ordonnance** = `3.0` (impact +1.835) — Nombre de lignes de l'ordonnance = 3.00
- **montant_total** = `80000.0` (impact +1.026) — Montant total de la facture = 80000.00

### `FAC-00082615`
- **ratio_montant_moy_hist_prest** = `4.244092550049229` (impact +2.370) — Ratio au montant moyen historique du prestataire = 4.24
- **montant_total** = `69200.0` (impact +1.105) — Montant total de la facture = 69200.00
- **soin_hors_horaires** = `1.0` (impact +1.059) — Soin hors horaires d'ouverture = 1

### `FAC-00026744`
- **montant_total** = `53900.0` (impact +1.114) — Montant total de la facture = 53900.00
- **type_facture** = `LABORATOIRE` (impact +0.614) — Type de facture = LABORATOIRE
- **log_montant_total** = `10.89490430960068` (impact +0.327) — Montant total (échelle logarithmique) = 10.89

### `FAC-00082425`
- **ratio_montant_moy_hist_prest** = `4.463220675944334` (impact +2.237) — Ratio au montant moyen historique du prestataire = 4.46
- **soin_hors_horaires** = `1.0` (impact +1.059) — Soin hors horaires d'ouverture = 1
- **montant_total** = `69500.0` (impact +0.905) — Montant total de la facture = 69500.00

### `FAC-00082422`
- **ratio_montant_moy_hist_prest** = `4.667199321680147` (impact +2.427) — Ratio au montant moyen historique du prestataire = 4.67
- **montant_total** = `65800.0` (impact +1.132) — Montant total de la facture = 65800.00
- **nb_lignes_ordonnance** = `3.0` (impact +0.606) — Nombre de lignes de l'ordonnance = 3.00

### `FAC-00082184`
- **ratio_montant_moy_hist_prest** = `6.222025764081839` (impact +2.290) — Ratio au montant moyen historique du prestataire = 6.22
- **montant_total** = `78200.0` (impact +0.928) — Montant total de la facture = 78200.00
- **nb_lignes_ordonnance** = `3.0` (impact +0.597) — Nombre de lignes de l'ordonnance = 3.00

### `FAC-00055892`
- **ratio_montant_moy_hist_prest** = `0.9975763451284536` (impact -0.458) — Ratio au montant moyen historique du prestataire = 1.00
- **type_facture** = `CONSULTATION` (impact -0.440) — Type de facture = CONSULTATION
- **nb_lignes_ordonnance** = `0.0` (impact -0.406) — Nombre de lignes de l'ordonnance = 0.00

### `FAC-00006161`
- **ratio_montant_moy_hist_prest** = `0.9973016729627632` (impact -0.471) — Ratio au montant moyen historique du prestataire = 1.00
- **type_facture** = `CONSULTATION` (impact -0.436) — Type de facture = CONSULTATION
- **nb_lignes_ordonnance** = `0.0` (impact -0.413) — Nombre de lignes de l'ordonnance = 0.00

### `FAC-00059741`
- **nb_lignes_ordonnance** = `0.0` (impact -0.512) — Nombre de lignes de l'ordonnance = 0.00
- **ratio_montant_moy_hist_prest** = `0.5377896980950416` (impact -0.490) — Ratio au montant moyen historique du prestataire = 0.54
- **specialite_prestataire** = `PNEUMOLOGIE` (impact -0.489) — Spécialité du prestataire = PNEUMOLOGIE

### `FAC-00070082`
- **ratio_montant_moy_hist_prest** = `0.5359106815530744` (impact -0.488) — Ratio au montant moyen historique du prestataire = 0.54
- **nb_lignes_ordonnance** = `0.0` (impact -0.482) — Nombre de lignes de l'ordonnance = 0.00
- **specialite_prestataire** = `PNEUMOLOGIE` (impact -0.473) — Spécialité du prestataire = PNEUMOLOGIE

### `FAC-00031493`
- **ratio_montant_moy_hist_prest** = `0.5463953974222994` (impact -0.479) — Ratio au montant moyen historique du prestataire = 0.55
- **specialite_prestataire** = `PNEUMOLOGIE` (impact -0.474) — Spécialité du prestataire = PNEUMOLOGIE
- **type_facture** = `CONSULTATION` (impact -0.445) — Type de facture = CONSULTATION

### `FAC-00007762`
- **nb_lignes** = `4.0` (impact +1.661) — Nombre de lignes de la facture = 4
- **ratio_montant_moy_hist_prest** = `17.69555510452608` (impact +1.646) — Ratio au montant moyen historique du prestataire = 17.70
- **montant_total** = `1321000.0` (impact +0.948) — Montant total de la facture = 1321000.00

### `FAC-00083283`
- **delai_facture_reception_j** = `42` (impact +3.246) — Délai entre la facture et la réception (jours) = 42
- **delai_soin_reception_j** = `42` (impact +0.757) — Délai entre le soin et la réception (jours) = 42
- **nb_lignes_medicament** = `2` (impact +0.381) — Nombre de lignes de médicaments = 2

### `FAC-00083167`
- **delai_facture_reception_j** = `56.0` (impact +3.409) — Délai entre la facture et la réception (jours) = 56
- **delai_soin_reception_j** = `59.0` (impact +0.837) — Délai entre le soin et la réception (jours) = 59
- **jours_depuis_derniere_facture** = `41.0` (impact +0.430) — Jours depuis la dernière facture = 41.00

### `FAC-00083518`
- **delai_facture_reception_j** = `56` (impact +2.669) — Délai entre la facture et la réception (jours) = 56
- **jour_semaine_soin** = `6` (impact +1.282) — Jour de la semaine du soin = 6
- **delai_soin_reception_j** = `57` (impact +0.577) — Délai entre le soin et la réception (jours) = 57

### `FAC-00083360`
- **delai_facture_reception_j** = `53` (impact +3.338) — Délai entre la facture et la réception (jours) = 53
- **delai_soin_reception_j** = `53` (impact +0.762) — Délai entre le soin et la réception (jours) = 53
- **nb_lignes_medicament** = `2` (impact +0.408) — Nombre de lignes de médicaments = 2
