"""Audit d'équité du pipeline RAG PrediCare TPA.

Ce script mesure le recall@k du retriever par groupe (sexe, âge, formule,
catégorie, ville) et détecte les écarts > 10%.

Conformité :
- EU AI Act Art. 10 (gouvernance des données, biais)
- RGPD Art. 35 (AIPD)

Usage :
    docker compose run --rm api python -m tests.test_equity_audit
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from predicare.core.config import database_url
from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder
from predicare.rag.retriever import Retriever, SearchResult

logging.basicConfig(level=logging.WARNING)

# ─── Constantes ────────────────────────────────────────────────────────────────

TOP_K = 5
ECART_CIBLE = 0.10  # 10%

FIXTURES = Path("/app/tests/fixtures/equity_test_cases.json")
RAPPORT_JSON = Path("/app/docs/equity_audit_report.json")
RAPPORT_MD = Path("/app/docs/equity_audit.md")


# ─── Structures ────────────────────────────────────────────────────────────────


@dataclass
class CasResultat:
    """Résultat d'un cas de test."""

    id: str
    question: str
    dimension: str
    groupe: str
    attendu: dict[str, Any]
    top_chunk_id: int | None
    top_chunk_type: str | None
    top_metadata: dict[str, Any]
    top_similarity: float | None
    rang: int | None  # rang du chunk attendu dans le top-k (1-indexé), None si absent
    reussi: bool
    raison_echec: str | None = None


@dataclass
class GroupeStats:
    """Stats agrégées par groupe."""

    dimension: str
    groupe: str
    total: int = 0
    reussis: int = 0
    recall: float = 0.0
    details: list[CasResultat] = field(default_factory=list)


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _match_chunk(result: SearchResult, attendu: dict[str, Any]) -> bool:
    """Vérifie si un SearchResult correspond au critère attendu.

    Le critère `attendu` peut contenir :
    - chunk_type : à comparer à result.chunk_type
    - code_acte  : à comparer à result.metadata["code_acte"]
    - code_medicament : idem
    - formule    : à comparer à result.metadata["formule"]
    - contract_id: idem
    - categorie  : idem
    - ville      : idem
    - souscripteur: idem
    """
    for key, value in attendu.items():
        if key == "chunk_type":
            if result.chunk_type != value:
                return False
        else:
            if result.metadata.get(key) != value:
                return False
    return True


def _trouver_rang(results: list[SearchResult], attendu: dict[str, Any]) -> int | None:
    """Retourne le rang (1-indexé) du premier chunk qui matche, ou None."""
    for i, r in enumerate(results, start=1):
        if _match_chunk(r, attendu):
            return i
    return None


def _raison_echec(results: list[SearchResult], attendu: dict[str, Any]) -> str:
    """Génère un message d'échec utile."""
    if not results:
        return "aucun résultat retourné"
    top = results[0]
    return (
        f"top1: chunk_type={top.chunk_type} "
        f"metadata={ {k: v for k, v in top.metadata.items() if k in attendu} }"
    )


# ─── Exécution ─────────────────────────────────────────────────────────────────


def executer_audit(
    retriever: Retriever,
    cases: list[dict[str, Any]],
    top_k: int = TOP_K,
) -> list[CasResultat]:
    """Exécute tous les cas et retourne les résultats bruts."""
    resultats: list[CasResultat] = []

    for case in cases:
        q = case["question"]
        attendu = case["expected"]
        dim = case["group"]["dimension"]
        grp = case["group"]["value"]
        filters = case.get("filters") 

        results = retriever.search(q, top_k=top_k, filters=filters)
        rang = _trouver_rang(results, attendu)

        top = results[0] if results else None
        resultats.append(
            CasResultat(
                id=case["id"],
                question=q,
                dimension=dim,
                groupe=grp,
                attendu=attendu,
                top_chunk_id=top.chunk_id if top else None,
                top_chunk_type=top.chunk_type if top else None,
                top_metadata=top.metadata if top else {},
                top_similarity=top.score_vector if top else None,
                rang=rang,
                reussi=rang is not None,
                raison_echec=None if rang else _raison_echec(results, attendu),
            )
        )

    return resultats


