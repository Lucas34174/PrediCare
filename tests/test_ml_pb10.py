"""Tests PB-10 : analyse des faux négatifs et ajout des variables PB-09."""

from __future__ import annotations

import pandas as pd
import pytest

from predicare.ml.config import DATA_RAW, REPORTS_DIR, TARGET
from predicare.ml.false_negatives import ajouter_features_pb09, analyser


def _scores_disponibles() -> bool:
    return (DATA_RAW / "scores_test_cm.csv").is_file()


@pytest.mark.skipif(not _scores_disponibles(), reason="scores_test_cm.csv absent")
def test_analyse_faux_negatifs():
    resultat = analyser()
    assert set(resultat) >= {
        "synthese",
        "faux_negatifs",
        "par_type_facture",
        "par_tranche_montant",
        "par_code_regle",
        "profil",
    }
    synthese = resultat["synthese"].set_index("metrique")["valeur"]
    assert synthese["positifs_test"] > 0
    assert synthese["vrais_positifs"] + synthese["faux_negatifs"] == synthese["positifs_test"]
    assert 0 <= synthese["rappel"] <= 1


def test_ajouter_features_pb09():
    dataset = pd.DataFrame(
        {
            "facture_id": ["F1", "F2", "F3"],
            "montant_total": [1, 2, 3],
            TARGET: [0, 1, 0],
        }
    )
    alertes = pd.DataFrame(
        {
            "facture_id": ["F1", "F1", "F2"],
            "code_fraude": ["SURCONSOMMATION", "LIGNES_NON_PRESCRITES", "SURCONSOMMATION"],
        }
    )
    enrichi = ajouter_features_pb09(dataset, alertes)
    assert enrichi.loc[enrichi["facture_id"] == "F1", "pb09_surconsommation"].item() == 1
    assert enrichi.loc[enrichi["facture_id"] == "F1", "pb09_lignes_non_prescrites"].item() == 1
    assert enrichi.loc[enrichi["facture_id"] == "F3", "pb09_nb_alertes"].item() == 0


def test_resultat_amelioration_archive():
    chemin = REPORTS_DIR / "pb10" / "amelioration.csv"
    if not chemin.is_file():
        pytest.skip("amelioration.csv non généré")
    table = pd.read_csv(chemin).set_index("version")
    assert {"sans_pb09", "avec_pb09"}.issubset(table.index)
    assert table.loc["avec_pb09", "pr_auc"] >= table.loc["sans_pb09", "pr_auc"]
