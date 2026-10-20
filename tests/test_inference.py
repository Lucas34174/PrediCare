"""Tests unitaires pour l'inférence en ligne, anti-fuite et explicabilité (PB-22)."""

from __future__ import annotations

import pytest

from predicare.core.config import fraud_score_threshold
from predicare.ml.features import FORBIDDEN_FEATURE_COLS
from predicare.ml.service import (
    ModeleIndisponible,
    construire_features_facture,
    get_model,
    predire_facture_en_ligne,
    reset_model_cache,
)


def _facture_test() -> tuple[dict, list[dict]]:
    fac = {
        "facture_id": "FAC-TEST-001",
        "numero_facture": "F-2026-0001",
        "assure_id": "ASS-00421",
        "prestataire_id": "PR-0015",
        "ordonnance_id": "ORD-0003289",
        "date_soin": "2026-10-14",
        "date_emission": "2026-10-15",
        "montant_total": 45000,
        "part_assure": 9000,
    }
    lignes = [
        {
            "num_ligne": 1,
            "code": "ACT-CS-01",
            "type_ligne": "ACTE",
            "quantite": 1,
            "prix_unitaire": 30000,
            "montant_total": 30000,
        },
        {
            "num_ligne": 2,
            "code": "MED-CIP-0045",
            "type_ligne": "MEDICAMENT",
            "quantite": 2,
            "prix_unitaire": 7500,
            "montant_total": 15000,
        },
    ]
    return fac, lignes


def test_chargement_modele_champion_et_explainer():
    """Le modèle champion se charge en singleton avec son explainer SHAP."""
    reset_model_cache()
    try:
        modele = get_model()
    except ModeleIndisponible as exc:
        pytest.skip(f"Modèle champion absent de cet environnement : {exc}")

    assert modele.version
    assert len(modele.variables) == 23
    assert modele.explainer is not None


def test_anti_fuite_strict_features_inférence():
    """Garantit l'absence absolue de colonnes de fuite ou de labels dans les features calculées."""
    fac, lignes = _facture_test()
    # Injection volontaire de colonnes de fuite pour tester la purge
    fac["statut"] = "PAYEE"
    fac["motif_rejet"] = "AUCUN"
    fac["montant_pris_en_charge"] = 36000
    fac["date_traitement"] = "2026-10-16"
    fac["est_fraude"] = 1

    features_df = construire_features_facture(fac, lignes)
    fuites = set(features_df.columns) & FORBIDDEN_FEATURE_COLS
    assert not fuites, f"Colonnes interdites détectées : {fuites}"
    assert len(features_df) == 1
    assert len(features_df.columns) == 23


def test_inference_en_ligne_complete():
    """Vérifie le score [0, 1], la cohérence avec le seuil et les facteurs SHAP."""
    reset_model_cache()
    fac, lignes = _facture_test()

    try:
        res = predire_facture_en_ligne(fac, lignes, top_k=5)
    except ModeleIndisponible as exc:
        pytest.skip(f"Modèle indisponible : {exc}")

    assert 0.0 <= res["score_fraude"] <= 1.0
    seuil = fraud_score_threshold()
    assert res["seuil_applique"] == seuil
    assert res["est_anomalie"] == bool(res["score_fraude"] >= seuil)
    assert res["version_modele"]
    assert len(res["top_facteurs"]) <= 5
    assert res["recommandation"]

    # Contrôle PII : aucune information personnelle ne doit transparaître dans les explications
    pii_mots = {"rabe", "razafy", "cin", "telephone", "adresse", "email"}
    for f in res["top_facteurs"]:
        desc_lower = f["description"].lower()
        for pii in pii_mots:
            assert pii not in desc_lower


def test_modele_absent_leve_exception_explicite(monkeypatch):
    """Vérifie qu'un modèle introuvable lève ModeleIndisponible (pas de score factice)."""
    monkeypatch.setenv("PREDICARE_MODELE_PATH", "models/inexistant_fantome.joblib")
    reset_model_cache()

    fac, lignes = _facture_test()
    with pytest.raises(ModeleIndisponible) as exc_info:
        predire_facture_en_ligne(fac, lignes)
    assert "introuvable" in str(exc_info.value).lower()
