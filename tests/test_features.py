"""Tests unitaires du module de features ML (PB-05) – PrediCare TPA.

Règles :
  - Aucune donnée réelle : tout est synthétique (tmp_path ou DataFrames en dur).
  - Un cas par type de fraude avec valeur attendue calculable.
  - Parité lot/unitaire vérifiée sur les features sans historique.
  - Aucune colonne interdite dans la sortie.
"""

import pandas as pd
import pytest

from predicare.ml.features import (
    FEATURE_NAMES,
    FORBIDDEN_FEATURE_COLS,
    build_features,
)

# Helpers – construction de DataFrames synthétiques typés comme PB-04


def _fac(rows: list[dict]) -> pd.DataFrame:
    """DataFrame minimal de factures, sans colonnes de fuite."""
    defaults = {
        "facture_id": None,
        "numero_facture": None,
        "prestataire_id": None,
        "assure_id": None,
        "contrat_id": None,
        "ordonnance_id": None,
        "date_soin": None,
        "montant_total": None,
        "reste_a_charge": None,
        "nb_lignes": None,
    }
    data = [{**defaults, **r} for r in rows]
    df = pd.DataFrame(data)
    for col in ["montant_total", "reste_a_charge", "nb_lignes"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _lignes(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["num_ligne", "quantite", "prix_unitaire", "montant"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _ref_actes(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in [
        "tarif_min",
        "tarif_reference",
        "tarif_max",
        "ordonnance_requise",
        "entente_prealable",
        "age_min",
        "age_max",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _ref_meds(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["prix_reference", "remboursable", "chronique"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _grille(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["tarif_pratique"] = pd.to_numeric(df["tarif_pratique"], errors="coerce").astype("Int64")
    return df


def _ordo_lignes(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["num_ligne", "quantite"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def _ordonnances(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if "validite_jours" in df.columns:
        df["validite_jours"] = pd.to_numeric(df["validite_jours"], errors="coerce").astype("Int64")
    return df


# Tests anti-fuite (commit 1 + garde permanente)


def test_leakage_raises_on_statut():
    fac = _fac([{"facture_id": "F1", "statut": "PAYEE", "date_soin": "2025-01-01"}])
    with pytest.raises(ValueError, match="Colonnes interdites"):
        build_features(fac, {}, pd.DataFrame())


def test_leakage_raises_on_label_est_fraude():
    fac = _fac([{"facture_id": "F1", "est_fraude": 1, "date_soin": "2025-01-01"}])
    with pytest.raises(ValueError, match="Colonnes interdites"):
        build_features(fac, {}, pd.DataFrame())


def test_leakage_raises_in_history():
    fac = _fac([{"facture_id": "F1", "date_soin": "2025-01-01"}])
    hist = _fac([{"facture_id": "F0", "date_soin": "2024-12-01", "statut": "PAYEE"}])
    with pytest.raises(ValueError, match="Colonnes interdites"):
        build_features(fac, {}, hist)


def test_output_no_forbidden_col():
    fac = _fac([{"facture_id": "F1", "date_soin": "2025-01-01"}])
    out = build_features(fac, {}, pd.DataFrame())
    assert FORBIDDEN_FEATURE_COLS.isdisjoint(set(out.columns))


# Tests structure de sortie


def test_output_shape_et_colonnes():
    fac = _fac(
        [
            {"facture_id": "F1", "date_soin": "2025-01-01"},
            {"facture_id": "F2", "date_soin": "2025-01-02"},
        ]
    )
    out = build_features(fac, {}, pd.DataFrame())
    assert out.shape == (2, len(FEATURE_NAMES))
    assert list(out.columns) == FEATURE_NAMES
    assert out.index.name == "facture_id"


def test_output_sans_ref_tables_tout_nan():
    fac = _fac([{"facture_id": "F1", "date_soin": "2025-01-01"}])
    out = build_features(fac, {}, pd.DataFrame())
    assert out.isna().all().all()


# Tests SURFACTURATION – groupe tarifaire


_ACTE_BASE = {
    "code_acte": "ACT-01",
    "libelle": "Consultation",
    "categorie": "CONSULTATION",
    "specialite": None,
    "tarif_min": 10000,
    "tarif_reference": 30000,
    "tarif_max": 40000,
    "ordonnance_requise": 0,
    "entente_prealable": 0,
    "sexe_requis": None,
    "age_min": 0,
    "age_max": 120,
}
_FAC_BASE = {
    "facture_id": "F1",
    "prestataire_id": "P1",
    "assure_id": "A1",
    "date_soin": "2025-01-01",
}


def test_surfacturation_ecart_tarif_max_positif():
    """Prix facturé 50000 > tarif_max 40000 → écart +10000, nb_hors_max=1."""
    fac = _fac([_FAC_BASE])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "ACT-01",
                "type_ligne": "ACTE",
                "libelle": "Consultation",
                "quantite": 1,
                "prix_unitaire": 50000,
                "montant": 50000,
            }
        ]
    )
    ra = _ref_actes([_ACTE_BASE])
    out = build_features(fac, {"lignes_facture": lignes, "referentiel_actes": ra}, pd.DataFrame())
    assert out.loc["F1", "f_ecart_tarif_max_moy"] == pytest.approx(10000.0)
    assert out.loc["F1", "f_nb_lignes_hors_tarif_max"] == pytest.approx(1.0)
    assert out.loc["F1", "f_ratio_tarif_ref_max"] == pytest.approx(50000 / 30000)


def test_surfacturation_ecart_tarif_max_negatif():
    """Prix facturé 20000 < tarif_max 40000 → écart -20000, nb_hors_max=0."""
    fac = _fac([_FAC_BASE])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "ACT-01",
                "type_ligne": "ACTE",
                "libelle": "Consultation",
                "quantite": 1,
                "prix_unitaire": 20000,
                "montant": 20000,
            }
        ]
    )
    ra = _ref_actes([_ACTE_BASE])
    out = build_features(fac, {"lignes_facture": lignes, "referentiel_actes": ra}, pd.DataFrame())
    assert out.loc["F1", "f_ecart_tarif_max_moy"] == pytest.approx(-20000.0)
    assert out.loc["F1", "f_nb_lignes_hors_tarif_max"] == pytest.approx(0.0)


def test_surfacturation_ecart_grille_prestataire():
    """Prix 35000 > tarif_pratique grille 25000 → écart +10000."""
    fac = _fac([_FAC_BASE])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "ACT-01",
                "type_ligne": "ACTE",
                "libelle": "Soin",
                "quantite": 1,
                "prix_unitaire": 35000,
                "montant": 35000,
            }
        ]
    )
    grille = _grille([{"prestataire_id": "P1", "code": "ACT-01", "tarif_pratique": 25000}])
    out = build_features(
        fac, {"lignes_facture": lignes, "grille_tarifaire": grille}, pd.DataFrame()
    )
    assert out.loc["F1", "f_ecart_grille_prest_moy"] == pytest.approx(10000.0)


def test_surfacturation_ratio_medicament():
    """Prix médicament 15000 / prix_reference 10000 = ratio 1.5."""
    fac = _fac([_FAC_BASE])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "MED-01",
                "type_ligne": "MEDICAMENT",
                "libelle": "Amox",
                "quantite": 1,
                "prix_unitaire": 15000,
                "montant": 15000,
            }
        ]
    )
    rm = _ref_meds(
        [
            {
                "code_medicament": "MED-01",
                "libelle": "Amox",
                "prix_reference": 10000,
                "remboursable": 1,
                "classe": "ATB",
                "chronique": 0,
            }
        ]
    )
    out = build_features(
        fac, {"lignes_facture": lignes, "referentiel_medicaments": rm}, pd.DataFrame()
    )
    assert out.loc["F1", "f_ratio_med_prix_ref_max"] == pytest.approx(1.5)


