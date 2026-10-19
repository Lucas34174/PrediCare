"""Tests PB-13 : explicabilité SHAP et format du contrat de prédiction."""

from __future__ import annotations

import pytest

from predicare.ml.config import FEATURE_LABELS
from predicare.ml.explain import formater_feature, variable_source


def test_variable_source_numerique():
    variables = ["montant_total", "age_au_soin"]
    assert variable_source("num__montant_total", variables) == ("montant_total", None)


def test_variable_source_categorielle_onehot():
    variables = ["type_facture", "sexe"]
    variable, modalite = variable_source("cat__type_facture_PHARMACIE", variables)
    assert variable == "type_facture"
    assert modalite == "PHARMACIE"


def test_variable_source_indicateur_manquant():
    variables = ["montant_total"]
    variable, modalite = variable_source("num__montant_total_indicator", variables)
    assert variable == "montant_total"
    assert modalite is None


def test_formater_feature_retire_prefixe():
    assert formater_feature("num__montant_total") == "montant_total"
    assert formater_feature("cat__sexe_F") == "sexe_F"


def test_libelles_couvrent_les_variables_du_modele():
    from predicare.ml.scoring import charger_modele

    try:
        modele = charger_modele()
    except FileNotFoundError:
        pytest.skip("artefact modèle absent")
    manquants = [v for v in modele.variables if v not in FEATURE_LABELS]
    assert not manquants, f"libellés manquants : {manquants}"


def test_explications_conformes_au_contrat():
    from predicare.ml.explain import expliquer_facture
    from predicare.ml.scoring import charger_modele
    from predicare.ml.targets import charger_dataset_cm

    pytest.importorskip("shap")
    try:
        modele = charger_modele()
        dataset = charger_dataset_cm()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    ligne = dataset[dataset["split"] == "test"].iloc[0]
    facteurs, recommandation = expliquer_facture(modele, ligne, top_k=5)
    assert len(facteurs) == 5
    for facteur in facteurs:
        assert set(facteur) == {"feature", "valeur", "impact_shap", "description"}
        assert isinstance(facteur["feature"], str)
        assert isinstance(facteur["impact_shap"], float)
        assert facteur["description"]
    assert recommandation


def test_service_prediction_si_modele_disponible():
    from predicare.ml.service import FactureInconnue, predire_facture
    from predicare.ml.targets import charger_dataset_cm

    try:
        dataset = charger_dataset_cm()
        facture_id = dataset.loc[dataset["split"] == "test", "facture_id"].iloc[0]
        resultat = predire_facture(facture_id)
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    assert resultat["facture_id"] == facture_id
    prediction = resultat["prediction"]
    assert 0.0 <= prediction["score_fraude"] <= 1.0
    assert isinstance(prediction["est_anomalie"], bool)
    assert prediction["version_modele"]
    assert resultat["explicabilite"]["top_facteurs"]

    with pytest.raises(FactureInconnue):
        predire_facture("FAC-INEXISTANTE-999")
