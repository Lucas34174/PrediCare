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
        # Construire un contenu propre, colonne par colonne
        lignes = [prefix, f"Prestataire : {block['nom']}"]
        if block.get("categorie"):
            lignes.append(f"Catégorie : {block['categorie']}")
        if block.get("ville"):
            lignes.append(f"Ville : {block['ville']}")
        if block.get("horaires"):
            lignes.append(f"Horaires : {block['horaires']}")
        if block.get("contact"):
            lignes.append(f"Contact : {block['contact']}")
        if block.get("adresse"):
            lignes.append(f"Adresse : {block['adresse']}")
        if block.get("tarifs"):
            lignes.append(f"Tarifs : {block['tarifs']}")
        if block.get("qualite"):
            lignes.append(f"Évaluation : {block['qualite']}")
        # Fallback : si trop d'infos manquantes, on garde la ligne brute
        if not (block.get("contact") and block.get("horaires")):
            lignes.append(f"Détails : {block['ligne_brute']}")
    
        contenu = "\n".join(lignes)
        return Chunk(
            chunk_index=idx,
            chunk_type=self.chunk_type,
            contenu_enrichi=contenu,
            metadonnees={
                "numero": block["numero"],
                "categorie": block["categorie"],
                "ville": block["ville"],
                "prestataire_nom": block["nom"],
                "horaires": block.get("horaires"),
                "contact": block.get("contact"),
                "adresse": block.get("adresse"),
                "tarifs": block.get("tarifs"),
                "qualite": block.get("qualite"),
                "source_guide": block["source_guide"],
                "block_type": "prestataire",
                "doc_type": "guide_reseau",
            },
            token_count=_approx_tokens(contenu),
        )