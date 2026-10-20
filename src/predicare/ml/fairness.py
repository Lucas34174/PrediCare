"""PB-14 — Audit d'équité du modèle B.

Évalue les taux d'alerte, le rappel (TPR) et le taux de faux positifs (FPR) par
sous-groupe : sexe, tranche d'âge, ville (assuré et prestataire) et formule.

La ``ville`` n'est pas une variable du jeu d'apprentissage : elle est jointe
depuis ``assures.csv`` / ``prestataires.csv``. Les groupes à faible effectif
sont signalés et leurs intervalles de confiance fournis (Wilson).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from predicare.ml.config import DOCS_DIR, REPORTS_DIR, SOURCE_DIR, TARGET
from predicare.ml.targets import charger_dataset_cm

TRANCHES_AGE = [0, 25, 45, 60, np.inf]
LABELS_AGE = ["<25", "25-45", "45-60", "60+"]

SEUIL_ECART_TPR = 0.10  # écart maximal toléré entre groupes (10 points de rappel)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance de Wilson pour une proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denominateur = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominateur
    marge = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominateur
    return (max(0.0, centre - marge), min(1.0, centre + marge))


def _charger_villes(source_dir: Path | str | None = None) -> pd.DataFrame:
    dossier = Path(source_dir) if source_dir else SOURCE_DIR
    assures = pd.read_csv(dossier / "assures.csv", low_memory=False)[["assure_id", "ville"]]
    assures = assures.rename(columns={"assure_id": "meta_assure_id", "ville": "ville_assure"})
    prest = pd.read_csv(dossier / "prestataires.csv", low_memory=False)[
        ["prestataire_id", "ville"]
    ]
    prest = prest.rename(columns={"prestataire_id": "meta_prestataire_id", "ville": "ville_prestataire"})
    return assures, prest


def preparer_table(
    dataset: pd.DataFrame | None = None,
    scores: pd.DataFrame | None = None,
    source_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Table d'audit : cible, alerte, groupe d'appartenance et ville."""
    from predicare.ml.config import DATA_RAW

    dataset = dataset if dataset is not None else charger_dataset_cm()
    if scores is None:
        chemin = Path(os.environ.get("PREDICARE_SCORES_TEST", ""))
        if not chemin.is_file():
            v2 = REPORTS_DIR / "v2" / "scores_test.csv"
            v11 = REPORTS_DIR / "v11" / "scores_test.csv"
            chemin = (
                v2
                if v2.is_file()
                else v11
                if v11.is_file()
                else DATA_RAW / "scores_test_cm.csv"
            )
        scores = pd.read_csv(chemin)

    test = dataset[dataset["split"] == "test"].copy()
    test = test.merge(scores[["facture_id", "probabilite", "score_risque", "alerte"]], on="facture_id", how="left")
    test["alerte"] = test["alerte"].fillna(0).astype(int)

    if source_dir is not False:
        try:
            assures, prest = _charger_villes(source_dir)
            test = test.merge(assures, on="meta_assure_id", how="left")
            test = test.merge(prest, on="meta_prestataire_id", how="left")
        except FileNotFoundError:
            test["ville_assure"] = np.nan
            test["ville_prestataire"] = np.nan

    test["tranche_age"] = pd.cut(test["age_au_soin"], bins=TRANCHES_AGE, labels=LABELS_AGE, right=False)
    return test


def _groupe(df: pd.DataFrame, colonne: str) -> pd.DataFrame:
    lignes = []
    for valeur, bloc in df.groupby(colonne, observed=True):
        positifs = int(bloc[TARGET].sum())
        negatifs = int((bloc[TARGET] == 0).sum())
        alertes = int(bloc["alerte"].sum())
        tp = int(((bloc["alerte"] == 1) & (bloc[TARGET] == 1)).sum())
        fp = int(((bloc["alerte"] == 1) & (bloc[TARGET] == 0)).sum())
        tpr = tp / positifs if positifs else float("nan")
        fpr = fp / negatifs if negatifs else float("nan")
        tpr_ic = wilson(tp, positifs)
        fpr_ic = wilson(fp, negatifs)
        lignes.append(
            {
                "groupe": colonne,
                "modalite": str(valeur),
                "n": int(len(bloc)),
                "positifs": positifs,
                "alertes": alertes,
                "taux_alerte": alertes / max(len(bloc), 1),
                "tpr": tpr,
                "tpr_ic_bas": tpr_ic[0],
                "tpr_ic_haut": tpr_ic[1],
                "fpr": fpr,
                "fpr_ic_bas": fpr_ic[0],
                "fpr_ic_haut": fpr_ic[1],
                "precision": tp / max(tp + fp, 1),
                "effectif_faible": positifs < 5,
            }
        )
    return pd.DataFrame(lignes)


def auditer(
    dataset: pd.DataFrame | None = None,
    scores: pd.DataFrame | None = None,
    source_dir: Path | str | None = None,
) -> dict[str, pd.DataFrame]:
    """Audit par dimension d'équité."""
    table = preparer_table(dataset, scores, source_dir)
    dimensions = {
        "sexe": "sexe",
        "tranche_age": "tranche_age",
        "formule": "formule",
        "ville_assure": "ville_assure",
        "ville_prestataire": "ville_prestataire",
    }
    resultats = {}
    for nom, colonne in dimensions.items():
        if colonne in table.columns:
            resultats[nom] = _groupe(table, colonne)
    return resultats


