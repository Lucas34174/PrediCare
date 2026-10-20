"""Tests de conversion et de chargement PB-19."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pandas as pd
import pytest

from predicare.db.bootstrap import BootstrapError, source_checksum
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
