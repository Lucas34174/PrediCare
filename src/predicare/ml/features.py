"""Module de feature engineering orienté fraude pour PrediCare TPA.

Responsabilité :
    Construire, à partir des tables nettoyées du pipeline PB-04, un vecteur de
    features par facture couvrant les 14 types de fraude du dictionnaire §6.
    Ce module NE lit jamais les labels et NE produit jamais de colonne à fuite.

Interface publique :
    build_features(factures, ref_tables, history) -> pd.DataFrame

Anti-fuite (règle absolue) :
    Colonnes interdites en entrée ET en sortie :
      - statut, motif_rejet, montant_pris_en_charge, date_traitement (LEAKAGE_COLUMNS)
      - est_fraude, type_fraude, detail_fraude, est_valide, motif_invalidite, est_suspect
    Colonnes-clés non incluses comme features :
      - facture_id, assure_id (clés, pas de signal)
    Aucune statistique ajustée sur le jeu entier (moyenne, écart-type, encodage cible) :
      le découpage et l'ajustement appartiennent à PB-06.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger("predicare.ml.features")


# Constantes anti-fuite

LEAKAGE_COLS: frozenset[str] = frozenset(
    ["statut", "motif_rejet", "montant_pris_en_charge", "date_traitement"]
)
LABEL_COLS: frozenset[str] = frozenset(
    [
        "est_fraude",
        "type_fraude",
        "detail_fraude",
        "est_valide",
        "motif_invalidite",
        "est_suspect",
    ]
)
FORBIDDEN_FEATURE_COLS: frozenset[str] = LEAKAGE_COLS | LABEL_COLS


# Catalogue des features

# Chaque entrée : nom -> dict(description, fraude_visee, tables_sources, inference_ok)
FEATURE_CATALOGUE: dict[str, dict[str, Any]] = {
    # --- Groupe 1 : Tarifaire (SURFACTURATION) ---
    "f_ecart_tarif_max_moy": {
        "description": (
            "Écart moyen (prix facturé − tarif_max du référentiel) sur les lignes "
            "d'actes. Valeur positive = surfacturation par rapport au plafond."
        ),
        "fraude_visee": "SURFACTURATION",
        "tables_sources": ["lignes_facture", "referentiel_actes"],
        "inference_ok": True,
    },
    "f_ratio_tarif_ref_max": {
        "description": (
            "Ratio maximal (prix facturé / tarif_reference du référentiel) sur les "
            "lignes d'actes. Ratio > 1 = facturation au-dessus du tarif de référence."
        ),
        "fraude_visee": "SURFACTURATION",
        "tables_sources": ["lignes_facture", "referentiel_actes"],
        "inference_ok": True,
    },
    "f_ecart_grille_prest_moy": {
        "description": (
            "Écart moyen (prix facturé − tarif_pratique de la grille prestataire) sur "
            "les lignes ayant un code dans la grille. Valeur positive = dépassement "
            "de la grille conventionnelle."
        ),
        "fraude_visee": "SURFACTURATION",
        "tables_sources": ["lignes_facture", "grille_tarifaire"],
        "inference_ok": True,
    },
    "f_nb_lignes_hors_tarif_max": {
        "description": (
            "Nombre de lignes d'actes dont le prix unitaire dépasse le tarif_max du référentiel."
        ),
        "fraude_visee": "SURFACTURATION",
        "tables_sources": ["lignes_facture", "referentiel_actes"],
        "inference_ok": True,
    },
    "f_ratio_med_prix_ref_max": {
        "description": (
            "Ratio maximal (prix médicament facturé / prix_reference du référentiel) "
            "sur les lignes de médicaments."
        ),
        "fraude_visee": "SURFACTURATION",
        "tables_sources": ["lignes_facture", "referentiel_medicaments"],
        "inference_ok": True,
    },
    # --- Groupe 2 : Quantité (QUANTITE_EXCESSIVE) ---
    "f_qte_fac_vs_prescrite_max": {
        "description": (
            "Ratio maximal (quantité facturée / quantité prescrite) parmi les lignes "
            "dont le code figure dans l'ordonnance. Valeur > 1 = surconsommation."
        ),
        "fraude_visee": "QUANTITE_EXCESSIVE",
        "tables_sources": ["lignes_facture", "ordonnance_lignes"],
        "inference_ok": True,
    },
    "f_nb_lignes_qte_excessive": {
        "description": (
            "Nombre de lignes pour lesquelles la quantité facturée dépasse "
            "la quantité prescrite dans l'ordonnance."
        ),
        "fraude_visee": "QUANTITE_EXCESSIVE",
        "tables_sources": ["lignes_facture", "ordonnance_lignes"],
        "inference_ok": True,
    },
    # --- Groupe 3 : Ordonnance (LIGNES_NON_PRESCRITES, SUBSTITUTION, ACTE_FICTIF) ---
    "f_part_lignes_hors_ordonnance": {
        "description": (
            "Part (ratio 0-1) des lignes facturées dont le code est absent de "
            "l'ordonnance associée. NaN si pas d'ordonnance."
        ),
        "fraude_visee": "LIGNES_NON_PRESCRITES",
        "tables_sources": ["lignes_facture", "ordonnance_lignes"],
        "inference_ok": True,
    },
    "f_med_hors_ordo_cher": {
        "description": (
            "Indicateur (0/1) : au moins un médicament facturé est absent de "
            "l'ordonnance ET son prix unitaire dépasse le prix_reference médian "
            "du référentiel médicaments."
        ),
        "fraude_visee": "SUBSTITUTION_PRODUIT",
        "tables_sources": ["lignes_facture", "ordonnance_lignes", "referentiel_medicaments"],
        "inference_ok": True,
    },
    "f_ordonnance_absente_requise": {
        "description": (
            "Indicateur (0/1) : la facture n'a pas d'ordonnance (ordonnance_id null) "
            "mais contient au moins un acte pour lequel ordonnance_requise = 1 "
            "dans le référentiel."
        ),
        "fraude_visee": "ACTE_FICTIF",
        "tables_sources": ["factures", "lignes_facture", "referentiel_actes"],
        "inference_ok": True,
    },
    "f_ordonnance_autre_assure": {
        "description": (
            "Indicateur (0/1) : l'ordonnance associée appartient à un assure_id "
            "différent de celui de la facture."
        ),
        "fraude_visee": "ACTE_FICTIF",
        "tables_sources": ["factures", "ordonnances"],
        "inference_ok": True,
    },
    # --- Groupe 4 : Délai ordonnance (ORDONNANCE_EXPIREE) ---
    "f_delai_soin_prescription_j": {
        "description": (
            "Nombre de jours entre la date de prescription et la date de soin "
            "(date_soin − date_prescription). Valeur négative = soin avant prescription."
        ),
        "fraude_visee": "ORDONNANCE_EXPIREE",
        "tables_sources": ["factures", "ordonnances"],
        "inference_ok": True,
    },
    "f_ordonnance_expiree": {
        "description": (
            "Indicateur (0/1) : le délai soin−prescription dépasse la validite_jours "
            "de l'ordonnance."
        ),
        "fraude_visee": "ORDONNANCE_EXPIREE",
        "tables_sources": ["factures", "ordonnances"],
        "inference_ok": True,
    },
    # --- Groupe 5 : Calendrier (SOINS_JOUR_FERME) ---
    "f_soin_jour_ferme": {
        "description": (
            "Indicateur (0/1) : le jour de la semaine du soin n'est pas dans les "
            "jours_ouverture déclarés du prestataire "
            "(encodage : chiffres 1=lun … 7=dim concaténés)."
        ),
        "fraude_visee": "SOINS_JOUR_FERME",
        "tables_sources": ["factures", "prestataires"],
        "inference_ok": True,
    },
    # --- Groupe 6 : Doublon / Fractionnement ---
    "f_nb_doublons_anterieurs": {
        "description": (
            "Nombre de factures antérieures (ordre date_soin, facture_id) pour le "
            "même triplet (assure_id, prestataire_id, date_soin) avec le même "
            "montant_total."
        ),
        "fraude_visee": "DOUBLON",
        "tables_sources": ["factures", "history"],
        "inference_ok": True,
    },
    "f_numero_facture_deja_vu": {
        "description": (
            "Indicateur (0/1) : le numero_facture apparaît dans au moins une facture antérieure."
        ),
        "fraude_visee": "DOUBLON",
        "tables_sources": ["factures", "history"],
        "inference_ok": True,
    },
    "f_nb_factures_meme_jour_prest": {
        "description": (
            "Nombre de factures antérieures pour le même (assure_id, prestataire_id, "
            "date_soin), sans contrainte de montant — signal de fractionnement."
        ),
        "fraude_visee": "FRACTIONNEMENT",
        "tables_sources": ["factures", "history"],
        "inference_ok": True,
    },
    # --- Groupe 7 : Surconsommation d'ordonnance ---
    "f_nb_prest_meme_ordo_anterieurs": {
        "description": (
            "Nombre de prestataires distincts ayant facturé la même ordonnance_id "
            "dans des factures antérieures (hors ordonnance_id null)."
        ),
        "fraude_visee": "SURCONSOMMATION",
        "tables_sources": ["factures", "history"],
        "inference_ok": True,
    },
    # --- Groupe 8 : Profil (INCOHERENCE_PROFIL) ---
    "f_age_au_soin": {
        "description": (
            "Âge de l'assuré au moment du soin, calculé comme year(date_soin) − annee_naissance."
        ),
        "fraude_visee": "INCOHERENCE_PROFIL",
        "tables_sources": ["factures", "assures"],
        "inference_ok": True,
    },
    "f_age_hors_bornes_ref": {
        "description": (
            "Indicateur (0/1) : l'âge de l'assuré est hors des bornes [age_min, "
            "age_max] du référentiel pour au moins un acte facturé."
        ),
        "fraude_visee": "INCOHERENCE_PROFIL",
        "tables_sources": ["lignes_facture", "referentiel_actes", "assures"],
        "inference_ok": True,
    },
    "f_sexe_incompatible_ref": {
        "description": (
            "Indicateur (0/1) : le sexe de l'assuré est incompatible avec "
            "sexe_requis du référentiel pour au moins un acte (quand sexe_requis "
            "est renseigné)."
        ),
        "fraude_visee": "INCOHERENCE_PROFIL",
        "tables_sources": ["lignes_facture", "referentiel_actes", "assures"],
        "inference_ok": True,
    },
    # --- Groupe 9 : Prestataire radié (PRESTATAIRE_RADIE) ---
    "f_prestataire_non_conventionne": {
        "description": (
            "Indicateur (0/1) : le prestataire n'est pas conventionné (conventionne = 0)."
        ),
        "fraude_visee": "PRESTATAIRE_RADIE",
        "tables_sources": ["prestataires"],
        "inference_ok": True,
    },
    "f_soin_apres_fin_convention": {
        "description": (
            "Indicateur (0/1) : date_soin > date_fin_convention du prestataire "
            "(quand date_fin_convention n'est pas null)."
        ),
        "fraude_visee": "PRESTATAIRE_RADIE",
        "tables_sources": ["factures", "prestataires"],
        "inference_ok": True,
    },
    # --- Groupe 10 : Hors couverture (HORS_COUVERTURE) ---
    "f_soin_avant_adhesion": {
        "description": (
            "Indicateur (0/1) : date_soin est antérieure à la date d'adhésion de l'assuré."
        ),
        "fraude_visee": "HORS_COUVERTURE",
        "tables_sources": ["factures", "assures"],
        "inference_ok": True,
    },
    "f_soin_apres_radiation": {
        "description": (
            "Indicateur (0/1) : l'assuré est radié (date_radiation non null) "
            "et date_soin > date_radiation."
        ),
        "fraude_visee": "HORS_COUVERTURE",
        "tables_sources": ["factures", "assures"],
        "inference_ok": True,
    },
    "f_soin_hors_periode_contrat": {
        "description": (
            "Indicateur (0/1) : date_soin est hors de la période [date_effet, "
            "date_fin] du contrat (date_fin null = contrat ouvert)."
        ),
        "fraude_visee": "HORS_COUVERTURE",
        "tables_sources": ["factures", "contrats"],
        "inference_ok": True,
    },
    "f_soin_en_carence": {
        "description": (
            "Indicateur (0/1) : date_soin < date_adhesion + delai_carence_jours "
            "pour la formule et la catégorie de l'acte dominant du contrat. "
            "À mesurer : quasi-nul si tous les delai_carence_jours = 0."
        ),
        "fraude_visee": "HORS_COUVERTURE",
        "tables_sources": ["factures", "assures", "contrats", "garanties"],
        "inference_ok": True,
    },
    # --- Groupe 11 : UPCODING (proxy) ---
    "f_type_prest_vs_cat_acte": {
        "description": (
            "Indicateur (0/1) : le type_prestataire ne correspond pas à la "
            "spécialité attendue pour la catégorie d'acte la plus représentée "
            "dans la facture (proxy UPCODING ; sans heure_soin, signal partiel)."
        ),
        "fraude_visee": "UPCODING",
        "tables_sources": ["lignes_facture", "referentiel_actes", "prestataires"],
        "inference_ok": True,
    },
}

# Colonnes de features attendues en sortie (ordre stable)
FEATURE_NAMES: list[str] = list(FEATURE_CATALOGUE.keys())


# Fonction publique principale


def build_features(
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
    history: pd.DataFrame,
) -> pd.DataFrame:
    """Construit la table de features par facture.

    La sortie n'est indexée que par facture_id (non inclus comme feature).
    Les valeurs manquantes sont laissées à NaN (imputation = PB-06).

    Args:
        factures: DataFrame des factures à scorer (colonnes issues de PB-04, sans
                  colonnes de fuite ni labels). Peut contenir 1 ou N lignes.
        ref_tables: Dictionnaire des tables de référentiels et données annexes
                    nettoyées. Clés attendues : 'lignes_facture', 'ordonnances',
                    'ordonnance_lignes', 'assures', 'contrats', 'prestataires',
                    'garanties', 'referentiel_actes', 'referentiel_medicaments',
                    'grille_tarifaire'.
        history: DataFrame des factures déjà traitées (format identique à factures),
                 utilisé pour les features historiques (doublon, fractionnement,
                 surconsommation). Doit être libre de toute colonne de fuite.

    Returns:
        DataFrame indexé sur facture_id avec exactement FEATURE_NAMES comme colonnes.
        Aucune colonne de fuite, aucun label.

    Raises:
        ValueError: si une colonne interdite (FORBIDDEN_FEATURE_COLS) est détectée
                    en entrée.
    """
    _assert_no_leakage(factures, context="factures")
    _assert_no_leakage(history, context="history")

    feat = pd.DataFrame(index=factures["facture_id"])
    feat.index.name = "facture_id"

    feat = _add_tarif_features(feat, factures, ref_tables)
    feat = _add_quantite_features(feat, factures, ref_tables)
    feat = _add_ordonnance_features(feat, factures, ref_tables)
    feat = _add_calendrier_features(feat, factures, ref_tables)
    feat = _add_historique_features(feat, factures, history)
    feat = _add_profil_features(feat, factures, ref_tables)
    feat = _add_couverture_features(feat, factures, ref_tables)
    feat = _add_upcoding_features(feat, factures, ref_tables)

    # Garantie : colonnes dans l'ordre du catalogue, NaN si non calculé
    for col in FEATURE_NAMES:
        if col not in feat.columns:
            feat[col] = float("nan")
    return feat[FEATURE_NAMES]


# Garde anti-fuite


def _assert_no_leakage(df: pd.DataFrame, context: str = "") -> None:
    """Lève ValueError si une colonne interdite est présente dans df."""
    forbidden = FORBIDDEN_FEATURE_COLS & set(df.columns)
    if forbidden:
        raise ValueError(
            f"Colonnes interdites détectées dans '{context}' : {sorted(forbidden)}. "
            "Retirer ces colonnes avant d'appeler build_features()."
        )


# Stubs des groupes de features (Commit 1 : interfaces uniquement)
# Les groupes suivants seront implémentés dans les commits 2 à 6.


def _add_tarif_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 1 – Features tarifaires (SURFACTURATION). Implémenté en commit 2."""
    for col in [
        "f_ecart_tarif_max_moy",
        "f_ratio_tarif_ref_max",
        "f_ecart_grille_prest_moy",
        "f_nb_lignes_hors_tarif_max",
        "f_ratio_med_prix_ref_max",
    ]:
        feat[col] = float("nan")
    return feat


