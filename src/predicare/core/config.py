"""Configuration de l'application, lue dans les variables d'environnement."""

import os

from sqlalchemy.engine import URL


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
