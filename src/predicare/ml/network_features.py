"""Vague B — variables réseau et vélocité (v1.1).

Deux familles de signaux **absents du moteur de règles**, calculées en
point-in-time (uniquement avec l'information disponible à la réception) pour
éviter toute fuite temporelle :

* **réseau prestataire ↔ assuré** : dispersion des assurés d'un prestataire, des
  prestataires d'un assuré, intensité du couple (assuré, prestataire) ;
* **vélocité** : nombre de factures du prestataire / de l'assuré sur une fenêtre
  glissante de 7 et 30 jours, et sur la journée.

Ces variables sont ajoutées aux 100 variables de base et aux alertes
prescription PB-09 pour former ``dataset_cm_v11.csv``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from predicare.ml.config import ALERTES_FACTURES, DATA_RAW, REPORTS_DIR

DATASET_V11 = DATA_RAW / "dataset_cm_v11.csv"

# Codes d'alerte prescription retenus comme variables (PB-09).
CODES_PB09 = {
    "DOUBLON_PRESCRIPTION": "pb09_doublon_prescription",
    "SURCONSOMMATION": "pb09_surconsommation",
    "LIGNES_NON_PRESCRITES": "pb09_lignes_non_prescrites",
    "ORDONNANCE_ANTIDATEE": "pb09_ordonnance_antidatee",
    "PRESCRIPTEUR_RADIE": "pb09_prescripteur_radie",
    "PRESCRIPTEUR_INCOMPATIBLE": "pb09_prescripteur_incompatible",
}

VARIABLES_PB09 = [
    *CODES_PB09.values(),
    "pb09_nb_alertes",
    "pb09_gravite_max",
    "pb09_montant_en_jeu_max",
]

VARIABLES_RESEAU = [
    "reseau_prest_nb_assures_hist",
    "reseau_assure_nb_prest_hist",
    "reseau_couple_nb_factures_hist",
    "reseau_prest_part_couple_hist",
    "reseau_assure_part_prest_hist",
    "reseau_prest_nb_assures_jour",
    "reseau_assure_nb_prest_jour",
    "velocite_prest_7j",
    "velocite_prest_30j",
    "velocite_assure_7j",
    "velocite_assure_30j",
]


def _cumul_distinct(df: pd.DataFrame, cle: str, groupe: str) -> pd.Series:
    """Nombre cumulé de valeurs distinctes de ``cle`` déjà vues pour ``groupe``."""
    premiere = ~df.duplicated(subset=[groupe, cle], keep="first")
    return premiere.groupby(df[groupe]).cumsum().astype("int32")


def _fenetre_glissante(df: pd.DataFrame, groupe: str, jours: int) -> np.ndarray:
    """Nombre de lignes du groupe sur la fenêtre glissante ``jours`` (incluse).

    ``df`` doit porter une colonne ``_pos`` (position d'origine) et être indexé
    positionnellement ; le tableau renvoyé suit l'ordre des lignes de ``df``.
    """
    tmp = df[[groupe, "date_reception", "_pos"]].sort_values(
        [groupe, "date_reception"], kind="mergesort"
    )
    comptes = (
        tmp.groupby(groupe, sort=False)
        .rolling(f"{jours}D", on="date_reception")["_pos"]
        .count()
        .to_numpy()
    )
    par_position = pd.Series(comptes, index=tmp["_pos"].to_numpy())
    return par_position.reindex(df["_pos"].to_numpy()).fillna(0).to_numpy().astype("int32")


def construire_features_reseau(dataset: pd.DataFrame) -> pd.DataFrame:
    """Renvoie ``facture_id`` + les variables réseau/vélocité (point-in-time).

    Le résultat est aligné sur l'ordre d'entrée de ``dataset``.
    """
    base = dataset[
        ["facture_id", "meta_assure_id", "meta_prestataire_id", "meta_date_reception"]
    ].copy()
    base["date_reception"] = pd.to_datetime(base["meta_date_reception"], errors="coerce")
    base["_pos"] = np.arange(len(base))
    tri = base.sort_values("date_reception", kind="mergesort").reset_index(drop=True)

    prest = tri["meta_prestataire_id"]
    assure = tri["meta_assure_id"]
    jour = tri["date_reception"].dt.normalize()

    sortie = pd.DataFrame({"facture_id": tri["facture_id"], "_pos": tri["_pos"]})
    sortie["reseau_prest_nb_assures_hist"] = _cumul_distinct(
        tri, "meta_assure_id", "meta_prestataire_id"
    )
    sortie["reseau_assure_nb_prest_hist"] = _cumul_distinct(
        tri, "meta_prestataire_id", "meta_assure_id"
    )

    couple = tri.groupby(["meta_assure_id", "meta_prestataire_id"], sort=False).cumcount() + 1
    nb_prest = prest.groupby(prest).cumcount() + 1
    nb_assure = assure.groupby(assure).cumcount() + 1
    sortie["reseau_couple_nb_factures_hist"] = couple.to_numpy()
    sortie["reseau_prest_part_couple_hist"] = (couple / nb_prest).to_numpy()
    sortie["reseau_assure_part_prest_hist"] = (couple / nb_assure).to_numpy()

    sortie["reseau_prest_nb_assures_jour"] = (
        tri.groupby([prest, jour], sort=False)["meta_assure_id"].transform("nunique").to_numpy()
    )
    sortie["reseau_assure_nb_prest_jour"] = (
        tri.groupby([assure, jour], sort=False)["meta_prestataire_id"]
        .transform("nunique")
        .to_numpy()
    )

    sortie["velocite_prest_7j"] = _fenetre_glissante(tri, "meta_prestataire_id", 7)
    sortie["velocite_prest_30j"] = _fenetre_glissante(tri, "meta_prestataire_id", 30)
    sortie["velocite_assure_7j"] = _fenetre_glissante(tri, "meta_assure_id", 7)
    sortie["velocite_assure_30j"] = _fenetre_glissante(tri, "meta_assure_id", 30)

    return sortie.sort_values("_pos").drop(columns=["_pos"]).reset_index(drop=True)


def _alertes_pb09(chemin: Path | str | None = None) -> pd.DataFrame:
    chemin = Path(chemin) if chemin else REPORTS_DIR / "pb09" / "alertes_prescription.csv"
    colonnes = ["facture_id", *VARIABLES_PB09]
    if not chemin.is_file():
        fallback = Path(ALERTES_FACTURES)
        if not fallback.is_file():
            return pd.DataFrame(columns=colonnes)
        chemin = fallback
    alertes = pd.read_csv(chemin, low_memory=False)
    resultat = pd.DataFrame({"facture_id": alertes["facture_id"].unique()})
    for code, colonne in CODES_PB09.items():
        ids = set(alertes.loc[alertes["code_fraude"] == code, "facture_id"])
        resultat[colonne] = resultat["facture_id"].isin(ids).astype("int8")
    par_facture = alertes.groupby("facture_id")
    resultat["pb09_nb_alertes"] = (
        resultat["facture_id"].map(par_facture.size()).fillna(0).astype("int16")
    )
    resultat["pb09_gravite_max"] = (
        resultat["facture_id"].map(par_facture["gravite"].max()).fillna(0).astype("int8")
    )
    resultat["pb09_montant_en_jeu_max"] = (
        resultat["facture_id"].map(par_facture["montant_en_jeu"].max()).fillna(0).astype("float32")
    )
    return resultat[colonnes]


def construire_dataset_v11(
    dataset: pd.DataFrame | None = None,
    chemin_sortie: Path | str | None = None,
) -> pd.DataFrame:
    """Assemble dataset_cm + PB-09 + réseau/vélocité et écrit ``dataset_cm_v11.csv``."""
    from predicare.ml.targets import charger_dataset_cm

    dataset = dataset if dataset is not None else charger_dataset_cm()
    reseau = construire_features_reseau(dataset)
    alertes = _alertes_pb09()

    enrichi = dataset.reset_index(drop=True).join(
        reseau.drop(columns=["facture_id"]).reset_index(drop=True)
    )
    enrichi = enrichi.merge(alertes, on="facture_id", how="left")
    for colonne in VARIABLES_PB09:
        if colonne in enrichi:
            enrichi[colonne] = enrichi[colonne].fillna(0)

    chemin_sortie = Path(chemin_sortie) if chemin_sortie else DATASET_V11
    enrichi.to_csv(chemin_sortie, index=False)
    return enrichi


def charger_dataset_v11(chemin: Path | str | None = None) -> pd.DataFrame:
    """Charge ``dataset_cm_v11.csv`` (le construit s'il est absent)."""
    chemin = Path(chemin) if chemin else DATASET_V11
    if not chemin.is_file():
        return construire_dataset_v11(chemin_sortie=chemin)
    return pd.read_csv(chemin, low_memory=False)


def main() -> None:  # pragma: no cover - CLI
    df = construire_dataset_v11()
    print(f"dataset_cm_v11 : {df.shape[0]} lignes × {df.shape[1]} colonnes")
    print("variables réseau :", VARIABLES_RESEAU)
    print(
        df[[*VARIABLES_RESEAU, "pb09_nb_alertes"]].describe().T[["mean", "std", "max"]].to_string()
    )


if __name__ == "__main__":  # pragma: no cover
    main()
