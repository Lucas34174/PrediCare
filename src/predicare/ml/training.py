"""PB-10 — entraînement du modèle de détection de fraude sur labels faibles.

Ce module remplace l'ancien proxy ``cible_controle_medical`` par la cible
faible ``est_fraude`` reconstruite par :mod:`predicare.ml.weak_labels`.

Points méthodologiques :

* les **variables de règles** utilisées pour fabriquer la cible sont exclues
  (voir :mod:`predicare.ml.dataset_fraude`) ;
* les positifs haute confiance pèsent 1,0, les positifs moyenne confiance 0,8,
  les négatifs « candidats » 0,3 (étiquette incertaine) ;
* Optuna optimise les hyperparamètres XGBoost sur la PR-AUC des mêmes plis ;
* LightGBM, XGBoost et SMOTE sont comparés par CV stratifiée groupée sur
  Train + Validation, sans partage d'assuré entre les plis ;
* calibration de Platt et seuil pour un rappel cible de 80 % sont calculés
  sur les prédictions out-of-fold ;
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
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

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
            f"{path} introuvable. Exécuter d'abord `python -m predicare.ml.dataset_fraude`."
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
        c for c in df.columns if c not in NON_FEATURES and pd.api.types.is_numeric_dtype(df[c])
    ] + [
        c
        for c in df.columns
        if c not in NON_FEATURES
        and (pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]))
    ]


def _preprocesseur(numeriques: list[str], categorielles: list[str]) -> ColumnTransformer:
    """Construit l'imputation et l'encodage, à ajuster séparément dans chaque fold."""
    transformers = []
    if numeriques:
        transformers.append(
            ("numeric", SimpleImputer(strategy="median", keep_empty_features=True), numeriques)
        )
    if categorielles:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "imputer",
                            SimpleImputer(strategy="most_frequent", keep_empty_features=True),
                        ),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorielles,
            )
        )
    return ColumnTransformer(transformers, remainder="drop")


def _types_features(df: pd.DataFrame, features: list[str]) -> tuple[list[str], list[str]]:
    numeriques = [c for c in features if pd.api.types.is_numeric_dtype(df[c])]
    return numeriques, [c for c in features if c not in numeriques]


def _matrices(df: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    numeriques, categorielles = _types_features(df, features)
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


def _candidats(params_xgboost_optimises: dict[str, Any]) -> list[dict[str, Any]]:
    """Construit les estimateurs candidats ; le rééchantillonnage se fait dans chaque fold."""
    from lightgbm import LGBMClassifier
    from xgboost import XGBClassifier

    return [
        {
            "modele": "LightGBM",
            "strategie": "poids_faibles",
            "estimateur": LGBMClassifier(**PARAMS_LIGHTGBM_V11),
        },
        {
            "modele": "LightGBM",
            "strategie": "aucun",
            "estimateur": LGBMClassifier(**PARAMS_LIGHTGBM_V11),
        },
        {
            "modele": "XGBoost",
            "strategie": "poids_faibles_config_base",
            "estimateur": XGBClassifier(**PARAMS_XGBOOST),
        },
        {
            "modele": "XGBoost",
            "strategie": "poids_faibles_optuna",
            "estimateur": XGBClassifier(**params_xgboost_optimises),
        },
        {
            "modele": "LightGBM",
            "strategie": "smote",
            "estimateur": LGBMClassifier(**PARAMS_LIGHTGBM_V11),
        },
    ]


def _ajuster(estimateur, x, y, poids=None):
    if poids is not None:
        estimateur.fit(x, y, sample_weight=poids)
    else:
        estimateur.fit(x, y)
    return estimateur


def _evaluer_cv_groupee(
    dev: pd.DataFrame,
    features: list[str],
    candidats: list[dict[str, Any]],
    n_splits: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Évalue les candidats par CV stratifiée, sans partager un assuré entre les plis."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    from predicare.ml.evaluation import metriques_comparaison

    if "meta_assure_id" not in dev:
        raise ValueError("La CV groupée exige la colonne meta_assure_id.")
    if dev["meta_assure_id"].isna().any():
        raise ValueError("meta_assure_id contient des valeurs manquantes ; CV refusée.")

    y = dev[TARGET].astype(int).reset_index(drop=True)
    groupes = dev["meta_assure_id"].reset_index(drop=True)
    poids = dev["poids_echantillon"].astype(float).reset_index(drop=True)
    n_groupes = int(groupes.nunique())
    n_positifs = int(y.sum())
    folds_effectifs = min(n_splits, n_groupes, n_positifs)
    if folds_effectifs < 2:
        raise ValueError("La CV exige au moins deux groupes et deux exemples positifs.")

    numeriques, categorielles = _types_features(dev, features)
    splitter = StratifiedGroupKFold(n_splits=folds_effectifs, shuffle=True, random_state=SEED)
    partitions = list(splitter.split(dev[features], y, groupes))
    resultats: list[dict[str, Any]] = []
    sorties_oof: list[dict[str, Any]] = []

    for candidat in candidats:
        probabilites = np.full(len(dev), np.nan, dtype=float)
        resultats_folds: list[dict[str, Any]] = []
        for numero_fold, (indices_train, indices_val) in enumerate(partitions, start=1):
            groupes_train = set(groupes.iloc[indices_train])
            groupes_val = set(groupes.iloc[indices_val])
            if not groupes_train.isdisjoint(groupes_val):
                raise AssertionError(
                    "Fuite détectée : un assuré est présent dans deux côtés du fold."
                )

            df_train = dev.iloc[indices_train]
            df_val = dev.iloc[indices_val]
            y_train = y.iloc[indices_train]
            y_val = y.iloc[indices_val]
            preprocesseur = _preprocesseur(numeriques, categorielles)
            x_train = preprocesseur.fit_transform(df_train[features])
            x_val = preprocesseur.transform(df_val[features])
            estimateur = clone(candidat["estimateur"])
            poids_train = poids.iloc[indices_train].to_numpy()

            if candidat["strategie"] == "smote":
                from imblearn.over_sampling import SMOTE

                x_train, y_train_fit = SMOTE(random_state=SEED, sampling_strategy=0.5).fit_resample(
                    x_train, y_train
                )
                estimateur.fit(x_train, y_train_fit)
            else:
                poids_fit = (
                    poids_train if candidat["strategie"].startswith("poids_faibles") else None
                )
                _ajuster(estimateur, x_train, y_train, poids_fit)

            probabilites_fold = estimateur.predict_proba(x_val)[:, 1]
            probabilites[indices_val] = probabilites_fold
            resultats_folds.append(
                {
                    "fold": numero_fold,
                    "n_train": int(len(indices_train)),
                    "n_validation": int(len(indices_val)),
                    "positifs_validation": int(y_val.sum()),
                    "groupes_train": int(len(groupes_train)),
                    "groupes_validation": int(len(groupes_val)),
                    "pr_auc": float(average_precision_score(y_val, probabilites_fold)),
                    "roc_auc": float(roc_auc_score(y_val, probabilites_fold)),
                    "metriques_oof": metriques_comparaison(y_val, probabilites_fold),
                }
            )

        if np.isnan(probabilites).any():
            raise AssertionError("Certaines lignes n'ont pas reçu de prédiction out-of-fold.")
        scores_pr = [ligne["pr_auc"] for ligne in resultats_folds]
        resultats.append(
            {
                "modele": candidat["modele"],
                "strategie": candidat["strategie"],
                "cv_pr_auc_moyenne": float(np.mean(scores_pr)),
                "cv_pr_auc_ecart_type": float(np.std(scores_pr, ddof=1))
                if len(scores_pr) > 1
                else 0.0,
                "folds": resultats_folds,
                "metriques_oof_globales": metriques_comparaison(y, probabilites),
            }
        )
        sorties_oof.append(
            {
                "modele": candidat["modele"],
                "strategie": candidat["strategie"],
                "probabilites": probabilites,
            }
        )

    return resultats, sorties_oof


def _optimiser_hyperparametres_xgboost(
    dev: pd.DataFrame,
    features: list[str],
    n_trials: int = 20,
    n_splits: int = 5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Optimise XGBoost sur la PR-AUC CV groupée, sans consulter le Test."""
    import optuna
    from xgboost import XGBClassifier

    if n_trials < 1:
        raise ValueError("n_trials doit être supérieur ou égal à 1.")
    if n_splits < 2:
        raise ValueError("n_splits doit être supérieur ou égal à 2.")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=SEED),
    )

    def objectif(trial: optuna.Trial) -> float:
        params = {
            **PARAMS_XGBOOST,
            "max_depth": trial.suggest_int("max_depth", 3, 8),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 200, 700, step=50),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 12.0, log=True),
            "subsample": trial.suggest_float("subsample", 0.65, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.60, 1.0),
            "scale_pos_weight": trial.suggest_float("scale_pos_weight", 0.5, 12.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 10.0, log=True),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        candidat = {
            "modele": "XGBoost",
            "strategie": "poids_faibles_optuna_trial",
            "estimateur": XGBClassifier(**params),
        }
        resultats, _ = _evaluer_cv_groupee(dev, features, [candidat], n_splits=n_splits)
        resultat = resultats[0]
        trial.set_user_attr("cv_pr_auc_ecart_type", resultat["cv_pr_auc_ecart_type"])
        return resultat["cv_pr_auc_moyenne"]

    study.optimize(objectif, n_trials=n_trials, n_jobs=1)
    params_optimises = {**PARAMS_XGBOOST, **study.best_params}
    plis_effectifs = min(
        n_splits,
        int(dev["meta_assure_id"].nunique()),
        int(dev[TARGET].sum()),
    )
    rapport = {
        "methode": "Optuna TPE",
        "objectif": "moyenne PR-AUC en CV stratifiée groupée par meta_assure_id",
        "n_trials_demandes": n_trials,
        "n_trials_termines": len(study.trials),
        "n_splits": plis_effectifs,
        "graine": SEED,
        "meilleur_trial": study.best_trial.number,
        "meilleure_pr_auc_cv": float(study.best_value),
        "avertissement": (
            "La meilleure PR-AUC CV sert à sélectionner les paramètres et peut être optimiste "
            "après plusieurs essais ; le Test chronologique reste l'évaluation finale indépendante."
        ),
        "essais": [
            {
                "trial": trial.number,
                "etat": trial.state.name,
                "pr_auc_cv": float(trial.value) if trial.value is not None else None,
                "parametres": trial.params,
            }
            for trial in study.trials
        ],
        "ecart_type_pr_auc_cv_meilleur_trial": float(
            study.best_trial.user_attrs.get("cv_pr_auc_ecart_type", 0.0)
        ),
        "parametres_retenus": params_optimises,
    }
    return params_optimises, rapport


