"""Tests de la cible B (`cible_controle_medical`) et du dataset CM."""

from __future__ import annotations

import pytest

from predicare.ml.config import DATA_RAW, META_COLUMNS, TARGET


def _charger():
    """Tests de la cible proxy historique : charger explicitement dataset_cm.csv.

    La production v2 utilise ``data/processed/dataset_cm_v2.csv`` (labels
    faibles) ; ces tests valident le schéma de l'ancienne cible proxy.
    """
    from predicare.ml.targets import charger_dataset_cm

    chemin = DATA_RAW / "dataset_cm.csv"
    if not chemin.is_file():
        pytest.skip(f"{chemin} absent (cible proxy historique)")
    try:
        return charger_dataset_cm(chemin)
    except FileNotFoundError as exc:  # données sources absentes du conteneur de test
        pytest.skip(str(exc))


@pytest.fixture(scope="module")
def dataset_cm():
    return _charger()


def test_cible_binaire(dataset_cm):
    assert TARGET in dataset_cm.columns
    assert dataset_cm[TARGET].isin([0, 1]).all()
    assert dataset_cm[TARGET].notna().all()


def test_trois_splits_et_positifs(dataset_cm):
    assert set(dataset_cm["split"].unique()) == {"train", "validation", "test"}
    for split in ("train", "validation", "test"):
        assert dataset_cm.loc[dataset_cm["split"] == split, TARGET].sum() > 0


def test_identifiants_uniques(dataset_cm):
    assert dataset_cm["facture_id"].is_unique


def test_prevalence_faible(dataset_cm):
    prevalence = dataset_cm[TARGET].mean()
    assert 0.005 < prevalence < 0.05


def test_pas_de_rejet_administratif(dataset_cm):
    """Seuls PAYEE et CONTROLE_MEDICAL composent la population B."""
    assert dataset_cm.loc[dataset_cm[TARGET] == 1, "motif_rejet"].eq("CONTROLE_MEDICAL").all()
    assert dataset_cm.loc[dataset_cm[TARGET] == 0, "motif_rejet"].isna().all()


def test_aucune_colonne_de_fuite_comme_variable(dataset_cm):
    features = [c for c in dataset_cm.columns if c not in META_COLUMNS]
    assert "cible" not in features
    assert "cible_controle_medical" not in features
    assert "statut" not in features
    assert "motif_rejet" not in features


def test_valider_dataset_cm_tout_ok(dataset_cm):
    from predicare.ml.targets import valider_dataset_cm

    rapport = valider_dataset_cm(dataset_cm)
    echecs = rapport[rapport["statut"] != "OK"]
    assert echecs.empty, echecs.to_string(index=False)
