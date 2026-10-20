"""Évaluation de PB-09 (règles) contre les labels faibles et le modèle v2.

Deux lectures sont produites :

1. **Règles vs labels faibles** : précision, rappel, lift, montants et
   couverture des 14 types. Attention : les règles PB-09 ont servi à
   construire une partie des labels faibles ; leur précision est donc
   circulaire pour SURCONSOMMATION et LIGNES_NON_PRESCRITES.
2. **Règles vs modèle à budget égal** : sur le test, on compare les alertes
   PB-09 au top-k du modèle (même nombre de factures alertées), puis au seuil
   produit du modèle.

Sorties : ``reports/ml/pb09/``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from predicare.ml.config import REPORTS_DIR

ALERTES_PB09 = REPORTS_DIR / "pb09" / "alertes_prescription.csv"
LABELS = Path("data/raw/labels/labels_fraude.csv")
DATASET = Path("data/processed/dataset_fraude_v2.csv")
SCORES_V2 = REPORTS_DIR / "v2" / "scores_test.csv"
SORTIE = REPORTS_DIR / "pb09"

#: Correspondance code PB-09 -> type de fraude faible (si pertinent).
CODE_VERS_TYPE = {
    "SURCONSOMMATION": "SURCONSOMMATION",
    "LIGNES_NON_PRESCRITES": "LIGNES_NON_PRESCRITES",
    "DOUBLON_PRESCRIPTION": "DOUBLON",
}


def _factures_alertees(alertes: pd.DataFrame) -> pd.DataFrame:
    return (
        alertes.groupby("facture_id")
        .agg(
            n_alertes=("code_fraude", "nunique"),
            codes=("code_fraude", lambda x: ";".join(sorted(set(x)))),
            gravite_max=("gravite", "max"),
            montant_en_jeu=("montant_en_jeu", "max"),
        )
        .reset_index()
    )


def _metriques(y: np.ndarray, alerte: np.ndarray) -> dict[str, float]:
    y = np.asarray(y, dtype=int)
    alerte = np.asarray(alerte, dtype=int)
    tp = int(((alerte == 1) & (y == 1)).sum())
    fp = int(((alerte == 1) & (y == 0)).sum())
    fn = int(((alerte == 0) & (y == 1)).sum())
    tn = int(((alerte == 0) & (y == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    prevalence = y.mean() if len(y) else float("nan")
    return {
        "n": int(len(y)),
        "positifs": int(y.sum()),
        "prevalence": float(prevalence),
        "alertes": int(alerte.sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(2 * precision * recall / max(precision + recall, 1e-12)),
        "lift": float(precision / prevalence) if prevalence else float("nan"),
        "part_alertee": float(alerte.mean()) if len(alerte) else float("nan"),
    }


def evaluer_pb09(
    alertes_path: str | Path = ALERTES_PB09,
    labels_path: str | Path = LABELS,
    dataset_path: str | Path = DATASET,
    scores_path: str | Path = SCORES_V2,
    sortie: str | Path = SORTIE,
) -> dict[str, Any]:
    alertes_path = Path(alertes_path)
    labels_path = Path(labels_path)
    dataset_path = Path(dataset_path)
    scores_path = Path(scores_path)
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)

    alertes = pd.read_csv(alertes_path, low_memory=False)
    labels = pd.read_csv(labels_path, low_memory=False)
    dataset = pd.read_csv(dataset_path, low_memory=False)[
        ["facture_id", "montant_total", "split"]
    ]
    inv = _factures_alertees(alertes)
    base = labels.merge(dataset, on="facture_id", how="left").merge(
        inv, on="facture_id", how="left"
    )
    base["alerte"] = base["n_alertes"].notna().astype(int)
    base["codes"] = base["codes"].fillna("")

    global_metrics = _metriques(base["est_fraude"], base["alerte"])
    montant_total = float(base["montant_total"].sum())
    montant_alerte = float(base.loc[base["alerte"] == 1, "montant_total"].sum())
    montant_positif = float(base.loc[base["est_fraude"] == 1, "montant_total"].sum())
    global_metrics.update(
        {
            "montant_total": montant_total,
            "montant_alerte": montant_alerte,
            "part_montant_alerte": montant_alerte / max(montant_total, 1),
            "montant_positifs": montant_positif,
        }
    )

    # Couverture des types faibles par au moins une alerte PB-09.
    couverture = []
    for type_fraude, bloc in base[base["est_fraude"] == 1].groupby("type_fraude"):
        couverture.append(
            {
                "type_fraude": type_fraude,
                "n_positifs": int(len(bloc)),
                "n_alertes": int(bloc["alerte"].sum()),
                "couverture": float(bloc["alerte"].mean()),
                "montant_total": float(bloc["montant_total"].sum()),
                "montant_alerte": float(
                    bloc.loc[bloc["alerte"] == 1, "montant_total"].sum()
                ),
            }
        )
    couverture = pd.DataFrame(couverture).sort_values("n_positifs", ascending=False)
    couverture.to_csv(sortie / "couverture_types.csv", index=False)

    # Précision par code PB-09.
    total_positifs = int(base["est_fraude"].sum())
    prevalence_globale = float(base["est_fraude"].mean())
    par_code = []
    for code, bloc in alertes.groupby("code_fraude"):
        ids = set(bloc["facture_id"])
        sous = base[base["facture_id"].isin(ids)]
        precision = float(sous["est_fraude"].mean()) if len(sous) else float("nan")
        rappel_global = (
            float(sous["est_fraude"].sum() / total_positifs)
            if total_positifs
            else float("nan")
        )
        type_cible = CODE_VERS_TYPE.get(code)
        couv_type = None
        if type_cible:
            type_ids = set(
                base.loc[
                    (base["est_fraude"] == 1) & (base["type_fraude"] == type_cible),
                    "facture_id",
                ]
            )
            couv_type = len(ids & type_ids) / max(len(type_ids), 1)
        par_code.append(
            {
                "code_fraude": code,
                "n_factures_alertees": int(bloc["facture_id"].nunique()),
                "precision": precision,
                "recall_global": rappel_global,
                "lift": (
                    float(precision / prevalence_globale)
                    if prevalence_globale
                    else float("nan")
                ),
                "montant_total": float(sous["montant_total"].sum()),
                "couverture_type_correspondant": couv_type,
            }
        )
    par_code = pd.DataFrame(par_code).sort_values(
        "n_factures_alertees", ascending=False
    )
    par_code.to_csv(sortie / "evaluation_par_code.csv", index=False)

    # Comparaison au modèle sur le test, à budget égal.
    comparaison = None
    if scores_path.is_file():
        scores = pd.read_csv(scores_path, low_memory=False)
        test_ids = set(scores["facture_id"])
        test = base[base["facture_id"].isin(test_ids)].copy()
        k = int(test["alerte"].sum())
        top = scores.sort_values("score_risque", ascending=False).head(max(k, 1))
        comparaison = pd.DataFrame(
            [
                {
                    "approche": "PB-09 (toutes alertes)",
                    **_metriques(test["est_fraude"], test["alerte"]),
                },
                {
                    "approche": f"Modèle v2 (top {k})",
                    **_metriques(scores["cible"], scores["facture_id"].isin(top["facture_id"]).astype(int)),
                },
                {
                    "approche": "Modèle v2 (seuil produit)",
                    **_metriques(scores["cible"], scores["alerte"]),
                },
            ]
        )
        comparaison.to_csv(sortie / "comparaison_regles_modele_test.csv", index=False)

    resultat = {
        "global": global_metrics,
        "par_code": par_code.to_dict(orient="records"),
        "couverture_types": couverture.to_dict(orient="records"),
        "comparaison_modele_test": (
            comparaison.to_dict(orient="records") if comparaison is not None else None
        ),
        "avertissement": (
            "Les règles PB-09 ont servi à construire une partie des labels "
            "faibles : la précision de SURCONSOMMATION et LIGNES_NON_PRESCRITES "
            "est circulaire. La comparaison au modèle à budget égal reste "
            "informative."
        ),
    }
    (sortie / "evaluation_pb09.json").write_text(
        json.dumps(resultat, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return resultat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Évaluation PB-09 vs labels faibles")
    parser.add_argument("--alertes", default=str(ALERTES_PB09))
    parser.add_argument("--labels", default=str(LABELS))
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--scores", default=str(SCORES_V2))
    parser.add_argument("--sortie", default=str(SORTIE))
    args = parser.parse_args(argv)

    resultat = evaluer_pb09(
        args.alertes, args.labels, args.dataset, args.scores, args.sortie
    )
    global_metrics = resultat["global"]
    print(
        f"PB-09 : {global_metrics['alertes']} alertes | "
        f"précision {global_metrics['precision']:.3f} | "
        f"rappel {global_metrics['recall']:.3f} | "
        f"lift {global_metrics['lift']:.2f}"
    )
    print("\nPar code :")
    print(pd.DataFrame(resultat["par_code"]).to_string(index=False))
    if resultat["comparaison_modele_test"]:
        print("\nComparaison test à budget égal :")
        print(pd.DataFrame(resultat["comparaison_modele_test"]).to_string(index=False))
    print(f"\nRapports écrits dans {args.sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
