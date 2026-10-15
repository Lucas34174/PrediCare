"""Router factures – /claims."""

from datetime import UTC, date, datetime

from fastapi import APIRouter

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


@router.get("", response_model=ClaimsListResponse)
def list_claims(
    page: int = 1,
    page_size: int = 20,
    statut: str | None = None,
    fraud_alert_only: bool = False,
) -> ClaimsListResponse:
    """Liste paginée des factures (mock)."""
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


@router.get("/{facture_id}", response_model=ClaimDetail)
def get_claim(facture_id: str) -> ClaimDetail:
    """Détail d'une facture (mock)."""
    return _MOCK_CLAIM


@router.post("", response_model=ClaimCreateResponse, status_code=201)
def create_claim(body: ClaimCreateRequest) -> ClaimCreateResponse:
    """Télétransmission d'une nouvelle facture (mock)."""
    return ClaimCreateResponse(
        facture_id="FAC-00084700",
        statut=StatutFacture.EN_COURS,
        score_fraude=0.88,
        est_anomalie=True,
        seuil_applique=0.80,
        message="Facture enregistrée. Alerte d'anomalie transmise au gestionnaire.",
    )


@router.get("/{facture_id}/prediction", response_model=PredictionResponse)
def get_prediction(facture_id: str) -> PredictionResponse:
    """Score de fraude et explicabilité SHAP (mock)."""
    return PredictionResponse(
        facture_id=facture_id,
        prediction=PredictionInfo(
            score_fraude=0.87,
            seuil_applique=0.80,
            est_anomalie=True,
            version_modele="v1.0.0-xgb",
            date_prediction=_NOW,
        ),
        explicabilite=ExplicabiliteInfo(
            top_facteurs=[
                ShapFactor(
                    feature="ecart_tarif_conventionne",
                    valeur=15000,
                    impact_shap=0.38,
                    description="Tarif facturé supérieur de 50 % au barème de référence",
                ),
                ShapFactor(
                    feature="jour_fermeture_etablissement",
                    valeur=1,
                    impact_shap=0.25,
                    description="Acte réalisé un jour de fermeture hebdomadaire",
                ),
            ],
            recommandation="Contrôle requis : anomalie tarifaire et temporelle détectée.",
        ),
    )


@router.post("/{facture_id}/decision", response_model=DecisionResponse)
def post_decision(facture_id: str, body: DecisionRequest) -> DecisionResponse:
    """Arbitrage gestionnaire (mock)."""
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