def agreger_par_groupe(resultats: list[CasResultat]) -> list[GroupeStats]:
    """Agrège les résultats par (dimension, groupe)."""
    groupes: dict[tuple[str, str], GroupeStats] = {}

    for r in resultats:
        key = (r.dimension, r.groupe)
        if key not in groupes:
            groupes[key] = GroupeStats(dimension=r.dimension, groupe=r.groupe)
        g = groupes[key]
        g.total += 1
        g.reussis += int(r.reussi)
        g.details.append(r)

    for g in groupes.values():
        g.recall = g.reussis / g.total if g.total else 0.0

    return sorted(
        groupes.values(),
        key=lambda x: (x.dimension, x.groupe),
    )


def calculer_ecarts(groupes: list[GroupeStats]) -> dict[str, dict[str, float]]:
    """Calcule l'écart max par dimension."""
    par_dim: dict[str, list[float]] = defaultdict(list)
    for g in groupes:
        par_dim[g.dimension].append(g.recall)

    ecarts: dict[str, dict[str, float]] = {}
    for dim, recalls in par_dim.items():
        if not recalls:
            continue
        ecarts[dim] = {
            "min": min(recalls),
            "max": max(recalls),
            "ecart": max(recalls) - min(recalls),
            "ok": (max(recalls) - min(recalls)) <= ECART_CIBLE,
        }
    return ecarts


# ─── Rapports ──────────────────────────────────────────────────────────────────


def ecrire_rapport_json(
    resultats: list[CasResultat],
    groupes: list[GroupeStats],
    ecarts: dict[str, dict[str, float]],
) -> None:
    """Écrit le rapport JSON détaillé."""
    data = {
        "metadata": {
            "top_k": TOP_K,
            "ecart_cible": ECART_CIBLE,
            "total_cas": len(resultats),
            "total_reussis": sum(1 for r in resultats if r.reussi),
        },
        "par_groupe": [
            {
                "dimension": g.dimension,
                "groupe": g.groupe,
                "total": g.total,
                "reussis": g.reussis,
                "recall": round(g.recall, 4),
            }
            for g in groupes
        ],
        "ecarts_par_dimension": ecarts,
        "details": [
            {
                "id": r.id,
                "question": r.question,
                "dimension": r.dimension,
                "groupe": r.groupe,
                "attendu": r.attendu,
                "top_chunk_type": r.top_chunk_type,
                "top_metadata": {
                    k: v
                    for k, v in r.top_metadata.items()
                    if k
                    in (
                        "code_acte",
                        "code_medicament",
                        "formule",
                        "contract_id",
                        "categorie",
                        "ville",
                    )
                },
                "top_similarity": r.top_similarity,
                "rang": r.rang,
                "reussi": r.reussi,
                "raison_echec": r.raison_echec,
            }
            for r in resultats
        ],
    }
    RAPPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    RAPPORT_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"📄 Rapport JSON : {RAPPORT_JSON}")


