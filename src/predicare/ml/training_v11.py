"""v1.1.0 — modèle LightGBM régularisé, sélectionné par validation croisée.

La v1.0.0 avait été choisie sur la validation (120 positifs), puis évaluée sur
le test : ce protocole est instable. La v1.1.0 est sélectionnée par validation
croisée 5 plis × 3 graines **sur le train**, puis évaluée une seule fois sur le
test (holdout). Le test n'a jamais servi à choisir les hyperparamètres.

Apports mesurés (voir ``reports/ml/v11/comparaison_cv.csv``) :

* CV PR-AUC : v1.1.0 ≈ v1.0.0 (0,151 vs 0,151) mais **variance plus faible**
  (0,011 vs 0,016) grâce à une régularisation plus forte (9 feuilles au lieu
  de 31, 91 échantillons minimum par feuille) ;
* holdout test : PR-AUC 0,175 vs 0,141 pour la v1.0.0.

Les variables PB-09 et réseau/vélocité ont été testées : elles **n'améliorent
pas** la validation croisée et ne sont donc pas retenues (voir
``docs/experiments_v11.md``).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from predicare.ml.config import (
    MODELS_DIR_V11,
    PARAMS_LIGHTGBM,
    PARAMS_LIGHTGBM_V11,
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

VERSION = "v1.1.0"
REPORTS_V11 = REPORTS_DIR / "v11"


def _matrices(df: pd.DataFrame):
    """Prétraite les trois splits (ajustement sur le train uniquement)."""
    from predicare.ml.training import _colonnes_features, _preprocesseur

    numeriques, categorielles = _colonnes_features(df)
    variables = numeriques + categorielles
    pre = _preprocesseur(numeriques, categorielles)

    train = df[df["split"] == "train"].copy()
    validation = df[df["split"] == "validation"].copy()
    test = df[df["split"] == "test"].copy()
    X_train = pre.fit_transform(train[variables])
    X_val = pre.transform(validation[variables])
    X_test = pre.transform(test[variables])
    return {
        "pre": pre,
        "variables": variables,
        "numeriques": numeriques,
        "categorielles": categorielles,
        "train": train,
        "validation": validation,
        "test": test,
        "X_train": X_train,
        "X_val": X_val,
        "X_test": X_test,
    }


def _lightgbm(params: dict):
    from lightgbm import LGBMClassifier

    return LGBMClassifier(**params)


def entrainer_v11(
    dataset_path: Path | str | None = None,
    modele_path: Path | str | None = None,
    rapports_dir: Path | str | None = None,
    ecrire: bool = True,
    promouvoir: bool = True,
) -> dict:
    """Entraîne, calibre, évalue et enregistre la v1.1.0."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    from predicare.ml.scoring import CalibrateurPlatt, normaliser_score

    df = charger_dataset_cm(dataset_path)
    if TARGET not in df:
        raise ValueError(f"Cible {TARGET!r} absente du dataset.")
    m = _matrices(df)

    y_train = m["train"][TARGET].to_numpy()
    y_val = m["validation"][TARGET].to_numpy()
    y_test = m["test"][TARGET].to_numpy()

    estimateur = _lightgbm(PARAMS_LIGHTGBM_V11)
    estimateur.fit(m["X_train"], y_train)
    p_val = estimateur.predict_proba(m["X_val"])[:, 1]
    p_test = estimateur.predict_proba(m["X_test"])[:, 1]

    # Calibration de Platt (validation) : strictement croissante, donc compatible
    # avec un seuil par budget d'alertes.
    calibrateur = CalibrateurPlatt(
        LogisticRegression().fit(p_val.reshape(-1, 1), y_val)
    )
    p_val_cal = calibrateur.predict(p_val)
    p_test_cal = calibrateur.predict(p_test)

    seuil = seuil_pour_recall(y_val, p_val_cal, RECALL_TARGET)
    seuil_brut = seuil_pour_recall(y_val, p_val, RECALL_TARGET)

    m_test = metriques_seuil(y_test, p_test_cal, seuil)
    m_test["pr_auc"] = float(metriques_comparaison(y_test, p_test_cal)["pr_auc"])
    m_test["roc_auc"] = float(metriques_comparaison(y_test, p_test_cal)["roc_auc"])
    m_test["brier"] = float(metriques_comparaison(y_test, p_test_cal)["brier"])
    m_test["pr_auc_ic95"] = intervalle_confiance_bootstrap(y_test, p_test_cal, "pr_auc")
    m_test["roc_auc_ic95"] = intervalle_confiance_bootstrap(y_test, p_test_cal, "roc_auc")
    m_test["ece"] = ece(y_test, p_test_cal)[0]
    m_test["precision_a_recall80"] = float(
        metriques_comparaison(y_test, p_test_cal)["precision_a_recall80"]
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
        "variables": m["variables"],
        "variables_numeriques": m["numeriques"],
        "variables_categorielles": m["categorielles"],
        "modele": "LightGBM",
        "traitement_desequilibre": "aucun",
        "justification_desequilibre": (
            "Poids de classe et SMOTE testés : PR-AUC de validation inférieure "
            "(0,138 / 0,130 vs 0,156). Le signal métier porte l'essentiel."
        ),
        "selection": (
            "Validation croisée 5 plis × 3 graines sur le train ; holdout test "
            "évalué une seule fois."
        ),
        "recall_cible_validation": RECALL_TARGET,
        "graine": SEED,
        "cible": TARGET_LABEL,
        "cible_description": TARGET_DESCRIPTION,
        "date_entrainement_donnees": str(m["train"]["meta_date_reception"].max()),
        "date_creation": datetime.now(UTC).isoformat(),
        "version": VERSION,
        "metriques_validation": metriques_comparaison(y_val, p_val_cal),
        "metriques_test": {k: v for k, v in m_test.items() if not isinstance(v, dict)},
        "labellisation": (
            "Proxy : motif de rejet CONTROLE_MEDICAL. "
            "Aucun label de fraude confirmée n'est disponible dans le jeu fourni."
        ),
    }

    scores_test = pd.DataFrame(
        {
            "facture_id": m["test"]["facture_id"].to_numpy(),
            "y": y_test,
            "score": p_test,
            "probabilite": p_test_cal,
            "alerte": (p_test_cal >= seuil).astype(int),
        }
    )
    scores_test["score_risque"] = normaliser_score(p_test_cal, seuil)
    if "montant_total" in m["test"]:
        scores_test["montant_total"] = m["test"]["montant_total"].to_numpy()

    if ecrire:
        rapports_dir = Path(rapports_dir) if rapports_dir else REPORTS_V11
        rapports_dir.mkdir(parents=True, exist_ok=True)
        modele_path = Path(modele_path) if modele_path else MODELS_DIR_V11 / "model.joblib"
        modele_path.parent.mkdir(parents=True, exist_ok=True)

        import joblib

        joblib.dump(artefact, modele_path)

        pd.DataFrame(
            [
                {
                    "version": "v1.0.0",
                    "selection": "validation",
                    "strategie_retenue": "aucun (repli SMOTE silencieux)",
                    "test_pr_auc": 0.1412,
                    "test_recall": 0.8203,
                    "test_precision": 0.1343,
                },
                {
                    "version": VERSION,
                    "selection": "validation croisée (train)",
                    "strategie_retenue": "aucun",
                    "test_pr_auc": m_test["pr_auc"],
                    "test_recall": m_test["recall"],
                    "test_precision": m_test["precision"],
                },
            ]
        ).to_csv(rapports_dir / "comparaison_v10_v11.csv", index=False)
        courbe_seuils(y_test, p_test_cal).to_csv(
            rapports_dir / "courbe_seuils_test.csv", index=False
        )
        scores_test.to_csv(rapports_dir / "scores_test.csv", index=False)
        (rapports_dir / "metriques_test.json").write_text(
            json.dumps(
                {k: v for k, v in m_test.items() if not isinstance(v, dict)},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (MODELS_DIR_V11 / "metadata.json").write_text(
            json.dumps(
                {
                    k: artefact[k]
                    for k in (
                        "modele",
                        "traitement_desequilibre",
                        "justification_desequilibre",
                        "selection",
                        "variables",
                        "seuil_score_brut",
                        "seuil_probabilite_calibree",
                        "seuil_produit",
                        "seuils_budget_validation",
                        "version",
                        "cible",
                        "cible_description",
                        "date_creation",
                        "metriques_validation",
                        "metriques_test",
                        "labellisation",
                    )
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

        from predicare.ml import registry

        registry.enregistrer_version(
            VERSION,
            modele_path,
            metadonnees={
                "modele": "LightGBM",
                "strategie": "aucun",
                "selection": "validation croisée",
                "test_pr_auc": m_test["pr_auc"],
                "test_recall": m_test["recall"],
                "test_precision": m_test["precision"],
                "cible": TARGET_LABEL,
            },
            statut="staging",
            promouvoir=promouvoir,
        )

    return {
        "artefact": artefact,
        "metriques_test": m_test,
        "scores_test": scores_test,
        "matrices": m,
    }


def comparer_cv(
    dataset_path: Path | str | None = None,
    graines=(42, 7, 2024),
    plis: int = 5,
) -> pd.DataFrame:
    """Compare v1.0.0, v1.1.0, XGBoost et l'ensemble par validation croisée."""
    from sklearn.metrics import average_precision_score
    from sklearn.model_selection import StratifiedKFold
    from xgboost import XGBClassifier

    from predicare.ml.config import PARAMS_XGBOOST

    df = charger_dataset_cm(dataset_path)
    m = _matrices(df)
    X, y = m["X_train"], m["train"][TARGET].to_numpy()

    resultats: dict[str, list[float]] = {
        "v1.0.0": [],
        "v1.1.0": [],
        "xgboost": [],
        "ensemble": [],
    }
    for graine in graines:
        skf = StratifiedKFold(n_splits=plis, shuffle=True, random_state=graine)
        for tr_idx, va_idx in skf.split(X, y):
            p = {}
            modele = _lightgbm(PARAMS_LIGHTGBM)
            modele.fit(X[tr_idx], y[tr_idx])
            p["v1.0.0"] = modele.predict_proba(X[va_idx])[:, 1]

            modele = _lightgbm(PARAMS_LIGHTGBM_V11)
            modele.fit(X[tr_idx], y[tr_idx])
            p["v1.1.0"] = modele.predict_proba(X[va_idx])[:, 1]

            params_xgb = {**PARAMS_XGBOOST, "max_depth": 4, "min_child_weight": 7}
            modele = XGBClassifier(**params_xgb)
            modele.fit(X[tr_idx], y[tr_idx])
            p["xgboost"] = modele.predict_proba(X[va_idx])[:, 1]
            p["ensemble"] = (p["v1.1.0"] + p["xgboost"]) / 2

            for nom, proba in p.items():
                resultats[nom].append(average_precision_score(y[va_idx], proba))

    lignes = []
    for nom, valeurs in resultats.items():
        valeurs = np.asarray(valeurs)
        lignes.append(
            {
                "modele": nom,
                "cv_pr_auc_moyenne": float(valeurs.mean()),
                "cv_pr_auc_ecart_type": float(valeurs.std()),
                "cv_pr_auc_min": float(valeurs.min()),
                "cv_pr_auc_max": float(valeurs.max()),
                "nb_plis": len(valeurs),
            }
        )
    return pd.DataFrame(lignes)


def main() -> None:  # pragma: no cover - CLI
    parseur = argparse.ArgumentParser(description="Entraînement du modèle v1.1.0")
    parseur.add_argument("--cv", action="store_true", help="recalcule la comparaison CV")
    parseur.add_argument("--sans-promotion", action="store_true", help="laisse en staging")
    args = parseur.parse_args()

    if args.cv:
        REPORTS_V11.mkdir(parents=True, exist_ok=True)
        table = comparer_cv()
        table.to_csv(REPORTS_V11 / "comparaison_cv.csv", index=False)
        print(table.to_string(index=False))

    resultat = entrainer_v11(promouvoir=not args.sans_promotion)
    metriques = resultat["metriques_test"]
    print(f"Modèle {VERSION} — {resultat['artefact']['modele']}")
    print(f"Seuil calibré : {resultat['artefact']['seuil_probabilite_calibree']:.4f}")
    print(f"Test PR-AUC : {metriques['pr_auc']:.4f} (IC95 {metriques['pr_auc_ic95']})")
    print(f"Test ROC-AUC: {metriques['roc_auc']:.4f}")
    print(f"Test recall : {metriques['recall']:.4f} | précision : {metriques['precision']:.4f}")
    print(f"Alertes     : {metriques['nb_alertes']} ({metriques['part_alertee']:.2%})")


if __name__ == "__main__":  # pragma: no cover
    main()
