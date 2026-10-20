"""EDA du dataset ML de fraude (PB-06).

Analyse la cible officielle ``est_fraude`` : prévalence, types de fraude,
évolution mensuelle, prestataires, types de facture, montants et factures
invalides. Les sorties sont écrites en CSV et en figures dans un dossier de
rapport.

Usage ::

    PYTHONPATH=src python -m predicare.ml.eda \
        --dataset data/processed/dataset_ml.csv \
        --hors-modele data/processed/factures_hors_modele.csv \
        --out-dir reports/eda_fraude
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("predicare.ml.eda")


def _prevalence(dataset: pd.DataFrame) -> pd.DataFrame:
    lignes = []
    for split, d in dataset.groupby("split", sort=False):
        lignes.append(
            {
                "split": split,
                "factures": len(d),
                "positifs": int(d["cible"].sum()),
                "prevalence": float(d["cible"].mean()) if len(d) else np.nan,
            }
        )
    return pd.DataFrame(lignes)


def _par_type_fraude(dataset: pd.DataFrame) -> pd.DataFrame:
    d = dataset.copy()
    d["type_fraude"] = d.get("type_fraude", pd.Series(pd.NA, index=d.index)).fillna("NON_LABELLISE")
    g = (
        d.groupby("type_fraude", dropna=False)
        .agg(
            factures=("facture_id", "count"),
            positifs=("cible", "sum"),
            prevalence=("cible", "mean"),
            montant_moyen=("montant_total", "mean"),
            montant_total=("montant_total", "sum"),
        )
        .reset_index()
        .sort_values(["positifs", "factures"], ascending=False)
    )
    return g


def _par_mois(dataset: pd.DataFrame) -> pd.DataFrame:
    d = dataset.copy()
    d["date_reception"] = pd.to_datetime(d["date_reception"], errors="coerce")
    d["mois"] = d["date_reception"].dt.to_period("M").astype(str)
    g = (
        d.groupby("mois", dropna=False)
        .agg(
            factures=("facture_id", "count"),
            positifs=("cible", "sum"),
            prevalence=("cible", "mean"),
            montant_total=("montant_total", "sum"),
        )
        .reset_index()
        .sort_values("mois")
    )
    return g


def _par_prestataire(dataset: pd.DataFrame, top: int = 30) -> pd.DataFrame:
    if "prestataire_id" not in dataset.columns:
        return pd.DataFrame()
    base = float(dataset["cible"].mean()) if len(dataset) else np.nan
    g = (
        dataset.groupby("prestataire_id", dropna=False)
        .agg(
            factures=("facture_id", "count"),
            positifs=("cible", "sum"),
            prevalence=("cible", "mean"),
            montant_total=("montant_total", "sum"),
        )
        .reset_index()
    )
    g["lift"] = g["prevalence"] / base if base and not np.isnan(base) else np.nan
    return g.sort_values(["positifs", "factures"], ascending=False).head(top)


def _par_type_facture(dataset: pd.DataFrame) -> pd.DataFrame:
    if "type_facture" not in dataset.columns:
        return pd.DataFrame()
    base = float(dataset["cible"].mean()) if len(dataset) else np.nan
    g = (
        dataset.groupby("type_facture", dropna=False)
        .agg(
            factures=("facture_id", "count"),
            positifs=("cible", "sum"),
            prevalence=("cible", "mean"),
            montant_moyen=("montant_total", "mean"),
        )
        .reset_index()
    )
    g["lift"] = g["prevalence"] / base if base and not np.isnan(base) else np.nan
    return g.sort_values("positifs", ascending=False)


def _montants(dataset: pd.DataFrame) -> pd.DataFrame:
    if "montant_total" not in dataset.columns:
        return pd.DataFrame()
    d = dataset.dropna(subset=["montant_total"]).copy()
    g = (
        d.groupby("cible")
        .agg(
            factures=("montant_total", "count"),
            moyenne=("montant_total", "mean"),
            mediane=("montant_total", "median"),
            total=("montant_total", "sum"),
            p95=("montant_total", lambda s: s.quantile(0.95)),
        )
        .reset_index()
    )
    return g


def _invalidite(hors_modele: pd.DataFrame | None) -> pd.DataFrame:
    if hors_modele is None or hors_modele.empty or "est_valide" not in hors_modele.columns:
        return pd.DataFrame(columns=["motif_invalidite", "factures"])
    invalides = hors_modele[hors_modele["est_valide"].eq(0)]
    if invalides.empty:
        return pd.DataFrame(columns=["motif_invalidite", "factures"])
    return (
        invalides.groupby("motif_invalidite", dropna=False)
        .agg(factures=("facture_id", "count"))
        .reset_index()
        .sort_values("factures", ascending=False)
    )


def _figures(prevalence, par_mois, par_type, par_prestataire, dossier: Path) -> list[str]:
    """Génère les figures principales ; retourne les chemins écrits."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ecrits: list[str] = []
    dossier.mkdir(parents=True, exist_ok=True)

    if not par_mois.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(par_mois["mois"], par_mois["positifs"], color="#c0392b", label="positifs")
        ax.set_ylabel("Factures positives")
        ax.set_title("Fraudes par mois de réception")
        ax.tick_params(axis="x", rotation=45)
        ax2 = ax.twinx()
        ax2.plot(par_mois["mois"], par_mois["prevalence"], color="#2c3e50", marker="o")
        ax2.set_ylabel("Prévalence")
        fig.tight_layout()
        chemin = dossier / "prevalence_mensuelle.png"
        fig.savefig(chemin, dpi=130)
        plt.close(fig)
        ecrits.append(str(chemin))

    if not par_type.empty and par_type["positifs"].sum() > 0:
        d = par_type[par_type["positifs"] > 0].head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(9, 0.45 * len(d) + 1.5))
        ax.barh(d["type_fraude"], d["positifs"], color="#e67e22")
        ax.set_xlabel("Factures positives")
        ax.set_title("Types de fraude (labels)")
        fig.tight_layout()
        chemin = dossier / "types_fraude.png"
        fig.savefig(chemin, dpi=130)
        plt.close(fig)
        ecrits.append(str(chemin))

    if not par_prestataire.empty:
        d = par_prestataire.head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(9, 0.45 * len(d) + 1.5))
        ax.barh(d["prestataire_id"].astype(str), d["positifs"], color="#8e44ad")
        ax.set_xlabel("Factures positives")
        ax.set_title("Top prestataires par fraudes labellisées")
        fig.tight_layout()
        chemin = dossier / "top_prestataires.png"
        fig.savefig(chemin, dpi=130)
        plt.close(fig)
        ecrits.append(str(chemin))

    return ecrits


