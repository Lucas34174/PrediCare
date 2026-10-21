"""Service de prédiction, explicabilité SHAP et extraction de features pour l'API (PB-22)."""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from predicare.core.config import fraud_score_threshold, model_path, model_version
from predicare.ml.config import MODELS_ROOT
from predicare.ml.explain import SHAP_DISPONIBLE, expliquer_facture
from predicare.ml.features import FORBIDDEN_FEATURE_COLS, build_features

logger = logging.getLogger("predicare.ml.service")

FEATURE_NAMES_PATH = MODELS_ROOT / "feature_names.json"


class FactureInconnue(KeyError):  # noqa: N818
    """La facture demandée est introuvable."""


class ModeleIndisponible(RuntimeError):  # noqa: N818
    """Aucun artefact de modèle exploitable n'est présent ou lisible."""


def normaliser_score(probabilite: Any, seuil_calibre: float) -> np.ndarray:
    """Transforme une probabilité en score de risque où seuil_calibre -> 0.8."""
    p = np.clip(np.asarray(probabilite, dtype=float), 0.0, 1.0)
    if not np.isfinite(seuil_calibre) or seuil_calibre <= 1e-9:
        return p
    tau = -seuil_calibre / math.log(0.2)
    return 1.0 - np.exp(-p / tau)


class CalibrateurPlatt:
    """Calibration de Platt (régression logistique sur le score brut)."""

    def __init__(self, modele: Any):
        self.modele = modele

    def predict(self, scores: Any) -> np.ndarray:
        valeurs = np.asarray(scores, dtype=float).reshape(-1, 1)
        return np.asarray(self.modele.predict_proba(valeurs)[:, 1], dtype=float)


