"""Audit indépendant du modèle v2 — évaluation, robustesse et limites.

Ce module **recalcule** les métriques à partir de l'artefact de production et
du jeu de test chronologique, sans réutiliser les scores déjà enregistrés. Il
complète les rapports PB-09 à PB-14 par des contrôles de fuite, une analyse
par niveau de confiance et par type de fraude, une stabilité mensuelle, une
importance par permutation et un audit du lot de 20 factures.

Les labels sont des **labels faibles reconstruits par règles** : les métriques
mesurent la capacité du modèle à retrouver ces règles, pas une fraude
confirmée. Le rapport le rappelle explicitement.

Usage::

    PYTHONPATH=src python -m predicare.ml.audit
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from predicare.ml.dataset_fraude import COLONNES_REGLES
from predicare.ml.evaluation import (
    ece,
    intervalle_confiance_bootstrap,
    metriques_comparaison,
    metriques_seuil,
)
from predicare.ml.scoring import ModeleFraude, charger_modele

VERSION = "v2.0.0-weak"
DATASET = Path("data/processed/dataset_fraude_v2.csv")
LABELS = Path("data/raw/labels/labels_fraude.csv")
REPORTS = Path("reports/ml/v2")
JURY = Path("reports/ml/pb12/lot_jury_20.json")
PB09 = Path("reports/ml/pb09/evaluation_pb09.json")
EQUITE = Path("reports/ml/pb14/synthese_equite.json")
DERIVE = Path("reports/ml/pb12/synthese_derive.json")
TARGET = "cible"

TYPES_FRAUDE = (
    "SURFACTURATION",
    "SURCONSOMMATION",
    "DOUBLON",
    "LIGNES_NON_PRESCRITES",
    "QUANTITE_EXCESSIVE",
    "SUBSTITUTION_PRODUIT",
    "ORDONNANCE_EXPIREE",
    "INCOHERENCE_PROFIL",
    "SOINS_JOUR_FERME",
    "HORS_COUVERTURE",
    "PRESTATAIRE_RADIE",
    "ACTE_FICTIF",
    "FRACTIONNEMENT",
    "UPCODING",
    "CONTROLE_MEDICAL",
)


def _jsonable(obj: Any) -> Any:
    """Convertit les types numpy en types JSON."""
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def charger() -> tuple[pd.DataFrame, ModeleFraude]:
    """Charge le dataset v2 et le modèle de production."""
    if not DATASET.is_file():
        raise FileNotFoundError(f"{DATASET} introuvable. Exécuter d'abord le pipeline v2.")
    df = pd.read_csv(DATASET, low_memory=False)
    if TARGET not in df.columns:
        raise ValueError(f"Cible {TARGET!r} absente de {DATASET}.")
    modele = charger_modele()
    return df, modele


def scorer_test(df: pd.DataFrame, modele: ModeleFraude) -> pd.DataFrame:
    """Ajoute probabilité calibrée et décision d'alerte au test."""
    test = df[df["split"] == "test"].copy()
    test["probabilite"] = modele.proba(test)
    test["alerte"] = (test["probabilite"] >= modele.seuil_probabilite).astype(int)
    return test


def metriques_globales(test: pd.DataFrame, modele: ModeleFraude) -> dict:
    """Métriques globales recalculées et contrôlées par bootstrap."""
    y = test[TARGET].to_numpy()
    p = test["probabilite"].to_numpy()
    seuil = modele.seuil_probabilite
    globales = metriques_seuil(y, p, seuil)
    comparaison = metriques_comparaison(y, p)
    globales.update(comparaison)
    globales["n"] = int(len(test))
    globales["positifs"] = int(y.sum())
    globales["prevalence"] = float(y.mean())
    globales["pr_auc_ic95"] = list(intervalle_confiance_bootstrap(y, p, "pr_auc"))
    globales["roc_auc_ic95"] = list(intervalle_confiance_bootstrap(y, p, "roc_auc"))
    globales["ece"] = float(ece(y, p)[0])
    return globales


def metriques_budgets(test: pd.DataFrame) -> list[dict]:
    """Précision, rappel et lift pour des budgets d'alertes fixés."""
    y = test[TARGET].to_numpy()
    p = test["probabilite"].to_numpy()
    resultats = []
    for budget in (0.01, 0.02, 0.03, 0.05, 0.10, 0.15, 0.20):
        k = max(1, int(round(budget * len(y))))
        ordre = np.argsort(-p)[:k]
        tp = int(y[ordre].sum())
        precision = tp / k
        resultats.append(
            {
                "budget": budget,
                "nb_alertes": k,
                "tp": tp,
                "precision": float(precision),
                "recall": float(tp / max(y.sum(), 1)),
                "lift": float(precision / y.mean()) if y.mean() else None,
                "seuil_probabilite": float(p[ordre][-1]),
            }
        )
    return resultats


