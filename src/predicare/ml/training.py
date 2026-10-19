"""Entraînement, sélection et calibration du modèle B (contrôle médical).

Le module :
1. charge ``dataset_cm.csv`` (cible B) ;
2. ajuste le prétraitement sur le train uniquement ;
3. compare LightGBM et XGBoost, avec poids de classe et SMOTE ;
4. sélectionne le meilleur modèle sur la validation (PR-AUC) ;
5. calibre les probabilités (isotonique) et choisit le seuil au rappel cible ;
6. évalue sur le test et écrit l'artefact versionné + les rapports.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from predicare.ml.config import (
    DATA_RAW,
    DEFAULT_THRESHOLD,
    METADATA_PATH,
    MODEL_PATH,
    MODELS_DIR,
    PARAMS_LIGHTGBM,
    PARAMS_XGBOOST,
    RECALL_TARGET,
    REPORTS_DIR,
    SEED,
    TARGET,
    TARGET_DESCRIPTION,
    TARGET_LABEL,
)
from predicare.ml.evaluation import (
    courbe_seuils,
    ece,
    intervalle_confiance_bootstrap,
    metriques_comparaison,
    metriques_seuil,
    seuil_pour_recall,
)
from predicare.ml.targets import charger_dataset_cm

try:  # dépendances optionnelles au moment des tests unitaires
    from lightgbm import LGBMClassifier
except Exception:  # pragma: no cover
    LGBMClassifier = None  # type: ignore[assignment]

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None  # type: ignore[assignment]


def _colonnes_features(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Sépare variables numériques et catégorielles (hors colonnes techniques)."""
    from predicare.ml.config import META_COLUMNS

    exclues = set(META_COLUMNS)
    numeriques = [
        c
        for c in df.columns
        if c not in exclues and pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
    ]
    categorielles = [
        c
        for c in df.columns
        if c not in exclues
        and (pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]))
    ]
    return numeriques, categorielles


def _preprocesseur(numeriques: list[str], categorielles: list[str]):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import OneHotEncoder

    return ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median", add_indicator=True), numeriques),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", min_frequency=20, sparse_output=False),
                categorielles,
            ),
        ],
        remainder="drop",
    )


def _smote(X, y, ratio: float = 0.25, seed: int = SEED):  # noqa: N803
    """Sur-échantillonnage synthétique de la classe positive (CDC Module 2)."""
    try:
        from imblearn.over_sampling import SMOTE

        return SMOTE(random_state=seed, sampling_strategy=ratio).fit_resample(X, y)
    except Exception:  # pragma: no cover - repli si imblearn absent
        return X, y


def _candidats(numeriques: list[str], categorielles: list[str], scale_pos_weight: float):
    """Construit les candidats (modèle, stratégie de déséquilibre)."""
    candidats = []
    if LGBMClassifier is not None:
        candidats.append(
            (
                "LightGBM",
                "poids",
                LGBMClassifier(**PARAMS_LIGHTGBM, scale_pos_weight=scale_pos_weight),
            )
        )
        candidats.append(("LightGBM", "smote", LGBMClassifier(**PARAMS_LIGHTGBM)))
    if XGBClassifier is not None:
        candidats.append(
            (
                "XGBoost",
                "poids",
                XGBClassifier(**PARAMS_XGBOOST, scale_pos_weight=scale_pos_weight),
            )
        )
    if not candidats:
        raise ImportError("Aucun classifieur disponible (lightgbm / xgboost).")
    return candidats