def synthese(resultats: dict[str, pd.DataFrame]) -> dict:
    """Indicateurs d'écart et alertes d'équité."""
    synthese_dict: dict = {"dimensions": {}}
    for nom, table in resultats.items():
        valides = table[(~table["effectif_faible"]) & table["tpr"].notna()]
        ecart_tpr = (
            float(valides["tpr"].max() - valides["tpr"].min()) if len(valides) >= 2 else None
        )
        ecart_fpr = (
            float(valides["fpr"].max() - valides["fpr"].min())
            if len(valides) >= 2 and valides["fpr"].notna().any()
            else None
        )
        alertes = []
        if ecart_tpr is not None and ecart_tpr > SEUIL_ECART_TPR:
            alertes.append(f"écart de rappel {ecart_tpr:.3f} > {SEUIL_ECART_TPR}")
        synthese_dict["dimensions"][nom] = {
            "nb_groupes": int(len(table)),
            "nb_groupes_faibles": int(table["effectif_faible"].sum()),
            "ecart_tpr_max_min": ecart_tpr,
            "ecart_fpr_max_min": ecart_fpr,
            "alerte_equite": alertes,
        }
    return synthese_dict


def rapport_markdown(resume: dict, resultats: dict[str, pd.DataFrame], seuil: float) -> str:
    """Rédige le rapport d'audit d'équité en markdown."""
    lignes = [
        "# Audit d'équité du modèle PrediCare (cible B)",
        "",
        "> Cible : `est_fraude` (label faible reconstruit, 14 types de fraude). "
        "Ce n'est pas une vérité terrain : cet audit porte sur les "
        "**alertes du modèle**, pas sur une fraude confirmée.",
        "",
        f"Seuil d'alerte appliqué : **{seuil:.2f}** (score de risque normalisé).",
        "",
        "Écart de rappel maximal toléré entre groupes : "
        f"**{SEUIL_ECART_TPR:.0%}**.",
        "",
        "## Synthèse",
        "",
        "| Dimension | Groupes | Groupes à faible effectif | Écart TPR | Écart FPR | Alerte |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for nom, info in resume["dimensions"].items():
        ecart_tpr = f"{info['ecart_tpr_max_min']:.3f}" if info["ecart_tpr_max_min"] is not None else "n/a"
        ecart_fpr = f"{info['ecart_fpr_max_min']:.3f}" if info["ecart_fpr_max_min"] is not None else "n/a"
        alerte = "⚠️ " + " ; ".join(info["alerte_equite"]) if info["alerte_equite"] else "✅"
        lignes.append(
            f"| {nom} | {info['nb_groupes']} | {info['nb_groupes_faibles']} | {ecart_tpr} | {ecart_fpr} | {alerte} |"
        )

    lignes += [
        "",
        "## Détail par dimension",
        "",
        "Un effectif de moins de 5 positifs rend le rappel instable : ces groupes "
        "sont marqués et ne doivent pas fonder de conclusion.",
        "",
    ]
    for nom, table in resultats.items():
        lignes += [
            f"### {nom}",
            "",
            "| Groupe | n | Positifs | Alertes | Taux d'alerte | Rappel (IC95) | FPR (IC95) | Précision |",
            "|---|---:|---:|---:|---:|---|---|---:|",
        ]
        for _, r in table.sort_values("n", ascending=False).iterrows():
            marque = " *(effectif faible)*" if r["effectif_faible"] else ""
            tpr = f"{r['tpr']:.3f} [{r['tpr_ic_bas']:.2f}–{r['tpr_ic_haut']:.2f}]" if r["tpr"] == r["tpr"] else "n/a"
            fpr = f"{r['fpr']:.3f} [{r['fpr_ic_bas']:.2f}–{r['fpr_ic_haut']:.2f}]" if r["fpr"] == r["fpr"] else "n/a"
            lignes.append(
                f"| {r['modalite']}{marque} | {r['n']} | {r['positifs']} | {r['alertes']} | "
                f"{r['taux_alerte']:.1%} | {tpr} | {fpr} | {r['precision']:.3f} |"
            )
        lignes.append("")

    positifs_test = (
        int(next(iter(resultats.values()))["positifs"].sum()) if resultats else 0
    )
    lignes += [
        "## Limites",
        "",
        "- Cible = label faible reconstruit par règles, pas de la fraude confirmée.",
        f"- Test : {positifs_test} positifs faibles → les sous-groupes restent petits.",
        "- Données synthétiques : les écarts observés peuvent refléter le générateur.",
        "- La ville est jointe hors du jeu d'apprentissage (dimension d'audit, pas variable du modèle).",
        "",
        "## Mesures correctives proposées",
        "",
        "1. Recalibrer le seuil par sous-groupe uniquement si un écart TPR persiste sur un jeu plus large.",
        "2. Surveiller mensuellement les taux d'alerte par groupe (voir PB-12, dérive).",
        "3. Documenter tout écart résiduel dans la model card (PB-11).",
        "",
        "Analyse de mitigation (seuils par sous-groupe, évaluée sur le test) : "
        "`docs/equity_mitigation.md`.",
    ]
    return "\n".join(lignes)


def main() -> None:  # pragma: no cover - CLI
    import os

    from predicare.ml.scoring import SEUIL_PRODUIT_DEFAUT

    seuil = float(os.environ.get("PREDICARE_SEUIL_ALERTE", SEUIL_PRODUIT_DEFAUT))
    resultats = auditer()
    resume = synthese(resultats)
    dossier = REPORTS_DIR / "pb14"
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, table in resultats.items():
        table.to_csv(dossier / f"equite_{nom}.csv", index=False)
    (dossier / "synthese_equite.json").write_text(
        json.dumps(resume, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "equity_audit_modele.md").write_text(
        rapport_markdown(resume, resultats, seuil), encoding="utf-8"
    )
    print(json.dumps(resume, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover
    main()
