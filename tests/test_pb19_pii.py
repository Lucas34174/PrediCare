"""Tests unitaires du chiffrement PII (PB-19)."""

from __future__ import annotations

import pytest

from predicare.core.pii import (
    MIN_KEY_LENGTH,
    PIIError,
    validate_pii_key,
)
from predicare.db.schemas import PII_ENCRYPTED_COLUMNS


def test_validate_key_rejects_missing_key():
    with pytest.raises(PIIError):
        validate_pii_key("")


def test_validate_key_rejects_short_key():
    with pytest.raises(PIIError):
        validate_pii_key("x" * (MIN_KEY_LENGTH - 1))


def test_validate_key_accepts_long_key():
    key = "k" * MIN_KEY_LENGTH
    assert validate_pii_key(key) == key


def test_validate_key_rejects_demo_key_in_production():
    with pytest.raises(PIIError):
        validate_pii_key("change_me_" + "x" * 40, app_env="prod")


def test_pii_mapping_covers_expected_columns():
    assert set(PII_ENCRYPTED_COLUMNS) == {
        "nom",
        "prenoms",
        "date_naissance",
        "telephone",
        "email",
        "adresse",
        "numero_cin",
    }
    assert PII_ENCRYPTED_COLUMNS["nom"] == "nom_chiffre"
    assert PII_ENCRYPTED_COLUMNS["numero_cin"] == "numero_cin_chiffre"
