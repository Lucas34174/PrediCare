"""Tests PB-14 : audit d'équité par sous-groupe."""

from __future__ import annotations

import numpy as np
import pandas as pd

from predicare.ml.fairness import SEUIL_ECART_TPR, auditer, rapport_markdown, synthese, wilson


def _dataset_scores(n: int = 300):
    rng = np.random.default_rng(1)
    dataset = pd.DataFrame(
        {
            "facture_id": [f"F{i}" for i in range(n)],
            "split": ["train"] * (n // 2) + ["test"] * (n - n // 2),
            "cible_cm": rng.integers(0, 2, n),
            "sexe": rng.choice(["F", "M"], n),
            "age_au_soin": rng.integers(18, 80, n),
            "formule": rng.choice(["BASIQUE", "CONFORT", "PREMIUM"], n),
            "meta_assure_id": ["ASS-1"] * n,
            "meta_prestataire_id": ["PR-1"] * n,
        }
    )
    test = dataset[dataset["split"] == "test"].copy()
    probabilite = rng.random(len(test))
    scores = pd.DataFrame(
        {
            "facture_id": test["facture_id"].to_numpy(),
            "probabilite": probabilite,
            "score_risque": probabilite,
            "alerte": (probabilite >= 0.8).astype(int),
        }
    )
    return dataset, scores


def test_wilson_intervalle():
    bas, haut = wilson(5, 10)
    assert 0.2 < bas < 0.3
    assert 0.7 < haut < 0.8
    assert bas < haut


def test_wilson_effectif_nul():
    bas, haut = wilson(0, 0)
    assert np.isnan(bas) and np.isnan(haut)


def test_audit_par_dimension():
    dataset, scores = _dataset_scores()
    resultats = auditer(dataset, scores, source_dir=False)
    assert {"sexe", "tranche_age", "formule"}.issubset(resultats)
    table = resultats["sexe"]
    assert {"groupe", "modalite", "n", "positifs", "taux_alerte", "tpr", "fpr"} <= set(table.columns)
    assert table["n"].sum() > 0


def test_synthese_et_seuil():
    dataset, scores = _dataset_scores()
    resultats = auditer(dataset, scores, source_dir=False)
    resume = synthese(resultats)
    assert "dimensions" in resume
    for info in resume["dimensions"].values():
        assert "ecart_tpr_max_min" in info
        assert "alerte_equite" in info
        if info["ecart_tpr_max_min"] is not None and info["ecart_tpr_max_min"] > SEUIL_ECART_TPR:
            assert info["alerte_equite"]


def test_rapport_markdown():
    dataset, scores = _dataset_scores()
    resultats = auditer(dataset, scores, source_dir=False)
    resume = synthese(resultats)
    markdown = rapport_markdown(resume, resultats, seuil=0.8)
    assert "Audit d'équité" in markdown
    assert "Limites" in markdown
    assert "Mesures correctives" in markdown
