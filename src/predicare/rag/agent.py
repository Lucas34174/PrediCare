"""Agent ReAct sourcé pour PrediCare TPA.

Implémente PB-36 :
- Combine RAG et SQL
- Citations obligatoires
- Refus de spéculer (abstention si sources insuffisantes)
- Limité à l'assuré connecté (contract_id du JWT)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import Engine

from predicare.rag.config import RagConfig
from predicare.rag.prompts import REACT_PROMPT, SYSTEM_PROMPT
from predicare.rag.retriever import Retriever
from predicare.rag.tools import Tools

logger = logging.getLogger(__name__)


# Seuil de similarité pour accepter une source (anti-hallucination)
SEUIL_ABSTENTION = 0.60

MAX_ITERATIONS = 3  # garde-fou contre les boucles


# Dans agent.py, avant la boucle for (ou en haut du fichier)


def _normaliser_action(action: str) -> str:
    """Rend l'agent tolérant aux hallucinations de nom d'outil du LLM."""
    a = action.lower().strip()

    # Recherche documentaire (RAG)
    if any(k in a for k in ["search_doc", "document", "bareme", "rag", "search"]):
        return "search_documents"

    # Recherche de factures (SQL)
    if any(k in a for k in ["claim", "facture", "financial", "mes_factures", "dossier"]):
        return "search_my_claims"

    # Réponse finale
    if any(k in a for k in ["final", "answer", "reponse", "respond"]):
        return "final_answer"

    return a


@dataclass
class AgentResult:
    """Résultat de l'agent ReAct."""

    answer: str
    abstention: bool
    sources: list[dict[str, str]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


class ReactAgent:
    """Agent ReAct combinant RAG et SQL."""

    def __init__(
        self,
        engine: Engine,
        retriever: Retriever,
        config: RagConfig,
        llm_model: str = "phi3:mini",
    ) -> None:
        self._engine = engine
        self._retriever = retriever
        self._config = config
        self._llm_model = llm_model
        self._tools = Tools(engine, retriever)
        self._client = httpx.Client(
            base_url=config.ollama_base_url,
            timeout=httpx.Timeout(180.0, connect=10.0),
        )

    def run(
        self,
        question: str,
        contract_id: str,
    ) -> AgentResult:
        """Exécute l'agent sur une question.

        Args:
            question: la question de l'assuré.
            contract_id: le contrat de l'assuré connecté (issu du JWT).
        """
        steps: list[dict[str, Any]] = []
        history: list[str] = []
        sources: list[dict[str, str]] = []

        question_lower = question.lower()
        mots_factures = [
            "facture",
            "remboursement",
            "dossier",
            "dossier de soin",
            "attente",
            "payé",
            "rejeté",
        ]

        if any(mot in question_lower for mot in mots_factures) and contract_id:
            logger.info("Routage forcé vers search_my_claims")
            claims = self._tools.search_my_claims(contract_id)
            history.append(
                "[TOOL search_my_claims()]\n"
                + "\n".join(
                    f"- {c['numero_facture']} ({c['date_soin']}) : "
                    f"{c['montant_total']} Ar — {c['statut']}"
                    for c in claims
                )
            )
            # On note que l'outil a été appelé pour le test
            steps.append(
                {
                    "iteration": 1,
                    "thought": "Routage forcé (factures)",
                    "action": "search_my_claims",
                }
            )

        for iteration in range(MAX_ITERATIONS):
            # 1. Demander au LLM quoi faire
            llm_output = self._call_llm(question, history)

            if llm_output is None:
                return AgentResult(
                    answer="Je ne peux pas traiter cette question pour le moment.",
                    abstention=True,
                    sources=[],
                    steps=steps,
                )

            thought = llm_output.get("thought", "")
            action = llm_output.get("action", "")

            action_brute = llm_output.get("action", "")
            action = _normaliser_action(action_brute)
            if action != action_brute:
                logger.info("Action normalisée : '%s' → '%s'", action_brute, action)

            action_input = llm_output.get("action_input", {})

            steps.append(
                {
                    "iteration": iteration + 1,
                    "thought": thought,
                    "action": action,
                }
            )

            # 2. Si réponse finale → on sort
            if action == "final_answer":
                answer = llm_output.get("answer", "")
                abstention = bool(llm_output.get("abstention", False))

                # Règle : si le LLM prétend répondre sans source, on force l'abstention
                if not abstention and not sources:
                    answer = (
                        "Je ne peux pas répondre à cette question : "
                        "je n'ai pas de source documentaire fiable."
                    )
                    abstention = True

                return AgentResult(
                    answer=answer,
                    abstention=abstention,
                    sources=sources,
                    steps=steps,
                )

            # 3. Sinon, exécuter l'outil demandé
            if action == "search_documents":
                query = action_input.get("query", question)
                results = self._tools.search_documents(query, top_k=5)

                # Filtrer par seuil (anti-hallucination)
                bons = [r for r in results if (r["similarity"] or 0) >= SEUIL_ABSTENTION]

                if bons:
                    sources.extend(r["source"] for r in bons)
                    history.append(
                        f"[TOOL search_documents('{query}')]\n"
                        + "\n\n".join(
                            f"Source: {r['source']['document']} — {r['source']['section']}\n"
                            f"Contenu: {r['contenu'][:100]}"
                            for r in bons
                        )
                    )
                else:
                    history.append(
                        f"[TOOL search_documents('{query}')] Aucun document "
                        f"pertinent (seuil {SEUIL_ABSTENTION})."
                    )

            elif action == "search_my_claims":
                # ⚠️ contract_id vient du JWT, jamais du LLM
                claims = self._tools.search_my_claims(contract_id)
                if claims:
                    history.append(
                        "[TOOL search_my_claims()]\n"
                        + "\n".join(
                            f"- {c['numero_facture']} ({c['date_soin']}) : "
                            f"{c['montant_total']} Ar — {c['statut']}"
                            for c in claims
                        )
                    )
                else:
                    history.append("[TOOL search_my_claims()] Aucune facture trouvée.")

            else:
                logger.warning("Action inconnue : %s", action)
                break

        # Trop d'itérations → abstention
        return AgentResult(
            answer="Je ne parviens pas à répondre à cette question.",
            abstention=True,
            sources=sources,
            steps=steps,
        )

    def _call_llm(self, question: str, history: list[str]) -> dict[str, Any] | None:
        """Appelle le LLM via Ollama et retourne le JSON parsé."""
        prompt = REACT_PROMPT.format(
            question=question,
            history="\n\n".join(history) if history else "(aucune action encore)",
        )

        try:
            response = self._client.post(
                "/api/generate",
                json={
                    "model": self._llm_model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.0},
                },
            )
            response.raise_for_status()
            raw = response.json().get("response", "")

            # Extraire le JSON (parfois entouré de ```)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            return json.loads(raw)

        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
            logger.error("Erreur LLM : %s", exc)
            return None

    def close(self) -> None:
        self._client.close()