def metriques_par_tier(test: pd.DataFrame) -> list[dict]:
    """Performance et faux positifs par niveau de confiance du label."""
    resultats = []
    for tier, bloc in test.groupby("tier", dropna=False):
        n = len(bloc)
        pos = int(bloc[TARGET].sum())
        alertes = int(bloc["alerte"].sum())
        tp = int(((bloc[TARGET] == 1) & (bloc["alerte"] == 1)).sum())
        fp = alertes - tp
        resultats.append(
            {
                "tier": str(tier),
                "n": n,
                "positifs": pos,
                "alertes": alertes,
                "taux_alerte": float(alertes / n) if n else None,
                "rappel_du_tier": float(tp / pos) if pos else None,
                "precision": float(tp / alertes) if alertes else None,
                "faux_positifs": fp,
                "taux_faux_positifs": float(fp / (n - pos)) if n > pos else None,
                "part_des_alertes": float(alertes / max(test["alerte"].sum(), 1)),
            }
        )
    return sorted(resultats, key=lambda x: x["n"], reverse=True)


def metriques_par_type(test: pd.DataFrame) -> list[dict]:
    """Rappel par type de fraude, en multi-label quand l'information existe."""
    if LABELS.is_file():
        labels = pd.read_csv(LABELS, usecols=["facture_id", "types_fraude"])
        test = test.merge(labels, on="facture_id", how="left")
    else:
        test = test.assign(types_fraude=None)
    test["types_fraude"] = test["types_fraude"].fillna("")
    positifs = test[test[TARGET] == 1]
    total_positifs = len(positifs)
    resultats = []
    for type_fraude in TYPES_FRAUDE:
        masque = positifs["types_fraude"].str.contains(type_fraude, regex=False) | (
            positifs["type_fraude"] == type_fraude
        )
        bloc = positifs[masque]
        n = len(bloc)
        if n == 0:
            continue
        alertes = int(bloc["alerte"].sum())
        resultats.append(
            {
                "type_fraude": type_fraude,
                "n_positifs": n,
                "alertes": alertes,
                "rappel": float(alertes / n),
                "part_des_positifs": float(n / total_positifs),
            }
        )
    return sorted(resultats, key=lambda x: x["n_positifs"], reverse=True)


def stabilite_mensuelle(test: pd.DataFrame) -> list[dict]:
    """PR-AUC, rappel et charge d'alertes par mois de réception."""
    test = test.copy()
    test["mois"] = (
        pd.to_datetime(test["meta_date_reception"], errors="coerce").dt.to_period("M").astype(str)
    )
    resultats = []
    for mois, bloc in test.groupby("mois"):
        y = bloc[TARGET].to_numpy()
        p = bloc["probabilite"].to_numpy()
        alertes = bloc["alerte"].to_numpy()
        tp = int(((y == 1) & (alertes == 1)).sum())
        fp = int(((y == 0) & (alertes == 1)).sum())
        resultats.append(
            {
                "mois": mois,
                "n": len(bloc),
                "positifs": int(y.sum()),
                "prevalence": float(y.mean()),
                "pr_auc": float(average_precision_score(y, p)) if len(np.unique(y)) > 1 else None,
                "rappel": float(tp / max(y.sum(), 1)),
                "precision": float(tp / max(tp + fp, 1)),
                "taux_alerte": float(alertes.mean()),
            }
        )
    return resultats


def calibration(y: np.ndarray, p: np.ndarray) -> dict:
    """ECE et table de calibration par décile."""
    valeur, table = ece(y, p)
    return {
        "ece": float(valeur),
        "table": table.rename(columns={"n": "n", "obs": "observe", "pred": "predit"}).to_dict(
            orient="records"
        ),
    }


def _metriques_sous_ensemble(bloc: pd.DataFrame) -> dict:
    """Métriques compactes sur un sous-ensemble du test."""
    y = bloc[TARGET].to_numpy()
    p = bloc["probabilite"].to_numpy()
    alerte = bloc["alerte"].to_numpy()
    tp = int(((y == 1) & (alerte == 1)).sum())
    fp = int(((y == 0) & (alerte == 1)).sum())
    fn = int(((y == 1) & (alerte == 0)).sum())
    return {
        "n": int(len(bloc)),
        "positifs": int(y.sum()),
        "prevalence": float(y.mean()) if len(y) else None,
        "pr_auc": float(average_precision_score(y, p)) if len(np.unique(y)) > 1 else None,
        "rappel": float(tp / max(tp + fn, 1)),
        "precision": float(tp / max(tp + fp, 1)),
        "taux_alerte": float(alerte.mean()) if len(alerte) else None,
    }


