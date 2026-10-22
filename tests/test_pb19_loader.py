"""Tests de conversion et de chargement PB-19."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pandas as pd
import pytest

from predicare.db.bootstrap import (
    BootstrapError,
    filter_bootstrap_data,
    source_checksum,
)
from predicare.db.load import _normalise_value


def test_opening_days_are_converted_to_array():
    assert _normalise_value("prestataires", "jours_ouverture", 12345) == [1, 2, 3, 4, 5]
    assert _normalise_value("prestataires", "jours_ouverture", "1234567") == [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    ]


def test_nif_is_kept_as_text():
    assert _normalise_value("prestataires", "nif", 1939042955) == "1939042955"
    assert _normalise_value("prestataires", "nif", 1939042955.0) == "1939042955"


def test_excluded_acts_are_split():
    assert _normalise_value("garanties", "actes_exclus", "DENT-PROTH|DENT-ORTHO") == [
        "DENT-PROTH",
        "DENT-ORTHO",
    ]


def test_booleans_are_converted():
    assert _normalise_value("referentiel_actes", "ordonnance_requise", 0) is False
    assert _normalise_value("referentiel_actes", "ordonnance_requise", 1) is True


def test_dates_and_times_are_converted():
    assert _normalise_value("factures", "date_soin", "2024-11-11") == date(2024, 11, 11)
    assert _normalise_value("factures", "heure_soin", "09:45") == time(9, 45)


def test_missing_values_become_none():
    assert _normalise_value("prestataires", "specialite", pd.NA) is None
    assert _normalise_value("factures", "motif_rejet", float("nan")) is None


def test_source_checksum_rejects_missing_files(tmp_path: Path):
    with pytest.raises(BootstrapError, match="Fichiers sources manquants"):
        source_checksum(tmp_path)


def test_filter_bootstrap_data_excludes_demo_provider():
    tables = {
        "factures": pd.DataFrame(
            [
                {"facture_id": "F1", "prestataire_id": "PRE-00050", "ordonnance_id": "ORD-1"},
                {"facture_id": "F2", "prestataire_id": "PRE-00050", "ordonnance_id": "ORD-SHARED"},
                {"facture_id": "F3", "prestataire_id": "PRE-00099", "ordonnance_id": "ORD-SHARED"},
                {"facture_id": "F4", "prestataire_id": "PRE-00099", "ordonnance_id": "ORD-2"},
            ]
        ),
        "lignes_facture": pd.DataFrame(
            [
                {"ligne_id": "L1", "facture_id": "F1"},
                {"ligne_id": "L2", "facture_id": "F2"},
                {"ligne_id": "L3", "facture_id": "F3"},
                {"ligne_id": "L4", "facture_id": "F4"},
            ]
        ),
        "ordonnances": pd.DataFrame(
            [
                {"ordonnance_id": "ORD-1", "prescripteur_id": "PRE-00010"},
                {"ordonnance_id": "ORD-SHARED", "prescripteur_id": "PRE-00010"},
                {"ordonnance_id": "ORD-2", "prescripteur_id": "PRE-00010"},
                {"ordonnance_id": "ORD-EXCL-DOC", "prescripteur_id": "PRE-00050"},
            ]
        ),
        "ordonnance_lignes": pd.DataFrame(
            [
                {"ordonnance_id": "ORD-1", "num_ligne": 1},
                {"ordonnance_id": "ORD-SHARED", "num_ligne": 1},
                {"ordonnance_id": "ORD-2", "num_ligne": 1},
                {"ordonnance_id": "ORD-EXCL-DOC", "num_ligne": 1},
            ]
        ),
    }

    filtered = filter_bootstrap_data(tables, excluded_prestataires=("PRE-00050",))

    # PRE-00050 factures excluded
    assert list(filtered["factures"]["facture_id"]) == ["F3", "F4"]
    # Corresponding lignes_facture excluded
    assert list(filtered["lignes_facture"]["ligne_id"]) == ["L3", "L4"]
    # ORD-1 excluded (only PRE-50), ORD-EXCL-DOC excluded (prescriber PRE-50),
    # ORD-SHARED kept (used by F3), ORD-2 kept (used by F4)
    assert set(filtered["ordonnances"]["ordonnance_id"]) == {"ORD-SHARED", "ORD-2"}
    # Corresponding ordonnance_lignes excluded
    assert set(filtered["ordonnance_lignes"]["ordonnance_id"]) == {"ORD-SHARED", "ORD-2"}
