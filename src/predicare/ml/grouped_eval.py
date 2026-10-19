"""Évaluation groupée par prestataire — généralisation à de nouveaux acteurs.

Deux questions distinctes :

1. **Validation croisée groupée** (``GroupKFold``) sur le train : les plis sont
   séparés par prestataire, ce qui mesure la capacité du modèle à scorer des
   prestataires qu'il n'a jamais vus. À comparer à la CV aléatoire.
2. **Démarrage à froid** sur le test : part des factures dont le prestataire
   est absent du train, et performance sur ce sous-ensemble. C'est le cas réel
   d'un nouveau prestataire conventionné.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from predicare.ml.config import PARAMS_LIGHTGBM_V11, REPORTS_DIR, TARGET
from predicare.ml.evaluation import intervalle_confiance_bootstrap
from predicare.ml.targets import charger_dataset_cm

REPORTS_V11 = REPORTS_DIR / "v11"


def validation_croisee_groupee(
    dataset: pd.DataFrame | None = None,
    plis: int = 5,
) -> pd.DataFrame:
    """PR-AUC en validation croisée groupée par prestataire."""
    from lightgbm import LGBMClassifier
    from sklearn.metrics import average_precision_score
    from sklearn.model_selection import GroupKFold

    from predicare.ml.training import _colonnes_features, _preprocesseur

    dataset = dataset if dataset is not None else charger_dataset_cm()
    train = dataset[dataset["split"] == "train"].copy()
    numeriques, categorielles = _colonnes_features(dataset)
    variables = numeriques + categorielles
    y = train[TARGET].to_numpy()
    groupes = train["meta_prestataire_id"].to_numpy()

    lignes = []
    gkf = GroupKFold(n_splits=plis)
    for numero, (tr_idx, va_idx) in enumerate(gkf.split(train, y, groupes), start=1):
        pre = _preprocesseur(numeriques, categorielles)
        X_tr = pre.fit_transform(train.iloc[tr_idx][variables])
        X_va = pre.transform(train.iloc[va_idx][variables])
        modele = LGBMClassifier(**PARAMS_LIGHTGBM_V11)
        modele.fit(X_tr, y[tr_idx])
        proba = modele.predict_proba(X_va)[:, 1]
        lignes.append(
            {
                "pli": numero,
                "n_validation": int(len(va_idx)),
                "positifs": int(y[va_idx].sum()),
                "prestataires_validation": int(len(set(groupes[va_idx]))),
                "pr_auc": float(average_precision_score(y[va_idx], proba)),
            }
        )
    return pd.DataFrame(lignes)


def demarrage_a_froid(
    dataset: pd.DataFrame | None = None,
    scores: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Performance sur les prestataires vus vs jamais vus pendant l'entraînement."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    dataset = dataset if dataset is not None else charger_dataset_cm()
    scores = (
        scores
        if scores is not None
        else pd.read_csv(REPORTS_V11 / "scores_test.csv")
    )
    train = dataset[dataset["split"] == "train"]
    test = dataset[dataset["split"] == "test"][
        ["facture_id", "meta_prestataire_id", TARGET]
    ]
    vus = set(train["meta_prestataire_id"])
    test = test.merge(scores[["facture_id", "probabilite"]], on="facture_id", how="left")
    test["prestataire_vu"] = test["meta_prestataire_id"].isin(vus)

    lignes = []
    for vu, bloc in test.groupby("prestataire_vu"):
        y = bloc[TARGET].to_numpy()
        p = bloc["probabilite"].to_numpy()
        ic = intervalle_confiance_bootstrap(y, p, "pr_auc") if y.sum() >= 5 else (np.nan, np.nan)
        lignes.append(
            {
                "prestataire_vu": bool(vu),
                "n": int(len(bloc)),
                "part_factures": float(len(bloc) / len(test)),
                "positifs": int(y.sum()),
                "prevalence": float(y.mean()),
                "pr_auc": float(average_precision_score(y, p)),
                "pr_auc_ic_bas": float(ic[0]),
                "pr_auc_ic_haut": float(ic[1]),
                "roc_auc": float(roc_auc_score(y, p)) if y.sum() and y.sum() < len(y) else np.nan,
            }
        )
    return pd.DataFrame(lignes)


def rapport_markdown(cv: pd.DataFrame, froid: pd.DataFrame) -> str:
    """Rapport lisible sur la généralisation par prestataire."""
    moyenne = cv["pr_auc"].mean()
    ecart = cv["pr_auc"].std()
    lignes = [
        "# Évaluation groupée par prestataire",
        "",
        "## Validation croisée groupée (train)",
        "",
        "| Protocole | PR-AUC moyenne | Écart-type | Plis |",
        "|---|---:|---:|---:|",
        f"| GroupKFold par prestataire | {moyenne:.4f} | {ecart:.4f} | {len(cv)} |",
        "| StratifiedKFold aléatoire (référence) | 0,1461 | 0,0143 | 15 |",
        "",
        "Les plis groupés empêchent le modèle de mémoriser un prestataire : "
        "l'écart avec la CV aléatoire mesure la dépendance à l'identité de "
        "l'acteur.",
        "",
        "## Démarrage à froid sur le test",
        "",
        "| Prestataire vu en train | n | Part | Positifs | Prévalence | PR-AUC (IC95) |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for _, r in froid.iterrows():
        libelle = "oui" if r["prestataire_vu"] else "**non (nouveau)**"
        if int(r["positifs"]) == 0:
            ic = "n/a (aucun positif)"
        elif r["pr_auc_ic_bas"] == r["pr_auc_ic_bas"]:
            ic = f"{r['pr_auc']:.4f} [{r['pr_auc_ic_bas']:.3f}–{r['pr_auc_ic_haut']:.3f}]"
        else:
            ic = f"{r['pr_auc']:.4f}"
        lignes.append(
            f"| {libelle} | {int(r['n'])} | {r['part_factures']:.1%} | "
            f"{int(r['positifs'])} | {r['prevalence']:.2%} | {ic} |"
        )
    lignes += [
        "",
        "## Lecture",
        "",
        "- Si la PR-AUC groupée reste proche de la CV aléatoire, le modèle "
        "s'appuie sur des signaux transférables (comportement de facturation) "
        "et non sur l'identité du prestataire.",
        "- Les prestataires nouveaux sont le cas critique en production : "
        "leur performance conditionne l'utilité réelle du système.",
        "- Les effectifs par pli restent modestes (≈ 140 positifs par pli) : "
        "les intervalles sont larges.",
        "",
        "## Limites",
        "",
        "- Données synthétiques : la structure des prestataires peut être plus "
        "régulière que dans la réalité.",
        "- La cible reste un proxy administratif, pas une fraude confirmée.",
    ]
    return "\n".join(lignes)


def main() -> None:  # pragma: no cover - CLI
    REPORTS_V11.mkdir(parents=True, exist_ok=True)
    cv = validation_croisee_groupee()
    froid = demarrage_a_froid()
    cv.to_csv(REPORTS_V11 / "evaluation_groupee_cv.csv", index=False)
    froid.to_csv(REPORTS_V11 / "evaluation_groupee_froid.csv", index=False)
    from predicare.ml.config import DOCS_DIR

    (DOCS_DIR / "evaluation_groupee.md").write_text(
        rapport_markdown(cv, froid), encoding="utf-8"
    )
    print(cv.to_string(index=False))
    print(froid.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
