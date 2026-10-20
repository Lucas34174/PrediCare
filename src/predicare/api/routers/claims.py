"""Router factures – /claims."""

import json
import logging
import math
import uuid
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
            contrat_id = (
                conn.execute(
                    text("SELECT contrat_id FROM assures WHERE assure_id = :aid"),
                    {"aid": body.assure_id},
                ).scalar()
                or "CTR-2025-001"
            )

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
                        "quantite, prix_unitaire, montant"
                        ") VALUES ("
                        ":ligne_id, :facture_id, :num_ligne, :code, :type_ligne, :libelle, "
                        ":quantite, :prix_unitaire, :montant"
                        ") ON CONFLICT (ligne_id) DO NOTHING"
                    ),
                    {
                        "ligne_id": ligne_id,
                        "facture_id": facture_id,
                        "num_ligne": ligne.num_ligne,
                        "code": ligne.code,
                        "type_ligne": ligne.type_ligne.value
                        if hasattr(ligne.type_ligne, "value")
                        else str(ligne.type_ligne),
                        "libelle": ligne.code,
                        "quantite": ligne.quantite,
                        "prix_unitaire": ligne.prix_unitaire,
                        "montant": ligne.montant_total,
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
                            "top_features": json.dumps(
                                [
                                    {
                                        k: (None if isinstance(v, float) and math.isnan(v) else v)
                                        for k, v in f.items()
                                    }
                                    for f in top_facteurs
                                ]
                            ),
                            "date_generation": date_prediction,
                        },
                    )
        return True
    except Exception as exc:
        logger.warning("Base indisponible pour l'enregistrement (repli mémoire actif) : %s", exc)
        return False


def _facture_existe(facture_id: str) -> bool:
    """Vérifie si la facture existe en mémoire ou en base PostgreSQL."""
    if facture_id in _SUBMITTED_CLAIMS or facture_id in _KNOWN_CLAIM_IDS:
        return True
    try:
        engine = _db_engine()
        if engine is not None:
            with engine.connect() as conn:
                res = conn.execute(
                    text("SELECT 1 FROM factures WHERE facture_id = :id LIMIT 1"),
                    {"id": facture_id},
                ).first()
                if res is not None:
                    return True
    except Exception:
        pass
    return False


# NOUVELLE fonction — lit une facture + lignes depuis PostgreSQL
def _get_claim_db(facture_id: str) -> ClaimDetail | None:
    try:
        engine = _db_engine()
        if engine is None:
            return None
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text("""
                SELECT f.facture_id, f.numero_facture, f.assure_id, f.prestataire_id,
                       pr.nom AS nom_etablissement, f.ordonnance_id,
                       f.date_soin, f.date_facture AS date_emission,
                       f.montant_total, f.reste_a_charge AS part_assure,
                       (f.montant_total - f.reste_a_charge) AS montant_demande,
                       f.statut, f.motif_rejet, f.montant_pris_en_charge
                FROM factures f
                LEFT JOIN prestataires pr ON pr.prestataire_id = f.prestataire_id
                WHERE f.facture_id = :fid
            """),
                    {"fid": facture_id},
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            lignes = (
                conn.execute(
                    text("""
                SELECT num_ligne, code, type_ligne, quantite, prix_unitaire,
                       montant AS montant_total
                FROM lignes_facture WHERE facture_id = :fid ORDER BY num_ligne
            """),
                    {"fid": facture_id},
                )
                .mappings()
                .all()
            )
            return ClaimDetail(
                facture_id=row["facture_id"],
                numero_facture=row["numero_facture"],
                assure_id=row["assure_id"],
                prestataire_id=row["prestataire_id"],
                nom_etablissement=row["nom_etablissement"],
                ordonnance_id=row["ordonnance_id"],
                date_soin=row["date_soin"],
                date_emission=row["date_emission"],
                montant_total=row["montant_total"],
                part_assure=row["part_assure"],
                montant_demande=row["montant_demande"],
                statut=StatutFacture(row["statut"]),
                motif_rejet=row["motif_rejet"],
                montant_pris_en_charge=row["montant_pris_en_charge"],
                lignes=[
                    LigneFacture(
                        num_ligne=l["num_ligne"],
                        code=l["code"],
                        type_ligne=TypeLigne(l["type_ligne"]),
                        quantite=l["quantite"],
                        prix_unitaire=l["prix_unitaire"],
                        montant_total=l["montant_total"],
                    )
                    for l in lignes
                ],
            )
    except Exception as exc:
        logger.warning("DB indisponible pour get_claim(%s) : %s", facture_id, exc)
        return None


