"""Schémas Pydantic de l'API PrediCare TPA.

Contrats d'interface définis dans docs/contrats_interface.md.
Montants toujours en ariary (entiers, jamais de décimales).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

# Énumérations partagées


class StatutFacture(StrEnum):
    """Statuts fermés des factures (§2 contrats)."""

    EN_COURS = "EN_COURS"
    PAYEE = "PAYEE"
    REJETEE = "REJETEE"


class TypeLigne(StrEnum):
    ACTE = "ACTE"
    MEDICAMENT = "MEDICAMENT"


class DecisionValeur(StrEnum):
    VALIDE = "VALIDE"
    REJETE = "REJETE"
    INVESTIGATION = "INVESTIGATION"


class Role(StrEnum):
    ASSURE = "assure"
    PROFESSIONNEL_SANTE = "professionnel_sante"
    GESTIONNAIRE = "gestionnaire"
    ADMINISTRATEUR = "administrateur"


# 3.1 Supervision & Santé


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    detail: str | None = None


# 3.2 Authentification & Profil


class LoginRequest(BaseModel):
    identifier: str = Field(..., examples=["gestionnaire1"])
    password: str = Field(..., min_length=1)


class UserInfo(BaseModel):
    id: str
    identifier: str
    role: Role
    nom_complet: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(3600, description="Durée de validité du token en secondes")
    user: UserInfo


# 3.3 Gestion des Factures & Télétransmissions


class LigneFacture(BaseModel):
    num_ligne: int = Field(..., ge=1)
    code: str
    type_ligne: TypeLigne
    quantite: int = Field(..., ge=1)
    prix_unitaire: int = Field(..., ge=0, description="Montant en ariary")
    montant_total: int = Field(..., ge=0, description="Montant en ariary")

    @field_validator("montant_total")
    @classmethod
    def montant_coherent(cls, v: int, info: ValidationInfo) -> int:
        """Vérifie que montant_total == quantite * prix_unitaire."""
        data = info.data
        if "quantite" in data and "prix_unitaire" in data:
            expected = data["quantite"] * data["prix_unitaire"]
            if v != expected:
                raise ValueError(f"montant_total ({v}) ≠ quantite × prix_unitaire ({expected})")
        return v


class ClaimSummary(BaseModel):
    facture_id: str
    numero_facture: str
    assure_id: str
    prestataire_id: str
    date_soin: date
    date_emission: date
    montant_total: int
    part_assure: int
    montant_demande: int
    statut: StatutFacture
    score_fraude: float | None = Field(None, ge=0.0, le=1.0)
    est_anomalie: bool | None = None


class ClaimsListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ClaimSummary]


class ClaimDetail(BaseModel):
    facture_id: str
    numero_facture: str
    assure_id: str
    prestataire_id: str
    nom_etablissement: str | None = None
    ordonnance_id: str | None = None
    date_soin: date
    date_emission: date
    montant_total: int
    part_assure: int
    montant_demande: int
    statut: StatutFacture
    motif_rejet: str | None = None
    montant_pris_en_charge: int | None = None
    lignes: list[LigneFacture]


class ClaimCreateRequest(BaseModel):
    numero_facture: str
    assure_id: str
    prestataire_id: str
    ordonnance_id: str | None = None
    date_soin: date
    date_emission: date
    montant_total: int = Field(..., ge=0)
    part_assure: int = Field(..., ge=0)
    lignes: list[LigneFacture] = Field(..., min_length=1)


class ClaimCreateResponse(BaseModel):
    facture_id: str
    statut: StatutFacture
    score_fraude: float = Field(..., ge=0.0, le=1.0)
    est_anomalie: bool
    seuil_applique: float
    message: str


# 3.4 Détection de Fraude & Arbitrage Métier


class PredictionInfo(BaseModel):
    score_fraude: float = Field(..., ge=0.0, le=1.0)
    seuil_applique: float
    est_anomalie: bool
    version_modele: str
    date_prediction: datetime


class ShapFactor(BaseModel):
    feature: str
    valeur: float | int | str
    impact_shap: float
    description: str


class ExplicabiliteInfo(BaseModel):
    top_facteurs: list[ShapFactor]
    recommandation: str


class PredictionResponse(BaseModel):
    facture_id: str
    prediction: PredictionInfo
    explicabilite: ExplicabiliteInfo


class DecisionRequest(BaseModel):
    decision: DecisionValeur
    motif: str = Field(..., min_length=1)
    montant_accorde: int = Field(..., ge=0)


class DecisionResponse(BaseModel):
    facture_id: str
    statut: StatutFacture
    decision: DecisionValeur
    gestionnaire_id: str
    date_decision: datetime
    message: str


# 3.5 Tableau de Bord Décisionnel & FinOps


class KpiMetrics(BaseModel):
    total_factures_traitees: int
    montant_total_demande: int
    montant_economise_fraude: int
    taux_detection_fraude: float
    dossiers_en_attente_arbitrage: int


class FraudeDistribution(BaseModel):
    type: str
    count: int


class DashboardKpisResponse(BaseModel):
    periode: str
    kpis: KpiMetrics
    distribution_fraudes: list[FraudeDistribution]


# 3.6 Assistant RAG Sécurisé & Agentique


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: str | None = Field(None, examples=["conv-4a8f9b2"])


class ChatSource(BaseModel):
    document: str
    section: str
    page: int | None = None


class ChatResponse(BaseModel):
    response: str
    sources: list[ChatSource]
    provenance_cache_semantique: bool


# 3.7 Administration, MLOps & Exploitation


class AdminConfig(BaseModel):
    fraud_score_threshold: float = Field(..., ge=0.0, le=1.0)
    n8n_webhook_url: str
    semantic_cache_enabled: bool
    semantic_cache_threshold: float = Field(..., ge=0.0, le=1.0)
    updated_at: datetime | None = None


class AdminConfigUpdateRequest(BaseModel):
    fraud_score_threshold: float | None = Field(None, ge=0.0, le=1.0)
    n8n_webhook_url: str | None = None
    semantic_cache_enabled: bool | None = None
    semantic_cache_threshold: float | None = Field(None, ge=0.0, le=1.0)


class ModelVersion(BaseModel):
    version_id: str
    type: str
    recall_test: float
    precision_test: float
    f1_score: float
    date_entrainement: date
    statut: str


class AdminModelsResponse(BaseModel):
    active_version: str
    available_models: list[ModelVersion]


class ModelActivateResponse(BaseModel):
    message: str
    active_version: str
    switched_at: datetime


class ApiMetrics(BaseModel):
    requests_total: int
    error_rate_5xx: float
    p95_latency_ms: float


class MlDriftInfo(BaseModel):
    metric: str
    psi_score: float
    statut_derive: str
    alerte_derive: bool
    derniere_evaluation: datetime


class AdminMetricsResponse(BaseModel):
    api_metrics: ApiMetrics
    ml_drift_monitoring: MlDriftInfo


class AuditEntry(BaseModel):
    id: int
    type_action: str
    utilisateur_id: str
    role_utilisateur: Role
    ressource_type: str
    ressource_id: str
    details: dict[str, Any]
    ip_source: str
    date_action: datetime


class AdminAuditResponse(BaseModel):
    total: int
    items: list[AuditEntry]
