"""Sécurité : hachage de mots de passe (bcrypt) et gestion des tokens JWT."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

ALGORITHM = "HS256"
DEFAULT_EXPIRE_SECONDS = (
    7 * 24 * 3600
)  # 7 jours (évite l'expiration de session en session de travail)


def get_jwt_secret() -> str:
    """Récupère le secret JWT depuis les variables d'environnement."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        # Valeur de repli pour tests locaux hors conteneur
        return "change_me_jwt_secret_0123456789abcdef"
    return secret


def hash_password(password: str) -> str:
    """Hache un mot de passe en clair avec bcrypt et un sel aléatoire."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe en clair correspond à son hash bcrypt."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Crée un token JWT signé avec l'algorithme HS256."""
    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(seconds=DEFAULT_EXPIRE_SECONDS)

    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(to_encode, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Décode et valide la signature et l'expiration d'un token JWT.

    Lève jwt.PyJWTError (ExpiredSignatureError, InvalidTokenError) si invalide.
    """
    return jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
