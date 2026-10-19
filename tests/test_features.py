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