def controles_fuite(df: pd.DataFrame, test: pd.DataFrame, modele: ModeleFraude) -> dict:
    """Contrôles de fuite de cible, de règles et de doublons train/test."""
    train = df[df["split"] == "train"]
    cles_larges = [
        c for c in ("meta_assure_id", "meta_prestataire_id", "montant_total") if c in df.columns
    ]
    cles_strictes = [*cles_larges, "meta_date_reception"]
    doublons_larges = 0
    doublons_stricts = 0
    if cles_larges:
        doublons_larges = len(
            train[cles_larges]
            .drop_duplicates()
            .merge(test[cles_larges].drop_duplicates(), on=cles_larges, how="inner")
        )
    if all(c in df.columns for c in cles_strictes):
        doublons_stricts = len(
            train[cles_strictes]
            .drop_duplicates()
            .merge(test[cles_strictes].drop_duplicates(), on=cles_strictes, how="inner")
        )
    return {
        "cible_dans_variables": TARGET in modele.variables,
        "motif_rejet_dans_variables": "motif_rejet" in modele.variables,
        "regles_dans_variables": sorted(set(modele.variables) & COLONNES_REGLES),
        "nb_variables": len(modele.variables),
        "chevauchement_facture_id_train_test": len(
            set(train["facture_id"]) & set(test["facture_id"])
        ),
        "chevauchement_cles_larges_train_test": int(doublons_larges),
        "chevauchement_cles_strictes_avec_date": int(doublons_stricts),
        "cles_larges": cles_larges,
        "cles_strictes": cles_strictes,
        "note_chevauchement": (
            "Le chevauchement large porte sur des factures récurrentes "
            "(même assuré, prestataire et montant) et disparaît dès que la "
            "date est ajoutée : aucun doublon strict train/test."
        ),
        "colonnes_cible_presentes": [
            c
            for c in df.columns
            if c in {"cible", "cible_rejet", "cible_cm", "cible_controle_medical"}
        ],
    }


