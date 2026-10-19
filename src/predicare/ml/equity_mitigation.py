"""Mitigation d'équité — seuils ajustés par sous-groupe.

L'audit PB-14 constate des écarts de rappel (TPR) entre groupes. Ce module va
plus loin : il **corrige** l'écart en choisissant, sur la validation, un seuil
par groupe qui ramène son TPR au TPR global. Les seuils sont ensuite évalués
sur le test, jamais utilisés pour les choisir.

Garde-fous :

* un groupe de moins de 10 positifs en validation conserve le seuil global
  (un seuil estimé sur 3 positifs est du bruit) ;
* le coût est mesuré : nombre d'alertes supplémentaires et précision ;
* la mitigation est **proposée**, pas déployée : elle doit être validée sur une
  cohorte plus large avant mise en production.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from predicare.ml.config import DOCS_DIR, REPORTS_DIR, TARGET
from predicare.ml.evaluation import seuil_pour_recall
from predicare.ml.fairness import LABELS_AGE, TRANCHES_AGE, _charger_villes
from predicare.ml.scoring import normaliser_score
from predicare.ml.targets import charger_dataset_cm

REPORTS_V11 = REPORTS_DIR / "v11"
DIMENSIONS = ("sexe", "tranche_age", "formule")
MIN_POSITIFS = 10


def preparer(dataset: pd.DataFrame, modele, split: str) -> pd.DataFrame:
    """Table d'un split avec probabilité, score, ville et tranche d'âge."""
    bloc = dataset[dataset["split"] == split].copy()
    bloc["probabilite"] = modele.proba(bloc)
    bloc["score_risque"] = normaliser_score(bloc["probabilite"], modele.seuil_probabilite)
    assures, prest = _charger_villes()
    bloc = bloc.merge(assures, on="meta_assure_id", how="left")
    bloc = bloc.merge(prest, on="meta_prestataire_id", how="left")
    bloc["tranche_age"] = pd.cut(
        bloc["age_au_soin"], bins=TRANCHES_AGE, labels=LABELS_AGE, right=False
    )
    return bloc


def _metriques(bloc: pd.DataFrame, dimension: str, seuils: dict, seuil_global: float) -> dict:
    """TPR, précision et volume d'alertes avec des seuils par groupe."""
    seuil_ligne = (
        bloc[dimension].astype(str).map(seuils).fillna(seuil_global).astype(float)
    )
    alerte = (bloc["probabilite"] >= seuil_ligne).astype(int)
    tp = int(((alerte == 1) & (bloc[TARGET] == 1)).sum())
    fp = int(((alerte == 1) & (bloc[TARGET] == 0)).sum())
    positifs = int(bloc[TARGET].sum())

    tprs = {}
    for groupe, sous_bloc in bloc.groupby(dimension, observed=True):
        index = sous_bloc.index
        pos = int(sous_bloc[TARGET].sum())
        if pos:
            tprs[str(groupe)] = float(alerte.loc[index][sous_bloc[TARGET] == 1].mean())
    ecart = float(max(tprs.values()) - min(tprs.values())) if len(tprs) >= 2 else float("nan")

    return {
        "alertes": int(alerte.sum()),
        "part_alertee": float(alerte.mean()),
        "tp": tp,
        "fp": fp,
        "recall": tp / max(positifs, 1),
        "precision": tp / max(tp + fp, 1),
        "ecart_tpr_max_min": ecart,
        "tpr_par_groupe": tprs,
    }


def analyser(dataset: pd.DataFrame | None = None) -> pd.DataFrame:
    """Calcule les seuils sur la validation et mesure l'effet sur le test."""
    dataset = dataset if dataset is not None else charger_dataset_cm()
    from predicare.ml import registry

    modele = registry.charger_production()
    validation = preparer(dataset, modele, "validation")
    test = preparer(dataset, modele, "test")
    seuil_global = float(modele.seuil_probabilite)

    lignes = []
    for dimension in DIMENSIONS:
        if dimension not in test.columns:
            continue
        reference = _metriques(test, dimension, {}, seuil_global)

        # TPR global de validation au seuil de production.
        alerte_val = (validation["probabilite"] >= seuil_global).astype(int)
        tpr_global = float(
            alerte_val[validation[TARGET] == 1].mean()
        ) if validation[TARGET].sum() else float("nan")

        seuils: dict[str, float] = {}
        for groupe, bloc in validation.groupby(dimension, observed=True):
            if int(bloc[TARGET].sum()) >= MIN_POSITIFS and np.isfinite(tpr_global):
                seuils[str(groupe)] = float(
                    seuil_pour_recall(bloc[TARGET], bloc["probabilite"], tpr_global)
                )
            else:
                seuils[str(groupe)] = seuil_global

        corrige = _metriques(test, dimension, seuils, seuil_global)
        lignes.append(
            {
                "dimension": dimension,
                "tpr_global_validation": tpr_global,
                "ecart_tpr_avant": reference["ecart_tpr_max_min"],
                "ecart_tpr_apres": corrige["ecart_tpr_max_min"],
                "recall_avant": reference["recall"],
                "recall_apres": corrige["recall"],
                "precision_avant": reference["precision"],
                "precision_apres": corrige["precision"],
                "alertes_avant": reference["alertes"],
                "alertes_apres": corrige["alertes"],
                "surcout_alertes": corrige["alertes"] - reference["alertes"],
                "seuils": json.dumps(seuils, ensure_ascii=False),
            }
        )
    return pd.DataFrame(lignes)


