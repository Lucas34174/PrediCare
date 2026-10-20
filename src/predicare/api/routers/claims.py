"""Router factures – /claims."""

import json
import logging
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text

from predicare.api.deps import _db_engine, get_optional_user
from predicare.api.schemas import Role, UserInfo
from predicare.core.config import fraud_score_threshold
from predicare.ml.service import ModeleIndisponible, predire_facture_en_ligne

from ..schemas import (
    ClaimCreateRequest,
    ClaimCreateResponse,
    ClaimDetail,
    ClaimsListResponse,
    ClaimSummary,
    DecisionRequest,
    DecisionResponse,
    DecisionValeur,
    ExplicabiliteInfo,
    LigneFacture,
    PredictionInfo,
    PredictionResponse,
    ShapFactor,
    StatutFacture,
    TypeLigne,
)

router = APIRouter(prefix="/claims", tags=["Factures"])

_NOW = datetime(2026, 10, 15, 10, 15, tzinfo=UTC)

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

_KNOWN_CLAIM_IDS = {"FAC-00005637", "FAC-00084700"}
_SUBMITTED_CLAIMS: dict[str, ClaimDetail] = {}

_PERSISTED_PREDICTIONS: dict[str, dict] = {}
logger = logging.getLogger("predicare.api.claims")


def _persister_facture_db(
    facture_id: str,
    body: ClaimCreateRequest,
    score_fraude: float | None,
    est_anomalie: bool,
    seuil_applique: float,
    version_modele: str,
    top_facteurs: list[dict],
    date_prediction: datetime,
) -> bool:
    """Insère la facture, ses lignes, la prédiction et le SHAP dans une seule transaction atomique."""
    try:
        engine = _db_engine()
        with engine.begin() as conn:
            # 1. Vérification / récupération du contrat_id pour cet assuré
            contrat_id = conn.execute(
                text("SELECT contrat_id FROM assures WHERE assure_id = :aid"),
                {"aid": body.assure_id},
            ).scalar() or "CTR-2025-001"

            # 2. Insertion facture
            conn.execute(
                text(
                    "INSERT INTO factures ("
                    "facture_id, numero_facture, prestataire_id, assure_id, contrat_id, "
                    "ordonnance_id, type_facture, date_soin, heure_soin, date_facture, "
                    "date_reception, canal_reception, mode_reglement, nb_lignes, "
                    "montant_total, montant_eligible, montant_pris_en_charge, reste_a_charge, statut"
                    ") VALUES ("
                    ":facture_id, :numero_facture, :prestataire_id, :assure_id, :contrat_id, "
                    ":ordonnance_id, 'CONSULTATION', :date_soin, '08:00:00', :date_facture, "
                    "CURRENT_DATE, 'TELETRANSMISSION', 'VIREMENT', :nb_lignes, "
                    ":montant_total, :montant_eligible, 0, :reste_a_charge, 'EN_COURS'"
                    ") ON CONFLICT (facture_id) DO NOTHING"
                ),
                {
                    "facture_id": facture_id,
                    "numero_facture": body.numero_facture,
                    "prestataire_id": body.prestataire_id,
                    "assure_id": body.assure_id,
                    "contrat_id": contrat_id,
                    "ordonnance_id": body.ordonnance_id,
                    "date_soin": body.date_soin,
                    "date_facture": body.date_emission,
                    "nb_lignes": len(body.lignes),
                    "montant_total": body.montant_total,
                    "montant_eligible": body.montant_total - body.part_assure,
                    "reste_a_charge": body.part_assure,
                },
            )

            # 3. Insertion lignes_facture
            for idx, ligne in enumerate(body.lignes, start=1):
                ligne_id = f"{facture_id}-L{idx:02d}"
                conn.execute(
                    text(
                        "INSERT INTO lignes_facture ("
                        "ligne_id, facture_id, num_ligne, code, type_ligne, libelle, "
                        "quantite, prix_unitaire, montant_total"
                        ") VALUES ("
                        ":ligne_id, :facture_id, :num_ligne, :code, :type_ligne, :libelle, "
                        ":quantite, :prix_unitaire, :montant_total"
                        ") ON CONFLICT (ligne_id) DO NOTHING"
                    ),
                    {
                        "ligne_id": ligne_id,
                        "facture_id": facture_id,
                        "num_ligne": ligne.num_ligne,
                        "code": ligne.code,
                        "type_ligne": ligne.type_ligne.value if hasattr(ligne.type_ligne, "value") else str(ligne.type_ligne),
                        "libelle": ligne.code,
                        "quantite": ligne.quantite,
                        "prix_unitaire": ligne.prix_unitaire,
                        "montant_total": ligne.montant_total,
                    },
                )

            # 4. Insertion prediction
            if score_fraude is not None:
                pred_id = conn.execute(
                    text(
                        "INSERT INTO predictions ("
                        "facture_id, score_fraude, est_anomalie, seuil_applique, version_modele, date_prediction"
                        ") VALUES ("
                        ":facture_id, :score_fraude, :est_anomalie, :seuil_applique, :version_modele, :date_prediction"
                        ") RETURNING id"
                    ),
                    {
                        "facture_id": facture_id,
                        "score_fraude": score_fraude,
                        "est_anomalie": est_anomalie,
                        "seuil_applique": seuil_applique,
                        "version_modele": version_modele,
                        "date_prediction": date_prediction,
                    },
                ).scalar()

                # 5. Insertion explications_shap (JSONB)
                if pred_id and top_facteurs:
                    conn.execute(
                        text(
                            "INSERT INTO explications_shap ("
                            "prediction_id, top_features, date_generation"
                            ") VALUES ("
                            ":prediction_id, :top_features, :date_generation"
                            ") ON CONFLICT (prediction_id) DO NOTHING"
                        ),
                        {
                            "prediction_id": pred_id,
                            "top_features": json.dumps(top_facteurs),
                            "date_generation": date_prediction,
                        },
                    )
        return True
    except Exception as exc:
        logger.warning("Base indisponible pour l'enregistrement (repli mémoire actif) : %s", exc)
        return False