# Tests QUANTITE_EXCESSIVE


def test_quantite_excessive_detectee():
    """5 unités facturées / 2 prescrites → ratio 2.5, nb_excessive=1."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-1"}])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "MED-01",
                "type_ligne": "MEDICAMENT",
                "libelle": "Méd",
                "quantite": 5,
                "prix_unitaire": 10000,
                "montant": 50000,
            }
        ]
    )
    ol = _ordo_lignes(
        [
            {
                "ordonnance_id": "ORD-1",
                "num_ligne": 1,
                "code": "MED-01",
                "libelle": "Méd",
                "quantite": 2,
                "posologie": "1/j",
            }
        ]
    )
    out = build_features(fac, {"lignes_facture": lignes, "ordonnance_lignes": ol}, pd.DataFrame())
    assert out.loc["F1", "f_qte_fac_vs_prescrite_max"] == pytest.approx(2.5)
    assert out.loc["F1", "f_nb_lignes_qte_excessive"] == pytest.approx(1.0)


def test_quantite_non_excessive():
    """2 facturées / 3 prescrites → ratio < 1, nb_excessive=0."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-1"}])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "MED-01",
                "type_ligne": "MEDICAMENT",
                "libelle": "Méd",
                "quantite": 2,
                "prix_unitaire": 10000,
                "montant": 20000,
            }
        ]
    )
    ol = _ordo_lignes(
        [
            {
                "ordonnance_id": "ORD-1",
                "num_ligne": 1,
                "code": "MED-01",
                "libelle": "Méd",
                "quantite": 3,
                "posologie": "1/j",
            }
        ]
    )
    out = build_features(fac, {"lignes_facture": lignes, "ordonnance_lignes": ol}, pd.DataFrame())
    assert out.loc["F1", "f_qte_fac_vs_prescrite_max"] == pytest.approx(2 / 3)
    assert out.loc["F1", "f_nb_lignes_qte_excessive"] == pytest.approx(0.0)


