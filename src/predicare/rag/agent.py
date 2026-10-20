"""Agent ReAct sourcé pour PrediCare TPA (Fast Path - POC)."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import Engine

from predicare.rag.config import RagConfig
from predicare.rag.retriever import Retriever
from predicare.rag.tools import Tools

logger = logging.getLogger(__name__)

SEUIL_ABSTENTION = 0.60


@dataclass
class AgentResult:
    answer: str
    abstention: bool
    sources: list[dict[str, str]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)


class ReactAgent:
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
        self._tools = Tools(engine, retriever)
        self._llm_model = llm_model
        # Timeout volontairement court (10s) pour éviter les blocages
        self._client = httpx.Client(
            base_url=config.ollama_base_url,
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    def run(self, question: str, contract_id: str) -> AgentResult:
        steps = []
        sources = []
        context_parts = []

        if not question.strip():
            return AgentResult(
                answer="Je ne peux pas répondre à une question vide.", abstention=True, steps=[]
            )

        q_lower = question.lower()

        # 0. GESTION DES SALUTATIONS
        if q_lower.strip() in ["bonjour", "salut", "hello", "bonsoir"]:
            return AgentResult(
                answer="Bonjour ! Je suis l'assistant PrediCare. Posez-moi une question sur vos garanties ou le barème.",
                abstention=False,
                sources=[],
                steps=[],
            )

        # --- GARDE-FOU 1 : Détection de prompt injection / jailbreak ---
        mots_interdits = [
            "ignore tes instructions",
            "ignore les instructions",
            "tu es maintenant",
            "sans restriction",
            "jailbreak",
            "mot de passe",
            "password",
            "system prompt",
        ]
        if any(mot in q_lower for mot in mots_interdits):
            steps.append({"action": "security_block", "reason": "prompt_injection"})
            return AgentResult(
                answer="Je ne peux pas répondre à cette question pour des raisons de sécurité.",
                abstention=True,
                steps=steps,
            )

        # --- GARDE-FOU 2 : Détection d'exfiltration d'un autre contrat ---
        import re

        autres_contrats = re.findall(r"CTR-\d{6}", question, re.IGNORECASE)
        for c in autres_contrats:
            if c.upper() != contract_id.upper():
                steps.append({"action": "security_block", "reason": "cross_tenant_access"})
                return AgentResult(
                    answer="Je n'ai pas accès aux informations des autres contrats.",
                    abstention=True,
                    steps=steps,
                )

        # --- CACHE SÉMANTIQUE ---
        cached_answer = self._check_cache(question)
        if cached_answer:
            return AgentResult(
                answer=cached_answer,
                abstention=False,
                sources=[],
                steps=[{"action": "cache_hit", "status": "success"}],
            )

        # 1. ROUTAGE SQL (Factures)
        if any(
            k in q_lower
            for k in ["facture", "remboursement", "dossier", "attente", "rejet", "payé", "paye"]
        ):
            claims = self._tools.search_my_claims(contract_id)
            if claims:
                steps.append({"action": "search_my_claims", "status": "success"})
                context_parts.append(
                    "Voici vos factures :\n"
                    + "\n".join(
                        f"- {c['numero_facture']} : {c['montant_total']} Ar ({c['statut']})"
                        for c in claims
                    )
                )
                sources.append({"document": "Votre dossier", "section": "Factures"})
            else:
                steps.append({"action": "search_my_claims", "status": "empty"})
                context_parts.append("Aucune facture trouvée pour votre contrat.")

        # 2. ROUTAGE RAG (Documents)
        if not context_parts:
            filters = {"contract_id": contract_id} if contract_id else None
            results = self._retriever.search(
                question, top_k=3, filters=filters, min_similarity=0.30
            )
            if not results:
                results = self._retriever.search(question, top_k=3, min_similarity=0.30)

            bons = [r for r in results if (r.score_vector or 0) >= SEUIL_ABSTENTION]

            if bons:
                steps.append({"action": "search_documents", "status": "success"})
                for r in bons:
                    sources.append(self._tools._extraire_source(r))
                    context_parts.append(r.contenu)
            else:
                return AgentResult(
                    answer="Je ne peux pas répondre : aucune source fiable trouvée.",
                    abstention=True,
                    steps=[{"action": "search_documents", "status": "failed"}],
                )

        # 3. GÉNÉRATION
        contexte = "\n\n".join(context_parts)
        answer = self._generate_answer(question, contexte)

        if not answer.startswith("D'après le document"):
            self._save_cache(question, answer)

        return AgentResult(answer=answer, abstention=False, sources=sources, steps=steps)

    def _generate_answer(self, question: str, contexte: str) -> str:
        import re

        contexte_propre = re.sub(r"\[.*?\]", "", contexte).strip()

        # On découpe par double saut de ligne pour isoler les documents
        documents = contexte_propre.split("\n\n")

        # ON NE GARDE QUE LE PREMIER DOCUMENT (le plus pertinent)
        premier_doc = documents[0] if documents else contexte_propre
        lignes = [l.strip() for l in premier_doc.split("\n") if l.strip()]

        infos_cles = []
        for l in lignes:
            if any(
                k in l
                for k in [
                    "Tarif",
                    "Contact",
                    "Horaires",
                    "Prestataire",
                    "Adresse",
                    "Exclu",
                    "pris en charge",
                    "taux",
                    "Libellé",
                ]
            ):
                infos_cles.append(l)

        if not infos_cles and lignes:
            infos_cles = [lignes[0]]

        resume = "\n".join(infos_cles[:4])  # Max 4 lignes du MÊME document

        # Le prompt pour le LLM
        prompt = (
            f"Voici les informations extraites d'un document officiel :\n"
            f"{resume}\n\n"
            f"Question de l'assuré : {question}\n\n"
            f"Rédige une réponse polie, claire et concise (1 ou 3 phrases) en te basant STRICTEMENT sur ces informations."
        )

        try:
            response = self._client.post(
                "/api/generate",
                json={
                    "model": self._llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 90},
                },
                timeout=50.0,
            )
            response.raise_for_status()
            ans = response.json().get("response", "").strip()
            if ans:
                return ans
        except Exception as exc:
            logger.warning("LLM trop lent (%s). Fallback local.", exc)

        # Fallback
        return f"D'après le document source :\n\n- {resume}\n\n(Note : Le générateur de texte est indisponible, voici l'extrait brut.)"

    def close(self) -> None:
        self._client.close()

    def _check_cache(self, question: str) -> str | None:
        """Cherche une réponse en cache pour cette question."""
        from sqlalchemy import text

        query_norm = question.lower().strip()

        with self._engine.begin() as conn:  # begin() permet le commit auto
            row = conn.execute(
                text("""
                SELECT response_text FROM semantic_cache
                WHERE query_text = :q LIMIT 1
            """),
                {"q": query_norm},
            ).fetchone()

            if row:
                # Incrémenter le hit_count
                conn.execute(
                    text("""
                    UPDATE semantic_cache SET hit_count = hit_count + 1
                    WHERE query_text = :q
                """),
                    {"q": query_norm},
                )
                return row[0]
        return None

    def _save_cache(self, question: str, response: str):
        from sqlalchemy import text

        query_norm = question.lower().strip()
        query_hash = hashlib.sha256(query_norm.encode("utf-8")).hexdigest()

        # Calcul de l'embedding
        embedding = self._retriever._embedder.embed_one(query_norm)
        # (vérifiez le nom exact de la méthode de votre embedder)

        with self._engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO semantic_cache (query_text, query_hash, query_embedding, response_text, hit_count)
                VALUES (:q, :h, :e, :r, 1)
                ON CONFLICT DO NOTHING
            """),
                {"q": query_norm, "h": query_hash, "e": embedding, "r": response},
            )