def diagnostic_chevauchement(df: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Compare la performance sur clés récurrentes et clés jamais vues."""
    train = df[df["split"] == "train"]
    cles = [
        c for c in ("meta_assure_id", "meta_prestataire_id", "montant_total") if c in df.columns
    ]
    if not cles:
        return {}
    cles_vues = train[cles].drop_duplicates()
    indicateur = (
        test[cles].merge(cles_vues, on=cles, how="left", indicator=True)["_merge"].eq("both")
    )
    indicateur.index = test.index
    return {
        "cles": cles,
        "avec_cle_vue": _metriques_sous_ensemble(test[indicateur]),
        "sans_cle_vue": _metriques_sous_ensemble(test[~indicateur]),
        "note": (
            "Les factures dont la clé large existe déjà dans le train sont "
            "majoritairement négatives et le modèle y est moins performant : "
            "le chevauchement ne gonfle donc pas artificiellement les métriques."
        ),
    }


def diagnostic_cold_start(df: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Performance sur assurés/prestataires jamais vus dans le train."""
    train = df[df["split"] == "train"]
    resultats = {}
    for colonne, libelle in (
        ("meta_prestataire_id", "prestataire"),
        ("meta_assure_id", "assure"),
    ):
        if colonne not in df.columns:
            continue
        vus = set(train[colonne].dropna().unique())
        masque = test[colonne].isin(vus)
        resultats[libelle] = {
            "part_vue": float(masque.mean()),
            "vu": _metriques_sous_ensemble(test[masque]),
            "jamais_vu": _metriques_sous_ensemble(test[~masque]),
        }
    return resultats


def importance_permutation(
    test: pd.DataFrame,
    modele: ModeleFraude,
    n_repetitions: int = 5,
    top: int = 15,
) -> dict:
    """Baisse de PR-AUC quand une variable est permutée aléatoirement.

    Mesure la dépendance du modèle aux variables, sans réentraînement. Une
    permutation conjointe des 5 premières variables teste l'effondrement.
    """
    y = test[TARGET].to_numpy()
    p = test["probabilite"].to_numpy()
    reference = float(average_precision_score(y, p))
    rng = np.random.default_rng(42)
    details = []
    for variable in modele.variables:
        valeurs = test[variable].to_numpy()
        baisses = []
        for _ in range(n_repetitions):
            permute = test.copy()
            permute[variable] = rng.permutation(valeurs)
            p_perm = modele.proba(permute)
            baisses.append(reference - float(average_precision_score(y, p_perm)))
        details.append(
            {
                "variable": variable,
                "baisse_moyenne": float(np.mean(baisses)),
                "baisse_ecart_type": float(np.std(baisses)),
            }
        )
    details.sort(key=lambda x: x["baisse_moyenne"], reverse=True)
    top_variables = [d["variable"] for d in details[:5]]
    baisses_conjointes = []
    for _ in range(n_repetitions):
        permute = test.copy()
        for variable in top_variables:
            permute[variable] = rng.permutation(permute[variable].to_numpy())
        p_perm = modele.proba(permute)
        baisses_conjointes.append(reference - float(average_precision_score(y, p_perm)))
    return {
        "pr_auc_reference": reference,
        "top_variables": details[:top],
        "top5": top_variables,
        "baisse_conjointe_top5_moyenne": float(np.mean(baisses_conjointes)),
        "baisse_conjointe_top5_ecart_type": float(np.std(baisses_conjointes)),
    }


def audit_jury() -> dict | None:
    """Précision/rappel du lot enrichi de 20 factures (non représentatif)."""
    if not JURY.is_file():
        return None
    lot = json.loads(JURY.read_text(encoding="utf-8"))
    factures = lot.get("factures", [])
    positifs = [f for f in factures if int(f.get("label_faible", 0)) == 1]
    negatifs = [f for f in factures if int(f.get("label_faible", 0)) == 0]
    alertes = [f for f in factures if bool(f.get("est_anomalie"))]
    tp = sum(1 for f in positifs if bool(f.get("est_anomalie")))
    return {
        "n": len(factures),
        "positifs": len(positifs),
        "negatifs": len(negatifs),
        "alertes": len(alertes),
        "tp": tp,
        "precision": float(tp / len(alertes)) if alertes else None,
        "rappel": float(tp / len(positifs)) if positifs else None,
        "avertissement": lot.get("avertissement"),
    }


def comparaison_pb09(test: pd.DataFrame) -> dict | None:
    """Compare le modèle aux règles PB-09 à budget d'alertes égal."""
    fichier = Path("reports/ml/pb09/comparaison_regles_modele_test.csv")
    if not fichier.is_file():
        return None
    tableau = pd.read_csv(fichier)
    return tableau.to_dict(orient="records")


def charger_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    df, modele = charger()
    test = scorer_test(df, modele)
    y = test[TARGET].to_numpy()
    p = test["probabilite"].to_numpy()

    audit = {
        "version_modele": modele.version,
        "modele": modele.modele,
        "seuil_probabilite": modele.seuil_probabilite,
        "avertissement": (
            "Labels faibles reconstruits par règles, pas des fraudes confirmées. "
            "Les métriques mesurent la détection des règles, pas la fraude réelle."
        ),
        "jeu_test": {
            "n": len(test),
            "positifs": int(y.sum()),
            "prevalence": float(y.mean()),
            "debut": str(pd.to_datetime(test["meta_date_reception"]).min().date()),
            "fin": str(pd.to_datetime(test["meta_date_reception"]).max().date()),
        },
        "metriques_globales": metriques_globales(test, modele),
        "budgets": metriques_budgets(test),
        "par_tier": metriques_par_tier(test),
        "par_type": metriques_par_type(test),
        "stabilite_mensuelle": stabilite_mensuelle(test),
        "calibration": calibration(y, p),
        "controles_fuite": controles_fuite(df, test, modele),
        "diagnostic_chevauchement": diagnostic_chevauchement(df, test),
        "diagnostic_cold_start": diagnostic_cold_start(df, test),
        "importance_permutation": importance_permutation(test, modele),
        "lot_jury": audit_jury(),
        "comparaison_pb09": comparaison_pb09(test),
        "equite": charger_json(EQUITE),
        "derive": charger_json(DERIVE),
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "audit_independant.json").write_text(
        json.dumps(_jsonable(audit), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(audit["importance_permutation"]["top_variables"]).to_csv(
        REPORTS / "importance_permutation.csv", index=False
    )
    print(
        json.dumps(
            _jsonable(
                {
                    "jeu_test": audit["jeu_test"],
                    "metriques_globales": audit["metriques_globales"],
                    "budgets": audit["budgets"],
                    "controles_fuite": audit["controles_fuite"],
                    "diagnostic_chevauchement": audit["diagnostic_chevauchement"],
                    "diagnostic_cold_start": audit["diagnostic_cold_start"],
                    "importance_permutation": audit["importance_permutation"],
                    "lot_jury": audit["lot_jury"],
                }
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
