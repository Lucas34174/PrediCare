"""Service de configuration dynamique (PB-25).

Gère la hiérarchie des sources : Base PostgreSQL (table app_config) > Variables d'environnement (.env).
Fournit un cache mémoire court (TTL = 3s) avec invalidation immédiate à l'écriture.
Trace chaque modification dans journal_audit sans divulgation de secret.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text

from predicare.api.schemas import AdminConfig
from predicare.core.config import (
    database_url,
    fraud_score_threshold,
    n8n_webhook_url,
)

logger = logging.getLogger("predicare.core.config_service")

_CACHE_LOCK = threading.Lock()
_CONFIG_CACHE: AdminConfig | None = None
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS: float = 3.0
_IN_MEMORY_OVERRIDES: dict[str, Any] = {}


def _get_engine(engine: Engine | None = None) -> Engine | None:
    if engine is not None:
        return engine
    try:
        from predicare.api.deps import _db_engine

        eng = _db_engine()
        if eng is not None:
            return eng
    except Exception:
        pass
    try:
        return create_engine(
            database_url(),
            connect_args={"connect_timeout": 2},
            pool_pre_ping=True,
        )
    except Exception:
        return None


def invalidate_config_cache(clear_overrides: bool = False) -> None:
    """Invalide immédiatement le cache mémoire local."""
    global _CONFIG_CACHE, _CACHE_TIMESTAMP, _IN_MEMORY_OVERRIDES
    with _CACHE_LOCK:
        _CONFIG_CACHE = None
        _CACHE_TIMESTAMP = 0.0
        if clear_overrides:
            _IN_MEMORY_OVERRIDES.clear()


def _get_env_default_config() -> AdminConfig:
    """Construit la configuration par défaut depuis l'environnement ou les overrides en mémoire."""
    semantic_cache_str = os.environ.get("SEMANTIC_CACHE_ENABLED", "true").lower()
    semantic_cache_enabled = semantic_cache_str in {"true", "1", "yes"}

    try:
        semantic_threshold = float(os.environ.get("SEMANTIC_CACHE_THRESHOLD", "0.85"))
    except ValueError:
        semantic_threshold = 0.85

    return AdminConfig(
        fraud_score_threshold=float(
            _IN_MEMORY_OVERRIDES.get("fraud_score_threshold", fraud_score_threshold())
        ),
        n8n_webhook_url=str(_IN_MEMORY_OVERRIDES.get("n8n_webhook_url", n8n_webhook_url())),
        semantic_cache_enabled=bool(
            _IN_MEMORY_OVERRIDES.get("semantic_cache_enabled", semantic_cache_enabled)
        ),
        semantic_cache_threshold=float(
            _IN_MEMORY_OVERRIDES.get("semantic_cache_threshold", semantic_threshold)
        ),
        updated_at=datetime.now(UTC),
    )


def get_system_config(engine: Engine | None = None) -> AdminConfig:
    """Récupère la configuration opérationnelle (Base > Cache > .env)."""
    global _CONFIG_CACHE, _CACHE_TIMESTAMP

    # 1. Vérification du cache mémoire (si pas d'engine spécifique imposé)
    if engine is None:
        with _CACHE_LOCK:
            if _CONFIG_CACHE is not None and (time.time() - _CACHE_TIMESTAMP) < _CACHE_TTL_SECONDS:
                return _CONFIG_CACHE

    # 2. Lecture depuis la base de données
    db_engine = _get_engine(engine)
    if db_engine is not None:
        try:
            with db_engine.connect() as conn:
                rows = conn.execute(text("SELECT cle, valeur, updated_at FROM app_config")).all()
                if rows:
                    values: dict[str, Any] = {}
                    latest_updated_at: datetime | None = None
                    for row in rows:
                        cle, val, dt = row[0], row[1], row[2]
                        # PostgreSQL JSONB peut être désérialisé automatiquement ou rester str
                        if isinstance(val, str):
                            try:
                                val = json.loads(val)
                            except Exception:
                                pass
                        values[cle] = val
                        if dt is not None and (latest_updated_at is None or dt > latest_updated_at):
                            latest_updated_at = dt

                    defaults = _get_env_default_config()
                    cfg = AdminConfig(
                        fraud_score_threshold=float(
                            values.get("fraud_score_threshold", defaults.fraud_score_threshold)
                        ),
                        n8n_webhook_url=str(
                            values.get("n8n_webhook_url", defaults.n8n_webhook_url)
                        ),
                        semantic_cache_enabled=bool(
                            values.get("semantic_cache_enabled", defaults.semantic_cache_enabled)
                        ),
                        semantic_cache_threshold=float(
                            values.get(
                                "semantic_cache_threshold", defaults.semantic_cache_threshold
                            )
                        ),
                        updated_at=latest_updated_at or defaults.updated_at,
                    )
                    if engine is None:
                        with _CACHE_LOCK:
                            _CONFIG_CACHE = cfg
                            _CACHE_TIMESTAMP = time.time()
                    return cfg
        except Exception as exc:
            logger.warning("Échec lecture table app_config : %s", exc)

    # 3. Repli sur les valeurs d'environnement
    default_cfg = _get_env_default_config()
    if engine is None:
        with _CACHE_LOCK:
            _CONFIG_CACHE = default_cfg
            _CACHE_TIMESTAMP = time.time()
    return default_cfg


