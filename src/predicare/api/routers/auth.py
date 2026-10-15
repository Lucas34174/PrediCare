"""Router d'authentification – /auth/login et /auth/me."""

from fastapi import APIRouter

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


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    """Authentification et émission du JWT (mock – PB-20 implémentera la vraie auth)."""
    user = _MOCK_USERS.get(body.identifier, _MOCK_USERS["gestionnaire1"])
    return LoginResponse(
        access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock",
        expires_in=3600,
        user=user,
    )


@router.get("/me", response_model=UserInfo)
def me() -> UserInfo:
    """Profil de l'utilisateur connecté (mock – retourne gestionnaire1)."""
    return _MOCK_USERS["gestionnaire1"]