def test_quantite_nan_si_pas_ordonnance():
    """Facture sans ordonnance_id → f_qte_* = NaN."""
    fac = _fac([_FAC_BASE])  # ordonnance_id absent/null
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "MED-01",
                "type_ligne": "MEDICAMENT",
                "libelle": "Méd",
                "quantite": 5,
                "prix_unitaire": 10000,
                "montant": 50000,
            }
        ]
    )
    ol = _ordo_lignes(
        [
            {
                "ordonnance_id": "ORD-X",
                "num_ligne": 1,
                "code": "MED-01",
                "libelle": "Méd",
                "quantite": 2,
                "posologie": "1/j",
            }
        ]
    )
    out = build_features(fac, {"lignes_facture": lignes, "ordonnance_lignes": ol}, pd.DataFrame())
    assert pd.isna(out.loc["F1", "f_qte_fac_vs_prescrite_max"])
    assert pd.isna(out.loc["F1", "f_nb_lignes_qte_excessive"])


# Test parité lot / unitaire – features tarifaires


def test_parite_lot_unitaire_tarif():
    """F1 calculée seule donne les mêmes features que F1 dans un lot (F1+F2)."""
    row_f1 = {**_FAC_BASE, "facture_id": "F1"}
    row_f2 = {**_FAC_BASE, "facture_id": "F2", "assure_id": "A2"}
    ligne_f1 = {
        "ligne_id": "L1",
        "facture_id": "F1",
        "num_ligne": 1,
        "code": "ACT-01",
        "type_ligne": "ACTE",
        "libelle": "C",
        "quantite": 1,
        "prix_unitaire": 50000,
        "montant": 50000,
    }
    ligne_f2 = {
        "ligne_id": "L2",
        "facture_id": "F2",
        "num_ligne": 1,
        "code": "ACT-01",
        "type_ligne": "ACTE",
        "libelle": "C",
        "quantite": 1,
        "prix_unitaire": 20000,
        "montant": 20000,
    }
    ra = _ref_actes([_ACTE_BASE])

    # Lot complet
    fac_lot = _fac([row_f1, row_f2])
    lignes_lot = _lignes([ligne_f1, ligne_f2])
    out_lot = build_features(
        fac_lot, {"lignes_facture": lignes_lot, "referentiel_actes": ra}, pd.DataFrame()
    )

    # F1 seule
    fac_solo = _fac([row_f1])
    lignes_solo = _lignes([ligne_f1])
    out_solo = build_features(
        fac_solo, {"lignes_facture": lignes_solo, "referentiel_actes": ra}, pd.DataFrame()
    )

    for col in ["f_ecart_tarif_max_moy", "f_ratio_tarif_ref_max", "f_nb_lignes_hors_tarif_max"]:
        assert out_lot.loc["F1", col] == pytest.approx(out_solo.loc["F1", col]), (
            f"Parité échouée pour {col}"
        )


