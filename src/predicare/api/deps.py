"""Dépendances FastAPI pour l'authentification et le contrôle d'accès RBAC."""

from __future__ import annotations

from collections.abc import Sequence
from functools import cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from predicare.api.schemas import Role, UserInfo
from predicare.core.config import database_url
from predicare.core.security import decode_access_token, hash_password

# Comptes de démonstration avec hash bcrypt (repli si la base n'est pas encore peuplée)
_DEMO_USERS: dict[str, dict[str, Any]] = {
    "gestionnaire1": {
        "id": "USR-0012",
        "identifier": "gestionnaire1",
        "role": Role.GESTIONNAIRE,
        "nom_complet": "Aina Razafy",
        "mot_de_passe_hash": hash_password("gestionnaire123"),
        "assure_id": None,
        "prestataire_id": None,
    },
    "assure1": {
        "id": "ASS-00421",
        "identifier": "assure1",
        "role": Role.ASSURE,
        "nom_complet": "Rabe Rakoto",
        "mot_de_passe_hash": hash_password("assure123"),
        "assure_id": "ASS-00421",
        "prestataire_id": None,
    },
    "admin1": {
        "id": "USR-0001",
        "identifier": "admin1",
        "role": Role.ADMINISTRATEUR,
        "nom_complet": "Hery Andriamaro",
        "mot_de_passe_hash": hash_password("admin123"),
        "assure_id": None,
        "prestataire_id": None,
    },
    "pro1": {
        "id": "USR-0050",
        "identifier": "pro1",
        "role": Role.PROFESSIONNEL_SANTE,
        "nom_complet": "Pharmacie Voninkazo Tanjombato",
        "mot_de_passe_hash": hash_password("pro123"),
        "assure_id": None,
        "prestataire_id": "PRE-00050",
    },
}


@cache
def _db_engine() -> Engine:
    return create_engine(database_url(), connect_args={"connect_timeout": 2}, pool_pre_ping=True)


def find_user_by_identifier(identifier: str) -> dict[str, Any] | None:
    """Cherche un utilisateur dans la table PostgreSQL 'utilisateurs', avec repli démo."""
    try:
        with _db_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT id, identifiant, mot_de_passe_hash, role, nom_complet, "
                        "assure_id, prestataire_id, actif "
                        "FROM utilisateurs WHERE identifiant = :identifiant AND actif = TRUE"
                    ),
                    {"identifiant": identifier},
                )
                .mappings()
                .first()
            )
            if row:
                return dict(row)
    except SQLAlchemyError:
        pass

    return _DEMO_USERS.get(identifier)


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> UserInfo:
    """Valide le token JWT Bearer et renvoie l'utilisateur connecté."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expiré.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    sub = payload.get("sub")
    role_str = payload.get("role")
    if not sub or not role_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide (payload incomplet).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        role = Role(role_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Rôle utilisateur inconnu.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    return UserInfo(
        id=payload.get("id", sub),
        identifier=sub,
        role=role,
        nom_complet=payload.get("nom_complet", sub),
        assure_id=payload.get("assure_id"),
        prestataire_id=payload.get("prestataire_id"),
    )


def require_roles(allowed_roles: Sequence[Role]):
    """Dépendance FastAPI vérifiant que le rôle de l'utilisateur fait partie de allowed_roles."""

    def _role_checker(
        current_user: Annotated[UserInfo, Depends(get_current_user)],
    ) -> UserInfo:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé pour le rôle '{current_user.role}'.",
            )
        return current_user

    return _role_checker


def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> UserInfo:
    """Valide le token JWT Bearer et renvoie l'utilisateur connecté (401 si absent)."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(authorization)