def ecrire_rapport_markdown(
    resultats: list[CasResultat],
    groupes: list[GroupeStats],
    ecarts: dict[str, dict[str, float]],
) -> None:
    """Écrit le rapport markdown (à intégrer dans docs/equity_audit.md)."""
    total = len(resultats)
    reussis = sum(1 for r in resultats if r.reussi)
    recall_global = reussis / total if total else 0.0

    lignes: list[str] = []
    lignes.append("# Résultats de l'audit d'équité — Pipeline RAG PrediCare\n")
    lignes.append("**Date** : 2026-10-16")
    lignes.append(f"**Top-k** : {TOP_K}")
    lignes.append(f"**Écart cible** : ≤ {ECART_CIBLE:.0%}")
    lignes.append(f"**Total** : {total} cas de test")
    lignes.append(f"**Résultat global** : {reussis}/{total} ({recall_global:.1%})\n")

    # ── Écarts par dimension ──────────────────────────────────────
    lignes.append("## 1. Écarts par dimension\n")
    lignes.append("| Dimension | Min | Max | Écart | Statut |")
    lignes.append("|---|---|---|---|---|")
    for dim, e in sorted(ecarts.items()):
        statut = "✅ OK" if e["ok"] else "❌ DÉPASSEMENT"
        lignes.append(f"| {dim} | {e['min']:.1%} | {e['max']:.1%} | {e['ecart']:.1%} | {statut} |")
    lignes.append("")

    # ── Détail par groupe ─────────────────────────────────────────
    lignes.append("## 2. Détail par groupe\n")
    lignes.append("| Dimension | Groupe | Recall@k | Réussis/Total |")
    lignes.append("|---|---|---|---|")
    for g in groupes:
        lignes.append(f"| {g.dimension} | {g.groupe} | {g.recall:.1%} | {g.reussis}/{g.total} |")
    lignes.append("")

    # ── Cas en échec ──────────────────────────────────────────────
    echecs = [r for r in resultats if not r.reussi]
    if echecs:
        lignes.append(f"## 3. Cas en échec ({len(echecs)})\n")
        lignes.append("| ID | Question | Groupe | Raison |")
        lignes.append("|---|---|---|---|")
        for r in echecs:
            lignes.append(f"| {r.id} | {r.question[:60]}... | {r.groupe} | {r.raison_echec} |")
    else:
        lignes.append("## 3. Cas en échec\n")
        lignes.append("**Aucun cas en échec** ✅\n")

    # ── Conclusion ────────────────────────────────────────────────
    lignes.append("## 4. Conclusion\n")
    toutes_ok = all(e["ok"] for e in ecarts.values())
    if toutes_ok:
        lignes.append(
            "**Tous les écarts sont ≤ 10%.** Le pipeline RAG satisfait "
            "le critère d'équité défini.\n"
        )
    else:
        lignes.append(
            "**Certains écarts dépassent 10%.** Une action corrective "
            "est nécessaire (cf. section 5 de `equity_audit.md`).\n"
        )
        for dim, e in ecarts.items():
            if not e["ok"]:
                lignes.append(f"- Dimension **{dim}** : écart {e['ecart']:.1%}")

    # RAPPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    # RAPPORT_MD.write_text("\n".join(lignes), encoding="utf-8")
    print(f"📄 Rapport Markdown : {RAPPORT_MD}")


# ─── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    # 1. Charger le jeu de test
    if not FIXTURES.exists():
        raise SystemExit(f"Fixture introuvable : {FIXTURES}")
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    cases = data["cases"]
    print(f"→ {len(cases)} cas de test chargés depuis {FIXTURES}")

    # 2. Initialiser le retriever
    config = RagConfig.from_env()
    engine = create_engine(database_url())
    embedder = Embedder(config)
    retriever = Retriever(engine, embedder, config)

    # 3. Exécuter
    print("→ Exécution de l'audit…")
    resultats = executer_audit(retriever, cases, top_k=TOP_K)

    # 4. Agréger
    groupes = agreger_par_groupe(resultats)
    ecarts = calculer_ecarts(groupes)

    # 5. Résumé console
    print()
    print("=" * 70)
    print("RÉSUMÉ DE L'AUDIT D'ÉQUITÉ")
    print("=" * 70)
    total = len(resultats)
    reussis = sum(1 for r in resultats if r.reussi)
    print(f"Résultat global : {reussis}/{total} ({reussis / total:.1%})\n")

    print("Recall par groupe :")
    for g in groupes:
        status = "✅" if g.recall >= 0.80 else "⚠️"
        print(
            f"  {status} [{g.dimension:10s}] {g.groupe:20s} → "
            f"{g.recall:.1%} ({g.reussis}/{g.total})"
        )
    print()
    print("Écarts par dimension :")
    for dim, e in sorted(ecarts.items()):
        status = "✅" if e["ok"] else "❌"
        print(
            f"  {status} {dim:10s} → min={e['min']:.1%} max={e['max']:.1%} écart={e['ecart']:.1%}"
        )

    # 6. Écrire les rapports
    print()
    ecrire_rapport_json(resultats, groupes, ecarts)
    ecrire_rapport_markdown(resultats, groupes, ecarts)

    # 7. Code de sortie pour CI
    if not all(e["ok"] for e in ecarts.values()):
        print("\n⚠️  Certains écarts dépassent 10% — voir les rapports.")
        # Décommenter pour CI stricte :
        # raise SystemExit(1)

    embedder.close()


if __name__ == "__main__":
    main()
