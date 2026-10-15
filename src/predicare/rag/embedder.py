"""Client d'embedding BGE-M3 via Ollama.

Choix : BGE-M3 servi localement (pas d'API externe) pour respecter les
contraintes RGPD (pas de transfert hors UE) et EU AI Act (reproductibilité).
"""

from __future__ import annotations

import logging

import httpx

from predicare.rag.config import RagConfig

logger = logging.getLogger(__name__)


class Embedder:
    """Client synchrone pour l'API Ollama d'embedding."""

    def __init__(self, config: RagConfig) -> None:
        self._config = config
        self._client = httpx.Client(
            base_url=config.ollama_base_url,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def embed_one(self, text: str) -> list[float]:
        """Embedding d'un seul texte."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embedding par batch.

        Ollama n'expose pas d'endpoint batch natif : on boucle mais on
        regroupe les appels HTTP pour limiter les allers-retours.
        """
        if not texts:
            return []

        vectors: list[list[float]] = []
        batch_size = self._config.embedding_batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            logger.debug("Embedding batch %d-%d / %d", i, i + len(batch), len(texts))
            for text in batch:
                vectors.append(self._embed_single_http(text))

        if len(vectors) != len(texts):
            raise RuntimeError(f"Nombre de vecteurs incohérent : {len(vectors)} != {len(texts)}")
        return vectors

    def _embed_single_http(self, text: str) -> list[float]:
        """Appel HTTP à Ollama pour un texte."""
        response = self._client.post(
            "/api/embeddings",
            json={"model": self._config.embedding_model, "prompt": text},
        )
        response.raise_for_status()
        payload = response.json()
        embedding = payload.get("embedding")
        if not embedding or len(embedding) != self._config.embedding_dim:
            raise RuntimeError(
                f"Embedding invalide : dim={len(embedding) if embedding else 0}, "
                f"attendu={self._config.embedding_dim}"
            )
        return embedding

    def healthcheck(self) -> bool:
        """Vérifie qu'Ollama répond et que le modèle est disponible."""
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
            models = [m["name"] for m in response.json().get("models", [])]
            return any(self._config.embedding_model in m for m in models)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Healthcheck Ollama échoué : %s", exc)
            return False

    def close(self) -> None:
        self._client.close()