def _rapport(
    prevalence: pd.DataFrame,
    par_type: pd.DataFrame,
    par_mois: pd.DataFrame,
    par_prestataire: pd.DataFrame,
    par_type_facture: pd.DataFrame,
    montants: pd.DataFrame,
    invalidite: pd.DataFrame,
    metadata: dict | None,
) -> str:
    cible = (metadata or {}).get("cible", "fraude")
    definition = (metadata or {}).get("definition", "est_fraude")
    total = int(prevalence["factures"].sum()) if not prevalence.empty else 0
    positifs = int(prevalence["positifs"].sum()) if not prevalence.empty else 0
    taux = positifs / total if total else float("nan")
    lignes_invalides = (
        invalidite.to_markdown(index=False) if not invalidite.empty else "Aucune facture invalide."
    )
    return f"""# PrediCare – EDA du dataset de fraude

## 1. Cible
- Cible : **{cible}** ({definition}).
- Factures modélisables : **{total}**.
- Positifs : **{positifs}** ({taux:.2%}).

## 2. Prévalence par ensemble
{prevalence.round(4).to_markdown(index=False) if not prevalence.empty else "—"}

## 3. Types de fraude
{par_type.round(4).to_markdown(index=False) if not par_type.empty else "—"}

## 4. Évolution mensuelle
{par_mois.round(4).to_markdown(index=False) if not par_mois.empty else "—"}

## 5. Types de facture
{par_type_facture.round(4).to_markdown(index=False) if not par_type_facture.empty else "—"}

## 6. Top prestataires
{par_prestataire.round(4).to_markdown(index=False) if not par_prestataire.empty else "—"}

## 7. Montants
{montants.round(2).to_markdown(index=False) if not montants.empty else "—"}

## 8. Factures invalides (exclues du modèle)
{lignes_invalides}

## 9. Lecture
- La prévalence sert de référence : une PR-AUC doit être comparée à ce taux.
- Les types de fraude très rares doivent être interprétés avec prudence.
- Une fraude non labellisée reste possible : la précision est une borne basse.
- Les données sont synthétiques ; les résultats reflètent le générateur.
"""


def eda_fraude(
    dataset: pd.DataFrame,
    hors_modele: pd.DataFrame | None = None,
    out_dir: str | Path = "reports/eda_fraude",
    metadata: dict | None = None,
) -> dict[str, pd.DataFrame]:
    """Calcule l'EDA et écrit les livrables dans ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if "cible" not in dataset.columns:
        raise ValueError("Le dataset doit contenir la colonne `cible`.")

    prevalence = _prevalence(dataset)
    par_type = _par_type_fraude(dataset)
    par_mois = _par_mois(dataset)
    par_prestataire = _par_prestataire(dataset)
    par_type_facture = _par_type_facture(dataset)
    montants = _montants(dataset)
    invalidite = _invalidite(hors_modele)

    sorties = {
        "prevalence": prevalence,
        "par_type_fraude": par_type,
        "par_mois": par_mois,
        "par_prestataire": par_prestataire,
        "par_type_facture": par_type_facture,
        "montants": montants,
        "invalidite": invalidite,
    }
    for nom, table in sorties.items():
        table.to_csv(out_dir / f"{nom}.csv", index=False, encoding="utf-8-sig")

    figures = _figures(prevalence, par_mois, par_type, par_prestataire, out_dir)
    rapport = _rapport(
        prevalence,
        par_type,
        par_mois,
        par_prestataire,
        par_type_facture,
        montants,
        invalidite,
        metadata,
    )
    (out_dir / "rapport_eda_fraude.md").write_text(rapport, encoding="utf-8")
    logger.info("EDA écrite dans %s (%d figures)", out_dir, len(figures))
    return sorties


def _cli() -> None:  # pragma: no cover
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    p = argparse.ArgumentParser(description="EDA du dataset de fraude – PrediCare TPA")
    p.add_argument("--dataset", default="data/processed/dataset_ml.csv")
    p.add_argument("--hors-modele", default="data/processed/factures_hors_modele.csv")
    p.add_argument("--metadata", default="data/processed/metadata_dataset.json")
    p.add_argument("--out-dir", default="reports/eda_fraude")
    args = p.parse_args()

    dataset = pd.read_csv(args.dataset, low_memory=False)
    hors = pd.read_csv(args.hors_modele, low_memory=False) if Path(args.hors_modele).is_file() else None
    meta = json.loads(Path(args.metadata).read_text(encoding="utf-8")) if Path(args.metadata).is_file() else None
    eda_fraude(dataset, hors, args.out_dir, meta)


if __name__ == "__main__":  # pragma: no cover
    _cli()
