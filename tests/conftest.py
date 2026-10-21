"""Fixtures partagées pour les tests PrediCare TPA (mock sans PostgreSQL)."""

from __future__ import annotations

import os
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from predicare.api.routers.claims import _PERSISTED_PREDICTIONS, _SUBMITTED_CLAIMS
from predicare.api.schemas import (
    ClaimDetail,
    LigneFacture,
    StatutFacture,
    TypeLigne,
)
from predicare.core.config import database_url
from predicare.core.security import hash_password

# ---------------------------------------------------------------------------
# Données de référence injectées en mémoire
# ---------------------------------------------------------------------------

_MOCK_CLAIM = ClaimDetail(
    facture_id="FAC-00005637",
    numero_facture="F-2025-00124",
    assure_id="ASS-00421",
    prestataire_id="PR-0015",
    nom_etablissement="Clinique Saint-Paul",
    ordonnance_id="ORD-0003289",
    date_soin=date(2025, 4, 12),
    date_emission=date(2025, 4, 13),
    montant_total=45000,
    part_assure=9000,
    montant_demande=36000,
    statut=StatutFacture.EN_COURS,
    lignes=[
        LigneFacture(
            num_ligne=1,
            code="ACT-CS-01",
            type_ligne=TypeLigne.ACTE,
            quantite=1,
            prix_unitaire=30000,
            montant_total=30000,
        ),
        LigneFacture(
            num_ligne=2,
            code="MED-CIP-0045",
            type_ligne=TypeLigne.MEDICAMENT,
            quantite=2,
            prix_unitaire=7500,
            montant_total=15000,
        ),
    ],
)

# Utilisateurs mock – tous ont le mot de passe « x »
_MOCK_USERS: dict[str, dict] = {
    "gestionnaire1": {
        "id": "USR-0012",
        "identifiant": "gestionnaire1",
        "mot_de_passe_hash": hash_password("x"),
        "role": "gestionnaire",
        "assure_id": None,
        "prestataire_id": None,
        "actif": True,
        "nom_complet": "Aina Razafy",
    },
    "assure1": {
        "id": "USR-0021",
        "identifiant": "assure1",
        "mot_de_passe_hash": hash_password("x"),
        "role": "assure",
        "assure_id": "ASS-00421",
        "prestataire_id": None,
        "actif": True,
        "nom_complet": "Jean Dupont",
    },
    "pro1": {
        "id": "USR-0031",
        "identifiant": "pro1",
        "mot_de_passe_hash": hash_password("x"),
        "role": "professionnel_sante",
        "assure_id": None,
        "prestataire_id": "PR-0015",
        "actif": True,
        "nom_complet": "Clinique Saint-Paul",
    },
    "admin1": {
        "id": "USR-0001",
        "identifiant": "admin1",
        "mot_de_passe_hash": hash_password("x"),
        "role": "administrateur",
        "assure_id": None,
        "prestataire_id": None,
        "actif": True,
        "nom_complet": "Hery Andriamaro",
    },
}


# ---------------------------------------------------------------------------
# Fixtures autouse
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seed_submitted_claims():
    """Injecte les factures de référence et leurs prédictions dans les dicts en mémoire."""
    from datetime import UTC, datetime

    _SUBMITTED_CLAIMS["FAC-00005637"] = _MOCK_CLAIM
    _SUBMITTED_CLAIMS["FAC-00084700"] = _MOCK_CLAIM.model_copy(
        update={"facture_id": "FAC-00084700"}
    )

    _mock_prediction = {
        "prediction": {
            "score_fraude": 0.12,
            "seuil_applique": 0.30,
            "est_anomalie": False,
            "version_modele": "v1.0.0-xgb",
            "date_prediction": datetime.now(UTC),
        },
        "explicabilite": {
            "top_facteurs": [
                {
                    "feature": "f_montant_total",
                    "valeur": 45000,
                    "impact_shap": 0.05,
                    "description": "Montant total de la facture",
                }
            ],
            "recommandation": "Dossier conforme aux critères de remboursement.",
        },
    }
    _PERSISTED_PREDICTIONS["FAC-00005637"] = _mock_prediction
    _PERSISTED_PREDICTIONS["FAC-00084700"] = _mock_prediction

    yield

    _SUBMITTED_CLAIMS.pop("FAC-00005637", None)
    _SUBMITTED_CLAIMS.pop("FAC-00084700", None)
    _PERSISTED_PREDICTIONS.pop("FAC-00005637", None)
    _PERSISTED_PREDICTIONS.pop("FAC-00084700", None)


@pytest.fixture(autouse=True)
def mock_db_and_auth():
    """
    Mock global :
      - _db_engine() dans claims et deps → retourne None (pas de DB réelle)
        Le code de list_claims saute le bloc `if engine is not None` et renvoie
        ClaimsListResponse(total=0) au lieu de lever 503.
      - find_user_by_identifier dans deps → retourne le _MOCK_USERS dict.
    """
    with (
        patch("predicare.api.routers.claims._db_engine", return_value=None),
        patch("predicare.api.deps._db_engine", return_value=None),
        patch(
            "predicare.api.routers.auth.find_user_by_identifier",
            side_effect=lambda identifier: _MOCK_USERS.get(identifier),
        ),
    ):
        yield


# ---------------------------------------------------------------------------
# Fixture DB réelle (intégration complète avec PostgreSQL)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_temporaire(monkeypatch):
    """Crée une base vide isolée, puis la supprime après le test."""
    nom = f"predicare_test_{uuid.uuid4().hex[:8]}"
    admin = create_engine(
        database_url().set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin.connect() as connexion:
            connexion.execute(text(f'CREATE DATABASE "{nom}"'))
    except OperationalError:
        admin.dispose()
        if os.environ.get("PREDICARE_REQUIRE_DB"):
            raise
        pytest.skip("PostgreSQL injoignable : test d'intégration ignoré")
    monkeypatch.setenv("DB_NAME", nom)
    yield nom
    with admin.connect() as connexion:
        connexion.execute(text(f'DROP DATABASE "{nom}" WITH (FORCE)'))
    admin.dispose()
