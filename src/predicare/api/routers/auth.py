"""Router d'authentification – /auth/login et /auth/me."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import create_engine, text

from predicare.api.deps import get_current_user
from predicare.core.config import database_url
from predicare.core.security import create_access_token

from ..schemas import LoginRequest, LoginResponse, Role, UserInfo

logger = logging.getLogger(__name__)

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
        nom_complet="Pharmacie Voninkazo Tanjombato",
        prestataire_id="PRE-00050",
    ),
}


def _fetch_display_name(user: UserInfo) -> str:
    """Résout le nom d'affichage depuis la base PostgreSQL selon le rôle.
    Retourne le nom hardcodé en repli si la base est inaccessible.
    """
    try:
        engine = create_engine(database_url())
        with engine.connect() as conn:
            if user.role == Role.PROFESSIONNEL_SANTE and user.prestataire_id:
                row = conn.execute(
                    text("SELECT nom FROM prestataires WHERE prestataire_id = :pid"),
                    {"pid": user.prestataire_id},
                ).scalar()
                if row:
                    return str(row)
            elif user.role == Role.ASSURE and user.assure_id:
                # Les noms sont chiffrés (identites_pii) ; on retourne l'id comme repli lisible
                # Si un jour le déchiffrement est exposé, brancher ici
                return f"Assuré {user.assure_id}"
    except Exception as exc:
        logger.warning("Impossible de résoudre le nom depuis la DB : %s", exc)
    return user.nom_complet


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

    # Mots de passe valides pour les comptes démo.
    # On accepte: "x", "demo", "password123", et "<prefixe_sans_chiffres>123"
    # Ex: pro1 → "pro123", gestionnaire1 → "gestionnaire123", assure1 → "assure123"
    import re
    prefix = re.sub(r"\d+$", "", user.identifier)  # "pro1" → "pro", "gestionnaire1" → "gestionnaire"
    passwords_valides = {"x", "demo", f"{prefix}123", f"{user.identifier}123", "password123"}
    if body.password not in passwords_valides:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )

    # Résoudre le nom d'affichage depuis PostgreSQL (prestataires / assures)
    display_name = _fetch_display_name(user)

    # Création du vrai token JWT signé
    assure_id = user.assure_id or (user.id if user.role == Role.ASSURE else None)
    token_payload = {
        "sub": user.identifier,
        "id": user.id,
        "role": str(user.role),
        "nom_complet": display_name,
        "assure_id": assure_id,
        "prestataire_id": user.prestataire_id,
    }
    access_token = create_access_token(token_payload)

    # Mettre à jour l'objet user avec le nom résolu pour LoginResponse
    user = UserInfo(
        id=user.id,
        identifier=user.identifier,
        role=user.role,
        nom_complet=display_name,
        assure_id=user.assure_id,
        prestataire_id=user.prestataire_id,
    )

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
