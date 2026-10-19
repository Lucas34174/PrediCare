"""Tests v1.1 : évaluation métier, réseau, généralisation, mitigation, budget."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from predicare.ml.business import (
    metriques_budget,
    scenario_cout_benefice,
    tableau_budgets,
)
from predicare.ml.equity_mitigation import _metriques
from predicare.ml.grouped_eval import demarrage_a_froid
from predicare.ml.network_features import (
    VARIABLES_RESEAU,
    construire_features_reseau,
)
from predicare.ml.scoring import ModeleFraude


def _jeu_simple():
    y = np.array([0, 1, 0, 1, 0, 0, 1, 0, 0, 1])
    p = np.array([0.10, 0.90, 0.20, 0.80, 0.30, 0.40, 0.70, 0.50, 0.60, 0.15])
    montant = np.arange(10, 20, dtype=float) * 1000
    return y, p, montant


def test_metriques_budget_invariants():
    y, p, montant = _jeu_simple()
    m = metriques_budget(y, p, montant, budget=0.30)
    assert m["nb_alertes"] == 3
    assert m["tp"] + m["fn"] == int(y.sum())
    assert m["tp"] + m["fp"] == m["nb_alertes"]
    assert 0 <= m["recall"] <= 1
    assert 0 <= m["precision"] <= 1
    assert m["lift"] > 1
    assert m["montant_tp"] <= m["montant_controle"]


def test_tableau_budgets_rappel_croissant():
    y, p, montant = _jeu_simple()
    table = tableau_budgets(y, p, montant, budgets=(0.1, 0.3, 0.5))
    assert list(table["budget"]) == [0.1, 0.3, 0.5]
    assert table["recall"].is_monotonic_increasing


def test_scenario_cout_benefice_colonnes():
    y, p, montant = _jeu_simple()
    table = tableau_budgets(y, p, montant)
    scenario = scenario_cout_benefice(table, cout_controle=1000)
    for colonne in (
        "cout_controle",
        "cout_par_tp",
        "benefice_net_taux_30pct",
        "taux_rentabilite_equilibre",
    ):
        assert colonne in scenario.columns
    assert (scenario["cout_par_tp"] > 0).all()


def test_features_reseau_petit_jeu():
    dataset = pd.DataFrame(
        {
            "facture_id": [f"F{i}" for i in range(8)],
            "meta_assure_id": ["A1", "A2", "A1", "A1", "A3", "A2", "A3", "A1"],
            "meta_prestataire_id": ["P1", "P1", "P1", "P2", "P2", "P2", "P1", "P1"],
            "meta_date_reception": [
                "2025-01-01",
                "2025-01-02",
                "2025-01-03",
                "2025-01-03",
                "2025-01-05",
                "2025-01-06",
                "2025-02-01",
                "2025-02-02",
            ],
        }
    )
    features = construire_features_reseau(dataset)
    assert set(VARIABLES_RESEAU) <= set(features.columns)
    assert features[VARIABLES_RESEAU].notna().all().all()
    assert (features["velocite_prest_7j"] >= 1).all()
    # P1 n'a vu que A1 puis A2 au 2 janvier.
    assert features.loc[0, "reseau_prest_nb_assures_hist"] == 1
    assert features.loc[1, "reseau_prest_nb_assures_hist"] == 2
    # Le couple (A1, P1) apparaît 3 fois au total (F0, F2, F7).
    assert features.loc[7, "reseau_couple_nb_factures_hist"] == 3


def test_seuil_pour_budget():
    from predicare.ml.scoring import normaliser_score

    modele = ModeleFraude(
        pipeline=object(),
        variables=[],
        seuil_probabilite=0.15,
        metadonnees={
            "seuils_budget_validation": {"0.01": 0.90, "0.03": 0.50, "0.05": 0.30}
        },
    )
    attendu = normaliser_score(0.50, 0.15)
    assert modele.seuil_pour_budget(0.031) == pytest.approx(attendu)
    assert modele.seuil_pour_budget(0.06) == pytest.approx(normaliser_score(0.30, 0.15))
    assert 0 < modele.seuil_pour_budget(0.031) < 1


def test_seuil_pour_budget_absent():
    modele = ModeleFraude(pipeline=object(), variables=[], seuil_probabilite=0.15)
    with pytest.raises(ValueError):
        modele.seuil_pour_budget(0.03)


def test_demarrage_a_froid():
    dataset = pd.DataFrame(
        {
            "facture_id": ["F1", "F2", "F3", "F4", "F5", "F6"],
            "split": ["train", "train", "test", "test", "test", "test"],
            "meta_prestataire_id": ["P1", "P1", "P2", "P1", "P3", "P1"],
            "cible_cm": [0, 1, 1, 0, 1, 0],
        }
    )
    scores = pd.DataFrame(
        {
            "facture_id": ["F3", "F4", "F5", "F6"],
            "probabilite": [0.9, 0.1, 0.8, 0.2],
        }
    )
    table = demarrage_a_froid(dataset, scores)
    assert set(table["prestataire_vu"]) == {True, False}
    assert table["n"].sum() == 4
    assert abs(table["part_factures"].sum() - 1.0) < 1e-9


def test_metriques_mitigation():
    bloc = pd.DataFrame(
        {
            "sexe": ["F", "F", "M", "M"],
            "cible_cm": [1, 0, 1, 1],
            "probabilite": [0.90, 0.20, 0.40, 0.30],
        }
    )
    metriques = _metriques(bloc, "sexe", {"F": 0.50, "M": 0.35}, 0.50)
    assert metriques["alertes"] == 2
    assert metriques["tp"] == 2
    assert metriques["fp"] == 0
    assert metriques["precision"] == 1.0
    assert metriques["recall"] == pytest.approx(2 / 3)
    assert metriques["ecart_tpr_max_min"] == pytest.approx(0.5)
