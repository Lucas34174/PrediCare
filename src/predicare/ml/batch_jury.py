"""Lot de 20 factures pour la démonstration jury (PB-12).

Sélectionne 5 positifs haute confiance, 5 positifs moyenne confiance, 5 vrais
négatifs et 5 faux positifs (ou négatifs à score élevé), puis produit pour
chaque facture :

* le score et la décision du modèle v2 ;
* les 3 principaux facteurs SHAP ;
* le label faible et sa confiance (rappel : ce n'est pas une vérité terrain).

Sorties : ``reports/ml/pb12/lot_jury_20.json`` et ``.md``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from predicare.ml.config import MODELS_ROOT, REPORTS_DIR

VERSION = "v2.0.0-weak"
MODELE = MODELS_ROOT / VERSION / "model.joblib"
DATASET = Path("data/processed/dataset_cm_v2.csv")
SCORES = REPORTS_DIR / "v2" / "scores_test.csv"
SORTIE = REPORTS_DIR / "pb12"


def _choisir(scores: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Sélectionne 20 factures contrastées, sans doublon."""
    scores = scores.drop_duplicates("facture_id").copy()
    scores["_rang"] = range(len(scores))
    choisis: list[pd.DataFrame] = []

    def prendre(bloc: pd.DataFrame, tri: str, ascendant: bool, k: int):
        return bloc.sort_values(tri, ascending=ascendant).head(k)

    def prendre_diversifie(
        bloc: pd.DataFrame, k: int, tri: str = "score_risque", ascendant: bool = False
    ) -> pd.DataFrame:
        """Prend k factures en privilégiant la diversité des types de fraude."""
        lignes: list[dict] = []
        vus: set[str] = set()
        for _, ligne in bloc.sort_values(tri, ascending=ascendant).iterrows():
            type_fraude = ligne.get("type_fraude")
            if type_fraude not in vus:
                lignes.append(ligne.to_dict())
                vus.add(type_fraude)
            if len(lignes) == k:
                break
        if len(lignes) < k:
            ids = {x["facture_id"] for x in lignes}
            for _, ligne in bloc.sort_values(tri, ascending=ascendant).iterrows():
                if ligne["facture_id"] not in ids:
                    lignes.append(ligne.to_dict())
                if len(lignes) == k:
                    break
        return pd.DataFrame(lignes)

    # Positifs haute confiance, en privilégiant la diversité des types.
    haute = scores[(scores["cible"] == 1) & (scores["confiance"] == "haute")]
    choisis.append(prendre_diversifie(haute, n))

    # Positifs moyenne confiance, avec diversité des types.
    moyenne = scores[(scores["cible"] == 1) & (scores["confiance"] == "moyenne")]
    choisis.append(prendre_diversifie(moyenne, n))

    # Vrais négatifs à faible score.
    deja = set(pd.concat(choisis)["facture_id"])
    negatifs = scores[
        (scores["cible"] == 0) & (~scores["facture_id"].isin(deja))
    ]
    choisis.append(prendre(negatifs, "score_risque", True, n))

    # Faux positifs / négatifs à score élevé.
    deja = set(pd.concat(choisis)["facture_id"])
    fp = scores[
        (scores["cible"] == 0)
        & (scores["alerte"] == 1)
        & (~scores["facture_id"].isin(deja))
    ]
    if len(fp) < n:
        fp = scores[
            (scores["cible"] == 0) & (~scores["facture_id"].isin(deja))
        ]
    choisis.append(prendre(fp, "score_risque", False, n))

    lot = pd.concat(choisis, ignore_index=True).drop_duplicates("facture_id")
    return lot.head(4 * n).reset_index(drop=True)


