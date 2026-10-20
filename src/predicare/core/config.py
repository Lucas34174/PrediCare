"""Configuration de l'application, lue dans les variables d'environnement."""

import os

from sqlalchemy.engine import URL

DEFAULT_FRAUD_THRESHOLD = 0.30


def database_url() -> URL:
    """URL de connexion PostgreSQL (driver psycopg 3).

    Les variables DB_* sont fournies par le docker-compose. Hors conteneur,
    les valeurs par défaut visent la base exposée sur la machine locale.
    """
    return URL.create(
        drivername="postgresql+psycopg",
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ.get("DB_NAME", "predicare"),
        username=os.environ.get("DB_USER", "predicare"),
        password=os.environ.get("DB_PASSWORD"),
    )


def fraud_score_threshold() -> float:
    """Seuil d'alerte de fraude lu dynamiquement depuis l'environnement (défaut 0.30)."""
    valeur = os.environ.get("FRAUD_SCORE_THRESHOLD")
    if valeur is not None:
        try:
            return float(valeur)
        except ValueError:
            pass
    return DEFAULT_FRAUD_THRESHOLD


def model_path() -> str:
    """Chemin de l'artefact modèle champion sérialisé."""
    return os.environ.get("PREDICARE_MODELE_PATH", "models/model_champion.joblib")


def model_version() -> str:
    """Identifiant de version du modèle champion actif."""
    return os.environ.get("PREDICARE_MODELE_VERSION", "v1.0.0-xgb")


def n8n_webhook_url() -> str:
    """URL du webhook n8n pour les alertes de fraude (contrat §4)."""
    return os.environ.get("N8N_WEBHOOK_URL", "http://n8n:5678/webhook/fraud-alert")


def dashboard_base_url() -> str:
    """URL de base du dashboard pour les liens d'action des alertes."""
    return os.environ.get("DASHBOARD_BASE_URL", "http://localhost:3000")
