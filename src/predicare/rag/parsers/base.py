"""Interfaces communes aux parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    """Résultat d'un parsing : contenu structuré + métadonnées globales."""

    source_path: Path
    doc_type: str
    raw_blocks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    nb_pages: int = 0


class BaseParser:
    """Interface à implémenter par chaque parser spécialisé."""

    doc_type: str = ""

    def parse(self, path: Path) -> ParsedDocument:
        raise NotImplementedError
