"""Interfaces communes aux chunkers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """Chunk prêt à être enrichi, embeddé et inséré."""

    chunk_index: int
    chunk_type: str
    contenu_enrichi: str
    metadonnees: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0


class BaseChunker:
    """Interface à implémenter par chaque chunker spécialisé."""

    chunk_type: str = ""

    def chunk(self, blocks: list[dict[str, Any]]) -> list[Chunk]:
        raise NotImplementedError