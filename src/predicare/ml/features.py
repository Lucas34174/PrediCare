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
            "Indicateur (0/1) : consultation de spécialiste (spécialité de l'acte ni "
            "GENERALISTE ni URGENCE) facturée par un cabinet généraliste, ou par un "
            "cabinet spécialiste d'une autre spécialité. NaN sans consultation."
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

_CONSULT_NON_SPECIALISTE: frozenset[str] = frozenset({"GENERALISTE", "URGENCE"})


def _to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce")


def _flag(cond: pd.Series, valid: pd.Series) -> pd.Series:
    """Indicateur 0/1 (float64), NaN là où `valid` est faux."""
    return cond.astype("float64").where(valid)


def _cols(df: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    """Sélectionne `names` ; les colonnes absentes sont créées à NaN."""
    out = df.reindex(columns=names).copy()
    return out


def _add_tarif_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 1 – Features tarifaires (SURFACTURATION).

    Jointures :
      - lignes_facture (ACTE)  × referentiel_actes  → écarts et ratios tarifaires
      - lignes_facture (MED)   × referentiel_meds   → ratio prix médicament
      - lignes_facture × factures[prestataire_id] × grille_tarifaire → écart grille
    """
    _cols = [
        "f_ecart_tarif_max_moy",
        "f_ratio_tarif_ref_max",
        "f_ecart_grille_prest_moy",
        "f_nb_lignes_hors_tarif_max",
        "f_ratio_med_prix_ref_max",
    ]
    lignes = ref_tables.get("lignes_facture", pd.DataFrame())
    if lignes.empty:
        for col in _cols:
            feat[col] = float("nan")
        return feat

    ref_actes = ref_tables.get("referentiel_actes", pd.DataFrame())
    ref_meds = ref_tables.get("referentiel_medicaments", pd.DataFrame())
    grille = ref_tables.get("grille_tarifaire", pd.DataFrame())

    # -- f1, f2, f4 : actes vs référentiel --
    if not ref_actes.empty and "code_acte" in ref_actes.columns:
        ref_a = ref_actes[["code_acte", "tarif_reference", "tarif_max"]].rename(
            columns={"code_acte": "code"}
        )
        la = lignes[lignes["type_ligne"] == "ACTE"].merge(ref_a, on="code", how="left")
        pu = la["prix_unitaire"].astype("float64")
        t_max = la["tarif_max"].astype("float64")
        t_ref = la["tarif_reference"].astype("float64")
        la["ecart_max"] = pu - t_max
        la["ratio_ref"] = pu / t_ref.where(t_ref > 0)
        la["hors_max"] = (pu > t_max).astype("float64").where(t_max.notna())
        grp_a = la.groupby("facture_id")
        feat["f_ecart_tarif_max_moy"] = grp_a["ecart_max"].mean()
        feat["f_ratio_tarif_ref_max"] = grp_a["ratio_ref"].max()
        feat["f_nb_lignes_hors_tarif_max"] = grp_a["hors_max"].sum()
    else:
        for col in ["f_ecart_tarif_max_moy", "f_ratio_tarif_ref_max", "f_nb_lignes_hors_tarif_max"]:
            feat[col] = float("nan")

    # -- f5 : médicaments vs référentiel --
    if not ref_meds.empty and "code_medicament" in ref_meds.columns:
        ref_m = ref_meds[["code_medicament", "prix_reference"]].rename(
            columns={"code_medicament": "code"}
        )
        lm = lignes[lignes["type_ligne"] == "MEDICAMENT"].merge(ref_m, on="code", how="left")
        pu_m = lm["prix_unitaire"].astype("float64")
        p_ref = lm["prix_reference"].astype("float64")
        lm["ratio_med"] = pu_m / p_ref.where(p_ref > 0)
        feat["f_ratio_med_prix_ref_max"] = lm.groupby("facture_id")["ratio_med"].max()
    else:
        feat["f_ratio_med_prix_ref_max"] = float("nan")

    # -- f3 : écart grille prestataire --
    if not grille.empty and "tarif_pratique" in grille.columns:
        fac_pr = factures[["facture_id", "prestataire_id"]]
        lg = lignes.merge(fac_pr, on="facture_id", how="left")
        lg = lg.merge(grille, on=["prestataire_id", "code"], how="left")
        pu_g = lg["prix_unitaire"].astype("float64")
        t_prat = lg["tarif_pratique"].astype("float64")
        lg["ecart_grille"] = pu_g - t_prat
        feat["f_ecart_grille_prest_moy"] = lg.groupby("facture_id")["ecart_grille"].mean()
    else:
        feat["f_ecart_grille_prest_moy"] = float("nan")

    return feat


def _add_quantite_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 2 – Features quantité excessive (QUANTITE_EXCESSIVE).

    Jointure : lignes_facture × factures[ordonnance_id] × ordonnance_lignes.
    NaN si la facture n'a pas d'ordonnance.
    """
    _cols = ["f_qte_fac_vs_prescrite_max", "f_nb_lignes_qte_excessive"]
    lignes = ref_tables.get("lignes_facture", pd.DataFrame())
    ol = ref_tables.get("ordonnance_lignes", pd.DataFrame())

    if lignes.empty or ol.empty:
        for col in _cols:
            feat[col] = float("nan")
        return feat

    fac_ordo = factures[["facture_id", "ordonnance_id"]].dropna(subset=["ordonnance_id"])
    if fac_ordo.empty:
        for col in _cols:
            feat[col] = float("nan")
        return feat

    # Lignes facturées avec leur ordonnance_id
    lg_ordo = lignes.merge(fac_ordo, on="facture_id", how="inner")

    # Quantité prescrite agrégée par (ordonnance_id, code)
    ol_agg = (
        ol.groupby(["ordonnance_id", "code"])["quantite"]
        .sum()
        .reset_index()
        .rename(columns={"quantite": "qte_prescrite"})
    )

    lg = lg_ordo.merge(ol_agg, on=["ordonnance_id", "code"], how="left")
    qte_f = lg["quantite"].astype("float64")
    qte_p = lg["qte_prescrite"].astype("float64")
    lg["ratio_qte"] = qte_f / qte_p.where(qte_p > 0)
    lg["qte_excessive"] = (qte_f > qte_p).astype("float64").where(qte_p.notna())

    grp_q = lg.groupby("facture_id")
    feat["f_qte_fac_vs_prescrite_max"] = grp_q["ratio_qte"].max()
    feat["f_nb_lignes_qte_excessive"] = grp_q["qte_excessive"].sum()
    return feat


def _add_ordonnance_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupes 3 et 4 – Features liées à l'ordonnance.

    Groupe 3 – LIGNES_NON_PRESCRITES / SUBSTITUTION_PRODUIT / ACTE_FICTIF :
      f_part_lignes_hors_ordonnance, f_med_hors_ordo_cher,
      f_ordonnance_absente_requise, f_ordonnance_autre_assure.
    Groupe 4 – ORDONNANCE_EXPIREE :
      f_delai_soin_prescription_j, f_ordonnance_expiree.

    Convention NaN :
      - Toutes les features ordonnance sont NaN si la facture n'a pas d'ordonnance_id,
        sauf f_ordonnance_absente_requise (0 si acte ne requiert pas d'ordonnance).
    """
    lignes = ref_tables.get("lignes_facture", pd.DataFrame())
    ordonnances = ref_tables.get("ordonnances", pd.DataFrame())
    ol = ref_tables.get("ordonnance_lignes", pd.DataFrame())
    ref_actes = ref_tables.get("referentiel_actes", pd.DataFrame())
    ref_meds = ref_tables.get("referentiel_medicaments", pd.DataFrame())

    fac_ordo = factures[["facture_id", "ordonnance_id"]].dropna(subset=["ordonnance_id"])
    fac_sans_ordo_ids = set(factures.loc[factures["ordonnance_id"].isna(), "facture_id"].dropna())

    # ---- f_part_lignes_hors_ordonnance et f_med_hors_ordo_cher ----
    if not lignes.empty and not ol.empty and not fac_ordo.empty:
        ordo_codes = ol[["ordonnance_id", "code"]].drop_duplicates()
        lg_ordo = lignes.merge(fac_ordo, on="facture_id", how="inner")
        lg_ordo = lg_ordo.merge(
            ordo_codes.assign(dans_ordo=True), on=["ordonnance_id", "code"], how="left"
        )
        lg_ordo["hors_ordo"] = lg_ordo["dans_ordo"].isna().astype(float)
        feat["f_part_lignes_hors_ordonnance"] = lg_ordo.groupby("facture_id")["hors_ordo"].mean()
        # f_med_hors_ordo_cher : médicament hors ordonnance avec prix > médiane référentiel
        if not ref_meds.empty and "prix_reference" in ref_meds.columns:
            prix_median = ref_meds["prix_reference"].astype("float64").median()
            lg_med_hors = lg_ordo[
                (lg_ordo["type_ligne"] == "MEDICAMENT") & (lg_ordo["hors_ordo"] == 1.0)
            ].copy()
            lg_med_hors["cher"] = (
                lg_med_hors["prix_unitaire"].astype("float64") > prix_median
            ).astype(float)
            feat["f_med_hors_ordo_cher"] = lg_med_hors.groupby("facture_id")["cher"].max()
            # factures avec ordo mais sans med hors ordo → 0
            feat["f_med_hors_ordo_cher"] = feat["f_med_hors_ordo_cher"].fillna(0.0)
            # factures sans ordonnance → NaN
            feat.loc[feat.index.isin(fac_sans_ordo_ids), "f_med_hors_ordo_cher"] = float("nan")
        else:
            feat["f_med_hors_ordo_cher"] = float("nan")
    else:
        feat["f_part_lignes_hors_ordonnance"] = float("nan")
        feat["f_med_hors_ordo_cher"] = float("nan")

    # ---- f_ordonnance_absente_requise ----
    # Par défaut 0 : si l'ordonnance est présente ou si l'acte n'en requiert pas
    feat["f_ordonnance_absente_requise"] = 0.0
    if not lignes.empty and not ref_actes.empty and "ordonnance_requise" in ref_actes.columns:
        actes_req = set(
            ref_actes.loc[ref_actes["ordonnance_requise"].astype(float) == 1, "code_acte"].dropna()
        )
        if fac_sans_ordo_ids and actes_req:
            lg_sans = lignes[lignes["facture_id"].isin(fac_sans_ordo_ids)].copy()
            lg_sans["acte_req"] = lg_sans["code"].isin(actes_req).astype(float)
            grp_req = lg_sans.groupby("facture_id")["acte_req"].max()
            # Mise à jour vectorisée (sécurisée contre les facture_ids hors feat.index)
            grp_aligned = grp_req.reindex(feat.index)
            feat["f_ordonnance_absente_requise"] = feat["f_ordonnance_absente_requise"].where(
                grp_aligned.isna(), grp_aligned
            )
    else:
        feat["f_ordonnance_absente_requise"] = float("nan")

    # ---- f_ordonnance_autre_assure ----
    if not ordonnances.empty and "assure_id" in ordonnances.columns and not fac_ordo.empty:
        fac_avec = factures[["facture_id", "assure_id", "ordonnance_id"]].dropna(
            subset=["ordonnance_id"]
        )
        ordo_assure = ordonnances[["ordonnance_id", "assure_id"]].rename(
            columns={"assure_id": "assure_ordo"}
        )
        mg = fac_avec.merge(ordo_assure, on="ordonnance_id", how="left")
        mg["autre_assure"] = (mg["assure_id"] != mg["assure_ordo"]).astype(float)
        mg.loc[mg["assure_ordo"].isna(), "autre_assure"] = float("nan")
        feat["f_ordonnance_autre_assure"] = mg.set_index("facture_id")["autre_assure"]
    else:
        feat["f_ordonnance_autre_assure"] = float("nan")

    # ---- f_delai_soin_prescription_j et f_ordonnance_expiree ----
    if not ordonnances.empty and "date_prescription" in ordonnances.columns and not fac_ordo.empty:
        fac_ordo_ds = factures[["facture_id", "date_soin", "ordonnance_id"]].dropna(
            subset=["ordonnance_id"]
        )
        ordo_dates = ordonnances[["ordonnance_id", "date_prescription", "validite_jours"]]
        mg_d = fac_ordo_ds.merge(ordo_dates, on="ordonnance_id", how="left")
        ds = pd.to_datetime(mg_d["date_soin"], errors="coerce")
        dp = pd.to_datetime(mg_d["date_prescription"], errors="coerce")
        mg_d["delai_j"] = (ds - dp).dt.days.astype("float64")
        vj = mg_d["validite_jours"].astype("float64")
        mg_d["expiree"] = (
            (mg_d["delai_j"] > vj).astype("float64").where(vj.notna() & mg_d["delai_j"].notna())
        )
        idx = mg_d.set_index("facture_id")
        feat["f_delai_soin_prescription_j"] = idx["delai_j"]
        feat["f_ordonnance_expiree"] = idx["expiree"]
    else:
        feat["f_delai_soin_prescription_j"] = float("nan")
        feat["f_ordonnance_expiree"] = float("nan")

    return feat


def _add_calendrier_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 5 – SOINS_JOUR_FERME.

    jours_ouverture : entier de chiffres concaténés (1=lun … 7=dim), ex. 12345.
    NaN si le prestataire, ses jours d'ouverture ou la date de soin sont inconnus.
    """
    presta = ref_tables.get("prestataires", pd.DataFrame())
    if presta.empty or "jours_ouverture" not in presta.columns:
        feat["f_soin_jour_ferme"] = float("nan")
        return feat

    fac = factures[["facture_id", "prestataire_id", "date_soin"]].merge(
        presta[["prestataire_id", "jours_ouverture"]], on="prestataire_id", how="left"
    )
    jour = pd.to_datetime(fac["date_soin"], errors="coerce").dt.dayofweek + 1
    jours = fac["jours_ouverture"].astype("string")
    fac["ferme"] = [
        float("nan") if pd.isna(j) or pd.isna(s) else float(str(int(j)) not in s)
        for j, s in zip(jour, jours, strict=True)
    ]
    feat["f_soin_jour_ferme"] = fac.set_index("facture_id")["ferme"]
    return feat


def _add_upcoding_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupe 11 – UPCODING : consultation de spécialiste hors du bon type de cabinet.

    NaN si la facture n'a aucune ligne de consultation connue du référentiel.
    Les signaux majoration/urgence (heure, jour) sont traités dans un commit ultérieur.
    """
    lignes = ref_tables.get("lignes_facture", pd.DataFrame())
    ref_actes = ref_tables.get("referentiel_actes", pd.DataFrame())
    presta = ref_tables.get("prestataires", pd.DataFrame())
    if lignes.empty or ref_actes.empty or presta.empty:
        feat["f_type_prest_vs_cat_acte"] = float("nan")
        return feat

    ra = ref_actes.loc[ref_actes["categorie"] == "CONSULTATION", ["code_acte", "specialite"]]
    ra = ra.rename(columns={"code_acte": "code", "specialite": "spec_acte"})
    la = lignes[lignes["type_ligne"] == "ACTE"].merge(ra, on="code", how="inner")
    la = la.merge(factures[["facture_id", "prestataire_id"]], on="facture_id", how="left")
    pr = presta[["prestataire_id", "type_prestataire", "specialite"]].rename(
        columns={"specialite": "spec_prest"}
    )
    la = la.merge(pr, on="prestataire_id", how="left")

    spec_acte = la["spec_acte"]
    type_p = la["type_prestataire"]
    est_spec = spec_acte.notna() & ~spec_acte.isin(_CONSULT_NON_SPECIALISTE)
    incoh_gen = est_spec & (type_p == "CABINET_GENERALISTE")
    incoh_spec = est_spec & (type_p == "CABINET_SPECIALISTE") & (la["spec_prest"] != spec_acte)
    la["incoh"] = (incoh_gen | incoh_spec).astype("float64").where(type_p.notna())
    feat["f_type_prest_vs_cat_acte"] = la.groupby("facture_id")["incoh"].max()
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
    """Groupe 8 – INCOHERENCE_PROFIL (âge, sexe vs bornes du référentiel d'actes)."""
    cols = ["f_age_au_soin", "f_age_hors_bornes_ref", "f_sexe_incompatible_ref"]
    assures = ref_tables.get("assures", pd.DataFrame())
    if assures.empty:
        for col in cols:
            feat[col] = float("nan")
        return feat

    fac = factures[["facture_id", "assure_id", "date_soin"]].merge(
        _cols(assures, ["assure_id", "sexe", "annee_naissance"]), on="assure_id", how="left"
    )
    annee = fac["annee_naissance"].astype("float64")
    fac["age"] = _to_dt(fac["date_soin"]).dt.year.astype("float64") - annee
    feat["f_age_au_soin"] = fac.set_index("facture_id")["age"]

    lignes = ref_tables.get("lignes_facture", pd.DataFrame())
    ref_actes = ref_tables.get("referentiel_actes", pd.DataFrame())
    if lignes.empty or ref_actes.empty:
        feat["f_age_hors_bornes_ref"] = float("nan")
        feat["f_sexe_incompatible_ref"] = float("nan")
        return feat

    ra = _cols(ref_actes, ["code_acte", "age_min", "age_max", "sexe_requis"])
    ra = ra.rename(columns={"code_acte": "code"})
    la = lignes.loc[lignes["type_ligne"] == "ACTE", ["facture_id", "code"]]
    la = la.merge(ra, on="code", how="left", indicator=True)
    la = la.merge(fac[["facture_id", "age", "sexe"]], on="facture_id", how="left")
    connu = la["_merge"] == "both"

    a_min = la["age_min"].astype("float64")
    a_max = la["age_max"].astype("float64")
    hors = (la["age"] < a_min) | (la["age"] > a_max)
    la["hors_bornes"] = _flag(hors, connu & la["age"].notna() & a_min.notna() & a_max.notna())

    sexe_req = la["sexe_requis"]
    incompat = sexe_req.notna() & (la["sexe"] != sexe_req)
    la["sexe_incompat"] = _flag(incompat, connu & la["sexe"].notna())

    grp = la.groupby("facture_id")
    feat["f_age_hors_bornes_ref"] = grp["hors_bornes"].max()
    feat["f_sexe_incompatible_ref"] = grp["sexe_incompat"].max()
    return feat


def _add_couverture_features(
    feat: pd.DataFrame,
    factures: pd.DataFrame,
    ref_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Groupes 9 et 10 – PRESTATAIRE_RADIE et HORS_COUVERTURE (sans carence).

    f_soin_en_carence reste NaN : implémenté dans un commit ultérieur.
    """
    feat["f_soin_en_carence"] = float("nan")
    base = factures[["facture_id", "prestataire_id", "assure_id", "contrat_id", "date_soin"]].copy()
    base["ds"] = _to_dt(base["date_soin"])

    # -- Prestataire : convention --
    presta = ref_tables.get("prestataires", pd.DataFrame())
    if presta.empty:
        feat["f_prestataire_non_conventionne"] = float("nan")
        feat["f_soin_apres_fin_convention"] = float("nan")
    else:
        pr = _cols(presta, ["prestataire_id", "conventionne", "date_fin_convention"])
        pr["_p"] = 1.0
        pr["fin_conv"] = _to_dt(pr["date_fin_convention"])
        m = base.merge(pr.drop(columns="date_fin_convention"), on="prestataire_id", how="left")
        conv = m["conventionne"].astype("float64")
        m["non_conv"] = _flag(conv == 0, conv.notna())
        apres = m["fin_conv"].notna() & (m["ds"] > m["fin_conv"])
        m["apres_fin"] = _flag(apres, m["_p"].notna() & m["ds"].notna())
        idx = m.set_index("facture_id")
        feat["f_prestataire_non_conventionne"] = idx["non_conv"]
        feat["f_soin_apres_fin_convention"] = idx["apres_fin"]

    # -- Assuré : adhésion et radiation --
    assures = ref_tables.get("assures", pd.DataFrame())
    if assures.empty:
        feat["f_soin_avant_adhesion"] = float("nan")
        feat["f_soin_apres_radiation"] = float("nan")
    else:
        asr = _cols(assures, ["assure_id", "date_adhesion", "date_radiation"])
        asr["_a"] = 1.0
        asr["adh"] = _to_dt(asr["date_adhesion"])
        asr["rad"] = _to_dt(asr["date_radiation"])
        m = base.merge(asr[["assure_id", "_a", "adh", "rad"]], on="assure_id", how="left")
        m["avant_adh"] = _flag(m["ds"] < m["adh"], m["ds"].notna() & m["adh"].notna())
        apres_rad = m["rad"].notna() & (m["ds"] > m["rad"])
        m["apres_rad"] = _flag(apres_rad, m["_a"].notna() & m["ds"].notna())
        idx = m.set_index("facture_id")
        feat["f_soin_avant_adhesion"] = idx["avant_adh"]
        feat["f_soin_apres_radiation"] = idx["apres_rad"]

    # -- Contrat : période de couverture --
    contrats = ref_tables.get("contrats", pd.DataFrame())
    if contrats.empty:
        feat["f_soin_hors_periode_contrat"] = float("nan")
    else:
        ct = _cols(contrats, ["contrat_id", "date_effet", "date_fin"])
        ct["effet"] = _to_dt(ct["date_effet"])
        ct["fin"] = _to_dt(ct["date_fin"])
        m = base.merge(ct[["contrat_id", "effet", "fin"]], on="contrat_id", how="left")
        hors = (m["ds"] < m["effet"]) | (m["fin"].notna() & (m["ds"] > m["fin"]))
        m["hors_periode"] = _flag(hors, m["ds"].notna() & m["effet"].notna())
        feat["f_soin_hors_periode_contrat"] = m.set_index("facture_id")["hors_periode"]
    return feat
