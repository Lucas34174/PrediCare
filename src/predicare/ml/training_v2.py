"""PB-10 v2 — entraînement sur labels faibles reconstruits.

Ce module remplace l'ancien proxy ``cible_controle_medical`` par la cible
faible ``est_fraude`` reconstruite par :mod:`predicare.ml.weak_labels`.

Points méthodologiques :

* les **variables de règles** utilisées pour fabriquer la cible sont exclues
  (voir :mod:`predicare.ml.dataset_fraude`) ;
* les positifs haute confiance pèsent 1,0, les positifs moyenne confiance 0,8,
  les négatifs « candidats » 0,3 (étiquette incertaine) ;
* LightGBM, XGBoost et SMOTE sont comparés sur la validation ;
* calibration de Platt sur la validation, seuil pour un rappel cible de 80 % ;
* évaluation unique sur le test chronologique.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from predicare.ml.config import (
    MODELS_ROOT,
    PARAMS_LIGHTGBM_V11,
    PARAMS_XGBOOST,
    RECALL_TARGET,
    REPORTS_DIR,
    SEED,
)
from predicare.ml.evaluation import (
    courbe_seuils,
    ece,
    intervalle_confiance_bootstrap,
    metriques_comparaison,
    metriques_seuil,
    seuil_pour_recall,
)
from predicare.ml.registry import enregistrer_version
from predicare.ml.scoring import CalibrateurPlatt, normaliser_score

VERSION = "v2.0.0-weak"
DATASET_V2 = Path("data/processed/dataset_fraude_v2.csv")
MANIFEST_V2 = Path("data/processed/dataset_fraude_v2_manifest.json")
MODELS_V2 = MODELS_ROOT / VERSION
REPORTS_V2 = REPORTS_DIR / "v2"
TARGET = "cible"

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


def charger_dataset(path: str | Path = DATASET_V2) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} introuvable. Exécuter d'abord "
            "`python -m predicare.ml.dataset_fraude`."
        )
    df = pd.read_csv(path, low_memory=False)
    if TARGET not in df.columns:
        raise ValueError(f"Cible {TARGET!r} absente de {path}.")
    if not set(df["split"].unique()) >= {"train", "validation", "test"}:
        raise ValueError("Splits train/validation/test incomplets.")
    return df


def _features(df: pd.DataFrame, manifest_path: Path = MANIFEST_V2) -> list[str]:
    """Liste des variables depuis le manifeste, avec repli sûr."""
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        features = [c for c in manifest.get("features", []) if c in df.columns]
        if features:
            return features
    return [
        c
        for c in df.columns
        if c not in NON_FEATURES and pd.api.types.is_numeric_dtype(df[c])
    ] + [
        c
        for c in df.columns
        if c not in NON_FEATURES
        and (pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]))
    ]


def _matrices(df: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    from predicare.ml.training import _preprocesseur

    numeriques = [
        c for c in features if pd.api.types.is_numeric_dtype(df[c])
    ]
    categorielles = [c for c in features if c not in numeriques]
    pre = _preprocesseur(numeriques, categorielles)

    train = df[df["split"] == "train"].copy()
    validation = df[df["split"] == "validation"].copy()
    test = df[df["split"] == "test"].copy()

    X_train = pre.fit_transform(train[features])
    X_val = pre.transform(validation[features])
    X_test = pre.transform(test[features])
    return {
        "pre": pre,
        "features": features,
        "numeriques": numeriques,
        "categorielles": categorielles,
        "train": train,
        "validation": validation,
        "test": test,
        "X_train": X_train,
        "X_val": X_val,
        "X_test": X_test,
        "y_train": train[TARGET].to_numpy(),
        "y_val": validation[TARGET].to_numpy(),
        "y_test": test[TARGET].to_numpy(),
        "w_train": train["poids_echantillon"].to_numpy(),
    }


def _candidats(x_train, y_train, w_train):
    """Construit les candidats (modèle, stratégie de déséquilibre)."""
    from lightgbm import LGBMClassifier
    from xgboost import XGBClassifier

    candidats = [
        (
            "LightGBM",
            "poids_faibles",
            LGBMClassifier(**PARAMS_LIGHTGBM_V11),
            w_train,
        ),
        (
            "LightGBM",
            "aucun",
            LGBMClassifier(**PARAMS_LIGHTGBM_V11),
            None,
        ),
        (
            "XGBoost",
            "poids_faibles",
            XGBClassifier(**PARAMS_XGBOOST),
            w_train,
        ),
    ]

    try:
        from imblearn.over_sampling import SMOTE

        x_res, y_res = SMOTE(
            random_state=SEED, sampling_strategy=0.5
        ).fit_resample(x_train, y_train)
        candidats.append(
            (
                "LightGBM",
                "smote",
                LGBMClassifier(**PARAMS_LIGHTGBM_V11),
                None,
                x_res,
                y_res,
            )
        )
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        print(f"SMOTE ignoré : {exc}")
    return candidats


def _ajuster(estimateur, x, y, poids=None):
    if poids is not None:
        estimateur.fit(x, y, sample_weight=poids)
    else:
        estimateur.fit(x, y)
    return estimateur


def entrainer_v2(
    dataset_path: str | Path = DATASET_V2,
    modele_path: str | Path | None = None,
    rapports_dir: str | Path | None = None,
    promouvoir: bool = True,
) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    df = charger_dataset(dataset_path)
    features = _features(df)
    m = _matrices(df, features)

    y_train, y_val, y_test = m["y_train"], m["y_val"], m["y_test"]
    w_train = m["w_train"]

    resultats: list[dict] = []
    meilleur = None
    for candidat in _candidats(m["X_train"], y_train, w_train):
        nom, strategie, estimateur, poids = candidat[:4]
        if len(candidat) > 4:
            x_fit, y_fit = candidat[4], candidat[5]
            poids_fit = None
        else:
            x_fit, y_fit = m["X_train"], y_train
            poids_fit = poids

        estimateur = _ajuster(estimateur, x_fit, y_fit, poids_fit)
        p_val = estimateur.predict_proba(m["X_val"])[:, 1]
        p_test = estimateur.predict_proba(m["X_test"])[:, 1]
        metriques_val = metriques_comparaison(y_val, p_val)
        metriques_test = metriques_comparaison(y_test, p_test)
        ligne = {
            "modele": nom,
            "strategie": strategie,
            **{f"val_{k}": v for k, v in metriques_val.items()},
            **{f"test_{k}": v for k, v in metriques_test.items()},
        }
        resultats.append(ligne)
        print(
            f"{nom:9s} {strategie:15s} | val PR-AUC {metriques_val['pr_auc']:.4f} "
            f"| val préc@R80 {metriques_val['precision_a_recall80']:.4f} "
            f"| test PR-AUC {metriques_test['pr_auc']:.4f}"
        )
        if meilleur is None or (
            metriques_val["pr_auc"], metriques_val["precision_a_recall80"]
        ) > (
            meilleur["val_metrics"]["pr_auc"],
            meilleur["val_metrics"]["precision_a_recall80"],
        ):
            meilleur = {
                "nom": nom,
                "strategie": strategie,
                "estimateur": estimateur,
                "p_val": p_val,
                "p_test": p_test,
                "val_metrics": metriques_val,
                "test_metrics": metriques_test,
            }

    assert meilleur is not None
    estimateur = meilleur["estimateur"]
    p_val, p_test = meilleur["p_val"], meilleur["p_test"]

    calibrateur = CalibrateurPlatt(
        LogisticRegression(max_iter=1000).fit(
            p_val.reshape(-1, 1), y_val
        )
    )
    p_val_cal = calibrateur.predict(p_val)
    p_test_cal = calibrateur.predict(p_test)

    seuil = seuil_pour_recall(y_val, p_val_cal, RECALL_TARGET)
    seuil_brut = seuil_pour_recall(y_val, p_val, RECALL_TARGET)

    metriques_test = metriques_seuil(y_test, p_test_cal, seuil)
    comparaison_test = metriques_comparaison(y_test, p_test_cal)
    metriques_test.update(
        {
            "pr_auc": comparaison_test["pr_auc"],
            "roc_auc": comparaison_test["roc_auc"],
            "brier": comparaison_test["brier"],
            "precision_a_recall80": comparaison_test["precision_a_recall80"],
            "pr_auc_ic95": intervalle_confiance_bootstrap(
                y_test, p_test_cal, "pr_auc"
            ),
            "roc_auc_ic95": intervalle_confiance_bootstrap(
                y_test, p_test_cal, "roc_auc"
            ),
            "ece": ece(y_test, p_test_cal)[0],
        }
    )

    metriques_val = metriques_seuil(y_val, p_val_cal, seuil)
    comparaison_val = metriques_comparaison(y_val, p_val_cal)
    metriques_val.update(
        {
            "pr_auc": comparaison_val["pr_auc"],
            "roc_auc": comparaison_val["roc_auc"],
            "brier": comparaison_val["brier"],
            "precision_a_recall80": comparaison_val["precision_a_recall80"],
            "ece": ece(y_val, p_val_cal)[0],
        }
    )

    seuils_budget = {
        str(budget): float(np.quantile(p_val_cal, 1 - budget))
        for budget in (0.01, 0.02, 0.03, 0.05, 0.10)
    }

    artefact = {
        "pipeline": Pipeline([("pre", m["pre"]), ("clf", estimateur)]),
        "calibrateur": calibrateur,
        "seuil_score_brut": float(seuil_brut),
        "seuil_probabilite_calibree": float(seuil),
        "seuil_produit": 0.80,
        "seuils_budget_validation": seuils_budget,
        "variables": features,
        "variables_numeriques": m["numeriques"],
        "variables_categorielles": m["categorielles"],
        "modele": meilleur["nom"],
        "traitement_desequilibre": meilleur["strategie"],
        "justification_desequilibre": (
            "Comparaison validation LightGBM/XGBoost, avec et sans pondération "
            "des labels faibles, plus SMOTE. Sélection sur PR-AUC de validation."
        ),
        "selection": (
            "Validation chronologique ; test holdout évalué une seule fois."
        ),
        "recall_cible_validation": RECALL_TARGET,
        "graine": SEED,
        "cible": "est_fraude (label faible reconstruit)",
        "cible_description": (
            "1 = fraude probable selon les règles du référentiel métier ; "
            "0 = non détecté par les règles (pas nécessairement légitime)."
        ),
        "labellisation": (
            "Labels faibles reconstruits à partir des 12 CSV et des 14 types "
            "de fraude du référentiel métier. Ce ne sont pas des fraudes "
            "confirmées. Les variables de règles sont exclues de l'entraînement."
        ),
        "date_entrainement_donnees": str(m["train"]["meta_date_reception"].max()),
        "date_creation": datetime.now(UTC).isoformat(),
        "version": VERSION,
        "dataset": str(dataset_path),
        "nb_features": len(features),
        "metriques_validation": metriques_val,
        "metriques_test": metriques_test,
        "comparaison_modeles": resultats,
    }

    modele_path = Path(modele_path) if modele_path else MODELS_V2 / "model.joblib"
    modele_path.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(artefact, modele_path)

    rapports_dir = Path(rapports_dir) if rapports_dir else REPORTS_V2
    rapports_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(resultats).to_csv(
        rapports_dir / "comparaison_modeles.csv", index=False
    )

    scores = pd.DataFrame(
        {
            "facture_id": m["test"]["facture_id"].to_numpy(),
            "probabilite": p_test_cal,
            "score_risque": normaliser_score(p_test_cal, seuil),
            "alerte": (p_test_cal >= seuil).astype(int),
            "cible": y_test,
            "type_fraude": m["test"]["type_fraude"].to_numpy(),
            "confiance": m["test"]["confiance"].to_numpy(),
            "candidat": m["test"]["candidat"].to_numpy(),
            "montant_total": m["test"]["montant_total"].to_numpy(),
        }
    ).sort_values("score_risque", ascending=False)
    scores.to_csv(rapports_dir / "scores_test.csv", index=False)

    courbe_seuils(y_test, p_test_cal).to_csv(
        rapports_dir / "courbe_seuils_test.csv", index=False
    )
    courbe_seuils(y_val, p_val_cal).to_csv(
        rapports_dir / "courbe_seuils_validation.csv", index=False
    )

    metadonnees_json = {
        k: v
        for k, v in artefact.items()
        if k not in {"pipeline", "calibrateur"}
    }
    (modele_path.parent / "metadata.json").write_text(
        json.dumps(metadonnees_json, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (rapports_dir / "metrics.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "modele": meilleur["nom"],
                "strategie": meilleur["strategie"],
                "validation": metriques_val,
                "test": metriques_test,
                "seuils_budget_validation": seuils_budget,
                "comparaison": resultats,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    entree = enregistrer_version(
        VERSION,
        modele_path,
        metadonnees=metadonnees_json,
        statut="staging",
        promouvoir=promouvoir,
    )
    return {
        "artefact": artefact,
        "metriques_validation": metriques_val,
        "metriques_test": metriques_test,
        "modele_path": modele_path,
        "registre": entree,
        "scores_test": scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entraînement v2 sur labels faibles")
    parser.add_argument("--dataset", default=str(DATASET_V2))
    parser.add_argument("--modele", default=None)
    parser.add_argument("--rapports", default=None)
    parser.add_argument("--sans-promotion", action="store_true")
    args = parser.parse_args(argv)

    resultat = entrainer_v2(
        dataset_path=args.dataset,
        modele_path=args.modele,
        rapports_dir=args.rapports,
        promouvoir=not args.sans_promotion,
    )
    m = resultat["metriques_test"]
    print(f"\nModèle {VERSION} — {resultat['artefact']['modele']}")
    print(f"Seuil calibré : {resultat['artefact']['seuil_probabilite_calibree']:.4f}")
    print(f"Test PR-AUC : {m['pr_auc']:.4f} (IC95 {m['pr_auc_ic95']})")
    print(f"Test ROC-AUC: {m['roc_auc']:.4f}")
    print(
        f"Test recall : {m['recall']:.4f} | précision : {m['precision']:.4f}"
    )
    print(
        f"Alertes     : {m['nb_alertes']} ({m['part_alertee']:.2%}) | lift {m['lift']:.2f}"
    )
    print(f"Registre    : {resultat['registre']['version']} [{resultat['registre']['statut']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
