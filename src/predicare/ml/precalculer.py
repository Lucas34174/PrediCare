"""Script pour pré-calculer les scores de fraude sur les factures en attente (MVP)."""

import json
import logging
import math

from sqlalchemy import text

from predicare.api.deps import _db_engine
from predicare.api.routers.claims import _get_claim_db
from predicare.ml.service import predire_facture_en_ligne

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("precalculer_predictions")


def precalculer(limite: int = 50) -> int:
    engine = _db_engine()
    if engine is None:
        logger.error("Connexion base de données indisponible.")
        return 0

    with engine.connect() as conn:
        query = text(
            "SELECT f.facture_id FROM factures f "
            "LEFT JOIN predictions p ON p.facture_id = f.facture_id "
            "WHERE f.statut = 'EN_COURS' AND p.id IS NULL "
            "ORDER BY f.date_soin DESC "
            "LIMIT :limite"
        )
        fids = [r[0] for r in conn.execute(query, {"limite": limite}).fetchall()]

    logger.info("Dossiers cibles trouvés : %d", len(fids))
    succes = 0

    for fid in fids:
        claim = _get_claim_db(fid)
        if not claim:
            continue
        try:
            inf = predire_facture_en_ligne(
                {
                    "facture_id": claim.facture_id,
                    "numero_facture": claim.numero_facture,
                    "assure_id": claim.assure_id,
                    "prestataire_id": claim.prestataire_id,
                    "ordonnance_id": claim.ordonnance_id,
                    "date_soin": claim.date_soin,
                    "date_emission": claim.date_emission,
                    "montant_total": claim.montant_total,
                    "part_assure": claim.part_assure,
                },
                [l.model_dump() for l in claim.lignes],
            )
            clean_top_facteurs = [
                {
                    "feature": f["feature"],
                    "valeur": None
                    if (isinstance(f.get("valeur"), float) and math.isnan(f["valeur"]))
                    else f.get("valeur"),
                    "impact_shap": float(f["impact_shap"]),
                    "description": f["description"],
                }
                for f in inf.get("top_facteurs", [])
            ]
            with engine.begin() as conn:
                pred_row = conn.execute(
                    text(
                        "INSERT INTO predictions "
                        "(facture_id, score_fraude, est_anomalie, seuil_applique, version_modele, date_prediction) "
                        "VALUES (:fid, :score, :anom, :seuil, :ver, :dt) "
                        "RETURNING id"
                    ),
                    {
                        "fid": fid,
                        "score": inf["score_fraude"],
                        "anom": inf["est_anomalie"],
                        "seuil": inf["seuil_applique"],
                        "ver": inf["version_modele"],
                        "dt": inf["date_prediction"],
                    },
                ).first()
                if pred_row and clean_top_facteurs:
                    conn.execute(
                        text(
                            "INSERT INTO explications_shap (prediction_id, top_features, date_generation) "
                            "VALUES (:pid, CAST(:tf AS jsonb), :dt)"
                        ),
                        {
                            "pid": pred_row[0],
                            "tf": json.dumps(clean_top_facteurs),
                            "dt": inf["date_prediction"],
                        },
                    )
            succes += 1
        except Exception as exc:
            logger.warning("Erreur scoring %s : %s", fid, exc)

    logger.info("Scores calculés et enregistrés avec succès : %d / %d", succes, len(fids))
    return succes


if __name__ == "__main__":
    precalculer(limite=50)