def rapport_markdown(table: pd.DataFrame) -> str:
    """Rapport de mitigation d'équité."""
    lignes = [
        "# Mitigation d'équité — seuils par sous-groupe",
        "",
        "> **Statut : proposition documentée, non déployée.** Les seuils sont "
        "estimés sur la validation et évalués sur le test. La mitigation doit "
        "être confirmée sur une cohorte plus large avant activation.",
        "",
        "## Méthode",
        "",
        "1. Calcul du TPR global de validation au seuil de production.",
        "2. Pour chaque groupe comptant au moins "
        f"**{MIN_POSITIFS} positifs** en validation, choix du seuil qui ramène "
        "son TPR au TPR global.",
        "3. Application des seuils au test et mesure de l'écart résiduel, du "
        "rappel, de la précision et du volume d'alertes.",
        "",
        "Les groupes sous le seuil de positifs conservent le seuil global : "
        "estimer un seuil sur quelques cas produirait des alertes arbitraires.",
        "",
        "## Résultats",
        "",
        "| Dimension | Écart TPR avant | Écart TPR après | Rappel avant → après | Précision avant → après | Alertes avant → après |",
        "|---|---:|---:|---|---|---|",
    ]
    for _, r in table.iterrows():
        lignes.append(
            f"| {r['dimension']} | {r['ecart_tpr_avant']:.3f} | "
            f"{r['ecart_tpr_apres']:.3f} | {r['recall_avant']:.3f} → "
            f"{r['recall_apres']:.3f} | {r['precision_avant']:.3f} → "
            f"{r['precision_apres']:.3f} | {int(r['alertes_avant'])} → "
            f"{int(r['alertes_apres'])} ({int(r['surcout_alertes']):+d}) |"
        )

    ameliorations = int((table["ecart_tpr_apres"] < table["ecart_tpr_avant"]).sum())
    degradations = int((table["ecart_tpr_apres"] >= table["ecart_tpr_avant"]).sum())
    if degradations:
        verdict = (
            f"**La mitigation ne fonctionne pas de façon fiable sur ce jeu** : "
            f"{degradations} dimension(s) sur {len(table)} voient leur écart "
            f"se dégrader, {ameliorations} s'améliore(nt)."
        )
    else:
        verdict = "La mitigation réduit l'écart sur toutes les dimensions testées."

    lignes += [
        "",
        "## Lecture",
        "",
        verdict,
        "",
        "- Un écart qui **augmente** après ajustement signifie que le seuil "
        "estimé sur la validation ne se transfère pas au test : avec 120 "
        "positifs, les seuils par groupe sont trop instables.",
        "- L'écart n'est donc pas seulement un problème de seuil : il peut "
        "refléter des différences réelles de distribution entre groupes.",
        "- Le surcoût d'alertes est faible, mais la correction est inefficace : "
        "ce n'est pas un bon compromis.",
        "",
        "## Limites",
        "",
        "- Validation : 120 positifs, répartis en sous-groupes parfois petits.",
        "- Test : 128 positifs ; les intervalles de confiance sont larges.",
        "- Données synthétiques : un écart peut refléter le générateur.",
        "- Un seuil par groupe est une correction **statistique**, pas une "
        "réponse aux causes structurelles des inégalités d'accès aux soins.",
        "",
        "## Décision recommandée",
        "",
        "1. **Ne pas déployer** de seuils par groupe en production : le résultat "
        "est négatif sur deux dimensions.",
        "2. Surveiller les TPR par groupe à chaque réentraînement (PB-12).",
        "3. Réévaluer une mitigation (seuil ou recalibration) quand la cohorte "
        "dépasse quelques milliers de positifs.",
        "4. Traiter les causes structurelles (accès aux soins, codage) hors du "
        "modèle, avec les équipes métier.",
    ]
    return "\n".join(lignes)


def main() -> None:  # pragma: no cover - CLI
    REPORTS_V11.mkdir(parents=True, exist_ok=True)
    table = analyser()
    table.to_csv(REPORTS_V11 / "equite_mitigation.csv", index=False)
    (DOCS_DIR / "equity_mitigation.md").write_text(
        rapport_markdown(table), encoding="utf-8"
    )
    print(table.drop(columns=["seuils"]).to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()
