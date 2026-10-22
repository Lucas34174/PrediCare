"""Tests de la supervision faible : labels faibles, dataset, modèle, règles."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from predicare.ml.registry import enregistrer_version

RACINE = Path(__file__).resolve().parents[1]
LABELS = RACINE / "data" / "raw" / "labels" / "labels_fraude.csv"
MANIFEST_LABELS = RACINE / "data" / "raw" / "labels" / "weak_labels_manifest.json"
DATASET = RACINE / "data" / "processed" / "dataset_fraude_v2.csv"
MANIFEST_DATASET = RACINE / "data" / "processed" / "dataset_fraude_v2_manifest.json"

TYPES14 = {
    "SURFACTURATION",
    "QUANTITE_EXCESSIVE",
    "UPCODING",
    "LIGNES_NON_PRESCRITES",
    "SUBSTITUTION_PRODUIT",
    "ORDONNANCE_EXPIREE",
    "SOINS_JOUR_FERME",
    "DOUBLON",
    "FRACTIONNEMENT",
    "SURCONSOMMATION",
    "ACTE_FICTIF",
    "INCOHERENCE_PROFIL",
    "PRESTATAIRE_RADIE",
    "HORS_COUVERTURE",
}


@pytest.mark.skipif(not LABELS.is_file(), reason="labels faibles absents")
def test_labels_faibles_schema_et_volumes():
    labels = pd.read_csv(LABELS)
    assert len(labels) == 84593
    assert labels["facture_id"].is_unique
    assert set(labels["est_fraude"].unique()) <= {0, 1}
    assert labels["est_valide"].eq(1).all()
    assert int(labels["est_fraude"].sum()) == 7347
    assert abs(labels["est_fraude"].mean() - 7347 / 84593) < 1e-9
    types = set(labels.loc[labels["est_fraude"] == 1, "type_fraude"]) - {
        "AUCUN",
        "CONTROLE_MEDICAL",
    }
    assert types <= TYPES14
    assert {"confiance", "candidat", "types_fraude", "precision_attendue"} <= set(labels.columns)


@pytest.mark.skipif(not MANIFEST_LABELS.is_file(), reason="manifeste labels absent")
def test_manifeste_labels_documente_les_limites():
    manifest = json.loads(MANIFEST_LABELS.read_text(encoding="utf-8"))
    assert manifest["nb_positifs"] == 7347
    assert manifest["nb_haute"] > 0
    assert manifest["nb_moyenne_retenue"] > 0
    assert manifest["limites"]
    assert "pas une vérité terrain" in manifest["avertissement"].lower()


@pytest.mark.skipif(not DATASET.is_file(), reason="dataset v2 absent")
def test_dataset_v2_exclut_les_variables_de_regles():
    manifest = json.loads(MANIFEST_DATASET.read_text(encoding="utf-8"))
    features = manifest["features"]
    dataset = pd.read_csv(DATASET, nrows=5)
    assert "cible" in dataset.columns
    assert "cible" not in features
    assert not set(features) & set(manifest["colonnes_exclues_regles"])
    assert len(features) >= 40
    for split in ("train", "validation", "test"):
        assert split in manifest["par_split"]
        assert manifest["par_split"][split]["positifs"] > 0


def test_registre_contient_v2(tmp_path):
    modele = tmp_path / "modele.joblib"
    modele.write_bytes(b"artefact de test")
    chemin_registre = tmp_path / "registry.json"
    enregistrer_version(
        version="v2.0.0-weak",
        chemin_modele=modele,
        chemin_registre=chemin_registre,
        racine_modeles=tmp_path / "models",
    )

    registre = json.loads(chemin_registre.read_text(encoding="utf-8"))
    versions = {v["version"] for v in registre["versions"]}
    assert "v2.0.0-weak" in versions
    entree = next(v for v in registre["versions"] if v["version"] == "v2.0.0-weak")
    assert entree["sha256"]
    assert entree["statut"] in {"staging", "production", "archive"}
