"""Explicabilité SHAP par alerte (PB-13).

Produit des facteurs au format du contrat API :
``ShapFactor{feature, valeur, impact_shap, description}``.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from predicare.ml.config import feature_label

try:
    import shap

    SHAP_DISPONIBLE = True
except Exception:  # pragma: no cover
    shap = None
    SHAP_DISPONIBLE = False


def _noms_features(preprocesseur: Any) -> list[str]:
    try:
        return [str(n) for n in preprocesseur.get_feature_names_out()]
    except Exception:  # pragma: no cover
        return []


def variable_source(nom_feature: str, variables: list[str]) -> tuple[str, str | None]:
    """Retrouve la variable d'origine et, le cas échéant, la modalité one-hot."""
    for prefixe in ("num__", "cat__"):
        if nom_feature.startswith(prefixe):
            base = nom_feature[len(prefixe) :]
            if base.endswith("_indicator") or base.startswith("missingindicator_"):
                return base.replace("missingindicator_", "").removesuffix("_indicator"), None
            if base in variables:
                return base, None
            candidats = [v for v in variables if base.startswith(v + "_")]
            if candidats:
                variable = max(candidats, key=len)
                return variable, base[len(variable) + 1 :]
            return base, None
    return nom_feature, None


def _valeur_lisible(valeur: Any) -> float | int | str:
    if isinstance(valeur, (np.integer,)):
        return int(valeur)
    if isinstance(valeur, (np.floating,)):
        return float(valeur)
    if isinstance(valeur, (int, float, str)):
        return valeur
    return str(valeur)


def _description(variable: str, modalite: str | None, valeur: Any, manquante: bool) -> str:
    label = feature_label(variable)
    if manquante:
        return f"{label} : valeur manquante"
    if modalite:
        return f"{label} = {modalite.replace('_', ' ')}"
    if isinstance(valeur, (int, np.integer)):
        return f"{label} = {int(valeur)}"
    if isinstance(valeur, (float, np.floating)):
        return f"{label} = {float(valeur):.2f}"
    return f"{label} = {valeur}"


def _valeurs_shap(clf: Any, X: Any) -> np.ndarray:  # noqa: N803
    """Valeurs SHAP de la classe positive, quelle que soit la version de shap."""
    explainer = shap.TreeExplainer(clf)
    valeurs = explainer.shap_values(X)
    if isinstance(valeurs, list):
        valeurs = valeurs[1] if len(valeurs) > 1 else valeurs[0]
    valeurs = np.asarray(valeurs)
    if valeurs.ndim == 3:
        valeurs = valeurs[:, :, 1]
    return valeurs


def expliquer_lot(modele: Any, factures: pd.DataFrame, top_k: int = 5) -> pd.DataFrame:
    """Explications SHAP pour un lot de factures."""
    if not SHAP_DISPONIBLE:
        raise ImportError("Le paquet `shap` est requis pour l'explicabilité.")

    pre = modele.pipeline.named_steps["pre"]
    clf = modele.pipeline.named_steps["clf"]
    variables = list(modele.variables)
    X = pre.transform(factures[variables])
    noms = _noms_features(pre)
    valeurs = _valeurs_shap(clf, X)

    lignes: list[dict[str, Any]] = []
    for i, (_, ligne) in enumerate(factures.iterrows()):
        contributions = valeurs[i]
        ordre = np.argsort(-np.abs(contributions))[:top_k]
        for rang, j in enumerate(ordre, start=1):
            nom = noms[j] if j < len(noms) else f"f{j}"
            variable, modalite = variable_source(nom, variables)
            manquante = nom.endswith("_indicator") or "missingindicator" in nom
            brut = ligne.get(variable)
            valeur = _valeur_lisible(brut)
            lignes.append(
                {
                    "facture_id": ligne.get("facture_id"),
                    "rang": rang,
                    "feature": variable,
                    "valeur": valeur,
                    "impact_shap": float(contributions[j]),
                    "description": _description(variable, modalite, valeur, manquante),
                }
            )
    return pd.DataFrame(lignes)


def expliquer_facture(
    modele: Any, facture: pd.Series | dict, top_k: int = 5
) -> tuple[list[dict[str, Any]], str]:
    """Explications d'une facture unique + recommandation métier."""
    serie = facture if isinstance(facture, pd.Series) else pd.Series(facture)
    lot = expliquer_lot(modele, pd.DataFrame([serie]), top_k=top_k)
    facteurs = [
        {
            "feature": r["feature"],
            "valeur": r["valeur"],
            "impact_shap": round(float(r["impact_shap"]), 6),
            "description": r["description"],
        }
        for _, r in lot.iterrows()
    ]
    positifs = [f for f in facteurs if f["impact_shap"] > 0][:3]
    if positifs:
        details = " ; ".join(f["description"] for f in positifs)
        recommandation = f"Contrôle requis : {details}."
    else:
        recommandation = "Aucun facteur majeur d'alerte ; facture conforme au profil appris."
    return facteurs, recommandation


def formater_feature(nom: str) -> str:
    """Normalise un nom de variable pour l'affichage (sans préfixe technique)."""
    return re.sub(r"^(num|cat)__", "", str(nom))
