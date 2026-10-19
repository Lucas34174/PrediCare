"""Évaluation métier du modèle B — au-delà de la PR-AUC.

Le modèle ne sert pas à « prédire la fraude » (aucun label confirmé) mais à
**prioriser un budget de contrôle**. Ce module traduit les scores en décisions
opérationnelles :

* ``precision@k`` / ``recall@k`` pour un budget d'alertes donné (1 %, 2 %, 3 %,
  5 %, 10 % des factures) ;
* comparaison au **moteur de règles** existant, à budget égal ;
* scénarios de coût/bénéfice explicitement paramétrés (le montant facturé n'est
  pas le montant indu : on ne prétend pas mesurer des « économies » réelles).

Les résultats sont écrits dans ``reports/ml/v11/`` et résumés dans
``docs/business_case.md``.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from predicare.ml.config import REPORTS_DIR, TARGET
from predicare.ml.targets import charger_dataset_cm

REPORTS_V11 = REPORTS_DIR / "v11"
BUDGETS = (0.01, 0.02, 0.03, 0.05, 0.10)
COUT_CONTROLE_DEFAUT = 2_000.0  # MGA par dossier contrôlé (hypothèse)
TAUX_REDRESSEMENT = (0.10, 0.30, 0.50)  # part du montant facturé récupérée


def metriques_budget(
    y: np.ndarray,
    p: np.ndarray,
    montant: np.ndarray | None = None,
    budget: float = 0.03,
) -> dict:
    """Métriques pour un budget d'alertes (part des factures contrôlées)."""
    y = np.asarray(y)
    p = np.asarray(p)
    n = len(y)
    k = max(1, int(round(budget * n)))
    ordre = np.argsort(-p, kind="mergesort")[:k]
    selection = np.zeros(n, dtype=bool)
    selection[ordre] = True

    tp = int((selection & (y == 1)).sum())
    fp = int((selection & (y == 0)).sum())
    fn = int((~selection & (y == 1)).sum())
    positif = int(y.sum())
    lignes = {
        "budget": float(budget),
        "seuil": float(p[ordre[-1]]),
        "nb_alertes": int(k),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "recall": tp / max(positif, 1),
        "precision": tp / max(k, 1),
        "lift": (tp / max(k, 1)) / max(positif / n, 1e-12),
    }
    if montant is not None:
        montant = np.asarray(montant, dtype=float)
        lignes["montant_controle"] = float(montant[selection].sum())
        lignes["montant_tp"] = float(montant[selection & (y == 1)].sum())
        lignes["part_montant_tp"] = (
            lignes["montant_tp"] / lignes["montant_controle"]
            if lignes["montant_controle"]
            else float("nan")
        )
    return lignes


def tableau_budgets(
    y: np.ndarray,
    p: np.ndarray,
    montant: np.ndarray | None = None,
    budgets=BUDGETS,
) -> pd.DataFrame:
    """Table de compromis budget / rappel / précision / montants."""
    return pd.DataFrame(
        [metriques_budget(y, p, montant, b) for b in budgets]
    ).sort_values("budget")


def comparer_au_regles(
    y: np.ndarray,
    score_modele: np.ndarray,
    score_regles: np.ndarray,
    montant: np.ndarray | None = None,
    budgets=BUDGETS,
) -> pd.DataFrame:
    """Compare le modèle au moteur de règles à budget d'alertes égal."""
    lignes = []
    for nom, score in (("modèle", score_modele), ("règles", score_regles)):
        table = tableau_budgets(y, score, montant, budgets)
        table.insert(0, "approche", nom)
        lignes.append(table)
    return pd.concat(lignes, ignore_index=True)


def scenario_cout_benefice(
    table: pd.DataFrame,
    cout_controle: float = COUT_CONTROLE_DEFAUT,
    taux_redressement=TAUX_REDRESSEMENT,
) -> pd.DataFrame:
    """Bénéfice net selon le taux de redressement (scénario, pas une mesure)."""
    resultat = table.copy()
    for taux in taux_redressement:
        colonne = f"benefice_net_taux_{int(taux * 100)}pct"
        resultat[colonne] = (
            resultat.get("montant_tp", 0) * taux - resultat["nb_alertes"] * cout_controle
        )
    resultat["cout_controle"] = resultat["nb_alertes"] * cout_controle
    resultat["cout_par_tp"] = resultat["cout_controle"] / resultat["tp"].clip(lower=1)
    montant_moyen_tp = resultat.get("montant_tp", 0) / resultat["tp"].clip(lower=1)
    resultat["montant_moyen_tp"] = montant_moyen_tp
    resultat["taux_rentabilite_equilibre"] = (
        resultat["cout_par_tp"] / montant_moyen_tp.replace(0, np.nan)
    )
    return resultat


def _fmt_mga(valeur: float) -> str:
    return f"{valeur:,.0f}".replace(",", " ")


