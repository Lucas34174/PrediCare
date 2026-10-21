"""Tests pour la configuration externalisée et la protection des secrets (PB-25)."""

import pytest
from fastapi.testclient import TestClient

from predicare.core.config import (
    DEFAULT_FRAUD_THRESHOLD,
    ConfigurationError,
    fraud_score_threshold,
    validate_required_secrets,
)
from predicare.core.security import get_jwt_secret


def test_validate_required_secrets_nominal(monkeypatch):
    """Validation nominale quand tous les secrets requis sont présents."""
    monkeypatch.setenv("JWT_SECRET", "cle_secrete_jwt_super_longue_et_aleatoire_123456")
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "cle_pii_chiffrement_32_caracteres_min!")
    # Ne doit pas lever d'exception
    validate_required_secrets()


def test_validate_required_secrets_manquant_jwt(monkeypatch):
    """Vérifie l'échec explicite si JWT_SECRET est manquant."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("PII_ENCRYPTION_KEY", "cle_pii_chiffrement_32_caracteres_min!")
    with pytest.raises(ConfigurationError) as exc_info:
        validate_required_secrets()
    message = str(exc_info.value)
    assert "JWT_SECRET" in message
    assert "PII_ENCRYPTION_KEY" not in message


def test_validate_required_secrets_manquant_pii(monkeypatch):
    """Vérifie l'échec explicite si PII_ENCRYPTION_KEY est manquante."""
    monkeypatch.setenv("JWT_SECRET", "cle_secrete_jwt_super_longue_et_aleatoire_123456")
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_required_secrets()
    message = str(exc_info.value)
    assert "PII_ENCRYPTION_KEY" in message
    assert "JWT_SECRET" not in message


def test_validate_required_secrets_aucun_secret_dans_message(monkeypatch):
    """Garantit qu'aucune valeur de secret ne fuite dans le message d'erreur."""
    mon_secret_jwt = "secret_top_confidentiel_xyz"
    monkeypatch.setenv("JWT_SECRET", mon_secret_jwt)
    monkeypatch.delenv("PII_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        validate_required_secrets()
    message = str(exc_info.value)
    assert mon_secret_jwt not in message


def test_get_jwt_secret_sans_repli_par_defaut(monkeypatch):
    """Vérifie que get_jwt_secret ne fournit plus de valeur par défaut codée en dur."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        get_jwt_secret()
    assert "JWT_SECRET" in str(exc_info.value)

    monkeypatch.setenv("JWT_SECRET", "mon_vrai_secret_jwt")
    assert get_jwt_secret() == "mon_vrai_secret_jwt"


def test_seuil_alerte_supporte_alert_threshold_et_fraud_score_threshold(monkeypatch):
    """Vérifie le support des deux variables d'environnement avec priorité à ALERT_THRESHOLD."""
    monkeypatch.delenv("ALERT_THRESHOLD", raising=False)
    monkeypatch.delenv("FRAUD_SCORE_THRESHOLD", raising=False)
    assert fraud_score_threshold() == DEFAULT_FRAUD_THRESHOLD

    # Si seul FRAUD_SCORE_THRESHOLD est défini
    monkeypatch.setenv("FRAUD_SCORE_THRESHOLD", "0.72")
    assert fraud_score_threshold() == 0.72

    # Si ALERT_THRESHOLD est également défini, il a la priorité (alignement docker-compose/.env)
    monkeypatch.setenv("ALERT_THRESHOLD", "0.85")
    assert fraud_score_threshold() == 0.85

    # Si hors bornes (ex > 1.0 ou négatif) ou invalide -> repli sur défaut
    monkeypatch.setenv("ALERT_THRESHOLD", "1.5")
    assert fraud_score_threshold() == DEFAULT_FRAUD_THRESHOLD


def test_api_demarrage_echoue_sans_secret(monkeypatch):
    """Vérifie que l'API refuse de démarrer via son lifespan si un secret manque."""
    from predicare.api.main import app

    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ConfigurationError) as exc_info:
        with TestClient(app):
            pass
    assert "JWT_SECRET" in str(exc_info.value)
