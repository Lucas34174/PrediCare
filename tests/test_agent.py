"""Tests de l'agent ReAct.

Utilise le LLM local (Ollama). Le test peut être lent (~30 s).
"""

import logging

import pytest
from sqlalchemy import create_engine

from predicare.core.config import database_url
from predicare.rag.agent import ReactAgent
from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder
from predicare.rag.retriever import Retriever

logging.basicConfig(level=logging.WARNING)


@pytest.fixture(scope="module")
def agent():
    config = RagConfig.from_env()
    engine = create_engine(database_url())
    embedder = Embedder(config)
    retriever = Retriever(engine, embedder, config)
    a = ReactAgent(engine, retriever, config)
    yield a
    a.close()
    embedder.close()


def test_question_simple_sur_bareme(agent):
    """Question simple sur le barème → réponse sourcée."""
    result = agent.run(
        "Combien coûte une consultation de cardiologie ?",
        contract_id="CTR-000048",
    )
    assert not result.abstention, "Ne devrait pas s'abstenir sur une question claire"
    assert "40" in result.answer or "200" in result.answer, result.answer
    assert any("Barème" in s["document"] for s in result.sources)


def test_question_hors_corpus_abstention(agent):
    """Question sans réponse dans le corpus → abstention obligatoire."""
    result = agent.run(
        "Quel est le numéro de téléphone du président de Madagascar ?",
        contract_id="CTR-000048",
    )
    assert result.abstention, f"Aurait dû s'abstenir, réponse : {result.answer}"


def test_question_sur_mes_factures(agent):
    """Question sur les factures de l'assuré → utilise search_my_claims."""
    result = agent.run(
        "Combien j'ai de factures en attente ?",
        contract_id="CTR-000048",
    )
    # On ne peut pas prédire la réponse exacte, mais l'agent doit avoir utilisé l'outil SQL
    assert any(step["action"] == "search_my_claims" for step in result.steps), (
        f"L'outil search_my_claims n'a pas été appelé. Steps : {result.steps}"
    )


def test_isolation_contract(agent):
    """Un assuré ne peut PAS voir les factures d'un autre (test de sécurité)."""
    result_ctr048 = agent.run("Combien j'ai de factures ?", contract_id="CTR-000048")
    result_ctr066 = agent.run("Combien j'ai de factures ?", contract_id="CTR-000066")
    # Les deux réponses doivent être différentes (ou les 2 abstentions si pas de facture)
    # En aucun cas l'un doit voir les factures de l'autre
    assert result_ctr048.answer != result_ctr066.answer or result_ctr048.abstention
