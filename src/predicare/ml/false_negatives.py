"""PB-10 — Analyse des faux négatifs et amélioration mesurée.

Le modèle B est un filtre de précision : il rate une partie des dossiers
réellement orientés contrôle médical. Ce module :

* liste les faux négatifs et les segmente (type de règle, gravité, montant,
  type de facture, prestataire) ;
* compare le profil des faux négatifs à celui des vrais positifs ;
* teste une amélioration concrète : ajout des alertes prescription PB-09 comme
  variables, avec mesure avant / après sur le test.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from predicare.ml.config import (
    ALERTES_FACTURES,
    DATA_RAW,
    PARAMS_LIGHTGBM,
    REFERENCE_DIR,
    REPORTS_DIR,
    SEED,
    TARGET,
)
from predicare.ml.evaluation import metriques_comparaison, seuil_pour_recall
from predicare.ml.targets import charger_dataset_cm

TRANCHES_MONTANT = [0, 10_000, 25_000, 50_000, 100_000, 250_000, np.inf]
LABELS_MONTANT = ["<10k", "10-25k", "25-50k", "50-100k", "100-250k", ">250k"]


def _tranche_montant(serie: pd.Series) -> pd.Series:
    return pd.cut(serie, bins=TRANCHES_MONTANT, labels=LABELS_MONTANT, right=False)


def _charger_alertes(alertes_path: Path | str | None = None) -> pd.DataFrame:
    chemin = Path(alertes_path) if alertes_path else ALERTES_FACTURES
    if not chemin.is_file():
        chemin = REFERENCE_DIR / "alertes_factures_detail.csv"
    if not chemin.is_file():
        return pd.DataFrame(columns=["facture_id", "code_fraude", "gravite"])
    return pd.read_csv(chemin, low_memory=False)


def analyser(
    dataset: pd.DataFrame | None = None,
    scores: pd.DataFrame | None = None,
    alertes: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """Analyse descriptive des faux négatifs du modèle B sur le test."""
    dataset = dataset if dataset is not None else charger_dataset_cm()
    if scores is None:
        scores = pd.read_csv(DATA_RAW / "scores_test_cm.csv")
    alertes = alertes if alertes is not None else _charger_alertes()

    test = dataset[dataset["split"] == "test"].copy()
    colonnes_scores = ["facture_id", "alerte"]
    if "probabilite" in scores.columns:
        colonnes_scores += ["probabilite", "score_risque"]
    else:
        scores = scores.rename(columns={"score_calibre": "probabilite"})
        if "score_risque" not in scores.columns:
            from predicare.ml.scoring import normaliser_score

            seuil = float(scores["probabilite"].max())  # repli : simple normalisation
            scores["score_risque"] = normaliser_score(scores["probabilite"], max(seuil, 1e-6))
        colonnes_scores += ["probabilite", "score_risque"]
    test = test.merge(scores[colonnes_scores], on="facture_id")

    pos = test[test[TARGET] == 1].copy()
    fn = pos[pos["alerte"] == 0].copy()
    tp = pos[pos["alerte"] == 1].copy()

    # Rattachement des codes de règles (financières + prescription).
    codes = (
        alertes.groupby("facture_id")["code_fraude"]
        .apply(lambda s: ", ".join(sorted(set(s.astype(str)))))
        .rename("codes_fraude")
    )
    fn = fn.merge(codes, left_on="facture_id", right_index=True, how="left")
    tp = tp.merge(codes, left_on="facture_id", right_index=True, how="left")
    fn["codes_fraude"] = fn["codes_fraude"].fillna("AUCUN_CODE")
    tp["codes_fraude"] = tp["codes_fraude"].fillna("AUCUN_CODE")

    fn["tranche_montant"] = _tranche_montant(fn["montant_total"])
    tp["tranche_montant"] = _tranche_montant(tp["montant_total"])

    par_type = (
        test.assign(tranche=_tranche_montant(test["montant_total"]))
        .groupby(["type_facture"], as_index=False)
        .agg(
            positifs=(TARGET, "sum"),
            alertes=("alerte", "sum"),
            taux_rappel=("alerte", "mean"),
        )
        .sort_values("positifs", ascending=False)
    )
    par_type["taux_rappel"] = par_type["alertes"] / par_type["positifs"].replace(0, np.nan)

    par_tranche = (
        pd.DataFrame({"tranche": _tranche_montant(test["montant_total"]), TARGET: test[TARGET], "alerte": test["alerte"]})
        .groupby("tranche", observed=True, as_index=False)
        .agg(positifs=(TARGET, "sum"), alertes=("alerte", "sum"))
    )
    par_tranche["taux_rappel"] = par_tranche["alertes"] / par_tranche["positifs"].replace(0, np.nan)

    par_code = (
        pd.DataFrame(
            {
                "code": fn["codes_fraude"].str.split(", ").explode().to_numpy(),
            }
        )
        .value_counts()
        .rename("nb_fn")
        .reset_index()
    )

    profil = pd.DataFrame(
        {
            "indicateur": [
                "montant_total moyen",
                "score de risque moyen",
                "nb_alertes_metier moyen",
                "score_regles_metier moyen",
                "part avec au moins une règle",
            ],
            "faux_negatifs": [
                fn["montant_total"].mean(),
                fn["score_risque"].mean(),
                fn["nb_alertes_metier"].mean(),
                fn["score_regles_metier"].mean(),
                (fn["nb_alertes_metier"] > 0).mean(),
            ],
            "vrais_positifs": [
                tp["montant_total"].mean(),
                tp["score_risque"].mean(),
                tp["nb_alertes_metier"].mean(),
                tp["score_regles_metier"].mean(),
                (tp["nb_alertes_metier"] > 0).mean(),
            ],
        }
    )

    synthese = pd.DataFrame(
        {
            "metrique": ["positifs_test", "vrais_positifs", "faux_negatifs", "rappel", "precision"],
            "valeur": [
                len(pos),
                len(tp),
                len(fn),
                len(tp) / max(len(pos), 1),
                len(tp) / max(int(test["alerte"].sum()), 1),
            ],
        }
    )

    return {
        "synthese": synthese,
        "faux_negatifs": fn,
        "par_type_facture": par_type,
        "par_tranche_montant": par_tranche,
        "par_code_regle": par_code,
        "profil": profil,
    }


def ajouter_features_pb09(
    dataset: pd.DataFrame, alertes_prescription: pd.DataFrame
) -> pd.DataFrame:
    """Ajoute les alertes prescription PB-09 comme variables binaires."""
    enrichi = dataset.copy()
    codes = {
        "SURCONSOMMATION": "pb09_surconsommation",
        "LIGNES_NON_PRESCRITES": "pb09_lignes_non_prescrites",
        "INADEQUATION_DIAGNOSTIC": "pb09_inadequation_diagnostic",
        "PRESCRIPTEUR_RADIE": "pb09_prescripteur_radie",
        "ORDONNANCE_ANTIDATEE": "pb09_ordonnance_antidatee",
    }
    for code, colonne in codes.items():
        ids = set(alertes_prescription.loc[alertes_prescription["code_fraude"] == code, "facture_id"])
        enrichi[colonne] = enrichi["facture_id"].isin(ids).astype(int)
    enrichi["pb09_nb_alertes"] = sum(enrichi[c] for c in codes.values())
    return enrichi


def tester_amelioration(
    dataset: pd.DataFrame | None = None,
    alertes_prescription: pd.DataFrame | None = None,
    graine: int = SEED,
) -> pd.DataFrame:
    """Compare le modèle B sans / avec les variables PB-09 (LightGBM + SMOTE)."""

    from predicare.ml.training import _colonnes_features, _preprocesseur, _smote

    dataset = dataset if dataset is not None else charger_dataset_cm()
    if alertes_prescription is None:
        chemin = REPORTS_DIR / "pb09" / "alertes_prescription.csv"
        alertes_prescription = pd.read_csv(chemin) if chemin.is_file() else pd.DataFrame(
            columns=["facture_id", "code_fraude"]
        )
    enrichi = ajouter_features_pb09(dataset, alertes_prescription)

    from lightgbm import LGBMClassifier

    resultats = []
    pb09_cols = [c for c in enrichi.columns if c.startswith("pb09_")]
    for version, table in (("sans_pb09", dataset), ("avec_pb09", enrichi)):
        base = (
            table.drop(columns=[c for c in pb09_cols if c in table.columns])
            if version == "sans_pb09"
            else table
        )
        numeriques, categorielles = _colonnes_features(base)
        variables = numeriques + categorielles

        train = table[table["split"] == "train"]
        validation = table[table["split"] == "validation"]
        test = table[table["split"] == "test"]

        pre = _preprocesseur(numeriques, categorielles)
        X_train = pre.fit_transform(train[variables])
        X_val = pre.transform(validation[variables])
        X_test = pre.transform(test[variables])
        X_fit, y_fit = _smote(X_train, train[TARGET].to_numpy())

        modele = LGBMClassifier(**PARAMS_LIGHTGBM)
        modele.fit(X_fit, y_fit)

        p_val = modele.predict_proba(X_val)[:, 1]
        p_test = modele.predict_proba(X_test)[:, 1]
        seuil = seuil_pour_recall(validation[TARGET].to_numpy(), p_val, 0.80)
        m = metriques_comparaison(test[TARGET].to_numpy(), p_test)
        pred = p_test >= seuil
        y_test = test[TARGET].to_numpy()
        tp = int(((pred) & (y_test == 1)).sum())
        fn = int(((~pred) & (y_test == 1)).sum())
        fp = int(((pred) & (y_test == 0)).sum())
        resultats.append(
            {
                "version": version,
                "pr_auc": m["pr_auc"],
                "roc_auc": m["roc_auc"],
                "seuil": seuil,
                "recall": tp / max(tp + fn, 1),
                "precision": tp / max(tp + fp, 1),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "nb_variables": len(variables),
            }
        )
    return pd.DataFrame(resultats)


def main() -> None:  # pragma: no cover - CLI
    resultat = analyser()
    dossier = REPORTS_DIR / "pb10"
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, table in resultat.items():
        table.to_csv(dossier / f"{nom}.csv", index=False)
    comparaison = tester_amelioration()
    comparaison.to_csv(dossier / "amelioration.csv", index=False)
    print(resultat["synthese"].to_string(index=False))
    print("\nAmélioration :")
    print(comparaison.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
