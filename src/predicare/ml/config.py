"""Configuration du module ML PrediCare (PB-09 → PB-14).

Cible retenue : ``cible_controle_medical`` (proxy « suspicion d'abus »).
Aucun label de fraude confirmée n'existe dans le jeu de données fourni : cette
limite est documentée dans ``docs/model_card_v1.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_RAW = PROJECT_ROOT / "data" / "raw"
MODELS_ROOT = PROJECT_ROOT / "models"
MODELS_DIR = MODELS_ROOT / "v1.0.0"
REPORTS_DIR = PROJECT_ROOT / "reports" / "ml"
DOCS_DIR = PROJECT_ROOT / "docs"

# Dossier de référence Phase 4 (dataset déjà construit, labels, alertes).
REFERENCE_DIR = Path(
    os.environ.get(
        "PREDICARE_REFERENCE_DIR",
        PROJECT_ROOT.parent / "rapports_predicare" / "phase4_ml",
    )
)

# Dossier des 12 CSV sources (pour PB-09 notamment).
SOURCE_DIR = Path(
    os.environ.get(
        "PREDICARE_SOURCE",
        PROJECT_ROOT.parent / "CohorteAI_datagen" / "dataset",
    )
)

DATASET_ML = DATA_RAW / "dataset_ml.csv"
LABELS_SECONDAIRES = DATA_RAW / "labels_secondaires.csv"
ALERTES_FACTURES = DATA_RAW / "alertes_factures.csv"
DATASET_CM = DATA_RAW / "dataset_cm.csv"
SCORES_TEST = DATA_RAW / "scores_test_cm.csv"
MODEL_PATH = MODELS_DIR / "model.joblib"
METADATA_PATH = MODELS_DIR / "metadata.json"
REGISTRY_PATH = MODELS_ROOT / "registry.json"

# --------------------------------------------------------------------------- #
# Cible et variables
# --------------------------------------------------------------------------- #
TARGET = "cible_cm"
TARGET_LABEL = "1 = facture orientée contrôle médical, 0 = facture payée"
TARGET_DESCRIPTION = (
    "Proxy de suspicion d'abus : motif de rejet CONTROLE_MEDICAL. "
    "Les rejets purement administratifs sont exclus de l'apprentissage."
)

# Colonnes techniques jamais utilisées comme variables.
META_COLUMNS = (
    "facture_id",
    "split",
    "fold_cv",
    "meta_date_reception",
    "meta_assure_id",
    "meta_prestataire_id",
    "cible",
    "cible_rejet",
    "cible_cm",
    "statut",
    "motif_rejet",
    "cible_controle_medical",
    "date_traitement",
    "montant_eligible",
    "montant_pris_en_charge",
    "reste_a_charge",
)

# Colonnes de fuite explicites (connues après la décision ou identifiants).
LEAKAGE_COLUMNS = (
    "statut",
    "motif_rejet",
    "date_traitement",
    "montant_eligible",
    "montant_pris_en_charge",
    "reste_a_charge",
    "cible",
    "cible_rejet",
    "cible_cm",
    "cible_controle_medical",
)

# --------------------------------------------------------------------------- #
# Modélisation
# --------------------------------------------------------------------------- #
SEED = 42
RECALL_TARGET = 0.80
DEFAULT_THRESHOLD = 0.80  # seuil produit demandé par le CDC (Flux 1)
PRECISION_FLOOR = 0.15  # garde-fou métier pour le point de fonctionnement

STRATEGIES_DESEQUILIBRE = ("poids", "smote")

PARAMS_LIGHTGBM = {
    "n_estimators": 500,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 30,
    "subsample": 0.85,
    "colsample_bytree": 0.7,
    "reg_lambda": 1.0,
    "random_state": SEED,
    "n_jobs": -1,
    "verbose": -1,
}

PARAMS_XGBOOST = {
    "n_estimators": 500,
    "learning_rate": 0.03,
    "max_depth": 5,
    "min_child_weight": 5,
    "subsample": 0.85,
    "colsample_bytree": 0.7,
    "reg_lambda": 1.0,
    "random_state": SEED,
    "n_jobs": -1,
    "eval_metric": "aucpr",
    "tree_method": "hist",
}

# --------------------------------------------------------------------------- #
# Libellés métier pour l'explicabilité (PB-13)
# --------------------------------------------------------------------------- #
FEATURE_LABELS: dict[str, str] = {
    "montant_total": "Montant total de la facture",
    "log_montant_total": "Montant total (échelle logarithmique)",
    "nb_lignes": "Nombre de lignes de la facture",
    "montant_moyen_ligne": "Montant moyen par ligne",
    "a_ordonnance": "Une ordonnance est rattachée",
    "a_attestation_pec": "Une attestation de prise en charge est rattachée",
    "a_entente_prealable": "Une entente préalable est rattachée",
    "ecart_tarif_reference": "Écart au tarif de référence",
    "ratio_prix_reference_max": "Ratio prix facturé / tarif maximal",
    "nb_lignes_sup_tarif_max": "Lignes au-dessus du tarif maximal",
    "ecart_grille_prestataire": "Écart à la grille tarifaire du prestataire",
    "ratio_prix_grille_max": "Ratio prix facturé / grille du prestataire",
    "nb_lignes_hors_grille": "Lignes hors grille tarifaire",
    "nb_lignes_exclues_formule": "Lignes exclues par la formule",
    "nb_lignes_profil_incoherent": "Lignes incohérentes avec le profil",
    "nb_lignes_non_prescrites": "Lignes non prescrites",
    "quantite_excedentaire": "Quantité facturée au-delà du prescrit",
    "ecart_prescription": "Écart entre facturation et prescription",
    "ordonnance_perimee": "Ordonnance périmée au moment du soin",
    "ordonnance_postdatee": "Ordonnance postdatée",
    "ordonnance_avant_adhesion": "Ordonnance antérieure à l'adhésion",
    "prescripteur_est_prestataire": "Le prescripteur est aussi le prestataire",
    "surconsommation_ordonnance": "Surconsommation / nomadisme pharmaceutique",
    "upcoding_majoration_indue": "Upcoding / majoration indue",
    "nb_lignes_doublon_prescription": "Lignes en doublon de prescription",
    "prescripteur_incompatible": "Prescripteur incompatible avec l'acte",
    "doublon_prescription_30j": "Doublon de prescription sur 30 jours",
    "nb_alertes_metier": "Nombre de règles métier déclenchées",
    "score_regles_metier": "Score du moteur de règles métier",
    "prest_taux_rejet_hist_lisse": "Taux de rejet historique du prestataire",
    "prest_nb_rejets_hist": "Rejets historiques du prestataire",
    "prest_nb_decidees_hist": "Décisions historiques du prestataire",
    "assure_taux_rejet_hist_lisse": "Taux de rejet historique de l'assuré",
    "assure_nb_factures_hist": "Factures historiques de l'assuré",
    "nb_doublons_exacts_anterieurs": "Doublons exacts antérieurs",
    "doublon_potentiel": "Doublon potentiel",
    "ratio_montant_moy_hist_prest": "Ratio au montant moyen historique du prestataire",
    "taux_conso_plafond_categorie": "Consommation du plafond de catégorie",
    "taux_conso_plafond_global": "Consommation du plafond global",
    "meme_ville_assure_prestataire": "Assuré et prestataire dans la même ville",
    "soin_week_end": "Soin réalisé le week-end",
    "soin_nuit": "Soin réalisé la nuit",
    "prestataire_ferme_jour_soin": "Prestataire fermé le jour du soin",
    "soin_hors_horaires": "Soin hors horaires d'ouverture",
    "convention_terminee_au_soin": "Convention terminée au moment du soin",
    "carence_non_ecoulee": "Carence non écoulée",
    "soin_avant_adhesion": "Soin antérieur à l'adhésion",
    "soin_apres_radiation": "Soin postérieur à la radiation",
    "soin_hors_contrat": "Soin hors contrat",
}

# Libellés complémentaires (lots, délais, profils, catégories).
FEATURE_LABELS.update(
    {
        "delai_soin_facture_j": "Délai entre le soin et la facture (jours)",
        "delai_facture_reception_j": "Délai entre la facture et la réception (jours)",
        "delai_soin_reception_j": "Délai entre le soin et la réception (jours)",
        "jour_semaine_soin": "Jour de la semaine du soin",
        "heure_soin_h": "Heure du soin",
        "nb_lignes_acte": "Nombre de lignes d'actes",
        "nb_lignes_medicament": "Nombre de lignes de médicaments",
        "nb_codes_distincts": "Nombre de codes distincts",
        "quantite_totale": "Quantité totale facturée",
        "quantite_max_ligne": "Quantité maximale sur une ligne",
        "ratio_prix_reference_moy": "Ratio prix moyen / tarif de référence",
        "ecart_tarif_reference_pct": "Écart relatif au tarif de référence (%)",
        "entente_requise_manquante": "Entente préalable requise mais absente",
        "ordonnance_requise_manquante": "Ordonnance requise mais absente",
        "attestation_requise_manquante": "Attestation requise mais absente",
        "ordonnance_age_au_soin_j": "Âge de l'ordonnance au moment du soin (jours)",
        "nb_lignes_ordonnance": "Nombre de lignes de l'ordonnance",
        "age_au_soin": "Âge du bénéficiaire au moment du soin",
        "nb_beneficiaires": "Nombre de bénéficiaires du contrat",
        "anciennete_adhesion_j": "Ancienneté de l'adhésion (jours)",
        "anciennete_contrat_j": "Ancienneté du contrat (jours)",
        "taux_remboursement": "Taux de remboursement de la garantie",
        "franchise_par_facture": "Franchise par facture",
        "delai_carence_jours": "Délai de carence (jours)",
        "attestation_requise": "Attestation requise par la garantie",
        "jours_carence_restants": "Jours de carence restants",
        "note_qualite": "Note de qualité du prestataire",
        "anciennete_convention_j": "Ancienneté de la convention (jours)",
        "prest_nb_decidees_90j": "Décisions du prestataire sur 90 jours",
        "prest_taux_rejet_90j_lisse": "Taux de rejet du prestataire sur 90 jours",
        "assure_nb_decidees_hist": "Décisions historiques de l'assuré",
        "assure_nb_rejets_hist": "Rejets historiques de l'assuré",
        "prest_nb_factures_hist": "Factures historiques du prestataire",
        "prest_nb_factures_90j": "Factures du prestataire sur 90 jours",
        "assure_nb_factures_30j": "Factures de l'assuré sur 30 jours",
        "assure_nb_factures_90j": "Factures de l'assuré sur 90 jours",
        "jours_depuis_derniere_facture": "Jours depuis la dernière facture",
        "premiere_facture_assure": "Première facture de l'assuré",
        "nb_factures_meme_jour_meme_prest_ant": "Factures antérieures le même jour chez le même prestataire",
        "numero_facture_deja_vu": "Numéro de facture déjà vu",
        "type_facture": "Type de facture",
        "canal_reception": "Canal de réception",
        "mode_reglement": "Mode de règlement",
        "type_ordonnance": "Type d'ordonnance",
        "sexe": "Sexe du bénéficiaire",
        "rang_beneficiaire": "Rang du bénéficiaire",
        "formule": "Formule de couverture",
        "secteur": "Secteur d'activité de l'employeur",
        "type_prestataire": "Type de prestataire",
        "specialite_prestataire": "Spécialité du prestataire",
        "niveau_tarif": "Niveau tarifaire du prestataire",
        "ecart_tarif_conventionne": "Écart au tarif conventionné",
        "jour_fermeture_etablissement": "Acte un jour de fermeture de l'établissement",
    }
)


def feature_label(name: str) -> str:
    """Libellé métier lisible d'une variable (repli : nom technique)."""
    return FEATURE_LABELS.get(name, name.replace("_", " "))
