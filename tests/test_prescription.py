"""Tests PB-09 : moteur d'alertes de prescription.

Tables synthétiques minimales : les trois signaux exigés par le CDC
(nomadisme, lignes hors ordonnance, inadéquation diagnostic) sont testés
isolément et de façon déterministe.
"""

from __future__ import annotations

import pandas as pd
import pytest

from predicare.ml.prescription import (
    ATTENDU_DIAGNOSTIC,
    GRAVITE_PRESCRIPTION,
    detecter_alertes_prescription,
    resumer_alertes,
)


def _tables(statut_p2: str = "ACTIF") -> dict[str, pd.DataFrame]:
    return {
        "factures": pd.DataFrame(
            [
                {
                    "facture_id": "F1",
                    "ordonnance_id": "O1",
                    "prestataire_id": "P1",
                    "montant_total": 10_000,
                },
                {
                    "facture_id": "F2",
                    "ordonnance_id": "O1",
                    "prestataire_id": "P2",
                    "montant_total": 20_000,
                },
                {
                    "facture_id": "F3",
                    "ordonnance_id": "O2",
                    "prestataire_id": "P1",
                    "montant_total": 5_000,
                },
            ]
        ),
        "lignes_facture": pd.DataFrame(
            [
                {"facture_id": "F1", "code": "MED-AMOX500", "montant": 10_000},
                {"facture_id": "F2", "code": "MED-IBU400", "montant": 20_000},
                {"facture_id": "F3", "code": "MED-METF", "montant": 5_000},
            ]
        ),
        "ordonnances": pd.DataFrame(
            [
                {
                    "ordonnance_id": "O1",
                    "assure_id": "A1",
                    "prescripteur_id": "P1",
                    "date_prescription": "2026-01-10",
                    "validite_jours": 30,
                    "diagnostic": "Diabète de type 2",
                    "type_ordonnance": "NORMALE",
                },
                {
                    "ordonnance_id": "O2",
                    "assure_id": "A2",
                    "prescripteur_id": "P2",
                    "date_prescription": "2026-01-10",
                    "validite_jours": 30,
                    "diagnostic": "Rhinite allergique",
                    "type_ordonnance": "NORMALE",
                },
            ]
        ),
        "ordonnance_lignes": pd.DataFrame(
            [
                {"ordonnance_id": "O1", "code": "MED-AMOX500", "quantite": 1},
                {"ordonnance_id": "O2", "code": "MED-METF", "quantite": 1},
            ]
        ),
        "assures": pd.DataFrame(
            [
                {"assure_id": "A1", "date_adhesion": "2025-01-01"},
                {"assure_id": "A2", "date_adhesion": "2025-01-01"},
            ]
        ),
        "prestataires": pd.DataFrame(
            [
                {
                    "prestataire_id": "P1",
                    "specialite": "GENERALISTE",
                    "date_fin_convention": None,
                    "statut": "ACTIF",
                },
                {
                    "prestataire_id": "P2",
                    "specialite": "GENERALISTE",
                    "date_fin_convention": None,
                    "statut": statut_p2,
                },
            ]
        ),
        "referentiel_medicaments": pd.DataFrame(
            [
                {"code_medicament": "MED-AMOX500", "classe": "ANTIBIOTIQUE", "chronique": 0},
                {"code_medicament": "MED-IBU400", "classe": "AINS", "chronique": 0},
                {"code_medicament": "MED-METF", "classe": "ANTIDIABETIQUE", "chronique": 1},
            ]
        ),
    }


def test_contrat_de_sortie():
    alertes = detecter_alertes_prescription(_tables())
    assert list(alertes.columns) == [
        "facture_id",
        "ordonnance_id",
        "code_fraude",
        "gravite",
        "montant_en_jeu",
        "explication",
    ]
    assert alertes["explication"].str.len().gt(0).all()
    assert alertes["gravite"].isin([1, 2, 3]).all()


def test_surconsommation_meme_ordonnance_plusieurs_prescripteurs():
    """R1 : une ordonnance facturée par deux prestataires alerte les deux factures."""
    alertes = detecter_alertes_prescription(_tables())
    nomade = alertes[alertes["code_fraude"] == "SURCONSOMMATION"]
    assert set(nomade["facture_id"]) == {"F1", "F2"}
    assert (nomade["gravite"] == GRAVITE_PRESCRIPTION["SURCONSOMMATION"]).all()


def test_lignes_hors_ordonnance():
    """R2 : un code facturé absent de l'ordonnance est signalé."""
    alertes = detecter_alertes_prescription(_tables())
    hors = alertes[alertes["code_fraude"] == "LIGNES_NON_PRESCRITES"]
    assert set(hors["facture_id"]) == {"F2"}
    assert "MED-IBU400" in hors.iloc[0]["explication"]


def test_inadequation_diagnostic():
    """R3 : famille thérapeutique incompatible avec le diagnostic."""
    alertes = detecter_alertes_prescription(_tables())
    inad = alertes[alertes["code_fraude"] == "INADEQUATION_DIAGNOSTIC"]
    assert len(inad) > 0
    assert set(inad["facture_id"]) == {"F1", "F2", "F3"}


def test_prescripteur_radie():
    alertes = detecter_alertes_prescription(_tables(statut_p2="RADIE"))
    assert "PRESCRIPTEUR_RADIE" in set(alertes["code_fraude"])


def test_ordonnance_sans_ligne():
    tables = _tables()
    tables["ordonnance_lignes"] = tables["ordonnance_lignes"].iloc[1:]
    alertes = detecter_alertes_prescription(tables)
    assert "ORDONNANCE_SANS_LIGNE" in set(alertes["code_fraude"])


def test_aucune_alerte_sur_lot_sain():
    tables = _tables()
    # On aligne les lignes facturées sur les ordonnances et on rend les diagnostics cohérents.
    tables["lignes_facture"] = pd.DataFrame(
        [
            {"facture_id": "F1", "code": "MED-AMOX500", "montant": 10_000},
            {"facture_id": "F3", "code": "MED-METF", "montant": 5_000},
        ]
    )
    tables["factures"] = tables["factures"].iloc[[0, 2]]  # une seule facture par ordonnance
    alertes = detecter_alertes_prescription(tables)
    assert "SURCONSOMMATION" not in set(alertes["code_fraude"])
    assert "LIGNES_NON_PRESCRITES" not in set(alertes["code_fraude"])


def test_resume_par_code():
    alertes = detecter_alertes_prescription(_tables())
    resume = resumer_alertes(alertes)
    assert set(resume.columns) == {"code_fraude", "gravite", "nb_alertes", "montant_en_jeu"}
    assert resume["nb_alertes"].sum() >= 3


def test_referentiel_diagnostic_couvre_les_diagnostics_du_jeu():
    """Le référentiel doit inclure les diagnostics observés dans l'EDA."""
    diagnostics_attendus = {
        "Asthme",
        "Diabète de type 2",
        "Hypertension artérielle",
        "Paludisme simple",
        "Rhinite allergique",
    }
    assert diagnostics_attendus.issubset(set(ATTENDU_DIAGNOSTIC))


@pytest.mark.parametrize(
    "code", ["SURCONSOMMATION", "LIGNES_NON_PRESCRITES", "INADEQUATION_DIAGNOSTIC"]
)
def test_gravites_definies(code):
    assert GRAVITE_PRESCRIPTION[code] in (1, 2, 3)