def _add_quantite_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 2 – Features quantité (QUANTITE_EXCESSIVE). Implémenté en commit 3."""
    for col in ["f_qte_fac_vs_prescrite_max", "f_nb_lignes_qte_excessive"]:
        feat[col] = float("nan")
    return feat


def _add_ordonnance_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 3+4 – Features ordonnance. Implémenté en commit 3."""
    for col in [
        "f_part_lignes_hors_ordonnance",
        "f_med_hors_ordo_cher",
        "f_ordonnance_absente_requise",
        "f_ordonnance_autre_assure",
        "f_delai_soin_prescription_j",
        "f_ordonnance_expiree",
    ]:
        feat[col] = float("nan")
    return feat


def _add_calendrier_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 5 – Features calendrier/prestataire. Implémenté en commit 4."""
    feat["f_soin_jour_ferme"] = float("nan")
    return feat


def _add_historique_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    history: pd.DataFrame,
) -> pd.DataFrame:
    """Groupe 6+7 – Features historiques. Implémenté en commit 6."""
    for col in [
        "f_nb_doublons_anterieurs",
        "f_numero_facture_deja_vu",
        "f_nb_factures_meme_jour_prest",
        "f_nb_prest_meme_ordo_anterieurs",
    ]:
        feat[col] = float("nan")
    return feat


def _add_profil_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 8 – Features profil assuré. Implémenté en commit 5."""
    for col in [
        "f_age_au_soin",
        "f_age_hors_bornes_ref",
        "f_sexe_incompatible_ref",
    ]:
        feat[col] = float("nan")
    return feat


def _add_couverture_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 9+10 – Features prestataire radié et couverture. Implémenté en commit 5."""
    for col in [
        "f_prestataire_non_conventionne",
        "f_soin_apres_fin_convention",
        "f_soin_avant_adhesion",
        "f_soin_apres_radiation",
        "f_soin_hors_periode_contrat",
        "f_soin_en_carence",
    ]:
        feat[col] = float("nan")
    return feat


def _add_upcoding_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 11 – Features UPCODING (proxy). Implémenté en commit 4."""
    feat["f_type_prest_vs_cat_acte"] = float("nan")
    return feat
