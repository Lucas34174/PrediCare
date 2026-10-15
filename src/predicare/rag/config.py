"""Configuration du pipeline RAG.

Toutes les valeurs sont surchargeables par variables d'environnement pour
respecter la logique FinOps (pas de hardcode) et faciliter l'audit EU AI Act
(traçabilité des paramètres utilisés).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RagConfig:
    """Paramètres figés du pipeline RAG.

    Modèle d'embedding : BGE-M3 (1024 dimensions), servi en local via Ollama.
    Ce choix est documenté dans docs/decisions.md (FinOps, RGPD, EU AI Act).
    """

    # Ollama
    ollama_base_url: str
    embedding_model: str
    embedding_dim: int

    # Batch
    embedding_batch_size: int

    # Chemins
    corpus_dir: Path

    @classmethod
    def from_env(cls) -> "RagConfig":
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "bge-m3"),
            embedding_dim=int(os.getenv("EMBEDDING_DIM", "1024")),
            embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "16")),
            corpus_dir=Path(os.getenv("RAG_CORPUS_DIR", "/data/raw/corpus")),
        )

    @property
    def version_modele_embedding(self) -> str:
        """Identifiant versionné du modèle, à stocker en base pour audit."""
        return f"{self.embedding_model}@{self.embedding_dim}"