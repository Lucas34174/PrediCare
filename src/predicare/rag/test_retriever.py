"""Test du retriever hybride.

Vérifie :
- Recherche vectorielle pure
- Recherche full-text pure
- Recherche hybride (RRF)
- Filtres métadonnées
"""

import logging

from sqlalchemy import create_engine

from predicare.core.config import database_url
from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder
from predicare.rag.retriever import Retriever

logging.basicConfig(level=logging.WARNING)


# ─── Jeu de test ───────────────────────────────────────────────────────────────

CASES = [
    {
        "query": "Combien coûte une consultation de cardiologie ?",
        "expected_chunk_type": "ligne_bareme",
        "expected_metadata": {"code_acte": "CONS-CARDIO"},
    },
    {
        "query": "Quelle est la règle de remboursement pour la maternité en CONFORT ?",
        "expected_chunk_type": "article",
        "expected_metadata": {"formule": "CONFORT"},
    },
    {
        "query": "Quelle pharmacie est ouverte 24h/24 à Antananarivo ?",
        "expected_chunk_type": "prestataire",
        "expected_metadata": {"categorie": "PHARMACIES"},
    },
    {
        "query": "Qui est le souscripteur du contrat CTR-000048 ?",
        "expected_chunk_type": "contrat_metadata",
        "expected_metadata": {"contract_id": "CTR-000048"},
    },
    {
        "query": "Où trouver un dentiste à Toamasina ?",
        "expected_chunk_type": "prestataire",
        "expected_metadata": {"categorie": "DENTISTES"},
    },
    {
        "query": "Quelles sont les exclusions de la formule ESSENTIEL ?",
        "expected_chunk_type": "article",
        "expected_metadata": {"formule": "ESSENTIEL"},
    },
]

# Cas avec filtres explicites
FILTERED_CASES = [
    {
        "query": "Quelles sont les exclusions ?",
        "filters": {"formule": "ESSENTIEL"},
        "check": lambda r: r.metadata.get("formule") == "ESSENTIEL",
    },
    {
        "query": "Tarif consultation",
        "filters": {"chunk_type": "ligne_bareme", "categorie": "CONSULTATION"},
        "check": lambda r: (
            r.chunk_type == "ligne_bareme" and r.metadata.get("categorie") == "CONSULTATION"
        ),
    },
]


# ─── Helpers ───────────────────────────────────────────────────────────────────


def _check_expected(result, expected_chunk_type: str, expected_metadata: dict) -> bool:
    if result.chunk_type != expected_chunk_type:
        return False
    for key, value in expected_metadata.items():
        if result.metadata.get(key) != value:
            return False
    return True


# ─── Test principal ────────────────────────────────────────────────────────────


def main() -> None:
    config = RagConfig.from_env()
    engine = create_engine(database_url())
    embedder = Embedder(config)
    retriever = Retriever(engine, embedder, config)

    print("=" * 70)
    print("TEST 1 — Recherche hybride (mode par défaut)")
    print("=" * 70)
    reussis = 0
    for case in CASES:
        results = retriever.search(case["query"], top_k=3)
        top = results[0] if results else None
        if top and _check_expected(top, case["expected_chunk_type"], case["expected_metadata"]):
            reussis += 1
            status = "✅"
        else:
            status = "❌"
        print(f"{status} Q: {case['query']}")
        if top:
            print(f"    → type={top.chunk_type} | sim={top.score_vector} | rrf={top.score_rrf:.4f}")
            for k, v in case["expected_metadata"].items():
                print(f"      attendu {k}={v} | obtenu {top.metadata.get(k)}")
        print()

    print(f"Résultat : {reussis}/{len(CASES)} réussis\n")

    print("=" * 70)
    print("TEST 2 — Comparaison des modes (vector / fulltext / hybrid)")
    print("=" * 70)
    query = "Combien coûte une consultation de cardiologie ?"
    for mode in ["vector", "fulltext", "hybrid"]:
        results = retriever.search(query, top_k=1, mode=mode)
        if results:
            r = results[0]
            print(
                f"  mode={mode:9s} → chunk_type={r.chunk_type:20s} "
                f"code_acte={r.metadata.get('code_acte')} "
                f"sim={r.score_vector} rrf={r.score_rrf:.4f}"
            )
        else:
            print(f"  mode={mode:9s} → aucun résultat")
    print()

    print("=" * 70)
    print("TEST 3 — Recherche exacte (full-text)")
    print("=" * 70)
    for query in ["CONS-CARDIO", "CTR-000048", "IMG-IRM"]:
        results = retriever.search(query, top_k=1, mode="fulltext")
        if results:
            r = results[0]
            print(
                f"  '{query}' → type={r.chunk_type} | "
                f"code={r.metadata.get('code_acte')} | "
                f"contract={r.metadata.get('contract_id')}"
            )
        else:
            print(f"  '{query}' → aucun résultat")
    print()

    print("=" * 70)
    print("TEST 4 — Filtres métadonnées")
    print("=" * 70)
    for case in FILTERED_CASES:
        results = retriever.search(case["query"], top_k=3, filters=case["filters"])
        if results and case["check"](results[0]):
            print(f"✅ '{case['query']}' avec {case['filters']}")
            print(
                f"    → type={results[0].chunk_type} | "
                f"formule={results[0].metadata.get('formule')} | "
                f"cat={results[0].metadata.get('categorie')}"
            )
        else:
            print(f"❌ '{case['query']}' avec {case['filters']}")
            if results:
                print(f"    → obtenu type={results[0].chunk_type} | metadata={results[0].metadata}")
        print()

    embedder.close()


if __name__ == "__main__":
    main()