# Tests groupes 3+4 – Features ordonnance


_ORDO_BASE = {
    "ordonnance_id": "ORD-1",
    "assure_id": "A1",
    "prescripteur_id": "P1",
    "date_prescription": "2025-01-01",
    "validite_jours": 10,
    "type_ordonnance": "STANDARD",
    "diagnostic": None,
    "renseignement_clinique": None,
}


def test_lignes_hors_ordonnance_part():
    """2 lignes, 1 dans ordonnance, 1 hors → part=0.5."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-1"}])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "ACT-01",
                "type_ligne": "ACTE",
                "libelle": "X",
                "quantite": 1,
                "prix_unitaire": 10000,
                "montant": 10000,
            },
            {
                "ligne_id": "L2",
                "facture_id": "F1",
                "num_ligne": 2,
                "code": "ACT-99",
                "type_ligne": "ACTE",
                "libelle": "Y",
                "quantite": 1,
                "prix_unitaire": 10000,
                "montant": 10000,
            },
        ]
    )
    ol = _ordo_lignes(
        [
            {
                "ordonnance_id": "ORD-1",
                "num_ligne": 1,
                "code": "ACT-01",
                "libelle": "X",
                "quantite": 1,
                "posologie": "",
            },
        ]
    )
    out = build_features(fac, {"lignes_facture": lignes, "ordonnance_lignes": ol}, pd.DataFrame())
    assert out.loc["F1", "f_part_lignes_hors_ordonnance"] == pytest.approx(0.5)


def test_ordonnance_absente_requise_flag():
    """Facture sans ordonnance, acte avec ordonnance_requise=1 → flag=1."""
    fac = _fac([_FAC_BASE])  # ordonnance_id null
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "ACT-01",
                "type_ligne": "ACTE",
                "libelle": "X",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant": 30000,
            },
        ]
    )
    ra = _ref_actes([{**_ACTE_BASE, "ordonnance_requise": 1}])
    out = build_features(fac, {"lignes_facture": lignes, "referentiel_actes": ra}, pd.DataFrame())
    assert out.loc["F1", "f_ordonnance_absente_requise"] == pytest.approx(1.0)


def test_ordonnance_non_requise_pas_flag():
    """Facture sans ordonnance, acte avec ordonnance_requise=0 → flag=0."""
    fac = _fac([_FAC_BASE])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": "ACT-01",
                "type_ligne": "ACTE",
                "libelle": "X",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant": 30000,
            },
        ]
    )
    ra = _ref_actes([{**_ACTE_BASE, "ordonnance_requise": 0}])
    out = build_features(fac, {"lignes_facture": lignes, "referentiel_actes": ra}, pd.DataFrame())
    assert out.loc["F1", "f_ordonnance_absente_requise"] == pytest.approx(0.0)


def test_ordonnance_autre_assure_flag():
    """Ordonnance appartient à A2, facture pour A1 → flag=1."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-1"}])  # assure_id = A1
    ordo = _ordonnances([{**_ORDO_BASE, "assure_id": "A2"}])  # ordo pour A2
    out = build_features(fac, {"ordonnances": ordo}, pd.DataFrame())
    assert out.loc["F1", "f_ordonnance_autre_assure"] == pytest.approx(1.0)


