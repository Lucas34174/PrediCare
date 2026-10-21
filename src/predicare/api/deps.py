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
from predicare.core.security import decode_access_token


@cache
def _db_engine() -> Engine:
    return create_engine(database_url(), connect_args={"connect_timeout": 2}, pool_pre_ping=True)


def find_user_by_identifier(identifier: str) -> dict[str, Any] | None:
    """Cherche un utilisateur dans la table PostgreSQL 'utilisateurs'.

    Résout automatiquement le nom_complet :
    - Pour un assuré : déchiffré à la volée depuis la table identites_pii (nom + prénoms)
    - Pour un professionnel de santé : nom depuis la table prestataires
    - Pour un gestionnaire/admin : nom de courtoisie basé sur l'identifiant
    """
    try:
        with _db_engine().connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT id, identifiant, mot_de_passe_hash, role, "
                        "assure_id, prestataire_id, actif "
                        "FROM utilisateurs WHERE identifiant = :identifiant AND actif = TRUE"
                    ),
                    {"identifiant": identifier},
                )
                .mappings()
                .first()
            )
            if not row:
                return None

            user_data = dict(row)
            role = user_data.get("role")
            assure_id = user_data.get("assure_id")
            prestataire_id = user_data.get("prestataire_id")

            # Résolution dynamique du nom complet
            nom_complet = identifier
            if role == "assure" and assure_id:
                try:
                    from predicare.core.pii import decrypt_identity, get_pii_key
                    pii = decrypt_identity(conn, assure_id, get_pii_key())
                    if pii and (pii.get("nom") or pii.get("prenoms")):
                        prenoms = pii.get("prenoms") or ""
                        nom = pii.get("nom") or ""
                        nom_complet = f"{prenoms} {nom}".strip()
                except Exception as exc:  # noqa: BLE001
                    import logging
                    logging.getLogger(__name__).warning("Impossible de déchiffrer PII pour %s : %s", assure_id, exc)

            elif role == "professionnel_sante" and prestataire_id:
                prest = (
                    conn.execute(
                        text("SELECT nom FROM prestataires WHERE prestataire_id = :pid"),
                        {"pid": prestataire_id},
                    )
                    .mappings()
                    .first()
                )
                if prest and prest.get("nom"):
                    nom_complet = prest["nom"]

            elif role == "gestionnaire":
                nom_complet = "Aina Razafy"
            elif role == "administrateur":
                nom_complet = "Hery Andriamaro"

            user_data["nom_complet"] = nom_complet
            return user_data

    except SQLAlchemyError as exc:
        import logging
        logging.getLogger(__name__).warning("DB inaccessible dans find_user_by_identifier : %s", exc)

    return None


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
