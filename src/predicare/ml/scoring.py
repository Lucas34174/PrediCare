"""Alias de compatibilité vers predicare.ml.service (évite la duplication)."""

from __future__ import annotations

from predicare.ml.service import (
    CalibrateurPlatt,
    FactureInconnue,
    ModeleFraude,
    ModeleIndisponible,
    charger_modele,
    normaliser_score,
    predire_facture,
)

__all__ = [
    "CalibrateurPlatt",
    "FactureInconnue",
    "ModeleFraude",
    "ModeleIndisponible",
    "charger_modele",
    "normaliser_score",
    "predire_facture",
]