def _get_or_404(facture_id: str) -> ClaimDetail:
    """Retourne la facture soumise ou mock, ou lève un 404 si l'id est inconnu."""
    if facture_id in _SUBMITTED_CLAIMS:
        return _SUBMITTED_CLAIMS[facture_id]
    if facture_id not in _KNOWN_CLAIM_IDS:
        raise HTTPException(status_code=404, detail=f"Facture {facture_id} introuvable.")
    return _MOCK_CLAIM.model_copy(update={"facture_id": facture_id})


@router.get("", response_model=ClaimsListResponse)
def list_claims(
    current_user: Annotated[UserInfo, Depends(get_optional_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    statut: StatutFacture | None = None,
    date_debut: date | None = None,
    date_fin: date | None = None,
    fraud_alert_only: bool = False,
) -> ClaimsListResponse:
    """Liste paginée des factures. Un assuré ne voit que ses propres dossiers."""
    # Si c'est un assuré et que la facture mock ne lui appartient pas : liste vide
    if current_user.role == Role.ASSURE and current_user.assure_id != _MOCK_CLAIM.assure_id:
        return ClaimsListResponse(total=0, page=page, page_size=page_size, items=[])

    item = ClaimSummary(
        facture_id=_MOCK_CLAIM.facture_id,
        numero_facture=_MOCK_CLAIM.numero_facture,
        assure_id=_MOCK_CLAIM.assure_id,
        prestataire_id=_MOCK_CLAIM.prestataire_id,
        date_soin=_MOCK_CLAIM.date_soin,
        date_emission=_MOCK_CLAIM.date_emission,
        montant_total=_MOCK_CLAIM.montant_total,
        part_assure=_MOCK_CLAIM.part_assure,
        montant_demande=_MOCK_CLAIM.montant_demande,
        statut=_MOCK_CLAIM.statut,
        score_fraude=0.87,
        est_anomalie=True,
    )
    return ClaimsListResponse(total=1, page=page, page_size=page_size, items=[item])


@router.get(
    "/{facture_id}",
    response_model=ClaimDetail,
    responses={
        403: {"description": "Accès refusé pour ce dossier."},
        404: {"description": "Facture inexistante."},
    },
)
def get_claim(
    facture_id: str,
    current_user: Annotated[UserInfo, Depends(get_optional_user)],
) -> ClaimDetail:
    """Détail d'une facture. Un assuré ne peut voir que ses propres factures."""
    claim = _get_or_404(facture_id)
    if current_user.role == Role.ASSURE and current_user.assure_id != claim.assure_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : vous n'êtes pas le titulaire de cette facture.",
        )
    return claim

@router.post("", response_model=ClaimCreateResponse, status_code=201)
def create_claim(
    body: ClaimCreateRequest,
    current_user: Annotated[UserInfo, Depends(get_optional_user)] = None,
) -> ClaimCreateResponse:
    """Télétransmission d'une nouvelle facture, inférence ML réelle et persistance atomique."""
    facture_id = f"FAC-{len(_SUBMITTED_CLAIMS) + 84700:08d}"

    # Inférence réelle par le modèle champion
    try:
        inference = predire_facture_en_ligne(
            body.model_dump(),
            [ligne.model_dump() for ligne in body.lignes],
        )
        score_fraude = inference["score_fraude"]
        seuil_applique = inference["seuil_applique"]
        est_anomalie = inference["est_anomalie"]
        version_modele = inference["version_modele"]
        top_facteurs = inference["top_facteurs"]
        recommandation = inference["recommandation"]
        date_prediction = inference["date_prediction"]
        message = (
            "Facture enregistrée. Alerte d'anomalie transmise au gestionnaire."
            if est_anomalie
            else "Facture enregistrée avec succès."
        )
    except ModeleIndisponible as exc:
        logger.error("Modèle indisponible lors de la soumission de %s : %s", facture_id, exc)
        score_fraude = None
        seuil_applique = fraud_score_threshold()
        est_anomalie = False
        version_modele = "indisponible"
        top_facteurs = []
        recommandation = "Modèle indisponible : contrôle manuel requis."
        date_prediction = datetime.now(UTC)
        message = "Facture enregistrée. Analyse de fraude en attente (modèle indisponible)."

    # Enregistrement en mémoire pour relecture immédiate
    _SUBMITTED_CLAIMS[facture_id] = ClaimDetail(
        facture_id=facture_id,
        numero_facture=body.numero_facture,
        assure_id=body.assure_id,
        prestataire_id=body.prestataire_id,
        nom_etablissement="Établissement de soins",
        ordonnance_id=body.ordonnance_id,
        date_soin=body.date_soin,
        date_emission=body.date_emission,
        montant_total=body.montant_total,
        part_assure=body.part_assure,
        montant_demande=body.montant_total - body.part_assure,
        statut=StatutFacture.EN_COURS,
        lignes=body.lignes,
    )

    _PERSISTED_PREDICTIONS[facture_id] = {
        "prediction": {
            "score_fraude": score_fraude,
            "seuil_applique": seuil_applique,
            "est_anomalie": est_anomalie,
            "version_modele": version_modele,
            "date_prediction": date_prediction,
        },
        "explicabilite": {
            "top_facteurs": top_facteurs,
            "recommandation": recommandation,
        },
    }

    # Persistance en base PostgreSQL si disponible
    _persister_facture_db(
        facture_id=facture_id,
        body=body,
        score_fraude=score_fraude,
        est_anomalie=est_anomalie,
        seuil_applique=seuil_applique,
        version_modele=version_modele,
        top_facteurs=top_facteurs,
        date_prediction=date_prediction,
    )

    return ClaimCreateResponse(
        facture_id=facture_id,
        statut=StatutFacture.EN_COURS,
        score_fraude=score_fraude,
        est_anomalie=est_anomalie,
        seuil_applique=seuil_applique,
        message=message,
    )


def _predire(facture_id: str, budget: float | None = None) -> dict | None:
    """Appelle le service ML ; renvoie None si l'environnement est incomplet."""
    try:
        from predicare.ml.service import FactureInconnue, ModeleIndisponible, predire_facture
    except Exception:
        return None
    try:
        return predire_facture(facture_id, budget=budget)
    except (FactureInconnue, ModeleIndisponible, FileNotFoundError, KeyError, ValueError):
        return None


def _prediction_repli(facture_id: str) -> PredictionResponse:
    """Repli documenté : même contrat, valeurs neutres (modèle non chargé)."""
    return PredictionResponse(
        facture_id=facture_id,
        prediction=PredictionInfo(
            score_fraude=0.0,
            seuil_applique=0.80,
            est_anomalie=False,
            version_modele="indisponible",
            date_prediction=_NOW,
        ),
        explicabilite=ExplicabiliteInfo(
            top_facteurs=[
                ShapFactor(
                    feature="modele_indisponible",
                    valeur=0.0,
                    impact_shap=0.0,
                    description="Modèle non chargé dans cet environnement.",
                )
            ],
            recommandation="Modèle indisponible : contrôle manuel requis.",
        ),
    )


@router.get(
    "/{facture_id}/prediction",
    response_model=PredictionResponse,
    responses={404: {"description": "Facture inexistante."}},
)
def get_prediction(
    facture_id: str,
    budget: Annotated[float | None, Query(gt=0, lt=1, description="Part cible contrôlée")] = None,
) -> PredictionResponse:
    """Score de fraude réel et explicabilité SHAP (modèle en production avec repli)."""
    _get_or_404(facture_id)
    resultat = _predire(facture_id, budget=budget)
    if resultat is None:
        return _prediction_repli(facture_id)

    top_facteurs = [
        ShapFactor(
            feature=f["feature"],
            valeur=f["valeur"] if isinstance(f["valeur"], (int, float)) else 0.0,
            impact_shap=float(f["impact_shap"]),
            description=f["description"],
        )
        for f in resultat["explicabilite"]["top_facteurs"]
    ]

    return PredictionResponse(
        facture_id=facture_id,
        prediction=PredictionInfo(
            score_fraude=resultat["prediction"]["score_fraude"],
            seuil_applique=resultat["prediction"]["seuil_applique"],
            est_anomalie=resultat["prediction"]["est_anomalie"],
            version_modele=resultat["prediction"]["version_modele"],
            date_prediction=datetime.now(UTC),
        ),
        explicabilite=ExplicabiliteInfo(
            top_facteurs=top_facteurs,
            recommandation=resultat["explicabilite"]["recommandation"],
        ),
    )


@router.post(
    "/{facture_id}/decision",
    response_model=DecisionResponse,
    responses={404: {"description": "Facture inexistante."}},
)
def post_decision(facture_id: str, body: DecisionRequest) -> DecisionResponse:
    """Arbitrage gestionnaire (mock)."""
    _get_or_404(facture_id)
    statut_map = {
        DecisionValeur.VALIDE: StatutFacture.PAYEE,
        DecisionValeur.REJETE: StatutFacture.REJETEE,
        DecisionValeur.INVESTIGATION: StatutFacture.EN_COURS,
    }
    return DecisionResponse(
        facture_id=facture_id,
        statut=statut_map[body.decision],
        decision=body.decision,
        gestionnaire_id="USR-0012",
        date_decision=_NOW,
        message="Décision enregistrée avec succès.",
    )
