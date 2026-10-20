"""Scoring du modèle B et normalisation du score de risque.

Le CDC impose un seuil produit à **0,8**. Les probabilités calibrées du modèle B
sont faibles (prévalence 1,2 %) : un seuil brut à 0,8 n'alerterait presque rien.
On expose donc un **score de risque normalisé** ∈ [0,1] tel que le point de
fonctionnement métier (seuil calibré) vaut 0,8. La probabilité calibrée reste
disponible pour l'audit.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from predicare.ml.config import DEFAULT_THRESHOLD, MODEL_PATH

SEUIL_PRODUIT_DEFAUT = float(os.environ.get("PREDICARE_SEUIL_ALERTE", DEFAULT_THRESHOLD))


def normaliser_score(probabilite, seuil_calibre: float) -> np.ndarray:
    """Transforme une probabilité en score de risque où ``seuil_calibre`` → 0,8.

    ``score = 1 - exp(-p / tau)`` avec ``tau = -seuil / ln(0,2)``.
    """
    p = np.clip(np.asarray(probabilite, dtype=float), 0.0, 1.0)
    if not np.isfinite(seuil_calibre) or seuil_calibre <= 1e-9:
        return p
    tau = -seuil_calibre / math.log(0.2)
    return 1.0 - np.exp(-p / tau)


class CalibrateurPlatt:
    """Calibration de Platt : régression logistique sur le score brut.

    Contrairement à la calibration isotonique (qui produit des paliers), elle
    reste **strictement croissante** et permet donc de choisir un seuil pour un
    budget d'alertes précis.
    """

    def __init__(self, modele):
        self.modele = modele

    def predict(self, scores) -> np.ndarray:
        valeurs = np.asarray(scores, dtype=float).reshape(-1, 1)
        return np.asarray(self.modele.predict_proba(valeurs)[:, 1], dtype=float)


@dataclass
class ModeleFraude:
    """Modèle B chargé, prêt à scorer et à alerter."""

    pipeline: object
    variables: list[str]
    seuil_probabilite: float
    seuil_produit: float = SEUIL_PRODUIT_DEFAUT
    calibrateur: object | None = None
    modele: str = ""
    version: str = ""
    metadonnees: dict = field(default_factory=dict)

    def seuil_pour_budget(self, budget: float) -> float:
        """Seuil de **score de risque normalisé** pour un budget d'alertes.

        Les seuils de probabilité calibrée sont pré-calculés sur la validation à
        l'entraînement (``seuils_budget_validation``) ; on retient le budget le
        plus proche, puis on le projette sur l'échelle normalisée où le seuil
        produit vaut 0,80.
        """
        seuils = (self.metadonnees or {}).get("seuils_budget_validation") or {}
        if not seuils:
            raise ValueError("Aucun seuil par budget disponible dans l'artefact.")
        cle = min(seuils, key=lambda k: abs(float(k) - float(budget)))
        return float(normaliser_score(float(seuils[cle]), self.seuil_probabilite))

    def proba(self, factures: pd.DataFrame) -> np.ndarray:
        """Probabilité calibrée de l'événement « contrôle médical »."""
        manquantes = [v for v in self.variables if v not in factures.columns]
        if manquantes:
            raise KeyError("Variables manquantes : " + ", ".join(sorted(manquantes)))
        brut = self.pipeline.predict_proba(factures[self.variables])[:, 1]
        if self.calibrateur is not None:
            return np.asarray(self.calibrateur.predict(brut), dtype=float)
        return np.asarray(brut, dtype=float)

    def scorer(self, factures: pd.DataFrame) -> pd.DataFrame:
        """Renvoie ``facture_id``, ``probabilite`` et ``score_risque``."""
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

    def alerter(
        self, factures: pd.DataFrame, colonne_montant: str = "montant_total"
    ) -> pd.DataFrame:
        """Score + décision d'alerte au seuil produit configurable."""
        sortie = self.scorer(factures)
        sortie["seuil_applique"] = self.seuil_produit
        sortie["alerte"] = (sortie["score_risque"] >= self.seuil_produit).astype(int)
        if colonne_montant in factures.columns:
            sortie["montant_en_jeu"] = factures[colonne_montant].to_numpy()
        return sortie.sort_values("score_risque", ascending=False).reset_index(drop=True)


def charger_modele(chemin: str | Path | None = None) -> ModeleFraude:
    """Charge un modèle.

    Sans argument, charge la version **en production** du registre (v2.0.0-weak
    par défaut), avec repli sur ``models/v1.0.0/model.joblib``. Un chemin
    explicite ou ``PREDICARE_MODELE_PATH`` permet de cibler un artefact pour
    les audits et les tests de non-régression sans modifier la production.
    """
    if chemin is None:
        chemin = os.environ.get("PREDICARE_MODELE_PATH")
        if chemin is None:
            try:
                from predicare.ml.registry import charger_production

                return charger_production()
            except Exception:
                chemin = MODEL_PATH
    chemin = Path(chemin)
    objet = joblib.load(chemin)
    seuil = float(objet.get("seuil_probabilite_calibree", np.nan))
    seuil_produit = float(objet.get("seuil_produit", SEUIL_PRODUIT_DEFAUT))
    # Le seuil produit reste surchargeable par l'environnement (CDC : configurable).
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
