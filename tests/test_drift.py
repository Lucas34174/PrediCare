"""Tests PB-12 : calcul de la dérive de distribution (Data Drift PSI / KS)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from predicare.ml.drift import (
    VARIABLES_TENDANCE,
    calculer_derive,
    construire_reference,
    synthese_derive,
)


def _petit_dataset(n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "facture_id": [f"F{i}" for i in range(n)],
            "split": ["train"] * (n // 2) + ["test"] * (n - n // 2),
            "cible_cm": rng.integers(0, 2, n),
            "montant_total": rng.normal(10_000, 2_000, n),
            "sexe": rng.choice(["F", "M"], n),
            "meta_date_reception": ["2026-01-01"] * n,
        }
    )


def test_reference_et_derive():
    dataset = _petit_dataset()
    reference = construire_reference(dataset)
    assert reference["n_train"] == 100
    assert {"montant_total", "sexe"}.issubset(reference["variables"])

    derive = calculer_derive(reference, dataset, split="test")
    assert set(derive.columns) >= {"variable", "type", "psi", "ks", "statut", "tendance"}
    assert derive["psi"].notna().all()
    assert derive["statut"].isin(
        {"ok", "vigilance", "alerte", "tendance_structurelle", "indetermine"}
    ).all()

    resume = synthese_derive(derive)
    assert resume["nb_variables"] == len(derive)
    assert resume["verdict"] in {"stable", "derive_moderee", "derive_significative"}


def test_compteurs_cumulatifs_marques_tendance():
    dataset = _petit_dataset()
    dataset["prest_nb_factures_hist"] = np.arange(len(dataset))
    reference = construire_reference(dataset)
    assert reference["variables"]["prest_nb_factures_hist"]["tendance"] is True
    assert "prest_nb_factures_hist" in VARIABLES_TENDANCE
