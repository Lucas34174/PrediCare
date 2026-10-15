"""Chunker du barème : 1 ligne = 1 chunk, avec préfixe contextuel.

Règle d'enrichissement : on ne stocke jamais le texte brut d'une ligne de
tableau. On préfixe avec le contexte (type, catégorie, code) pour que
l'embedding soit sémantiquement interrogeable.
"""

from __future__ import annotations

from typing import Any

from predicare.rag.chunkers.base import BaseChunker, Chunk


def _fmt_montant(value: int | None) -> str:
    if value is None:
        return "non renseigné"
    return f"{value:,} Ar".replace(",", " ")


class BaremeChunker(BaseChunker):
    chunk_type = "ligne_bareme"

    def chunk(self, blocks: list[dict[str, Any]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for idx, block in enumerate(blocks):
            if block["block_type"] == "acte":
                chunks.append(self._chunk_acte(idx, block))
            elif block["block_type"] == "medicament":
                chunks.append(self._chunk_medicament(idx, block))
        return chunks

    def _chunk_acte(self, idx: int, block: dict[str, Any]) -> Chunk:
        prefix = f"[Barème | Catégorie: {block['categorie']} | Code: {block['code']}]"
        contenu = (
            f"{prefix}\n"
            f"Libellé : {block['libelle']}\n"
            f"Tarif minimum : {_fmt_montant(block['tarif_min'])}\n"
            f"Tarif de référence : {_fmt_montant(block['tarif_reference'])}\n"
            f"Tarif maximum : {_fmt_montant(block['tarif_max'])}\n"
            f"Ordonnance requise : {'oui' if block['ordonnance_requise'] else 'non'}\n"
            f"Entente préalable : {'oui' if block['entente_requise'] else 'non'}\n"
            f"Restriction : {block['restriction'] or 'aucune'}"
        )
        metadata = {
            "code_acte": block["code"],
            "libelle": block["libelle"],
            "categorie": block["categorie"],
            "tarif_min": block["tarif_min"],
            "tarif_reference": block["tarif_reference"],
            "tarif_max": block["tarif_max"],
            "ordonnance_requise": block["ordonnance_requise"],
            "entente_requise": block["entente_requise"],
            "restriction": block["restriction"],
            "page": block["page"],
            "block_type": "acte",
        }
        return Chunk(
            chunk_index=idx,
            chunk_type=self.chunk_type,
            contenu_enrichi=contenu,
            metadonnees=metadata,
            token_count=_approx_tokens(contenu),
        )

    def _chunk_medicament(self, idx: int, block: dict[str, Any]) -> Chunk:
        prefix = f"[Barème | Médicament | Classe: {block['classe']} | Code: {block['code']}]"
        rembourse = "oui" if block["remboursable"] else "non (exclu)"
        contenu = (
            f"{prefix}\n"
            f"Libellé : {block['libelle']}\n"
            f"Classe : {block['classe']}\n"
            f"Prix de référence : {_fmt_montant(block['prix_reference'])}\n"
            f"Remboursable : {rembourse}"
        )
        metadata = {
            "code_medicament": block["code"],
            "libelle": block["libelle"],
            "classe": block["classe"],
            "prix_reference": block["prix_reference"],
            "remboursable": block["remboursable"],
            "page": block["page"],
            "block_type": "medicament",
        }
        return Chunk(
            chunk_index=idx,
            chunk_type=self.chunk_type,
            contenu_enrichi=contenu,
            metadonnees=metadata,
            token_count=_approx_tokens(contenu),
        )


def _approx_tokens(text: str) -> int:
    """Approximation grossière : 1 token ≈ 4 caractères (FR)."""
    return max(1, len(text) // 4)
