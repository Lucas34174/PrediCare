"""Parser spécialisé pour le Barème de référence des actes et médicaments.

Structure observée :
- 1 fichier : Bareme_Reference_Actes.pdf
- Plusieurs tableaux, chacun avec les colonnes :
  Code | Libellé | Catégorie | Min | Référence | Max | Ordonnance | Entente | Restriction
- 1 ligne = 1 acte ou 1 médicament
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pdfplumber

from predicare.rag.parsers.base import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)

# Colonnes attendues dans les tableaux du barème
COLONNES_ATTENDUES = [
    "Code",
    "Libellé",
    "Catégorie",
    "Min",
    "Référence",
    "Max",
    "Ordonnance",
    "Entente",
    "Restriction",
]

# Colonnes pour les médicaments
COLONNES_MEDICAMENTS = [
    "Code",
    "Libellé",
    "Classe",
    "Prix de référence",
    "Remboursable",
]


def _normalize_header(cell: str) -> str:
    return re.sub(r"\s+", " ", (cell or "").strip())


def _parse_montant(cell: str) -> int | None:
    """Convertit '10 000 Ar' en 10000, ou None si non numérique."""
    if not cell:
        return None
    cleaned = re.sub(r"[^\d]", "", cell)
    return int(cleaned) if cleaned else None


class BaremeParser(BaseParser):
    """Parser du barème (actes + médicaments)."""

    doc_type = "bareme"

    def parse(self, path: Path) -> ParsedDocument:
        logger.info("Parsing barème : %s", path.name)
        blocks: list[dict[str, Any]] = []
        nb_pages = 0

        with pdfplumber.open(path) as pdf:
            nb_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    header = [_normalize_header(c) for c in table[0]]

                    # Détection du type de tableau
                    if self._is_tableau_actes(header):
                        blocks.extend(self._parse_tableau_actes(table, page_num))
                    elif self._is_tableau_medicaments(header):
                        blocks.extend(self._parse_tableau_medicaments(table, page_num))
                    else:
                        logger.debug("Tableau non reconnu page %d : %s", page_num, header)

        return ParsedDocument(
            source_path=path,
            doc_type=self.doc_type,
            raw_blocks=blocks,
            metadata={"type_source": "bareme_reference"},
            nb_pages=nb_pages,
        )

    @staticmethod
    def _is_tableau_actes(header: list[str]) -> bool:
        return "Code" in header and "Catégorie" in header and "Référence" in header

    @staticmethod
    def _is_tableau_medicaments(header: list[str]) -> bool:
        return "Code" in header and "Classe" in header and "Remboursable" in header

    def _parse_tableau_actes(self, table: list[list[str]], page_num: int) -> list[dict[str, Any]]:
        header = [_normalize_header(c) for c in table[0]]
        blocks: list[dict[str, Any]] = []

        for row in table[1:]:
            if not row or not row[0]:
                continue
            row_norm = [_normalize_header(c) for c in row]
            data = dict(zip(header, row_norm, strict=False))

            code = data.get("Code", "").strip()
            libelle = data.get("Libellé", "").strip()
            if not code or not libelle:
                continue

            blocks.append(
                {
                    "block_type": "acte",
                    "code": code,
                    "libelle": libelle,
                    "categorie": data.get("Catégorie", "").strip(),
                    "tarif_min": _parse_montant(data.get("Min", "")),
                    "tarif_reference": _parse_montant(data.get("Référence", "")),
                    "tarif_max": _parse_montant(data.get("Max", "")),
                    "ordonnance_requise": bool(data.get("Ordonnance", "").strip()),
                    "entente_requise": bool(data.get("Entente", "").strip()),
                    "restriction": data.get("Restriction", "").strip() or None,
                    "page": page_num,
                }
            )
        return blocks

    def _parse_tableau_medicaments(
        self, table: list[list[str]], page_num: int
    ) -> list[dict[str, Any]]:
        header = [_normalize_header(c) for c in table[0]]
        blocks: list[dict[str, Any]] = []

        for row in table[1:]:
            if not row or not row[0]:
                continue
            row_norm = [_normalize_header(c) for c in row]
            data = dict(zip(header, row_norm, strict=False))

            code = data.get("Code", "").strip()
            libelle = data.get("Libellé", "").strip()
            if not code or not libelle:
                continue

            remboursable_cell = data.get("Remboursable", "").strip().lower()
            remboursable = remboursable_cell == "oui"

            blocks.append(
                {
                    "block_type": "medicament",
                    "code": code,
                    "libelle": libelle,
                    "classe": data.get("Classe", "").strip(),
                    "prix_reference": _parse_montant(data.get("Prix de référence", "")),
                    "remboursable": remboursable,
                    "page": page_num,
                }
            )
        return blocks
