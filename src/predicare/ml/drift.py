"""PB-12 — Référence de dérive et détection de dérive (PSI / KS).

Les compteurs cumulatifs (nombre de factures historiques, etc.) dérivent par
construction avec le temps : ils sont marqués ``tendance=True`` et exclus du
verdict global. Les autres variables sont suivies par PSI et KS.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from predicare.ml.config import REPORTS_DIR
from predicare.ml.targets import charger_dataset_cm

# Variables dont la croissance est structurelle (compteurs cumulatifs).
VARIABLES_TENDANCE = {
    "prest_nb_decidees_hist",
    "prest_nb_rejets_hist",
    "prest_nb_factures_hist",
    "prest_nb_decidees_90j",
    "prest_nb_factures_90j",
    "assure_nb_decidees_hist",
    "assure_nb_rejets_hist",
    "assure_nb_factures_hist",
    "assure_nb_factures_30j",
    "assure_nb_factures_90j",
    "jours_depuis_derniere_facture",
    "anciennete_adhesion_j",
    "anciennete_contrat_j",
    "anciennete_convention_j",
}

SEUILS_PSI = {"ok": 0.10, "vigilance": 0.25}


def _variables(dataset: pd.DataFrame) -> tuple[list[str], list[str]]:
    from predicare.ml.training import _colonnes_features

    return _colonnes_features(dataset)


def _bins_numeriques(serie: pd.Series, n: int = 10) -> list[float]:
    valeurs = pd.to_numeric(serie, errors="coerce").dropna()
    if valeurs.nunique() <= 1:
        return []
    edges = np.unique(np.quantile(valeurs, np.linspace(0, 1, n + 1)))
    return [float(e) for e in edges]


def construire_reference(
    dataset: pd.DataFrame | None = None, chemin: Path | str | None = None
) -> dict:
    """Calcule la distribution de référence sur le train."""
    dataset = dataset if dataset is not None else charger_dataset_cm()
    train = dataset[dataset["split"] == "train"]
    numeriques, categorielles = _variables(dataset)

    reference: dict = {"n_train": int(len(train)), "variables": {}}

    for nom in numeriques:
        serie = pd.to_numeric(train[nom], errors="coerce")
        edges = _bins_numeriques(serie)
        if edges:
            counts, _ = np.histogram(serie.dropna(), bins=edges)
            proportions = (counts / max(counts.sum(), 1)).tolist()
        else:
            proportions = []
        reference["variables"][nom] = {
            "type": "numerique",
            "moyenne": float(serie.mean()) if serie.notna().any() else None,
            "ecart_type": float(serie.std()) if serie.notna().any() else None,
            "min": float(serie.min()) if serie.notna().any() else None,
            "max": float(serie.max()) if serie.notna().any() else None,
            "bins": edges,
            "proportions": proportions,
            "manquants": float(serie.isna().mean()),
            "tendance": nom in VARIABLES_TENDANCE,
        }

    for nom in categorielles:
        serie = train[nom].astype(str)
        valeurs = serie.value_counts(normalize=True)
        reference["variables"][nom] = {
            "type": "categorielle",
            "modalites": valeurs.index.tolist(),
            "proportions": valeurs.to_numpy().tolist(),
            "manquants": float(train[nom].isna().mean()),
            "tendance": False,
        }

    if chemin is not None:
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(reference, indent=2, ensure_ascii=False), encoding="utf-8")
    return reference


def _psi(proportions_ref: list[float], proportions_cur: list[float]) -> float:
    p = np.clip(np.asarray(proportions_ref, dtype=float), 1e-6, None)
    q = np.clip(np.asarray(proportions_cur, dtype=float), 1e-6, None)
    if len(p) != len(q) or not len(p):
        return float("nan")
    return float(np.sum((p - q) * np.log(p / q)))


def _statut(psi: float, tendance: bool) -> str:
    if tendance:
        return "tendance_structurelle"
    if not np.isfinite(psi):
        return "indetermine"
    if psi < SEUILS_PSI["ok"]:
        return "ok"
    if psi < SEUILS_PSI["vigilance"]:
        return "vigilance"
    return "alerte"


def calculer_derive(
    reference: dict,
    dataset: pd.DataFrame | None = None,
    split: str = "test",
) -> pd.DataFrame:
    """Calcule PSI et KS entre la référence (train) et ``split``."""
    dataset = dataset if dataset is not None else charger_dataset_cm()
    current = dataset[dataset["split"] == split]

    lignes = []
    for nom, ref in reference["variables"].items():
        if nom not in current.columns:
            continue
        if ref["type"] == "numerique":
            serie = pd.to_numeric(current[nom], errors="coerce").dropna()
            edges = ref.get("bins") or []
            if edges:
                counts, _ = np.histogram(serie, bins=edges)
                proportions = counts / max(counts.sum(), 1)
            else:
                proportions = []
            psi = _psi(ref.get("proportions", []), proportions.tolist())
            ks = (
                float(ks_2samp(serie, pd.to_numeric(dataset.loc[dataset["split"] == "train", nom], errors="coerce").dropna()).statistic)
                if len(serie) > 1
                else float("nan")
            )
        else:
            serie = current[nom].astype(str)
            proportions = serie.value_counts(normalize=True).reindex(ref["modalites"], fill_value=0.0)
            psi = _psi(ref.get("proportions", []), proportions.to_numpy().tolist())
            ks = float("nan")

        lignes.append(
            {
                "variable": nom,
                "type": ref["type"],
                "psi": psi,
                "ks": ks,
                "statut": _statut(psi, bool(ref.get("tendance"))),
                "tendance": bool(ref.get("tendance")),
                "manquants_reference": ref.get("manquants"),
            }
        )
    return pd.DataFrame(lignes).sort_values(["statut", "psi"], ascending=[True, False]).reset_index(drop=True)


def synthese_derive(derive: pd.DataFrame) -> dict:
    """Verdict global hors variables de tendance."""
    hors_tendance = derive[~derive["tendance"]]
    return {
        "nb_variables": int(len(derive)),
        "nb_tendance_exclues": int(derive["tendance"].sum()),
        "nb_ok": int((hors_tendance["statut"] == "ok").sum()),
        "nb_vigilance": int((hors_tendance["statut"] == "vigilance").sum()),
        "nb_alerte": int((hors_tendance["statut"] == "alerte").sum()),
        "psi_max_hors_tendance": float(hors_tendance["psi"].max()) if len(hors_tendance) else None,
        "verdict": (
            "derive_significative"
            if (hors_tendance["statut"] == "alerte").any()
            else "derive_moderee"
            if (hors_tendance["statut"] == "vigilance").any()
            else "stable"
        ),
    }


def main() -> None:  # pragma: no cover - CLI
    dossier = REPORTS_DIR / "pb12"
    dossier.mkdir(parents=True, exist_ok=True)
    reference = construire_reference(chemin=dossier / "reference_distribution.json")
    derive = calculer_derive(reference, split="test")
    derive.to_csv(dossier / "derive_test.csv", index=False)
    synthese = synthese_derive(derive)
    (dossier / "synthese_derive.json").write_text(
        json.dumps(synthese, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(synthese, indent=2, ensure_ascii=False))
    print(derive.head(15).to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
