"""Expériences v1.1 — apport des variables PB-09 / réseau et du déséquilibre.

Le résultat est **négatif** et documenté comme tel : ni les alertes
prescription PB-09, ni les variables réseau/vélocité ne battent les 100
variables de base. Les stratégies de déséquilibre (poids, SMOTE) dégradent la
PR-AUC de validation.

Reproduction : ``python -m predicare.ml.experiments_v11``.
Sortie : ``reports/ml/v11/experiments_jeux_variables.csv``.
"""

from __future__ import annotations

import pandas as pd

from predicare.ml.config import PARAMS_LIGHTGBM, REPORTS_DIR, TARGET
from predicare.ml.evaluation import metriques_comparaison
from predicare.ml.network_features import (
    VARIABLES_PB09,
    VARIABLES_RESEAU,
    charger_dataset_v11,
)
from predicare.ml.training import _colonnes_features, _preprocesseur, _smote

REPORTS_V11 = REPORTS_DIR / "v11"

JEUX = {
    "base (100 variables)": lambda base, pb09, reseau: base,
    "base + PB-09": lambda base, pb09, reseau: base + pb09,
    "base + réseau": lambda base, pb09, reseau: base + reseau,
    "base + PB-09 + réseau": lambda base, pb09, reseau: base + pb09 + reseau,
}


def comparer_jeux_variables(
    dataset: pd.DataFrame | None = None,
    strategies=("aucun", "poids", "smote"),
) -> pd.DataFrame:
    """PR-AUC de validation pour chaque jeu de variables et stratégie."""
    from lightgbm import LGBMClassifier

    dataset = dataset if dataset is not None else charger_dataset_v11()
    numeriques, categorielles = _colonnes_features(dataset)
    toutes = numeriques + categorielles
    reseau = [c for c in toutes if c in VARIABLES_RESEAU]
    pb09 = [c for c in toutes if c in VARIABLES_PB09]
    base = [c for c in toutes if c not in set(reseau) | set(pb09)]

    train = dataset[dataset["split"] == "train"]
    validation = dataset[dataset["split"] == "validation"]
    y_train = train[TARGET].to_numpy()
    y_val = validation[TARGET].to_numpy()
    poids = (len(y_train) - y_train.sum()) / max(y_train.sum(), 1)

    lignes = []
    for nom, selecteur in JEUX.items():
        variables = selecteur(base, pb09, reseau)
        num = [c for c in variables if c in numeriques]
        cat = [c for c in variables if c in categorielles]
        pre = _preprocesseur(num, cat)
        X_train = pre.fit_transform(train[variables])
        X_val = pre.transform(validation[variables])
        for strategie in strategies:
            if strategie == "smote":
                X_fit, y_fit = _smote(X_train, y_train)
                modele = LGBMClassifier(**PARAMS_LIGHTGBM)
            elif strategie == "poids":
                X_fit, y_fit = X_train, y_train
                modele = LGBMClassifier(**PARAMS_LIGHTGBM, scale_pos_weight=poids)
            else:
                X_fit, y_fit = X_train, y_train
                modele = LGBMClassifier(**PARAMS_LIGHTGBM)
            modele.fit(X_fit, y_fit)
            proba = modele.predict_proba(X_val)[:, 1]
            metriques = metriques_comparaison(y_val, proba)
            lignes.append(
                {
                    "jeu_variables": nom,
                    "nb_variables": len(variables),
                    "strategie": strategie,
                    "pr_auc_validation": metriques["pr_auc"],
                    "precision_a_recall80": metriques["precision_a_recall80"],
                    "roc_auc": metriques["roc_auc"],
                }
            )
    return pd.DataFrame(lignes)


def main() -> None:  # pragma: no cover - CLI
    REPORTS_V11.mkdir(parents=True, exist_ok=True)
    table = comparer_jeux_variables()
    table.to_csv(REPORTS_V11 / "experiments_jeux_variables.csv", index=False)
    print(
        table.sort_values("pr_auc_validation", ascending=False).to_string(index=False)
    )


if __name__ == "__main__":  # pragma: no cover
    main()
