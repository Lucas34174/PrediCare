"""Service de prédiction exposé à l'API (PB-13).

Fait le lien entre le modèle B en **production** (registre PB-11) et l'API :
charge le modèle et le magasin de variables une seule fois, score une facture
et renvoie ses facteurs SHAP au format du contrat d'interface.

Le magasin de variables est le fichier ``dataset_cm.csv`` (pipeline Phase 4).
En production, il serait remplacé par la vue matérialisée des variables.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from predicare.ml.config import DATASET_CM


class FactureInconnue(KeyError):  # noqa: N818
    """La facture demandée n'est pas dans le magasin de variables."""


class ModeleIndisponible(RuntimeError):  # noqa: N818
    """Aucun artefact de modèle exploitable n'est présent."""


@lru_cache(maxsize=1)
def _modele():
    """Charge le modèle de production (registre), avec repli sur l'artefact courant."""
    from predicare.ml import registry
    from predicare.ml.scoring import charger_modele

    try:
        return registry.charger_production()
    except Exception:
        return charger_modele()


@lru_cache(maxsize=1)
def _magasin() -> pd.DataFrame:
    if not DATASET_CM.is_file():
        raise ModeleIndisponible(f"Magasin de variables absent : {DATASET_CM}")
    return pd.read_csv(DATASET_CM, low_memory=False).set_index("facture_id")


def modele_disponible() -> bool:
    """Indique si le modèle et le magasin sont exploitables (sans lever d'exception)."""
    try:
        _modele()
        _magasin()
        return True
    except Exception:
        return False


def _nettoyer(valeur: Any) -> Any:
    """Rend une valeur sérialisable en JSON (NaN → chaîne explicite)."""
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


def predire_facture(facture_id: str, top_k: int = 5) -> dict:
    """Score de risque + explicabilité SHAP d'une facture.

    Lève :class:`FactureInconnue` si la facture n'est pas connue du magasin.
    """
    from predicare.ml.explain import expliquer_facture

    modele = _modele()
    magasin = _magasin()
    if facture_id not in magasin.index:
        raise FactureInconnue(facture_id)

    ligne = magasin.loc[facture_id]
    if isinstance(ligne, pd.DataFrame):  # identifiant dupliqué : on prend la 1re
        ligne = ligne.iloc[0]

    score = modele.scorer(pd.DataFrame([ligne])).iloc[0]
    facteurs, recommandation = expliquer_facture(modele, ligne, top_k=top_k)

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
            "seuil_applique": float(modele.seuil_produit),
            "est_anomalie": bool(score["score_risque"] >= modele.seuil_produit),
            "version_modele": modele.version or "inconnue",
            "modele": modele.modele,
        },
        "explicabilite": {"top_facteurs": facteurs, "recommandation": recommandation},
    }
