"""Router d'authentification – /auth/login et /auth/me."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from predicare.api.deps import find_user_by_identifier, get_current_user
from predicare.core.security import create_access_token, verify_password

from ..schemas import LoginRequest, LoginResponse, Role, UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"description": "Identifiants erronés."}},
)
def login(body: LoginRequest) -> LoginResponse:
    """Authentification depuis la table PostgreSQL `utilisateurs` et émission du JWT."""
    db_user = find_user_by_identifier(body.identifier)

    if db_user is None or not verify_password(body.password, db_user.get("mot_de_passe_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )

    if not db_user.get("actif", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé. Contactez l'administrateur.",
        )

    role = db_user["role"] if isinstance(db_user["role"], Role) else Role(db_user["role"])
    assure_id = db_user.get("assure_id")
    prestataire_id = db_user.get("prestataire_id")
    nom_complet = db_user.get("nom_complet") or body.identifier

    token_payload = {
        "sub": db_user["identifiant"],
        "id": db_user["id"],
        "role": str(role),
        "nom_complet": nom_complet,
        "assure_id": assure_id,
        "prestataire_id": prestataire_id,
    }
    access_token = create_access_token(token_payload)

    user = UserInfo(
        id=db_user["id"],
        identifier=db_user["identifiant"],
        role=role,
        nom_complet=nom_complet,
        assure_id=assure_id,
        prestataire_id=prestataire_id,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=7 * 24 * 3600,
        user=user,
    )


@router.get(
    "/me",
    response_model=UserInfo,
    responses={401: {"description": "Token manquant, invalide ou expiré."}},
)
def me(current_user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    """Profil de l'utilisateur connecté, validé par décodage du JWT."""
    return current_user