def entrainer_v2(
    dataset_path: str | Path = DATASET_V2,
    modele_path: str | Path | None = None,
    rapports_dir: str | Path | None = None,
    promouvoir: bool = True,
    n_trials: int = 20,
    n_splits: int = 5,
) -> dict:
    from sklearn.linear_model import LogisticRegression

    df = charger_dataset(dataset_path)
    features = _features(df)
    train = df[df["split"] == "train"].copy()
    validation = df[df["split"] == "validation"].copy()
    test = df[df["split"] == "test"].copy()
    dev = pd.concat([train, validation], ignore_index=True)
    if dev.empty or test.empty:
        raise ValueError("Les partitions Train, Validation et Test doivent être non vides.")

    params_xgboost, rapport_optimisation = _optimiser_hyperparametres_xgboost(
        dev, features, n_trials=n_trials, n_splits=n_splits
    )
    candidats = _candidats(params_xgboost)
    resultats_cv, predictions_oof = _evaluer_cv_groupee(dev, features, candidats, n_splits=n_splits)
    meilleur_index = max(
        range(len(resultats_cv)),
        key=lambda i: (
            resultats_cv[i]["cv_pr_auc_moyenne"],
            resultats_cv[i]["metriques_oof_globales"]["precision_a_recall80"],
        ),
    )
    meilleur = candidats[meilleur_index]
    probabilites_oof = predictions_oof[meilleur_index]["probabilites"]
    y_dev = dev[TARGET].astype(int).to_numpy()
    poids_dev = dev["poids_echantillon"].astype(float).to_numpy()

    numeriques, categorielles = _types_features(dev, features)
    preprocesseur_final = _preprocesseur(numeriques, categorielles)
    x_dev = preprocesseur_final.fit_transform(dev[features])
    x_test = preprocesseur_final.transform(test[features])
    estimateur_final = clone(meilleur["estimateur"])
    if meilleur["strategie"] == "smote":
        from imblearn.over_sampling import SMOTE

        x_fit, y_fit = SMOTE(random_state=SEED, sampling_strategy=0.5).fit_resample(x_dev, y_dev)
        estimateur_final.fit(x_fit, y_fit)
    else:
        poids_fit = poids_dev if meilleur["strategie"].startswith("poids_faibles") else None
        _ajuster(estimateur_final, x_dev, y_dev, poids_fit)

    probabilites_test_brutes = estimateur_final.predict_proba(x_test)[:, 1]
    calibrateur = CalibrateurPlatt(
        LogisticRegression(max_iter=1000).fit(probabilites_oof.reshape(-1, 1), y_dev)
    )
    probabilites_oof_cal = calibrateur.predict(probabilites_oof)
    probabilites_test_cal = calibrateur.predict(probabilites_test_brutes)

    seuil = seuil_pour_recall(y_dev, probabilites_oof_cal, RECALL_TARGET)
    seuil_brut = seuil_pour_recall(y_dev, probabilites_oof, RECALL_TARGET)
    metriques_test = metriques_seuil(test[TARGET], probabilites_test_cal, seuil)
    comparaison_test = metriques_comparaison(test[TARGET], probabilites_test_cal)
    metriques_test.update(
        {
            "pr_auc": comparaison_test["pr_auc"],
            "roc_auc": comparaison_test["roc_auc"],
            "brier": comparaison_test["brier"],
            "precision_a_recall80": comparaison_test["precision_a_recall80"],
            "pr_auc_ic95": intervalle_confiance_bootstrap(
                test[TARGET], probabilites_test_cal, "pr_auc"
            ),
            "roc_auc_ic95": intervalle_confiance_bootstrap(
                test[TARGET], probabilites_test_cal, "roc_auc"
            ),
            "ece": ece(test[TARGET], probabilites_test_cal)[0],
        }
    )

    metriques_oof = metriques_seuil(y_dev, probabilites_oof_cal, seuil)
    comparaison_oof = metriques_comparaison(y_dev, probabilites_oof_cal)
    metriques_oof.update(
        {
            "pr_auc": comparaison_oof["pr_auc"],
            "roc_auc": comparaison_oof["roc_auc"],
            "brier": comparaison_oof["brier"],
            "precision_a_recall80": comparaison_oof["precision_a_recall80"],
            "ece": ece(y_dev, probabilites_oof_cal)[0],
        }
    )

    seuils_budget = {
        str(budget): float(np.quantile(probabilites_oof_cal, 1 - budget))
        for budget in (0.01, 0.02, 0.03, 0.05, 0.10)
    }
    n_splits_effectifs = min(
        n_splits,
        int(dev["meta_assure_id"].nunique()),
        int(dev[TARGET].sum()),
    )
    rapport_cv = {
        "methode": "StratifiedGroupKFold",
        "n_splits": n_splits_effectifs,
        "graine": SEED,
        "groupe": "meta_assure_id",
        "partition_evaluee": "Train + Validation",
        "partition_test_exclue": True,
        "n_factures_developpement": int(len(dev)),
        "n_groupes_assures": int(dev["meta_assure_id"].nunique()),
        "n_features": len(features),
        "optimisation_hyperparametres": rapport_optimisation,
        "selection": "PR-AUC moyenne des folds ; précision OOF au rappel cible en départage",
        "candidats": resultats_cv,
        "candidat_retenu": {
            "modele": meilleur["modele"],
            "strategie": meilleur["strategie"],
        },
    }
    artefact = {
        "pipeline": Pipeline([("pre", preprocesseur_final), ("clf", estimateur_final)]),
        "calibrateur": calibrateur,
        "seuil_score_brut": float(seuil_brut),
        "seuil_probabilite_calibree": float(seuil),
        "seuil_produit": 0.80,
        "seuils_budget_validation": seuils_budget,
        "variables": features,
        "variables_numeriques": numeriques,
        "variables_categorielles": categorielles,
        "modele": meilleur["modele"],
        "traitement_desequilibre": meilleur["strategie"],
        "justification_desequilibre": (
            "Candidat sélectionné par PR-AUC moyenne en CV stratifiée groupée par assuré ; "
            "poids de labels faibles ou SMOTE ajusté dans chaque fold uniquement."
        ),
        "optimisation_hyperparametres": rapport_optimisation,
        "selection": (
            "CV à 5 plis groupée par assuré sur Train + Validation ; "
            "Test chronologique réservé à une évaluation finale."
        ),
        "validation_croisee": rapport_cv,
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
        "date_entrainement_donnees": str(dev["meta_date_reception"].max()),
        "date_creation": datetime.now(UTC).isoformat(),
        "version": VERSION,
        "dataset": str(dataset_path),
        "nb_features": len(features),
        "metriques_validation": metriques_oof,
        "metriques_test": metriques_test,
        "comparaison_modeles": resultats_cv,
    }

    modele_path = Path(modele_path) if modele_path else MODELS_V2 / "model.joblib"
    modele_path.parent.mkdir(parents=True, exist_ok=True)
    import joblib

    joblib.dump(artefact, modele_path)

    rapports_dir = Path(rapports_dir) if rapports_dir else REPORTS_V2
    rapports_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "modele": r["modele"],
                "strategie": r["strategie"],
                "cv_pr_auc_moyenne": r["cv_pr_auc_moyenne"],
                "cv_pr_auc_ecart_type": r["cv_pr_auc_ecart_type"],
                **{f"oof_{k}": v for k, v in r["metriques_oof_globales"].items()},
            }
            for r in resultats_cv
        ]
    ).to_csv(rapports_dir / "comparaison_modeles.csv", index=False)
    (rapports_dir / "cross_validation.json").write_text(
        json.dumps(rapport_cv, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    scores = pd.DataFrame(
        {
            "facture_id": test["facture_id"].to_numpy(),
            "probabilite": probabilites_test_cal,
            "score_risque": normaliser_score(probabilites_test_cal, seuil),
            "alerte": (probabilites_test_cal >= seuil).astype(int),
            "cible": test[TARGET].to_numpy(),
            "type_fraude": test["type_fraude"].to_numpy(),
            "confiance": test["confiance"].to_numpy(),
            "candidat": test["candidat"].to_numpy(),
            "montant_total": test["montant_total"].to_numpy(),
        }
    ).sort_values("score_risque", ascending=False)
    scores.to_csv(rapports_dir / "scores_test.csv", index=False)
    courbe_seuils(test[TARGET], probabilites_test_cal).to_csv(
        rapports_dir / "courbe_seuils_test.csv", index=False
    )
    courbe_seuils(y_dev, probabilites_oof_cal).to_csv(
        rapports_dir / "courbe_seuils_validation.csv", index=False
    )

    metadonnees_json = {k: v for k, v in artefact.items() if k not in {"pipeline", "calibrateur"}}
    (modele_path.parent / "metadata.json").write_text(
        json.dumps(metadonnees_json, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (rapports_dir / "metrics.json").write_text(
        json.dumps(
            {
                "version": VERSION,
                "modele": meilleur["modele"],
                "strategie": meilleur["strategie"],
                "validation": metriques_oof,
                "test": metriques_test,
                "cross_validation": rapport_cv,
                "seuils_budget_validation": seuils_budget,
                "comparaison": resultats_cv,
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
        "metriques_validation": metriques_oof,
        "metriques_test": metriques_test,
        "rapport_cv": rapport_cv,
        "modele_path": modele_path,
        "registre": entree,
        "scores_test": scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entraînement v2 sur labels faibles")
    parser.add_argument("--dataset", default=str(DATASET_V2))
    parser.add_argument("--modele", default=None)
    parser.add_argument("--rapports", default=None)
    parser.add_argument(
        "--trials", type=int, default=20, help="Nombre d'essais Optuna pour XGBoost"
    )
    parser.add_argument("--folds", type=int, default=5, help="Nombre de plis groupés")
    parser.add_argument("--sans-promotion", action="store_true")
    args = parser.parse_args(argv)

    resultat = entrainer_v2(
        dataset_path=args.dataset,
        modele_path=args.modele,
        rapports_dir=args.rapports,
        promouvoir=not args.sans_promotion,
        n_trials=args.trials,
        n_splits=args.folds,
    )
    m = resultat["metriques_test"]
    print(f"\nModèle {VERSION} — {resultat['artefact']['modele']}")
    print(f"Seuil calibré : {resultat['artefact']['seuil_probabilite_calibree']:.4f}")
    cv = resultat["rapport_cv"]
    modele_cv = next(
        c
        for c in cv["candidats"]
        if (c["modele"], c["strategie"])
        == (cv["candidat_retenu"]["modele"], cv["candidat_retenu"]["strategie"])
    )
    print(
        "CV PR-AUC : "
        f"{modele_cv['cv_pr_auc_moyenne']:.4f} "
        f"(écart-type {modele_cv['cv_pr_auc_ecart_type']:.4f}, {cv['n_splits']} plis)"
    )
    print(f"Test PR-AUC : {m['pr_auc']:.4f} (IC95 {m['pr_auc_ic95']})")
    print(f"Test ROC-AUC: {m['roc_auc']:.4f}")
    print(f"Test recall : {m['recall']:.4f} | précision : {m['precision']:.4f}")
    print(f"Alertes     : {m['nb_alertes']} ({m['part_alertee']:.2%}) | lift {m['lift']:.2f}")
    print(f"Registre    : {resultat['registre']['version']} [{resultat['registre']['statut']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
