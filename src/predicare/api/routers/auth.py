"""Router d'authentification – /auth/login et /auth/me."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from predicare.api.deps import get_current_user
from predicare.core.security import create_access_token

from ..schemas import LoginRequest, LoginResponse, Role, UserInfo

router = APIRouter(prefix="/auth", tags=["Authentification"])

_MOCK_USERS: dict[str, UserInfo] = {
    "gestionnaire1": UserInfo(
        id="USR-0012",
        identifier="gestionnaire1",
        role=Role.GESTIONNAIRE,
        nom_complet="Aina Razafy",
    ),
    "assure1": UserInfo(
        id="ASS-00421",
        identifier="assure1",
        role=Role.ASSURE,
        nom_complet="Rabe Rakoto",
        assure_id="ASS-00421",
    ),
    "admin1": UserInfo(
        id="USR-0001",
        identifier="admin1",
        role=Role.ADMINISTRATEUR,
        nom_complet="Hery Andriamaro",
    ),
    "pro1": UserInfo(
        id="USR-0050",
        identifier="pro1",
        role=Role.PROFESSIONNEL_SANTE,
        nom_complet="Dr. Solo Rakotondrabe",
        prestataire_id="PRE-00148",
    ),
}


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"description": "Identifiants erronés."}},
)
def login(body: LoginRequest) -> LoginResponse:
    """Authentification et émission du JWT."""
    user = _MOCK_USERS.get(body.identifier)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )

    # Mots de passe valides pour les comptes démo (notamment "x" des tests de contrats)
    passwords_valides = {"x", "demo", f"{user.identifier}123", "password123"}
    if body.password not in passwords_valides:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )

    # Création du vrai token JWT signé
    assure_id = user.assure_id or (user.id if user.role == Role.ASSURE else None)
    token_payload = {
        "sub": user.identifier,
        "id": user.id,
        "role": str(user.role),
        "nom_complet": user.nom_complet,
        "assure_id": assure_id,
        "prestataire_id": user.prestataire_id,
    }
    access_token = create_access_token(token_payload)

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=3600,
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