def update_system_config(
    updates: dict[str, Any],
    user_id: str = "USR-0001",
    role: str = "administrateur",
    ip_source: str = "127.0.0.1",
    engine: Engine | None = None,
) -> AdminConfig:
    """Met à jour atomiquement la configuration en base et consigne l'audit."""
    current = get_system_config(engine=engine)
    filtered = {
        k: v
        for k, v in updates.items()
        if v is not None
        and k
        in {
            "fraud_score_threshold",
            "n8n_webhook_url",
            "semantic_cache_enabled",
            "semantic_cache_threshold",
        }
    }

    if not filtered:
        return current

    now = datetime.now(UTC)
    db_engine = _get_engine(engine)

    if db_engine is not None:
        try:
            with db_engine.begin() as conn:
                for cle, valeur in filtered.items():
                    conn.execute(
                        text("""
                        INSERT INTO app_config (cle, valeur, updated_at, updated_by)
                        VALUES (:cle, CAST(:valeur AS jsonb), :updated_at, :updated_by)
                        ON CONFLICT (cle) DO UPDATE
                        SET valeur = EXCLUDED.valeur,
                            updated_at = EXCLUDED.updated_at,
                            updated_by = EXCLUDED.updated_by
                    """),
                        {
                            "cle": cle,
                            "valeur": json.dumps(valeur),
                            "updated_at": now,
                            "updated_by": user_id,
                        },
                    )

                # Écriture dans journal_audit
                audit_details = {
                    "anciennes_valeurs": {k: getattr(current, k) for k in filtered},
                    "nouvelles_valeurs": filtered,
                }
                conn.execute(
                    text("""
                    INSERT INTO journal_audit
                    (type_action, utilisateur_id, role_utilisateur, ressource_type, ressource_id, details, ip_source, date_action)
                    VALUES ('MODIFICATION_CONFIGURATION', :uid, :role, 'configuration', 'app_config', CAST(:details AS jsonb), :ip, :dt)
                """),
                    {
                        "uid": user_id,
                        "role": role,
                        "details": json.dumps(audit_details),
                        "ip": ip_source,
                        "dt": now,
                    },
                )
        except Exception as exc:
            logger.warning("Échec écriture dans app_config ou journal_audit : %s", exc)

    # Invalidation immédiate du cache et calcul de la nouvelle configuration
    with _CACHE_LOCK:
        _IN_MEMORY_OVERRIDES.update(filtered)
    invalidate_config_cache(clear_overrides=False)
    new_data = current.model_dump()
    new_data.update(filtered)
    new_data["updated_at"] = now
    new_cfg = AdminConfig(**new_data)

    with _CACHE_LOCK:
        _CONFIG_CACHE = new_cfg
        _CACHE_TIMESTAMP = time.time()

    return new_cfg


def get_current_fraud_threshold(engine: Engine | None = None) -> float:
    """Renvoie le seuil d'alerte de fraude en vigueur (Base > Env)."""
    try:
        return get_system_config(engine=engine).fraud_score_threshold
    except Exception:
        return fraud_score_threshold()


def get_current_n8n_webhook_url(engine: Engine | None = None) -> str:
    """Renvoie l'URL du webhook n8n en vigueur (Base > Env)."""
    try:
        return get_system_config(engine=engine).n8n_webhook_url
    except Exception:
        return n8n_webhook_url()