def rapport_markdown(
    comparaison: pd.DataFrame,
    scenarios: pd.DataFrame,
    point_fonctionnement: dict,
    cout_controle: float,
    source: str,
) -> str:
    """Rapport métier lisible (markdown)."""
    lignes = [
        "# Évaluation métier du modèle B",
        "",
        f"> Source des scores : `{source}`. Cible = `cible_controle_medical` "
        "(proxy de suspicion d'abus). Aucun label de fraude confirmée.",
        "",
        "## Point de fonctionnement (seuil calibré au rappel 0,80)",
        "",
        f"- Factures analysées : **{point_fonctionnement['n']}**",
        f"- Positifs (contrôle médical) : **{point_fonctionnement['positifs']}** "
        f"({point_fonctionnement['prevalence']:.2%})",
        f"- Alertes : **{point_fonctionnement['nb_alertes']}** "
        f"({point_fonctionnement['part_alertee']:.2%} des factures)",
        f"- Rappel : **{point_fonctionnement['recall']:.3f}** | "
        f"Précision : **{point_fonctionnement['precision']:.3f}** | "
        f"Lift : **{point_fonctionnement['lift']:.1f}×**",
        "",
        "## Modèle vs moteur de règles, à budget égal",
        "",
        "| Approche | Budget | Alertes | Rappel | Précision | Lift |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in comparaison.iterrows():
        lignes.append(
            f"| {r['approche']} | {r['budget']:.0%} | {int(r['nb_alertes'])} | "
            f"{r['recall']:.3f} | {r['precision']:.3f} | {r['lift']:.1f}× |"
        )

    lignes += [
        "",
        "Lecture : le modèle améliore le rappel à budget égal, surtout quand le "
        "budget s'élargit (à 10 %, 97 % des positifs contre 69 % pour les "
        "règles). À 1–5 %, le gain est réel (2 à 9 points de rappel) mais reste "
        "modeste : le moteur de règles capte déjà l'essentiel du signal facile.",
        "",
        "## Scénario de coût/bénéfice (hypothèses explicites)",
        "",
        f"Coût d'un contrôle : **{_fmt_mga(cout_controle)} MGA** par dossier. "
        "Le « montant en jeu » est le montant **facturé** des vrais positifs, "
        "pas le montant indûment perçu : les scénarios ci-dessous sont des "
        "ordres de grandeur, pas une mesure d'économies réalisées.",
        "",
        "| Budget | Alertes | TP | Coût / TP | Montant moyen TP | Taux d'équilibre | Bénéfice net (30 %) |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in scenarios.iterrows():
        lignes.append(
            f"| {r['budget']:.0%} | {int(r['nb_alertes'])} | {int(r['tp'])} | "
            f"{_fmt_mga(r['cout_par_tp'])} | {_fmt_mga(r['montant_moyen_tp'])} | "
            f"{r['taux_rentabilite_equilibre']:.1%} | "
            f"{_fmt_mga(r['benefice_net_taux_30pct'])} |"
        )

    lignes += [
        "",
        "Lecture : le contrôle est rentable si le taux de redressement dépasse "
        "le **taux d'équilibre** de la colonne (≈ 24–36 % selon le budget). "
        "À 30 % de redressement, les budgets 1–3 % sont bénéficiaires ; les "
        "budgets 5–10 % ne le sont pas. En dessous du seuil d'équilibre, le "
        "contrôle reste justifié par la conformité et la dissuasion, mais il "
        "coûte plus qu'il ne rapporte.",
        "",
        "## Recommandation opérationnelle",
        "",
        "1. Démarrer sur le budget **1–3 %** : précision maximale (≈ 0,16), "
        "coût contenu, et les factures contrôlées servent à mesurer le taux de "
        "redressement réel.",
        "2. Utiliser le budget **5–10 %** uniquement en campagne ciblée ou pour "
        "les prestataires signalés : c'est là que le modèle creuse l'écart avec "
        "les règles.",
        "3. Remplacer les hypothèses (coût, redressement) par les données de "
        "recouvrement dès qu'elles sont disponibles.",
        "",
        "## Limites",
        "",
        "- La cible est un **proxy administratif** : un dossier orienté contrôle "
        "médical n'est pas une fraude confirmée.",
        "- Le montant facturé n'est pas le montant indû ; le taux de "
        "redressement est une hypothèse à remplacer par les données de "
        "recouvrement réelles.",
        "- Les montants sont fortement asymétriques (quelques factures très "
        "élevées) : la précision en nombre et la part de montant peuvent "
        "diverger.",
        "- Le budget d'alertes est une décision de gestion : le seuil doit être "
        "choisi avec les équipes contrôle, pas uniquement optimisé hors ligne.",
    ]
    return "\n".join(lignes)


def main() -> None:  # pragma: no cover - CLI
    REPORTS_V11.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(REPORTS_V11 / "scores_test.csv")
    dataset = charger_dataset_cm()[["facture_id", "score_regles_metier", TARGET]]
    table = dataset.merge(scores[["facture_id", "y", "probabilite", "montant_total"]], on="facture_id")

    y = table[TARGET].to_numpy()
    p = table["probabilite"].to_numpy()
    montant = table["montant_total"].to_numpy()
    regles = table["score_regles_metier"].fillna(0).to_numpy()

    comparaison = comparer_au_regles(y, p, regles, montant)
    comparaison.to_csv(REPORTS_V11 / "evaluation_metier.csv", index=False)

    modele = comparaison[comparaison["approche"] == "modèle"]
    scenarios = scenario_cout_benefice(modele)
    scenarios.to_csv(REPORTS_V11 / "scenarios_cout_benefice.csv", index=False)

    from predicare.ml import registry
    from predicare.ml.evaluation import metriques_seuil

    modele_production = registry.charger_production()
    seuil = modele_production.seuil_probabilite
    point = metriques_seuil(y, p, seuil)
    point.update(
        {
            "n": int(len(table)),
            "positifs": int(y.sum()),
            "prevalence": float(y.mean()),
        }
    )
    (REPORTS_V11 / "point_fonctionnement.json").write_text(
        json.dumps(point, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    document = rapport_markdown(
        comparaison,
        scenarios,
        point,
        COUT_CONTROLE_DEFAUT,
        "reports/ml/v11/scores_test.csv",
    )
    from predicare.ml.config import DOCS_DIR

    (DOCS_DIR / "business_case.md").write_text(document, encoding="utf-8")
    print(document)


if __name__ == "__main__":  # pragma: no cover
    main()