def construire_lot(
    scores_path: str | Path = SCORES,
    modele_path: str | Path = MODELE,
    dataset_path: str | Path = DATASET,
    sortie: str | Path = SORTIE,
    n_par_categorie: int = 5,
) -> dict[str, Any]:
    from predicare.ml import service

    scores_path = Path(scores_path)
    modele_path = Path(modele_path)
    dataset_path = Path(dataset_path)
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)

    if not scores_path.is_file():
        raise FileNotFoundError(scores_path)
    if not modele_path.is_file():
        raise FileNotFoundError(modele_path)
    if not dataset_path.is_file():
        raise FileNotFoundError(dataset_path)

    os.environ["PREDICARE_MODELE_PATH"] = str(modele_path)
    os.environ["PREDICARE_DATASET_CM"] = str(dataset_path)
    service._modele.cache_clear()
    service._magasin.cache_clear()

    scores = pd.read_csv(scores_path, low_memory=False)
    lot = _choisir(scores, n_par_categorie)

    factures = []
    for _, ligne in lot.iterrows():
        resultat = service.predire_facture(ligne["facture_id"], top_k=3)
        prediction = resultat.get("prediction", {})
        facteurs = resultat.get("explicabilite", {}).get("top_facteurs", [])
        factures.append(
            {
                "facture_id": ligne["facture_id"],
                "label_faible": int(ligne["cible"]),
                "confiance_label": ligne.get("confiance"),
                "type_fraude_faible": ligne.get("type_fraude"),
                "candidat": int(ligne.get("candidat", 0)),
                "probabilite_calibree": prediction.get("probabilite_calibree"),
                "score_fraude": prediction.get("score_fraude"),
                "est_anomalie": prediction.get("est_anomalie"),
                "version_modele": prediction.get("version_modele"),
                "top_facteurs": facteurs,
            }
        )

    document = {
        "version_modele": VERSION,
        "avertissement": (
            "Les labels sont des labels faibles reconstruits par règles, pas des "
            "fraudes confirmées. Le lot sert à montrer le comportement du modèle "
            "et son explicabilité, pas à valider la vérité terrain."
        ),
        "nb_factures": len(factures),
        "composition": {
            "positifs_haute": int(
                sum(
                    1
                    for f in factures
                    if f["label_faible"] == 1 and f["confiance_label"] == "haute"
                )
            ),
            "positifs_moyenne": int(
                sum(
                    1
                    for f in factures
                    if f["label_faible"] == 1 and f["confiance_label"] == "moyenne"
                )
            ),
            "negatifs": int(sum(1 for f in factures if f["label_faible"] == 0)),
            "alertes": int(sum(1 for f in factures if f["est_anomalie"])),
        },
        "factures": factures,
    }

    (sortie / "lot_jury_20.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    lignes = [
        "# Lot de 20 factures — démonstration jury",
        "",
        "> **Avertissement** : les labels sont des labels faibles reconstruits par "
        "règles, pas des fraudes confirmées. Ce lot illustre le comportement du "
        "modèle et son explicabilité.",
        "",
        f"Modèle : `{VERSION}` — {document['composition']['alertes']} alertes sur "
        f"{document['nb_factures']} factures.",
        "",
        "| # | Facture | Label faible | Confiance | Type faible | Proba | Score | Alerte |",
        "|---|---------|--------------|-----------|-------------|-------|-------|--------|",
    ]
    for i, f in enumerate(factures, 1):
        lignes.append(
            f"| {i} | `{f['facture_id']}` | {f['label_faible']} | "
            f"{f['confiance_label']} | {f['type_fraude_faible']} | "
            f"{f['probabilite_calibree']:.4f} | {f['score_fraude']:.4f} | "
            f"{'OUI' if f['est_anomalie'] else 'non'} |"
        )
    lignes += ["", "## Explications SHAP (top 3)", ""]
    for f in factures:
        lignes.append(f"### `{f['facture_id']}`")
        for facteur in f["top_facteurs"]:
            lignes.append(
                f"- **{facteur['feature']}** = `{facteur['valeur']}` "
                f"(impact {facteur['impact_shap']:+.3f}) — {facteur['description']}"
            )
        lignes.append("")
    (sortie / "lot_jury_20.md").write_text("\n".join(lignes), encoding="utf-8")

    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lot de 20 factures pour le jury")
    parser.add_argument("--scores", default=str(SCORES))
    parser.add_argument("--modele", default=str(MODELE))
    parser.add_argument("--dataset", default=str(DATASET))
    parser.add_argument("--sortie", default=str(SORTIE))
    parser.add_argument("--n", type=int, default=5, help="Factures par catégorie")
    args = parser.parse_args(argv)

    document = construire_lot(
        args.scores, args.modele, args.dataset, args.sortie, args.n
    )
    print(
        f"Lot de {document['nb_factures']} factures — "
        f"{document['composition']['alertes']} alertes"
    )
    print(f"JSON : {Path(args.sortie) / 'lot_jury_20.json'}")
    print(f"Markdown : {Path(args.sortie) / 'lot_jury_20.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