def test_ordonnance_meme_assure_pas_flag():
    """Ordonnance appartient au même assuré A1 → flag=0."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-1"}])
    ordo = _ordonnances([{**_ORDO_BASE, "assure_id": "A1"}])
    out = build_features(fac, {"ordonnances": ordo}, pd.DataFrame())
    assert out.loc["F1", "f_ordonnance_autre_assure"] == pytest.approx(0.0)


def test_ordonnance_expiree_detectee():
    """Soin 15j après prescription, validité 10j → expiree=1, delai=15."""
    fac = _fac([{**_FAC_BASE, "date_soin": "2025-01-16", "ordonnance_id": "ORD-1"}])
    ordo = _ordonnances([{**_ORDO_BASE, "date_prescription": "2025-01-01", "validite_jours": 10}])
    out = build_features(fac, {"ordonnances": ordo}, pd.DataFrame())
    assert out.loc["F1", "f_delai_soin_prescription_j"] == pytest.approx(15.0)
    assert out.loc["F1", "f_ordonnance_expiree"] == pytest.approx(1.0)


def test_ordonnance_valide_non_expiree():
    """Soin 5j après prescription, validité 10j → expiree=0, delai=5."""
    fac = _fac([{**_FAC_BASE, "date_soin": "2025-01-06", "ordonnance_id": "ORD-1"}])
    ordo = _ordonnances([{**_ORDO_BASE, "date_prescription": "2025-01-01", "validite_jours": 10}])
    out = build_features(fac, {"ordonnances": ordo}, pd.DataFrame())
    assert out.loc["F1", "f_delai_soin_prescription_j"] == pytest.approx(5.0)
    assert out.loc["F1", "f_ordonnance_expiree"] == pytest.approx(0.0)


def test_delai_nan_si_pas_ordonnance():
    """Facture sans ordonnance_id → delai et expiree = NaN."""
    fac = _fac([_FAC_BASE])
    out = build_features(fac, {}, pd.DataFrame())
    assert pd.isna(out.loc["F1", "f_delai_soin_prescription_j"])
    assert pd.isna(out.loc["F1", "f_ordonnance_expiree"])


# Tests groupe 5 – calendrier


def _presta(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["jours_ouverture"] = pd.to_numeric(df["jours_ouverture"], errors="coerce").astype("Int64")
    return df


def test_soin_jour_ferme_samedi():
    """2025-01-04 est un samedi (6) ; ouvert 12345 → fermé=1."""
    fac = _fac([{**_FAC_BASE, "date_soin": "2025-01-04"}])
    pr = _presta(
        [{"prestataire_id": "P1", "type_prestataire": "PHARMACIE", "jours_ouverture": 12345}]
    )
    out = build_features(fac, {"prestataires": pr}, pd.DataFrame())
    assert out.loc["F1", "f_soin_jour_ferme"] == pytest.approx(1.0)


def test_soin_jour_ouvert_lundi():
    """2025-01-06 est un lundi (1) ; ouvert 12345 → fermé=0."""
    fac = _fac([{**_FAC_BASE, "date_soin": "2025-01-06"}])
    pr = _presta(
        [{"prestataire_id": "P1", "type_prestataire": "PHARMACIE", "jours_ouverture": 12345}]
    )
    out = build_features(fac, {"prestataires": pr}, pd.DataFrame())
    assert out.loc["F1", "f_soin_jour_ferme"] == pytest.approx(0.0)


def test_soin_dimanche_prestataire_7j():
    """2025-01-05 est un dimanche (7) ; ouvert 1234567 → fermé=0."""
    fac = _fac([{**_FAC_BASE, "date_soin": "2025-01-05"}])
    pr = _presta(
        [{"prestataire_id": "P1", "type_prestataire": "PHARMACIE", "jours_ouverture": 1234567}]
    )
    out = build_features(fac, {"prestataires": pr}, pd.DataFrame())
    assert out.loc["F1", "f_soin_jour_ferme"] == pytest.approx(0.0)


# Tests groupe 11 – UPCODING


def _upcoding(code: str, spec_acte: str, type_p: str, spec_p: str | None) -> float:
    fac = _fac([_FAC_BASE])
    lignes = _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": code,
                "type_ligne": "ACTE",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant": 30000,
            }
        ]
    )
    ra = _ref_actes(
        [{**_ACTE_BASE, "code_acte": code, "categorie": "CONSULTATION", "specialite": spec_acte}]
    )
    pr = _presta(
        [
            {
                "prestataire_id": "P1",
                "type_prestataire": type_p,
                "specialite": spec_p,
                "jours_ouverture": 12345,
            }
        ]
    )
    out = build_features(
        fac, {"lignes_facture": lignes, "referentiel_actes": ra, "prestataires": pr}, pd.DataFrame()
    )
    return out.loc["F1", "f_type_prest_vs_cat_acte"]


def test_upcoding_specialiste_chez_generaliste():
    assert _upcoding("CONS-CARDIO", "CARDIOLOGIE", "CABINET_GENERALISTE", None) == 1.0


def test_upcoding_specialiste_bon_cabinet():
    assert _upcoding("CONS-CARDIO", "CARDIOLOGIE", "CABINET_SPECIALISTE", "CARDIOLOGIE") == 0.0


def test_upcoding_generaliste_normal():
    assert _upcoding("CONS-GEN", "GENERALISTE", "CABINET_GENERALISTE", None) == 0.0


# Tests groupes 8, 9, 10 – profil, prestataire radié, couverture


def _assures(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["annee_naissance"] = pd.to_numeric(df["annee_naissance"], errors="coerce").astype("Int64")
    return df


def _une_ligne_acte(code: str) -> pd.DataFrame:
    return _lignes(
        [
            {
                "ligne_id": "L1",
                "facture_id": "F1",
                "num_ligne": 1,
                "code": code,
                "type_ligne": "ACTE",
                "quantite": 1,
                "prix_unitaire": 30000,
                "montant": 30000,
            }
        ]
    )


def test_age_au_soin():
    """Soin en 2025, né en 2020 → 5 ans."""
    fac = _fac([_FAC_BASE])
    asr = _assures([{"assure_id": "A1", "sexe": "F", "annee_naissance": 2020}])
    out = build_features(fac, {"assures": asr}, pd.DataFrame())
    assert out.loc["F1", "f_age_au_soin"] == pytest.approx(5.0)


def test_age_hors_bornes_detecte():
    """Pédiatrie (age_max 17) pour un assuré de 35 ans → flag=1."""
    fac = _fac([_FAC_BASE])
    asr = _assures([{"assure_id": "A1", "sexe": "F", "annee_naissance": 1990}])
    ra = _ref_actes([{**_ACTE_BASE, "code_acte": "CONS-PEDIA", "age_min": 0, "age_max": 17}])
    out = build_features(
        fac,
        {"assures": asr, "lignes_facture": _une_ligne_acte("CONS-PEDIA"), "referentiel_actes": ra},
        pd.DataFrame(),
    )
    assert out.loc["F1", "f_age_hors_bornes_ref"] == pytest.approx(1.0)


def test_age_dans_bornes():
    """Pédiatrie pour un enfant de 5 ans → flag=0."""
    fac = _fac([_FAC_BASE])
    asr = _assures([{"assure_id": "A1", "sexe": "F", "annee_naissance": 2020}])
    ra = _ref_actes([{**_ACTE_BASE, "code_acte": "CONS-PEDIA", "age_min": 0, "age_max": 17}])
    out = build_features(
        fac,
        {"assures": asr, "lignes_facture": _une_ligne_acte("CONS-PEDIA"), "referentiel_actes": ra},
        pd.DataFrame(),
    )
    assert out.loc["F1", "f_age_hors_bornes_ref"] == pytest.approx(0.0)


def test_sexe_incompatible_detecte():
    """Acte réservé aux hommes (PSA) facturé pour une femme → flag=1."""
    fac = _fac([_FAC_BASE])
    asr = _assures([{"assure_id": "A1", "sexe": "F", "annee_naissance": 1980}])
    ra = _ref_actes([{**_ACTE_BASE, "code_acte": "LAB-PSA", "sexe_requis": "M", "age_min": 40}])
    out = build_features(
        fac,
        {"assures": asr, "lignes_facture": _une_ligne_acte("LAB-PSA"), "referentiel_actes": ra},
        pd.DataFrame(),
    )
    assert out.loc["F1", "f_sexe_incompatible_ref"] == pytest.approx(1.0)


def test_sexe_compatible():
    """Acte sans restriction de sexe → flag=0."""
    fac = _fac([_FAC_BASE])
    asr = _assures([{"assure_id": "A1", "sexe": "F", "annee_naissance": 1980}])
    ra = _ref_actes([_ACTE_BASE])
    out = build_features(
        fac,
        {"assures": asr, "lignes_facture": _une_ligne_acte("ACT-01"), "referentiel_actes": ra},
        pd.DataFrame(),
    )
    assert out.loc["F1", "f_sexe_incompatible_ref"] == pytest.approx(0.0)


def test_soin_apres_fin_convention():
    """Soin 2025-01-01, convention terminée le 2024-12-31 → flag=1."""
    fac = _fac([_FAC_BASE])
    pr = pd.DataFrame(
        [{"prestataire_id": "P1", "conventionne": 1, "date_fin_convention": "2024-12-31"}]
    )
    out = build_features(fac, {"prestataires": pr}, pd.DataFrame())
    assert out.loc["F1", "f_soin_apres_fin_convention"] == pytest.approx(1.0)
    assert out.loc["F1", "f_prestataire_non_conventionne"] == pytest.approx(0.0)


def test_prestataire_non_conventionne_sans_fin():
    """conventionne=0 et pas de date de fin → non conventionné=1, après fin=0."""
    fac = _fac([_FAC_BASE])
    pr = pd.DataFrame([{"prestataire_id": "P1", "conventionne": 0, "date_fin_convention": None}])
    out = build_features(fac, {"prestataires": pr}, pd.DataFrame())
    assert out.loc["F1", "f_prestataire_non_conventionne"] == pytest.approx(1.0)
    assert out.loc["F1", "f_soin_apres_fin_convention"] == pytest.approx(0.0)


def test_soin_avant_adhesion():
    """Soin 2025-01-01, adhésion 2025-02-01 → flag=1."""
    fac = _fac([_FAC_BASE])
    asr = _assures(
        [{"assure_id": "A1", "annee_naissance": 1980, "date_adhesion": "2025-02-01"}]
    ).assign(date_radiation=None)
    out = build_features(fac, {"assures": asr}, pd.DataFrame())
    assert out.loc["F1", "f_soin_avant_adhesion"] == pytest.approx(1.0)
    assert out.loc["F1", "f_soin_apres_radiation"] == pytest.approx(0.0)


def test_soin_apres_radiation():
    """Soin 2025-01-01, radiation 2024-12-01 → flag=1."""
    fac = _fac([_FAC_BASE])
    asr = _assures(
        [
            {
                "assure_id": "A1",
                "annee_naissance": 1980,
                "date_adhesion": "2024-01-01",
                "date_radiation": "2024-12-01",
            }
        ]
    )
    out = build_features(fac, {"assures": asr}, pd.DataFrame())
    assert out.loc["F1", "f_soin_apres_radiation"] == pytest.approx(1.0)
    assert out.loc["F1", "f_soin_avant_adhesion"] == pytest.approx(0.0)


def test_soin_hors_periode_contrat():
    """Soin 2025-01-01, contrat effectif dès 2025-06-01 → flag=1."""
    fac = _fac([{**_FAC_BASE, "contrat_id": "C1"}])
    ct = pd.DataFrame([{"contrat_id": "C1", "date_effet": "2025-06-01", "date_fin": None}])
    out = build_features(fac, {"contrats": ct}, pd.DataFrame())
    assert out.loc["F1", "f_soin_hors_periode_contrat"] == pytest.approx(1.0)


def test_soin_dans_periode_contrat():
    """Soin 2025-01-01, contrat du 2024-01-01 au 2025-12-31 → flag=0."""
    fac = _fac([{**_FAC_BASE, "contrat_id": "C1"}])
    ct = pd.DataFrame([{"contrat_id": "C1", "date_effet": "2024-01-01", "date_fin": "2025-12-31"}])
    out = build_features(fac, {"contrats": ct}, pd.DataFrame())
    assert out.loc["F1", "f_soin_hors_periode_contrat"] == pytest.approx(0.0)


# Tests groupe 6+7 – Features historiques


def test_history_vide_tout_nan():
    """History vide → toutes les features historiques = NaN."""
    fac = _fac([_FAC_BASE])
    out = build_features(fac, {}, pd.DataFrame())
    for col in [
        "f_nb_doublons_anterieurs",
        "f_numero_facture_deja_vu",
        "f_nb_factures_meme_jour_prest",
        "f_nb_prest_meme_ordo_anterieurs",
    ]:
        assert pd.isna(out.loc["F1", col]), f"{col} devrait être NaN avec history vide"


def test_doublon_exact_detecte():
    """Même (assure, prest, date, montant) dans history → doublon=1, meme_jour=1."""
    fac = _fac([{**_FAC_BASE, "numero_facture": "NUM-001", "montant_total": 10000}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "numero_facture": "NUM-000",
                "prestataire_id": "P1",
                "assure_id": "A1",
                "date_soin": "2025-01-01",
                "montant_total": 10000,
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_nb_doublons_anterieurs"] == pytest.approx(1.0)
    assert out.loc["F1", "f_nb_factures_meme_jour_prest"] == pytest.approx(1.0)


def test_doublon_montant_different():
    """Même triplet mais montant différent → doublon=0, meme_jour=1."""
    fac = _fac([{**_FAC_BASE, "numero_facture": "NUM-001", "montant_total": 10000}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "numero_facture": "NUM-000",
                "prestataire_id": "P1",
                "assure_id": "A1",
                "date_soin": "2025-01-01",
                "montant_total": 20000,
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_nb_doublons_anterieurs"] == pytest.approx(0.0)
    assert out.loc["F1", "f_nb_factures_meme_jour_prest"] == pytest.approx(1.0)


def test_pas_doublon_historique_different():
    """Historique différent (autre assure) → doublon=0, meme_jour=0."""
    fac = _fac([{**_FAC_BASE, "numero_facture": "NUM-001", "montant_total": 10000}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "numero_facture": "NUM-000",
                "prestataire_id": "P1",
                "assure_id": "A2",  # autre assuré
                "date_soin": "2025-01-01",
                "montant_total": 10000,
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_nb_doublons_anterieurs"] == pytest.approx(0.0)
    assert out.loc["F1", "f_nb_factures_meme_jour_prest"] == pytest.approx(0.0)


def test_numero_facture_deja_vu():
    """Même numero_facture dans history → flag=1."""
    fac = _fac([{**_FAC_BASE, "numero_facture": "NUM-001", "montant_total": 10000}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "numero_facture": "NUM-001",  # même numéro
                "prestataire_id": "P2",
                "assure_id": "A2",
                "date_soin": "2024-12-01",
                "montant_total": 5000,
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_numero_facture_deja_vu"] == pytest.approx(1.0)


def test_numero_facture_nouveau():
    """Nouveau numero_facture → flag=0."""
    fac = _fac([{**_FAC_BASE, "numero_facture": "NUM-999", "montant_total": 10000}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "numero_facture": "NUM-001",
                "prestataire_id": "P1",
                "assure_id": "A1",
                "date_soin": "2024-12-01",
                "montant_total": 10000,
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_numero_facture_deja_vu"] == pytest.approx(0.0)


def test_surconsommation_ordo_deux_prestataires():
    """2 prestataires distincts ont facturé la même ordonnance → nb=2."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-1"}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "prestataire_id": "P1",
                "assure_id": "A1",
                "date_soin": "2024-12-01",
                "ordonnance_id": "ORD-1",
                "montant_total": 5000,
                "numero_facture": "NUM-A",
            },
            {
                "facture_id": "F-1",
                "prestataire_id": "P2",
                "assure_id": "A1",
                "date_soin": "2024-12-02",
                "ordonnance_id": "ORD-1",
                "montant_total": 3000,
                "numero_facture": "NUM-B",
            },
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_nb_prest_meme_ordo_anterieurs"] == pytest.approx(2.0)


def test_ordo_aucun_match_historique():
    """Ordonnance présente mais pas dans history → nb=0 (pas NaN)."""
    fac = _fac([{**_FAC_BASE, "ordonnance_id": "ORD-NEW"}])
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "prestataire_id": "P1",
                "assure_id": "A1",
                "date_soin": "2024-12-01",
                "ordonnance_id": "ORD-OLD",
                "montant_total": 5000,
                "numero_facture": "NUM-A",
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert out.loc["F1", "f_nb_prest_meme_ordo_anterieurs"] == pytest.approx(0.0)


def test_sans_ordonnance_nb_prest_nan():
    """Facture sans ordonnance_id → f_nb_prest_meme_ordo_anterieurs = NaN."""
    fac = _fac([_FAC_BASE])  # ordonnance_id null
    hist = _fac(
        [
            {
                "facture_id": "F0",
                "prestataire_id": "P1",
                "assure_id": "A1",
                "date_soin": "2024-12-01",
                "ordonnance_id": "ORD-1",
                "montant_total": 5000,
                "numero_facture": "NUM-A",
            }
        ]
    )
    out = build_features(fac, {}, hist)
    assert pd.isna(out.loc["F1", "f_nb_prest_meme_ordo_anterieurs"])
