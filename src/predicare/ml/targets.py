"""Construction de la cible B : ``cible_controle_medical``.

Le jeu Phase 4 contient une cible « rejet administratif » qui mélange huit
motifs. Pour un projet de détection d'abus, seuls les rejets relevant d'un
jugement (``CONTROLE_MEDICAL``) sont conservés ; les rejets purement
administratifs sont exclus de l'apprentissage.

Aucun label de fraude confirmée n'étant fourni, ce proxy est explicite et
documenté.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from predicare.ml.config import (
    DATASET_CM,
    DATASET_ML,
    LABELS_SECONDAIRES,
    REFERENCE_DIR,
    TARGET,
)


def _resolve(path: Path, fallback_name: str | None = None) -> Path:
    """Retourne ``path`` s'il existe, sinon son équivalent dans le dossier de référence."""
    if path.is_file():
        return path
    if fallback_name is not None:
        candidate = REFERENCE_DIR / fallback_name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Fichier introuvable : {path} (repli : {REFERENCE_DIR / (fallback_name or '')})"
    )


def construire_dataset_cm(
    dataset_path: Path | str | None = None,
    labels_path: Path | str | None = None,
    output_path: Path | str | None = None,
) -> pd.DataFrame:
    """Construit ``dataset_cm.csv`` à partir de ``dataset_ml.csv`` et des labels.

    - ``cible_cm = 1`` pour ``cible_controle_medical == 1`` ;
    - ``cible_cm = 0`` pour les factures payées ;
    - les rejets pour un autre motif (943 lignes) sont **exclus**.

    Le split chronologique existant (``split``) est conservé.
    """
    dataset_path = Path(dataset_path) if dataset_path else _resolve(DATASET_ML)
    labels_path = (
        Path(labels_path) if labels_path else _resolve(LABELS_SECONDAIRES, "labels_secondaires.csv")
    )
    output_path = Path(output_path) if output_path else DATASET_CM

    dataset = pd.read_csv(dataset_path, low_memory=False)
    labels = pd.read_csv(labels_path, low_memory=False)

    if "facture_id" not in dataset or "facture_id" not in labels:
        raise ValueError("Les deux fichiers doivent contenir la colonne 'facture_id'.")
    if not labels["facture_id"].is_unique:
        raise ValueError("labels_secondaires.csv contient des facture_id dupliqués.")

    colonnes_labels = [
        c
        for c in ("facture_id", "statut", "motif_rejet", "cible_controle_medical")
        if c in labels.columns
    ]
    fusion = dataset.merge(
        labels[colonnes_labels], on="facture_id", how="left", validate="one_to_one"
    )

    if "cible_controle_medical" not in fusion:
        raise ValueError("Colonne 'cible_controle_medical' absente des labels.")

    # Population B : payées (0) + contrôle médical (1). Les autres rejets sont écartés.
    population = fusion[fusion["cible_controle_medical"].notna()].copy()
    population[TARGET] = population["cible_controle_medical"].astype(int)

    # La cible d'origine (rejet) est conservée sous un nom explicite, jamais utilisée
    # comme variable.
    if "cible" in population.columns:
        population = population.rename(columns={"cible": "cible_rejet"})

    population = population.drop(columns=["cible_controle_medical"])
    population.to_csv(output_path, index=False)
    return population


def valider_dataset_cm(df: pd.DataFrame) -> pd.DataFrame:
    """Contrôles de qualité bloquants, renvoyés sous forme de tableau."""
    resultats: list[dict] = []

    def verifier(nom: str, condition: bool, detail: str) -> None:
        resultats.append(
            {"test": nom, "statut": "OK" if bool(condition) else "ECHEC", "detail": detail}
        )

    verifier(
        "Cible binaire sans valeur manquante", df[TARGET].isin([0, 1]).all(), "cible_cm ∈ {0,1}"
    )
    verifier("Identifiants uniques", df["facture_id"].is_unique, f"{len(df)} lignes")
    verifier(
        "Partition stricte des splits",
        df.groupby("facture_id")["split"].nunique().max() == 1,
        "un facture_id dans un seul split",
    )
    verifier(
        "Trois splits présents",
        set(df["split"].unique()) == {"train", "validation", "test"},
        str(sorted(df["split"].unique())),
    )
    verifier(
        "Positifs dans chaque split",
        all(df.loc[df["split"] == s, TARGET].sum() > 0 for s in ("train", "validation", "test")),
        ", ".join(
            f"{s}={int(df.loc[df['split'] == s, TARGET].sum())}"
            for s in ("train", "validation", "test")
        ),
    )
    verifier(
        "Pas de rejet administratif résiduel",
        bool(
            (
                df.get("motif_rejet", pd.Series(index=df.index, dtype=object)).isna()
                | df.get("motif_rejet", pd.Series(index=df.index, dtype=object)).eq(
                    "CONTROLE_MEDICAL"
                )
            ).all()
        ),
        "seuls PAYEE et CONTROLE_MEDICAL sont conservés",
    )
    verifier(
        "Colonnes de fuite absentes des variables",
        not (set(df.columns) & {"cible", "cible_controle_medical"}),
        "les cibles brutes sont nommées cible_rejet / cible_cm",
    )
    return pd.DataFrame(resultats)


def charger_dataset_cm(path: Path | str | None = None) -> pd.DataFrame:
    """Charge ``dataset_cm.csv`` (le construit s'il est absent)."""
    path = Path(path) if path else DATASET_CM
    if not path.is_file():
        return construire_dataset_cm(output_path=path)
    return pd.read_csv(path, low_memory=False)
