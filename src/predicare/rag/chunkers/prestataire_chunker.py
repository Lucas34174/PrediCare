"""Chunker du Guide Réseau : 1 prestataire = 1 chunk."""

from __future__ import annotations

from typing import Any

from predicare.rag.chunkers.base import BaseChunker, Chunk


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class PrestataireChunker(BaseChunker):
    chunk_type = "prestataire"

    def chunk(self, blocks: list[dict[str, Any]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for idx, block in enumerate(blocks):
            if block.get("block_type") != "prestataire":
                continue
            chunks.append(self._chunk_prestataire(idx, block))
        return chunks

    def _chunk_prestataire(self, idx: int, block: dict[str, Any]) -> Chunk:
        prefix = (
            f"[Guide Réseau | Catégorie: {block['categorie']} "
            f"| Ville: {block['ville'] or 'non précisée'}]"
        )
        # Contenu enrichi : on privilégie la ligne brute si le parsing est incomplet
        contenu = (
            f"{prefix}\n"
            f"Prestataire : {block['nom']}\n"
            f"Horaires : {block['horaires'] or 'non renseignés'}\n"
            f"Contact : {block['contact'] or 'non renseigné'}\n"
            f"Détails : {block['ligne_brute']}"
        )
        return Chunk(
            chunk_index=idx,
            chunk_type=self.chunk_type,
            contenu_enrichi=contenu,
            metadonnees={
                "numero": block["numero"],
                "categorie": block["categorie"],
                "ville": block["ville"],
                "prestataire_nom": block["nom"],
                "horaires": block["horaires"],
                "contact": block["contact"],
                "qualite": block["qualite"],
                "source_guide": block["source_guide"],
                "block_type": "prestataire",
                "doc_type": "guide_reseau",
            },
            token_count=_approx_tokens(contenu),
        )