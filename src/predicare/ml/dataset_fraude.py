"""Construction du dataset de fraude v2 (labels faibles) pour l'entraînement.

Le dataset Phase 4 ``data/raw/dataset_ml.csv`` contient 107 colonnes et une
cible proxy ``cible`` (rejet administratif). Ce module :

1. joint les labels faibles ``data/raw/labels/labels_fraude.csv`` ;
2. remplace la cible proxy par ``cible = est_fraude`` ;
3. **exclut les variables qui encodent directement les règles** utilisées pour
   construire la cible (sinon le modèle ne fait que réapprendre les règles) ;
4. ajoute un poids d'échantillon pour la supervision faible ;
5. écrit ``data/processed/dataset_fraude_v2.csv`` + un manifeste.

Les variables conservées sont comportementales : montants, délais, volumes,
historique prestataire/assuré, profil, contrat, etc.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

DATASET_SOURCE = Path("data/raw/dataset_ml.csv")
LABELS_SOURCE = Path("data/raw/labels/labels_fraude.csv")
DATASET_OUT = Path("data/processed/dataset_fraude_v2.csv")
MANIFEST_OUT = Path("data/processed/dataset_fraude_v2_manifest.json")

#: Colonnes techniques ou de label : jamais des variables.
NON_FEATURES = {
    "facture_id",
    "split",
    "fold_cv",
    "meta_date_reception",
    "meta_assure_id",
    "meta_prestataire_id",
    "cible",
    "cible_rejet",
    "cible_cm",
    "cible_controle_medical",
    "statut",
    "motif_rejet",
    "type_fraude",
    "confiance",
    "candidat",
    "precision_attendue",
    "tier",
    "poids_echantillon",
}

#: Variables qui encodent directement une règle de labellisation ou une fuite.
#: Elles sont exclues de l'entraînement pour éviter la circularité.
COLONNES_REGLES = {
    # SURFACTURATION
    "ecart_tarif_reference",
    "ratio_prix_reference_max",
    "nb_lignes_sup_tarif_max",
    "ecart_grille_prestataire",
    "ratio_prix_grille_max",
    "nb_lignes_hors_grille",
    "ratio_prix_reference_moy",
    "ecart_tarif_reference_pct",
    # QUANTITE_EXCESSIVE
    "quantite_excedentaire",
    # LIGNES_NON_PRESCRITES
    "nb_lignes_non_prescrites",
    "ecart_prescription",
    # HORS_COUVERTURE
    "nb_lignes_exclues_formule",
    "soin_avant_adhesion",
    "soin_apres_radiation",
    "soin_hors_contrat",
    "carence_non_ecoulee",
    "jours_carence_restants",
    # INCOHERENCE_PROFIL
    "nb_lignes_profil_incoherent",
    # ORDONNANCE_EXPIREE
    "ordonnance_age_au_soin_j",
    "ordonnance_perimee",
    "ordonnance_postdatee",
    "ordonnance_avant_adhesion",
    # SOINS_JOUR_FERME
    "prestataire_ferme_jour_soin",
    # DOUBLON
    "nb_doublons_exacts_anterieurs",
    "doublon_potentiel",
    "numero_facture_deja_vu",
    # FRACTIONNEMENT
    "nb_factures_meme_jour_meme_prest_ant",
    # SURCONSOMMATION
    "surconsommation_ordonnance",
    "taux_conso_plafond_categorie",
    "taux_conso_plafond_global",
    # UPCODING
    "upcoding_majoration_indue",
    # PRESTATAIRE_RADIE
    "convention_terminee_au_soin",
    # ACTE_FICTIF
    "ordonnance_requise_manquante",
    "entente_requise_manquante",
    "attestation_requise_manquante",
    # Prescription / doublons de prescription
    "nb_lignes_doublon_prescription",
    "prescripteur_incompatible",
    "doublon_prescription_30j",
    # Agrégats de règles
    "nb_alertes_metier",
    "score_regles_metier",
}


def _poids(row: pd.Series) -> float:
    """Poids de supervision faible.

    * positif haute confiance : 1,0 ;
    * positif moyenne confiance : 0,8 ;
    * négatif candidat (règle faible) : 0,3 (étiquette incertaine) ;
    * négatif sans signal : 1,0.
    """
    if int(row["cible"]) == 1:
        return 1.0 if row.get("confiance") == "haute" else 0.8
    if int(row.get("candidat", 0)) == 1:
        return 0.3
    return 1.0


def construire_dataset(
    dataset_path: str | Path = DATASET_SOURCE,
    labels_path: str | Path = LABELS_SOURCE,
    out_path: str | Path = DATASET_OUT,
    manifest_path: str | Path = MANIFEST_OUT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    dataset_path = Path(dataset_path)
    labels_path = Path(labels_path)
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)
    if not labels_path.is_file():
        raise FileNotFoundError(labels_path)

    df = pd.read_csv(dataset_path, low_memory=False)
    labels = pd.read_csv(labels_path, low_memory=False)
    colonnes_labels = [
        "facture_id",
        "est_fraude",
        "type_fraude",
        "confiance",
        "candidat",
        "precision_attendue",
        "tier",
    ]
    manquantes = [c for c in colonnes_labels if c not in labels.columns]
    if manquantes:
        raise ValueError(f"Colonnes de labels manquantes : {manquantes}")

    df = df.merge(
        labels[colonnes_labels], on="facture_id", how="left", validate="one_to_one"
    )
    if df["est_fraude"].isna().any():
        raise ValueError("Certaines factures du dataset n'ont pas de label faible.")
    df["est_fraude"] = df["est_fraude"].astype(int)

    # La cible proxy d'origine est supprimée : elle ne doit jamais être une feature.
    for colonne in ("cible", "cible_rejet", "cible_cm", "cible_controle_medical"):
        if colonne in df.columns:
            df = df.drop(columns=colonne)
    df = df.rename(columns={"est_fraude": "cible"})
    df["cible"] = df["cible"].astype(int)

    # Poids de supervision faible (train uniquement).
    df["poids_echantillon"] = df.apply(_poids, axis=1).astype(float)

    features = [
        c
        for c in df.columns
        if c not in NON_FEATURES and c not in COLONNES_REGLES
    ]
    # Les identifiants à forte cardinalité ne sont jamais des features.
    features = [
        c
        for c in features
        if not pd.api.types.is_object_dtype(df[c])
        or df[c].nunique(dropna=True) <= 100
    ]

    # Contrôles
    if "cible" in features:
        raise AssertionError("La cible ne doit pas être une feature.")
    if set(features) & COLONNES_REGLES:
        raise AssertionError("Une variable de règle est encore présente.")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")

    par_split = (
        df.groupby("split")["cible"]
        .agg(["count", "sum", "mean"])
        .rename(columns={"count": "factures", "sum": "positifs", "mean": "prevalence"})
    )
    manifest: dict[str, Any] = {
        "version": "dataset_fraude_v2",
        "source_dataset": str(dataset_path),
        "source_labels": str(labels_path),
        "sortie": str(out_path),
        "nb_factures": int(len(df)),
        "nb_features": len(features),
        "features": features,
        "colonnes_exclues_regles": sorted(COLONNES_REGLES),
        "colonnes_non_features": sorted(NON_FEATURES),
        "prevalence_globale": float(df["cible"].mean()),
        "par_split": {
            str(k): {
                "factures": int(v["factures"]),
                "positifs": int(v["positifs"]),
                "prevalence": float(v["prevalence"]),
            }
            for k, v in par_split.iterrows()
        },
        "poids": {
            "positif_haute": 1.0,
            "positif_moyenne": 0.8,
            "negatif_candidat": 0.3,
            "negatif_sans_signal": 1.0,
        },
        "avertissement": (
            "Cible faible reconstruite ; les variables de règles sont exclues "
            "pour éviter que le modèle ne réapprenne les règles."
        ),
    }
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(
        "Dataset v2 : %d factures × %d features | prévalence %.2f%%",
        len(df),
        len(features),
        100 * manifest["prevalence_globale"],
    )
    for split, stats in manifest["par_split"].items():
        logger.info(
            "  %-10s : %5d factures | %4d positifs | %.2f%%",
            split,
            stats["factures"],
            stats["positifs"],
            100 * stats["prevalence"],
        )
    return df, manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construit le dataset de fraude v2.")
    parser.add_argument("--dataset", default=str(DATASET_SOURCE))
    parser.add_argument("--labels", default=str(LABELS_SOURCE))
    parser.add_argument("--out", default=str(DATASET_OUT))
    parser.add_argument("--manifest", default=str(MANIFEST_OUT))
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
    )
    construire_dataset(args.dataset, args.labels, args.out, args.manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