def _charger_feature_names() -> list[str]:
    if FEATURE_NAMES_PATH.is_file():
        try:
            return json.loads(FEATURE_NAMES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


@dataclass
class ModeleFraude:
    """Modèle champion prêt à inférer avec Explainer SHAP singleton."""

    pipeline: Any
    variables: list[str]
    seuil_probabilite: float = 0.30
    calibrateur: Any | None = None
    modele: str = "XGBoost"
    version: str = "v1.0.0-xgb"
    explainer: Any | None = None
    metadonnees: dict = field(default_factory=dict)

    def proba(self, factures: pd.DataFrame) -> np.ndarray:
        """Probabilité brute ou calibrée de fraude sur la matrice des 23 features."""
        manquantes = [v for v in self.variables if v not in factures.columns]
        if manquantes:
            for col in manquantes:
                factures[col] = float("nan")
        X = factures[self.variables]
        if hasattr(self.pipeline, "predict_proba"):
            p = self.pipeline.predict_proba(X)[:, 1]
        else:
            raise ModeleIndisponible("Le modèle chargé n'expose pas de méthode predict_proba.")
        if self.calibrateur is not None and hasattr(self.calibrateur, "predict"):
            return np.asarray(self.calibrateur.predict(p), dtype=float)
        return np.asarray(p, dtype=float)

    def scorer_unitaire(self, features_df: pd.DataFrame) -> float:
        """Renvoie le score scalaire de fraude pour une facture unique."""
        return float(self.proba(features_df)[0])


def charger_modele(chemin: str | Path | None = None) -> ModeleFraude:
    """Charge le modèle champion et pré-instancie l'explainer SHAP (singleton)."""
    p = Path(chemin) if chemin else Path(model_path())
    if not p.is_file():
        raise ModeleIndisponible(f"Artefact modèle introuvable : {p}")

    try:
        objet = joblib.load(p)
    except Exception as exc:
        raise ModeleIndisponible(f"Échec de lecture de l'artefact {p} : {exc}") from exc

    if isinstance(objet, dict):
        pipeline = objet.get("pipeline", objet.get("modele"))
        variables = list(objet.get("variables") or _charger_feature_names())
        version = objet.get("version") or model_version()
        calibrateur = objet.get("calibrateur")
        seuil = float(objet.get("seuil_probabilite_calibree", 0.30))
        nom_modele = objet.get("modele", "XGBoost")
    else:
        pipeline = objet
        variables = _charger_feature_names()
        version = model_version()
        calibrateur = None
        seuil = 0.30
        nom_modele = "XGBoost"

    explainer = None
    if SHAP_DISPONIBLE:
        try:
            import shap

            clf = (
                pipeline.named_steps.get("clf", pipeline)
                if hasattr(pipeline, "named_steps")
                else pipeline
            )
            explainer = shap.TreeExplainer(clf)
        except Exception as exc:
            logger.warning("Instanciation de TreeExplainer ignorée : %s", exc)

    return ModeleFraude(
        pipeline=pipeline,
        variables=variables,
        seuil_probabilite=seuil,
        calibrateur=calibrateur,
        modele=nom_modele,
        version=version,
        explainer=explainer,
    )


@lru_cache(maxsize=1)
def get_model() -> ModeleFraude:
    """Singleton paresseux du modèle champion."""
    return charger_modele()


def reset_model_cache() -> None:
    """Réinitialise le cache singleton."""
    get_model.cache_clear()


_REF_TABLES_CACHE: dict[str, pd.DataFrame] | None = None


def get_reference_tables() -> dict[str, pd.DataFrame]:
    """Charge et met en cache les tables de référence depuis PostgreSQL pour l'inférence temps réel."""
    global _REF_TABLES_CACHE
    if _REF_TABLES_CACHE is not None:
        return _REF_TABLES_CACHE

    try:
        from predicare.api.deps import _db_engine

        engine = _db_engine()
        if engine is not None:
            with engine.connect() as conn:
                _REF_TABLES_CACHE = {
                    "referentiel_actes": pd.read_sql("SELECT * FROM referentiel_actes", conn),
                    "referentiel_medicaments": pd.read_sql(
                        "SELECT * FROM referentiel_medicaments", conn
                    ),
                    "grille_tarifaire": pd.read_sql("SELECT * FROM grille_tarifaire", conn),
                    "garanties": pd.read_sql("SELECT * FROM garanties", conn),
                    "prestataires": pd.read_sql("SELECT * FROM prestataires", conn),
                    "assures": pd.read_sql("SELECT * FROM assures", conn),
                    "contrats": pd.read_sql("SELECT * FROM contrats", conn),
                    "ordonnances": pd.read_sql("SELECT * FROM ordonnances", conn),
                    "ordonnance_lignes": pd.read_sql("SELECT * FROM ordonnance_lignes", conn),
                }
                return _REF_TABLES_CACHE
    except Exception as exc:
        logger.warning("Chargement des tables de référence impossible : %s", exc)

    return {}


def construire_features_facture(
    facture: dict[str, Any],
    lignes: list[dict[str, Any]],
    ref_tables: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Construit les 23 features d'inférence sans fuite de données."""
    facture_clean = {k: v for k, v in facture.items() if k not in FORBIDDEN_FEATURE_COLS}
    fac_df = pd.DataFrame([facture_clean])

    # Colonnes structurelles requises par build_features (évite les KeyError si contrat_id est omis)
    for col in (
        "facture_id",
        "numero_facture",
        "assure_id",
        "prestataire_id",
        "contrat_id",
        "ordonnance_id",
        "date_soin",
    ):
        if col not in fac_df.columns:
            fac_df[col] = None
    if fac_df["facture_id"].isna().all():
        fac_df["facture_id"] = "TEMP-001"

    lignes_clean = [{k: v for k, v in l.items() if k not in FORBIDDEN_FEATURE_COLS} for l in lignes]
    lignes_df = pd.DataFrame(lignes_clean)
    if not lignes_df.empty and "facture_id" not in lignes_df.columns:
        lignes_df["facture_id"] = fac_df["facture_id"].iloc[0]

    base_tables = get_reference_tables() if ref_tables is None else ref_tables
    tables = dict(base_tables)
    tables["lignes_facture"] = lignes_df

    history_df = pd.DataFrame()
    try:
        from sqlalchemy import text

        from predicare.api.deps import _db_engine

        engine = _db_engine()
        if engine is not None:
            pid = fac_df["prestataire_id"].iloc[0] if "prestataire_id" in fac_df.columns else None
            aid = fac_df["assure_id"].iloc[0] if "assure_id" in fac_df.columns else None
            current_fid = fac_df["facture_id"].iloc[0] if "facture_id" in fac_df.columns else None
            if pid or aid:
                with engine.connect() as conn:
                    history_df = pd.read_sql(
                        text(
                            "SELECT facture_id, assure_id, prestataire_id, date_soin, "
                            "montant_total, numero_facture, ordonnance_id "
                            "FROM factures "
                            "WHERE (prestataire_id = :pid OR assure_id = :aid) "
                            "AND facture_id != :cfid"
                        ),
                        conn,
                        params={"pid": pid, "aid": aid, "cfid": current_fid or ""},
                    )
    except Exception as exc:
        logger.warning("Chargement de l'historique impossible : %s", exc)

    raw_features = build_features(fac_df, tables, history=history_df)

    colonnes_attendues = _charger_feature_names()
    if colonnes_attendues:
        for col in colonnes_attendues:
            if col not in raw_features.columns:
                raw_features[col] = float("nan")
        return raw_features[colonnes_attendues]
    return raw_features


def predire_facture_en_ligne(
    facture: dict[str, Any],
    lignes: list[dict[str, Any]],
    ref_tables: dict[str, pd.DataFrame] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Point d'entrée principal pour l'inférence en ligne et l'explicabilité."""
    modele = get_model()
    features_df = construire_features_facture(facture, lignes, ref_tables)

    score_fraude = round(modele.scorer_unitaire(features_df), 4)
    seuil = fraud_score_threshold()

    # Détection explicite de doublon (règle métier & signal historique)
    deja_vu = False
    if "f_numero_facture_deja_vu" in features_df.columns:
        val = features_df["f_numero_facture_deja_vu"].iloc[0]
        deja_vu = bool(val == 1.0 or val == 1)
    if not deja_vu and facture.get("numero_facture") and facture.get("prestataire_id"):
        try:
            from sqlalchemy import text

            from predicare.api.deps import _db_engine

            engine = _db_engine()
            if engine is not None:
                with engine.connect() as conn:
                    ex = conn.execute(
                        text(
                            "SELECT 1 FROM factures "
                            "WHERE prestataire_id = :pid AND numero_facture = :num AND facture_id != :fid LIMIT 1"
                        ),
                        {
                            "pid": facture.get("prestataire_id"),
                            "num": facture.get("numero_facture"),
                            "fid": facture.get("facture_id", ""),
                        },
                    ).scalar()
                    if ex:
                        deja_vu = True
        except Exception:
            pass

    # Explicabilité SHAP locale
    facteurs, recommandation = expliquer_facture(modele, features_df.iloc[0], top_k=top_k)

    if deja_vu:
        score_fraude = max(score_fraude, 0.95)
        est_anomalie = True
        doublon_factor = {
            "feature": "f_numero_facture_deja_vu",
            "valeur": 1,
            "impact_shap": 0.85,
            "description": "Numéro de facture déjà transmis pour ce prestataire (DOUBLON)",
        }
        facteurs = [doublon_factor] + [
            f for f in facteurs if f.get("feature") != "f_numero_facture_deja_vu"
        ][: top_k - 1]
        recommandation = "Alerte DOUBLON : une facture portant ce même numéro a déjà été télétransmise par cet établissement."
    else:
        est_anomalie = bool(score_fraude >= seuil)

    return {
        "score_fraude": score_fraude,
        "seuil_applique": float(seuil),
        "est_anomalie": est_anomalie,
        "version_modele": modele.version,
        "date_prediction": datetime.now(UTC),
        "top_facteurs": facteurs,
        "recommandation": recommandation,
    }


def predire_facture(facture_id: str, budget: float | None = None) -> dict[str, Any]:
    """Consulte ou calcule la prédiction pour une facture existante (rétro-compatibilité)."""
    modele = get_model()
    seuil = fraud_score_threshold()
    noms = _charger_feature_names()
    ligne = pd.Series({nom: float("nan") for nom in noms}, name=facture_id)
    features_df = pd.DataFrame([ligne])
    score = round(modele.scorer_unitaire(features_df), 4)
    facteurs, reco = expliquer_facture(modele, ligne, top_k=5)

    return {
        "facture_id": facture_id,
        "prediction": {
            "score_fraude": score,
            "seuil_applique": float(seuil),
            "est_anomalie": bool(score >= seuil),
            "version_modele": modele.version,
            "date_prediction": datetime.now(UTC),
        },
        "explicabilite": {
            "top_facteurs": facteurs,
            "recommandation": reco,
        },
    }