def entrainer(
    dataset_path: Path | str | None = None,
    modele_path: Path | str | None = None,
    rapports_dir: Path | str | None = None,
    ecrire: bool = True,
) -> dict:
    """Entraîne, sélectionne, calibre et évalue le modèle B.

    Renvoie un dictionnaire contenant l'artefact et les métriques.
    """
    from sklearn.isotonic import IsotonicRegression
    from sklearn.pipeline import Pipeline

    df = charger_dataset_cm(dataset_path)
    if TARGET not in df:
        raise ValueError(f"Cible {TARGET!r} absente du dataset.")

    numeriques, categorielles = _colonnes_features(df)
    variables = numeriques + categorielles

    train = df[df["split"] == "train"].copy()
    validation = df[df["split"] == "validation"].copy()
    test = df[df["split"] == "test"].copy()

    y_train = train[TARGET].to_numpy()
    y_val = validation[TARGET].to_numpy()
    y_test = test[TARGET].to_numpy()
    neg, pos = int((y_train == 0).sum()), int((y_train == 1).sum())
    scale_pos_weight = neg / max(pos, 1)

    lignes = []
    meilleur = None

    for nom, strategie, estimateur in _candidats(numeriques, categorielles, scale_pos_weight):
        pre = _preprocesseur(numeriques, categorielles)
        X_train = pre.fit_transform(train[variables])
        X_val = pre.transform(validation[variables])
        X_test = pre.transform(test[variables])

        if strategie == "smote":
            X_fit, y_fit = _smote(X_train, y_train)
        else:
            X_fit, y_fit = X_train, y_train

        estimateur.fit(X_fit, y_fit)
        p_val = estimateur.predict_proba(X_val)[:, 1]
        p_test = estimateur.predict_proba(X_test)[:, 1]
        m_val = metriques_comparaison(y_val, p_val)
        m_test = metriques_comparaison(y_test, p_test)
        lignes.append(
            {
                "modele": nom,
                "strategie": strategie,
                **{f"val_{k}": v for k, v in m_val.items()},
                **{f"test_{k}": v for k, v in m_test.items()},
            }
        )

        cle = (m_val["pr_auc"], m_val["precision_a_recall80"])
        if meilleur is None or cle > meilleur["cle"]:
            meilleur = {
                "cle": cle,
                "nom": nom,
                "strategie": strategie,
                "estimateur": estimateur,
                "pipeline": Pipeline([("pre", pre), ("clf", estimateur)]),
                "p_val": p_val,
                "p_test": p_test,
                "m_val": m_val,
                "m_test": m_test,
            }

    if meilleur is None:
        raise RuntimeError("Aucun modèle n'a pu être entraîné.")

    # Calibration isotonique sur la validation.
    calibrateur = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    calibrateur.fit(meilleur["p_val"], y_val)
    p_val_cal = calibrateur.predict(meilleur["p_val"])
    p_test_cal = calibrateur.predict(meilleur["p_test"])

    seuil_cal = seuil_pour_recall(y_val, p_val_cal, RECALL_TARGET)
    seuil_brut = seuil_pour_recall(y_val, meilleur["p_val"], RECALL_TARGET)

    m_test = metriques_seuil(y_test, p_test_cal, seuil_cal)
    m_test["pr_auc"] = meilleur["m_test"]["pr_auc"]
    m_test["roc_auc"] = meilleur["m_test"]["roc_auc"]
    m_test["brier"] = meilleur["m_test"]["brier"]
    m_test["pr_auc_ic95"] = intervalle_confiance_bootstrap(y_test, p_test_cal, "pr_auc")
    m_test["roc_auc_ic95"] = intervalle_confiance_bootstrap(y_test, p_test_cal, "roc_auc")
    m_test["ece"] = ece(y_test, p_test_cal)[0]
    m_test["seuil_produit_0_80"] = metriques_seuil(y_test, p_test_cal, DEFAULT_THRESHOLD)

    artefact = {
        "pipeline": meilleur["pipeline"],
        "calibrateur": calibrateur,
        "seuil_score_brut": float(seuil_brut),
        "seuil_probabilite_calibree": float(seuil_cal),
        "seuil_produit": float(DEFAULT_THRESHOLD),
        "variables": variables,
        "variables_numeriques": numeriques,
        "variables_categorielles": categorielles,
        "modele": meilleur["nom"],
        "traitement_desequilibre": meilleur["strategie"],
        "recall_cible_validation": RECALL_TARGET,
        "graine": SEED,
        "cible": TARGET_LABEL,
        "cible_description": TARGET_DESCRIPTION,
        "date_entrainement_donnees": str(train["meta_date_reception"].max()),
        "date_creation": datetime.now(UTC).isoformat(),
        "version": "v1.0.0",
        "metriques_validation": meilleur["m_val"],
        "metriques_test": {
            k: v for k, v in m_test.items() if not isinstance(v, dict)
        },
        "point_produit_0_80": m_test["seuil_produit_0_80"],
        "labellisation": (
            "Proxy : motif de rejet CONTROLE_MEDICAL. "
            "Aucun label de fraude confirmée n'est disponible dans le jeu fourni."
        ),
    }

    if ecrire:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        rapports_dir = Path(rapports_dir) if rapports_dir else REPORTS_DIR
        rapports_dir.mkdir(parents=True, exist_ok=True)
        modele_path = Path(modele_path) if modele_path else MODEL_PATH

        import joblib

        joblib.dump(artefact, modele_path)

        pd.DataFrame(lignes).to_csv(rapports_dir / "comparaison_modeles.csv", index=False)
        courbe_seuils(y_test, p_test_cal).to_csv(
            rapports_dir / "courbe_seuils_test.csv", index=False
        )
        pd.DataFrame(
            {
                "facture_id": test["facture_id"].to_numpy(),
                "y": y_test,
                "score": meilleur["p_test"],
                "score_calibre": p_test_cal,
                "probabilite": p_test_cal,
                "score_risque": __import__(
                    "predicare.ml.scoring", fromlist=["normaliser_score"]
                ).normaliser_score(p_test_cal, seuil_cal),
                "alerte": (p_test_cal >= seuil_cal).astype(int),
            }
        ).to_csv(DATA_RAW / "scores_test_cm.csv", index=False)
        (rapports_dir / "metriques_test.json").write_text(
            json.dumps(
                {k: v for k, v in m_test.items() if not isinstance(v, dict)},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        METADATA_PATH.write_text(
            json.dumps(
                {
                    k: v
                    for k, v in artefact.items()
                    if k
                    in {
                        "modele",
                        "traitement_desequilibre",
                        "variables",
                        "variables_numeriques",
                        "variables_categorielles",
                        "seuil_score_brut",
                        "seuil_probabilite_calibree",
                        "seuil_produit",
                        "version",
                        "cible",
                        "cible_description",
                        "date_creation",
                        "metriques_test",
                        "labellisation",
                    }
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return {
        "artefact": artefact,
        "comparaison": pd.DataFrame(lignes),
        "metriques_test": m_test,
        "y_test": y_test,
        "p_test_cal": p_test_cal,
    }


def main() -> None:  # pragma: no cover - point d'entrée CLI
    resultat = entrainer()
    m = resultat["metriques_test"]
    print(f"Modèle retenu : {resultat['artefact']['modele']} "
          f"({resultat['artefact']['traitement_desequilibre']})")
    print(f"Seuil calibration : {resultat['artefact']['seuil_probabilite_calibree']:.4f}")
    print(f"Test PR-AUC : {m['pr_auc']:.4f} (IC95 {m['pr_auc_ic95']})")
    print(f"Test ROC-AUC: {m['roc_auc']:.4f} (IC95 {m['roc_auc_ic95']})")
    print(f"Test recall : {m['recall']:.4f} | précision : {m['precision']:.4f}")
    print(f"Point produit 0.80 : {m['seuil_produit_0_80']}")


if __name__ == "__main__":  # pragma: no cover
    main()
