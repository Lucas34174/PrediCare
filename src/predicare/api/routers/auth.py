"""Router d'authentification – /auth/login et /auth/me."""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

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
    ),
}


_TOKEN_PREFIX = "mock-token-"


def _user_from_authorization(authorization: str | None) -> UserInfo:
    """Retrouve l'utilisateur mock depuis l'en-tête Authorization"""
    scheme, _, token = (authorization or "").partition(" ")
    identifier = token.removeprefix(_TOKEN_PREFIX)
    if (
        scheme.lower() != "bearer"
        or not token.startswith(_TOKEN_PREFIX)
        or identifier not in _MOCK_USERS
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token manquant ou invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _MOCK_USERS[identifier]


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"description": "Identifiants erronés."}},
)
def login(body: LoginRequest) -> LoginResponse:
    """Authentification et émission du JWT (mock – PB-20 implémentera la vraie auth)."""
    user = _MOCK_USERS.get(body.identifier)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )
    return LoginResponse(
        access_token=f"{_TOKEN_PREFIX}{user.identifier}",
        expires_in=3600,
        user=user,
    )


@router.get(
    "/me",
    response_model=UserInfo,
    responses={401: {"description": "Token manquant, invalide ou expiré."}},
)
def me(authorization: Annotated[str | None, Header()] = None) -> UserInfo:
    """Profil de l'utilisateur connecté (mock – PB-20 implémentera la vraie auth)."""
    return _user_from_authorization(authorization)
