"""Service de prédiction et scoring du modèle de fraude exposé à l'API (PB-13).

Regroupe :
- La normalisation mathématique du score de risque vers [0, 1].
- La classe :class:`ModeleFraude` et le chargeur :func:`charger_modele`.
- Le service :func:`predire_facture` consommé par le routeur `/claims`.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from predicare.ml.config import DATASET_CM, DEFAULT_THRESHOLD, MODEL_PATH

SEUIL_PRODUIT_DEFAUT = float(os.environ.get("PREDICARE_SEUIL_ALERTE", DEFAULT_THRESHOLD))


class FactureInconnue(KeyError):  # noqa: N818
    """La facture demandée n'est pas dans le magasin de variables."""


class ModeleIndisponible(RuntimeError):  # noqa: N818
    """Aucun artefact de modèle exploitable n'est présent."""


def normaliser_score(probabilite: Any, seuil_calibre: float) -> np.ndarray:
    """Transforme une probabilité en score de risque où ``seuil_calibre`` → 0,8."""
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


@dataclass
class ModeleFraude:
    """Modèle de fraude chargé, prêt à scorer et à alerter."""

    pipeline: Any
    variables: list[str]
    seuil_probabilite: float
    seuil_produit: float = SEUIL_PRODUIT_DEFAUT
    calibrateur: Any | None = None
    modele: str = ""
    version: str = ""
    metadonnees: dict = field(default_factory=dict)

    def seuil_pour_budget(self, budget: float) -> float:
        """Seuil de score de risque normalisé pour un budget d'alertes."""
        seuils = (self.metadonnees or {}).get("seuils_budget_validation") or {}
        if not seuils:
            raise ValueError("Aucun seuil par budget disponible dans l'artefact.")
        cle = min(seuils, key=lambda k: abs(float(k) - float(budget)))
        return float(normaliser_score(float(seuils[cle]), self.seuil_probabilite))

    def proba(self, factures: pd.DataFrame) -> np.ndarray:
        """Probabilité calibrée de fraude."""
        manquantes = [v for v in self.variables if v not in factures.columns]
        if manquantes:
            raise KeyError("Variables manquantes : " + ", ".join(sorted(manquantes)))
        brut = self.pipeline.predict_proba(factures[self.variables])[:, 1]
        if self.calibrateur is not None:
            return np.asarray(self.calibrateur.predict(brut), dtype=float)
        return np.asarray(brut, dtype=float)

    def scorer(self, factures: pd.DataFrame) -> pd.DataFrame:
        """Renvoie ``probabilite`` et ``score_risque``."""
        p = self.proba(factures)
        sortie = pd.DataFrame(
            {
                "probabilite": p,
                "score_risque": normaliser_score(p, self.seuil_probabilite),
            }
        )
        if "facture_id" in factures.columns:
            sortie.insert(0, "facture_id", factures["facture_id"].to_numpy())
        return sortie


def charger_modele(chemin: str | Path | None = None) -> ModeleFraude:
    """Charge le modèle sérialisé."""
    if chemin is None:
        chemin = os.environ.get("PREDICARE_MODELE_PATH", MODEL_PATH)
    chemin = Path(chemin)
    if not chemin.is_file():
        raise FileNotFoundError(f"Artefact modèle introuvable : {chemin}")
    objet = joblib.load(chemin)
    seuil = float(objet.get("seuil_probabilite_calibree", np.nan))
    seuil_produit = float(objet.get("seuil_produit", SEUIL_PRODUIT_DEFAUT))
    if "PREDICARE_SEUIL_ALERTE" in os.environ:
        seuil_produit = float(os.environ["PREDICARE_SEUIL_ALERTE"])
    return ModeleFraude(
        pipeline=objet["pipeline"],
        variables=list(objet["variables"]),
        seuil_probabilite=seuil,
        seuil_produit=seuil_produit,
        calibrateur=objet.get("calibrateur"),
        modele=objet.get("modele", ""),
        version=objet.get("version", ""),
        metadonnees=objet,
    )


@lru_cache(maxsize=1)
def _modele() -> ModeleFraude:
    return charger_modele()


@lru_cache(maxsize=1)
def _magasin() -> pd.DataFrame:
    if not DATASET_CM.is_file():
        raise ModeleIndisponible(f"Magasin de variables absent : {DATASET_CM}")
    return pd.read_csv(DATASET_CM, low_memory=False).set_index("facture_id")


def _nettoyer(valeur: Any) -> Any:
    if valeur is None:
        return "non renseigné"
    if isinstance(valeur, (np.floating, float)) and not np.isfinite(valeur):
        return "non renseigné"
    if isinstance(valeur, (np.integer,)):
        return int(valeur)
    if isinstance(valeur, (np.floating,)):
        return float(valeur)
    if isinstance(valeur, (np.bool_,)):
        return bool(valeur)
    return valeur


def predire_facture(facture_id: str, top_k: int = 5, budget: float | None = None) -> dict[str, Any]:
    """Score de risque + explicabilité SHAP d'une facture pour l'API."""
    from predicare.ml.explain import expliquer_facture

    modele = _modele()
    magasin = _magasin()
    if facture_id not in magasin.index:
        raise FactureInconnue(facture_id)

    ligne = magasin.loc[facture_id]
    if isinstance(ligne, pd.DataFrame):
        ligne = ligne.iloc[0]

    score = modele.scorer(pd.DataFrame([ligne])).iloc[0]
    facteurs, recommandation = expliquer_facture(modele, ligne, top_k=top_k)

    seuil = modele.seuil_produit
    if budget is not None:
        seuil = modele.seuil_pour_budget(budget)

    facteurs = [
        {
            "feature": f["feature"],
            "valeur": _nettoyer(f["valeur"]),
            "impact_shap": float(f["impact_shap"]),
            "description": f["description"],
        }
        for f in facteurs
    ]

    return {
        "facture_id": facture_id,
        "prediction": {
            "score_fraude": round(float(score["score_risque"]), 6),
            "probabilite_calibree": round(float(score["probabilite"]), 6),
            "seuil_applique": float(seuil),
            "est_anomalie": bool(score["score_risque"] >= seuil),
            "budget_applique": budget,
            "version_modele": modele.version or "inconnue",
            "modele": modele.modele,
        },
        "explicabilite": {"top_facteurs": facteurs, "recommandation": recommandation},
    }
