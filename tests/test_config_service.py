"""Tests unitaires et d'intégration pour le service de configuration dynamique (PB-25)."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from predicare.core.config import database_url
from predicare.core.config_service import (
    get_current_fraud_threshold,
    get_current_n8n_webhook_url,
    get_system_config,
    invalidate_config_cache,
    update_system_config,
)


def test_get_system_config_fallback_env(monkeypatch):
    """En l'absence de base de données, les valeurs par défaut proviennent de l'environnement."""
    invalidate_config_cache(clear_overrides=True)
    monkeypatch.setattr("predicare.core.config_service._get_engine", lambda eng=None: None)
    monkeypatch.setenv("ALERT_THRESHOLD", "0.45")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/test-env")

    cfg = get_system_config(engine=None)
    assert cfg.fraud_score_threshold == 0.45
    assert cfg.n8n_webhook_url == "http://n8n:5678/webhook/test-env"
    assert cfg.semantic_cache_enabled is True
    assert cfg.semantic_cache_threshold == 0.85


def test_config_cache_ttl_and_invalidation(monkeypatch):
    """Vérifie le fonctionnement du cache et son invalidation explicite."""
    invalidate_config_cache(clear_overrides=True)
    monkeypatch.setattr("predicare.core.config_service._get_engine", lambda eng=None: None)
    monkeypatch.setenv("ALERT_THRESHOLD", "0.40")
    cfg1 = get_system_config(engine=None)
    assert cfg1.fraud_score_threshold == 0.40

    # Changement d'environnement sans invalidation -> toujours la valeur en cache
    monkeypatch.setenv("ALERT_THRESHOLD", "0.99")
    cfg_cached = get_system_config(engine=None)
    assert cfg_cached.fraud_score_threshold == 0.40

    # Après invalidation explicite -> prend la nouvelle valeur
    invalidate_config_cache()
    cfg2 = get_system_config(engine=None)
    assert cfg2.fraud_score_threshold == 0.99


def test_update_system_config_in_memory(monkeypatch):
    """Vérifie la mise à jour immédiate en mémoire même sans base."""
    invalidate_config_cache()
    monkeypatch.setattr("predicare.core.config_service._get_engine", lambda eng=None: None)
    updated = update_system_config(
        {"fraud_score_threshold": 0.88, "n8n_webhook_url": "http://n8n:5678/webhook/new"},
        user_id="USR-0001",
        role="administrateur",
        ip_source="10.0.0.1",
        engine=None,
    )
    assert updated.fraud_score_threshold == 0.88
    assert updated.n8n_webhook_url == "http://n8n:5678/webhook/new"

    # Vérification via les helpers d'accès
    assert get_current_fraud_threshold() == 0.88
    assert get_current_n8n_webhook_url() == "http://n8n:5678/webhook/new"


def test_persistence_and_audit_with_database(db_temporaire):
    """Test d'intégration complet avec PostgreSQL : persistance et écriture dans journal_audit."""
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    cfg_alembic = Config(str(racine / "alembic.ini"))
    cfg_alembic.set_main_option("script_location", str(racine / "migrations"))
    command.upgrade(cfg_alembic, "head")

    moteur = create_engine(database_url())
    invalidate_config_cache()

    # Mise à jour de la configuration
    updated = update_system_config(
        {
            "fraud_score_threshold": 0.77,
            "semantic_cache_threshold": 0.91,
        },
        user_id="USR-0001",
        role="administrateur",
        ip_source="192.168.1.50",
        engine=moteur,
    )
    assert updated.fraud_score_threshold == 0.77
    assert updated.semantic_cache_threshold == 0.91

    # Invalidation du cache pour forcer une relecture depuis PostgreSQL
    invalidate_config_cache()
    reloaded = get_system_config(engine=moteur)
    assert reloaded.fraud_score_threshold == 0.77
    assert reloaded.semantic_cache_threshold == 0.91

    # Vérification de l'entrée dans journal_audit
    with moteur.connect() as conn:
        audit_row = (
            conn.execute(
                text("""
            SELECT type_action, utilisateur_id, role_utilisateur, details
            FROM journal_audit
            WHERE type_action = 'MODIFICATION_CONFIGURATION'
            ORDER BY date_action DESC LIMIT 1
        """)
            )
            .mappings()
            .first()
        )

        assert audit_row is not None
        assert audit_row["type_action"] == "MODIFICATION_CONFIGURATION"
        assert audit_row["utilisateur_id"] == "USR-0001"
        assert audit_row["role_utilisateur"] == "administrateur"
        details = audit_row["details"]
        if isinstance(details, str):
            import json

            details = json.loads(details)
        assert details["nouvelles_valeurs"]["fraud_score_threshold"] == 0.77
        assert details["nouvelles_valeurs"]["semantic_cache_threshold"] == 0.91

    moteur.dispose()
