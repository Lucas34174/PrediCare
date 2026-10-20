"""Tests PB-12 : lot de 20 factures et robustesse aux anomalies déterministes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from predicare.ml.config import SOURCE_DIR
from predicare.ml.robustness import (
    CODES_INVALIDITE,
    charger_referentiels,
    valider_facture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "factures_test_set.json"


@pytest.fixture(scope="module")
def lot():
    if not FIXTURE.is_file():
        pytest.skip("factures_test_set.json absent")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_lot_20_factures_et_categories(lot):
    total = len(lot["valides"]) + len(lot["invalides"])
    assert total >= 20
    categories = set(lot["categorie_effectifs"])
    assert {"normal", "suspect", "invalide", "incomplet"}.issubset(categories)
    assert lot["categorie_effectifs"]["normal"] > 0
    assert lot["categorie_effectifs"]["suspect"] > 0


def test_10_codes_invalidite_couverts(lot):
    codes_lot = {c for cas in lot["invalides"] for c in cas["attendu"]}
    assert set(CODES_INVALIDITE).issubset(codes_lot)


@pytest.mark.skipif(not SOURCE_DIR.is_dir(), reason="CSV sources absents")
def test_factures_invalides_rejetees_avec_code(lot):
    referentiels = charger_referentiels(SOURCE_DIR)
    for cas in lot["invalides"]:
        codes = valider_facture(cas["facture"], referentiels, lot["date_reference"])
        assert set(cas["attendu"]).issubset(set(codes)), (cas["facture_id"], codes)


@pytest.mark.skipif(not SOURCE_DIR.is_dir(), reason="CSV sources absents")
def test_facture_valide_acceptee(lot):
    referentiels = charger_referentiels(SOURCE_DIR)
    base = dict(lot["invalides"][0]["facture"])
    base["lignes"] = [
        {"code": sorted(referentiels["codes"])[0], "quantite": 1, "prix_unitaire": 1000, "montant": 1000}
    ]
    base["montant_total"] = 1000
    base["date_soin"] = "2026-06-01"
    base["devise"] = "MGA"
    codes = valider_facture(base, referentiels, lot["date_reference"])
    assert "DEVISE_INVALIDE" not in codes
    assert "MONTANT_NEGATIF" not in codes