# _get_or_404 mise à jour (mémoire → DB → mock)
def _get_or_404(facture_id: str) -> ClaimDetail:
    if facture_id in _SUBMITTED_CLAIMS:
        return _SUBMITTED_CLAIMS[facture_id]
    claim_db = _get_claim_db(facture_id)
    if claim_db is not None:
        return claim_db
    if facture_id not in _KNOWN_CLAIM_IDS:
        raise HTTPException(status_code=404, detail=f"Facture {facture_id} introuvable.")
    return _MOCK_CLAIM.model_copy(update={"facture_id": facture_id})


def _lire_prediction_db(facture_id: str) -> PredictionResponse | None:
    """Tente de lire la dernière prédiction et son SHAP depuis PostgreSQL."""
    try:
        engine = _db_engine()
        if engine is None:
            return None
        with engine.connect() as conn:
            query = text(
                "SELECT p.id, p.score_fraude, p.est_anomalie, p.seuil_applique, "
                "p.version_modele, p.date_prediction, s.top_features "
                "FROM predictions p "
                "LEFT JOIN explications_shap s ON s.prediction_id = p.id "
                "WHERE p.facture_id = :facture_id "
                "ORDER BY p.date_prediction DESC LIMIT 1"
            )
            row = conn.execute(query, {"facture_id": facture_id}).mappings().first()
            if not row or row["score_fraude"] is None:
                return None

            top_features_raw = row["top_features"]
            if isinstance(top_features_raw, str):
                try:
                    top_facteurs_data = json.loads(top_features_raw)
                except Exception:
                    top_facteurs_data = []
            elif isinstance(top_features_raw, list):
                top_facteurs_data = top_features_raw
            else:
                top_facteurs_data = []

            top_facteurs = [
                ShapFactor(
                    feature=f.get("feature", ""),
                    valeur=float(f.get("valeur", 0.0))
                    if isinstance(f.get("valeur"), (int, float))
                    else 0.0,
                    impact_shap=float(f.get("impact_shap", 0.0)),
                    description=f.get("description", ""),
                )
                for f in top_facteurs_data
            ]
            recommandation = (
                "Contrôle requis : anomalie détectée."
                if row["est_anomalie"]
                else "Facture conforme : aucun risque significatif détecté."
            )

            return PredictionResponse(
                facture_id=facture_id,
                prediction=PredictionInfo(
                    score_fraude=float(row["score_fraude"]),
                    seuil_applique=float(row["seuil_applique"])
                    if row["seuil_applique"] is not None
                    else fraud_score_threshold(),
                    est_anomalie=bool(row["est_anomalie"]),
                    version_modele=str(row["version_modele"] or "inconnue"),
                    date_prediction=row["date_prediction"],
                ),
                explicabilite=ExplicabiliteInfo(
                    top_facteurs=top_facteurs,
                    recommandation=recommandation,
                ),
            )
    except Exception as exc:
        logger.warning("Erreur lors de la lecture DB de la prédiction %s : %s", facture_id, exc)
        return None


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

    try:
        engine = _db_engine()

        if engine is not None:
            with engine.connect() as conn:
                conditions = []
                params = {}

                # Restriction d'accès pour les assurés
                if current_user.role == Role.ASSURE:
                    if not current_user.assure_id:
                        return ClaimsListResponse(
                            total=0,
                            page=page,
                            page_size=page_size,
                            items=[],
                        )

                    conditions.append("f.assure_id = :assure_id")
                    params["assure_id"] = current_user.assure_id

                # Filtre par statut
                if statut:
                    conditions.append("f.statut = :statut")
                    params["statut"] = statut.value

                # Filtre par date de début
                if date_debut:
                    conditions.append("f.date_soin >= :date_debut")
                    params["date_debut"] = date_debut

                # Filtre par date de fin
                if date_fin:
                    conditions.append("f.date_soin <= :date_fin")
                    params["date_fin"] = date_fin

                # Filtre sur les alertes de fraude
                if fraud_alert_only:
                    conditions.append("p.est_anomalie = true")

                where = "WHERE " + " AND ".join(conditions) if conditions else ""

                # Dernière prédiction de chaque facture
                join = """
                    LEFT JOIN LATERAL (
                        SELECT score_fraude, est_anomalie
                        FROM predictions
                        WHERE facture_id = f.facture_id
                        ORDER BY date_prediction DESC
                        LIMIT 1
                    ) p ON true
                """

                # Nombre total de résultats correspondant aux filtres
                total = (
                    conn.execute(
                        text(
                            f"""
                        SELECT COUNT(*)
                        FROM factures f
                        {join}
                        {where}
                        """
                        ),
                        params,
                    ).scalar()
                    or 0
                )

                # Paramètres de pagination
                params["lim"] = page_size
                params["off"] = (page - 1) * page_size

                # Récupération de la page demandée
                rows = (
                    conn.execute(
                        text(
                            f"""
                        SELECT
                            f.facture_id,
                            f.numero_facture,
                            f.assure_id,
                            f.prestataire_id,
                            f.date_soin,
                            f.date_facture AS date_emission,
                            f.montant_total,
                            f.reste_a_charge AS part_assure,
                            (
                                f.montant_total - f.reste_a_charge
                            ) AS montant_demande,
                            f.statut,
                            p.score_fraude,
                            p.est_anomalie
                        FROM factures f
                        {join}
                        {where}
                        ORDER BY
                            f.date_soin DESC,
                            f.facture_id DESC
                        LIMIT :lim OFFSET :off
                        """
                        ),
                        params,
                    )
                    .mappings()
                    .all()
                )

                return ClaimsListResponse(
                    total=total,
                    page=page,
                    page_size=page_size,
                    items=[
                        ClaimSummary(
                            facture_id=r["facture_id"],
                            numero_facture=r["numero_facture"],
                            assure_id=r["assure_id"],
                            prestataire_id=r["prestataire_id"],
                            date_soin=r["date_soin"],
                            date_emission=r["date_emission"],
                            montant_total=r["montant_total"],
                            part_assure=r["part_assure"],
                            montant_demande=r["montant_demande"],
                            statut=StatutFacture(r["statut"]),
                            score_fraude=(
                                float(r["score_fraude"]) if r["score_fraude"] is not None else None
                            ),
                            est_anomalie=(
                                bool(r["est_anomalie"]) if r["est_anomalie"] is not None else None
                            ),
                        )
                        for r in rows
                    ],
                )

    except Exception as exc:
        logger.warning(
            "DB indisponible pour list_claims (repli mock) : %s",
            exc,
        )

    # Repli mock existant
    if current_user.role == Role.ASSURE and current_user.assure_id != _MOCK_CLAIM.assure_id:
        return ClaimsListResponse(
            total=0,
            page=page,
            page_size=page_size,
            items=[],
        )

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

    # Application des filtres au mock
    if statut is not None and item.statut != statut:
        return ClaimsListResponse(
            total=0,
            page=page,
            page_size=page_size,
            items=[],
        )

    if date_debut is not None and item.date_soin < date_debut:
        return ClaimsListResponse(
            total=0,
            page=page,
            page_size=page_size,
            items=[],
        )

    if date_fin is not None and item.date_soin > date_fin:
        return ClaimsListResponse(
            total=0,
            page=page,
            page_size=page_size,
            items=[],
        )

    if fraud_alert_only and not item.est_anomalie:
        return ClaimsListResponse(
            total=0,
            page=page,
            page_size=page_size,
            items=[],
        )

    # Pagination du mock
    if page > 1:
        return ClaimsListResponse(
            total=1,
            page=page,
            page_size=page_size,
            items=[],
        )

    return ClaimsListResponse(
        total=1,
        page=page,
        page_size=page_size,
        items=[item],
    )


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
    facture_id = f"FAC-N{uuid.uuid4().hex[:7].upper()}"

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
        score_fraude = 0.0
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
    responses={
        401: {"description": "Token manquant ou expiré."},
        403: {"description": "Accès réservé aux gestionnaires et administrateurs."},
        404: {"description": "Facture inexistante ou aucune prédiction disponible."},
    },
)
def get_prediction(
    facture_id: str,
    current_user: Annotated[UserInfo, Depends(get_optional_user)],
    budget: Annotated[float | None, Query(gt=0, lt=1, description="Part cible contrôlée")] = None,
) -> PredictionResponse:
    """Score de fraude réel et explicabilité SHAP (réservé aux gestionnaires et administrateurs)."""
    # 1. Contrôle RBAC
    if current_user.role not in {Role.GESTIONNAIRE, Role.ADMINISTRATEUR}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Accès refusé pour le rôle '{current_user.role}'. Réservé aux gestionnaires et administrateurs.",
        )

    # 2. Vérification d'existence de la facture
    if not _facture_existe(facture_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facture {facture_id} introuvable.",
        )

    # 3. Lecture en base PostgreSQL si disponible
    pred_db = _lire_prediction_db(facture_id)
    if pred_db is not None:
        return pred_db

    # 4. Lecture dans le cache mémoire de soumission
    if facture_id in _PERSISTED_PREDICTIONS:
        persisted = _PERSISTED_PREDICTIONS[facture_id]
        pred_data = persisted.get("prediction", {})
        if pred_data.get("score_fraude") is not None:
            expl_data = persisted.get("explicabilite", {})
            top_facteurs = [
                ShapFactor(
                    feature=f["feature"],
                    valeur=f["valeur"] if isinstance(f["valeur"], (int, float, str)) else 0.0,
                    impact_shap=float(f["impact_shap"]),
                    description=f["description"],
                )
                for f in expl_data.get("top_facteurs", [])
            ]
            return PredictionResponse(
                facture_id=facture_id,
                prediction=PredictionInfo(
                    score_fraude=float(pred_data["score_fraude"]),
                    seuil_applique=float(pred_data["seuil_applique"]),
                    est_anomalie=bool(pred_data["est_anomalie"]),
                    version_modele=str(pred_data["version_modele"]),
                    date_prediction=pred_data["date_prediction"],
                ),
                explicabilite=ExplicabiliteInfo(
                    top_facteurs=top_facteurs,
                    recommandation=str(expl_data.get("recommandation", "")),
                ),
            )

    # 5. Si facture de référence connue (ex: FAC-00005637), calcul dynamique
    if facture_id in _KNOWN_CLAIM_IDS:
        resultat = _predire(facture_id, budget=budget)
        if resultat is None:
            return _prediction_repli(facture_id)

        top_facteurs = [
            ShapFactor(
                feature=f["feature"],
                valeur=f["valeur"] if isinstance(f["valeur"], (int, float, str)) else 0.0,
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

    # 6. La facture existe mais aucune prédiction n'est disponible
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Aucune prédiction disponible pour la facture {facture_id}.",
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
