# Catalogue des Features – PrediCare TPA

Ce document constitue la **source de vérité** du catalogue de 28 features de détection de fraude. Il est généré depuis `FEATURE_CATALOGUE` dans
`src/predicare/ml/features.py` et doit être maintenu en cohérence avec lui.

Consommateurs : (baseline / split),(dérive), (labels SHAP),
**PB-22** (inférence temps réel).

---

## Règles anti-fuite (absolues)

Colonnes **jamais** présentes en entrée ni en sortie de `build_features()` :

| Catégorie       | Colonnes                                                                                      |
| --------------- | --------------------------------------------------------------------------------------------- |
| Fuite processus | `statut`, `motif_rejet`, `montant_pris_en_charge`, `date_traitement`                          |
| Labels          | `est_fraude`, `type_fraude`, `detail_fraude`, `est_valide`, `motif_invalidite`, `est_suspect` |

Clés exclues comme features (pas de signal direct) : `facture_id`, `assure_id`.

---

## Convention NaN

- **NaN** = information indisponible ou non applicable (pas d'ordonnance, ref manquant…).
- **0** = information disponible mais absence du signal (pas de doublon, tarif conforme…).
- L'imputation est déléguée à **PB-06** (avant entraînement) et **PB-22** (inférence).

---

## Catalogue des 28 features

### Groupe 1 – SURFACTURATION (5 features)

| Feature                      | Description                                                                        | NaN si                                      |
| ---------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------- |
| `f_ecart_tarif_max_moy`      | Écart moyen (prix − tarif_max ref) sur lignes ACTE. Positif = surfacturation.      | aucune ligne ACTE dans le référentiel       |
| `f_ratio_tarif_ref_max`      | Ratio max (prix / tarif_reference ref) sur lignes ACTE. > 1 = au-dessus du barème. | idem                                        |
| `f_ecart_grille_prest_moy`   | Écart moyen (prix − tarif_pratique grille) pour le prestataire concerné.           | aucun code dans la grille                   |
| `f_nb_lignes_hors_tarif_max` | Nombre de lignes ACTE dont prix > tarif_max ref.                                   | aucune ligne ACTE dans le référentiel       |
| `f_ratio_med_prix_ref_max`   | Ratio max (prix médicament / prix_reference ref) sur lignes MEDICAMENT.            | aucune ligne MEDICAMENT dans le référentiel |

### Groupe 2 – QUANTITE_EXCESSIVE (2 features)

| Feature                      | Description                                                                          | NaN si           |
| ---------------------------- | ------------------------------------------------------------------------------------ | ---------------- |
| `f_qte_fac_vs_prescrite_max` | Ratio max (qté facturée / qté prescrite) parmi les codes présents dans l'ordonnance. | pas d'ordonnance |
| `f_nb_lignes_qte_excessive`  | Nombre de lignes où qté facturée > qté prescrite.                                    | pas d'ordonnance |

### Groupe 3 – LIGNES_NON_PRESCRITES / SUBSTITUTION / ACTE_FICTIF (4 features)

| Feature                         | Description                                                                  | NaN si                                     |
| ------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------ |
| `f_part_lignes_hors_ordonnance` | Part (0–1) des lignes dont le code est absent de l'ordonnance.               | pas d'ordonnance                           |
| `f_med_hors_ordo_cher`          | 1 si au moins un médicament hors ordonnance a prix > médiane du référentiel. | pas d'ordonnance                           |
| `f_ordonnance_absente_requise`  | 1 si pas d'ordonnance ET un acte requiert ordonnance (ref). 0 sinon.         | référentiel absent                         |
| `f_ordonnance_autre_assure`     | 1 si l'ordonnance appartient à un assuré différent.                          | pas d'ordonnance ou ordonnance non trouvée |

### Groupe 4 – ORDONNANCE_EXPIREE (2 features)

| Feature                       | Description                                                                    | NaN si                                    |
| ----------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------- |
| `f_delai_soin_prescription_j` | Jours entre date_prescription et date_soin. Négatif = soin avant prescription. | pas d'ordonnance                          |
| `f_ordonnance_expiree`        | 1 si délai > validite_jours de l'ordonnance.                                   | pas d'ordonnance ou validite_jours absent |

### Groupe 5 – SOINS_JOUR_FERME (1 feature)

| Feature             | Description                                                                   | NaN si                            |
| ------------------- | ----------------------------------------------------------------------------- | --------------------------------- |
| `f_soin_jour_ferme` | 1 si le jour de semaine du soin n'est pas dans jours_ouverture (1=lun…7=dim). | prestataire ou date_soin inconnus |

### Groupe 6 – DOUBLON / FRACTIONNEMENT (3 features)

> Ces features nécessitent un DataFrame `history` non vide (factures antérieures).
> NaN si `history` est vide.

| Feature                         | Description                                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------------- |
| `f_nb_doublons_anterieurs`      | Nb de factures en historique avec même (assure, prestataire, date, montant).                |
| `f_numero_facture_deja_vu`      | 1 si le numero_facture apparaît en historique.                                              |
| `f_nb_factures_meme_jour_prest` | Nb de factures en historique avec même (assure, prestataire, date) — signal fractionnement. |

### Groupe 7 – SURCONSOMMATION (1 feature)

| Feature                           | Description                                                                     | NaN si                           |
| --------------------------------- | ------------------------------------------------------------------------------- | -------------------------------- |
| `f_nb_prest_meme_ordo_anterieurs` | Nb de prestataires distincts ayant facturé la même ordonnance_id en historique. | pas d'ordonnance ou history vide |

### Groupe 8 – INCOHERENCE_PROFIL (3 features)

| Feature                   | Description                                                           | NaN si                                 |
| ------------------------- | --------------------------------------------------------------------- | -------------------------------------- |
| `f_age_au_soin`           | Âge assuré = année(date_soin) − annee_naissance.                      | assures absent ou annee_naissance null |
| `f_age_hors_bornes_ref`   | 1 si âge hors [age_min, age_max] du référentiel pour ≥ 1 acte.        | lignes ou référentiel absent           |
| `f_sexe_incompatible_ref` | 1 si sexe incompatible avec sexe_requis du référentiel pour ≥ 1 acte. | sexe ou référentiel absent             |

### Groupe 9 – PRESTATAIRE_RADIE (2 features)

| Feature                          | Description                           | NaN si                                        |
| -------------------------------- | ------------------------------------- | --------------------------------------------- |
| `f_prestataire_non_conventionne` | 1 si conventionne = 0.                | prestataires absent                           |
| `f_soin_apres_fin_convention`    | 1 si date_soin > date_fin_convention. | date_fin_convention null (contrat ouvert) → 0 |

### Groupe 10 – HORS_COUVERTURE (4 features)

| Feature                       | Description                                                                    | NaN si          |
| ----------------------------- | ------------------------------------------------------------------------------ | --------------- |
| `f_soin_avant_adhesion`       | 1 si date_soin < date_adhesion.                                                | assures absent  |
| `f_soin_apres_radiation`      | 1 si assuré radié ET date_soin > date_radiation.                               | assures absent  |
| `f_soin_hors_periode_contrat` | 1 si date_soin < date_effet OU date_soin > date_fin (quand date_fin non null). | contrats absent |
| `f_soin_en_carence`           | **Non implémenté V1** (variance attendue quasi-nulle). Toujours NaN.           | —               |

### Groupe 11 – UPCODING (1 feature)

| Feature                    | Description                                                        | NaN si                                     |
| -------------------------- | ------------------------------------------------------------------ | ------------------------------------------ |
| `f_type_prest_vs_cat_acte` | 1 si consultation de spécialiste facturée par un cabinet inadapté. | aucune consultation connue dans la facture |

---

## Note M2 (exclusions V1)

Les colonnes suivantes sont exclues de V1 pour risque de fuite ou manque de signal :
`canal_reception`, `mode_reglement`, `heure_soin`, `date_reception`, `type_facture`,
`attestation_pec_id`, `entente_prealable_id`, `montant_eligible`, `devise`.
Elles pourront être étudiées en M2 après audit data et ingénierie spécifique.

---

## Usage

```bash
# Données complètes
make features
# Échantillon (dev)
make features-sample
# Ou directement
PYTHONPATH=src python -m predicare.ml.features --sample 500 --seed 42
```
