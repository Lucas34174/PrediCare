"""Chunker des Conditions Générales : 1 article = 1 chunk.

Si un article dépasse MAX_TOKENS, il est découpé par paragraphe avec
un léger chevauchement (overlap) pour ne pas perdre le contexte.
"""

from __future__ import annotations

from typing import Any

from predicare.rag.chunkers.base import BaseChunker, Chunk

# Seuil au-delà duquel on découpe un article en sous-chunks
MAX_TOKENS = 800
OVERLAP_TOKENS = 50


def _approx_tokens(text: str) -> int:
    """Approximation : 1 token ≈ 4 caractères en français."""
    return max(1, len(text) // 4)


class ArticleChunker(BaseChunker):
    """Chunker pour les Conditions Générales."""

    chunk_type = "article"

    def __init__(self, formule: str | None = None) -> None:
        self._formule = formule

    def chunk(self, blocks: list[dict[str, Any]]) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0

        for block in blocks:
            if block["block_type"] != "article":
                continue

            article_num = block["article_num"]
            article_titre = block["article_titre"]
            contenu = block["contenu"]
            token_count = _approx_tokens(contenu)

            prefix = (
                f"[Conditions Générales | Formule {self._formule or 'INCONNUE'} "
                f"| Article {article_num} – {article_titre}]"
            )

            if token_count <= MAX_TOKENS:
                # 1 article = 1 chunk
                contenu_enrichi = f"{prefix}\n\n{contenu}"
                metadata = {
                    "formule": self._formule,
                    "article_num": article_num,
                    "article_titre": article_titre,
                    "pages": block.get("pages", []),
                    "block_type": "article",
                    "doc_type": "conditions_generales",
                }
                chunks.append(
                    Chunk(
                        chunk_index=idx,
                        chunk_type=self.chunk_type,
                        contenu_enrichi=contenu_enrichi,
                        metadonnees=metadata,
                        token_count=_approx_tokens(contenu_enrichi),
                    )
                )
                idx += 1
            else:
                # Article long : découpage par paragraphes
                sous_chunks = self._split_paragraphes(prefix, contenu, article_num, article_titre)
                for sc in sous_chunks:
                    sc.chunk_index = idx
                    chunks.append(sc)
                    idx += 1

        return chunks

    def _split_paragraphes(
        self,
        prefix: str,
        contenu: str,
        article_num: int,
        article_titre: str,
    ) -> list[Chunk]:
        """Découpe un long article par paragraphes avec chevauchement."""
        # Découper sur double saut de ligne (paragraphes)
        paragraphes = [p.strip() for p in contenu.split("\n\n") if p.strip()]

        sous_chunks: list[Chunk] = []
        buffer: list[str] = []
        buffer_tokens = 0

        for para in paragraphes:
            para_tokens = _approx_tokens(para)

            if buffer_tokens + para_tokens > MAX_TOKENS and buffer:
                # Flush du buffer actuel
                contenu_buffer = "\n\n".join(buffer)
                contenu_enrichi = f"{prefix}\n\n{contenu_buffer}"
                sous_chunks.append(
                    Chunk(
                        chunk_index=0,  # corrigé après
                        chunk_type="article_partie",
                        contenu_enrichi=contenu_enrichi,
                        metadonnees={
                            "formule": self._formule,
                            "article_num": article_num,
                            "article_titre": article_titre,
                            "partie": len(sous_chunks) + 1,
                            "block_type": "article_partie",
                            "doc_type": "conditions_generales",
                        },
                        token_count=_approx_tokens(contenu_enrichi),
                    )
                )
                # Garder un chevauchement (dernier paragraphe)
                overlap = buffer[-1:]
                buffer = overlap + [para]
                buffer_tokens = sum(_approx_tokens(p) for p in buffer)
            else:
                buffer.append(para)
                buffer_tokens += para_tokens

        # Flush final
        if buffer:
            contenu_buffer = "\n\n".join(buffer)
            contenu_enrichi = f"{prefix}\n\n{contenu_buffer}"
            sous_chunks.append(
                Chunk(
                    chunk_index=0,
                    chunk_type="article_partie",
                    contenu_enrichi=contenu_enrichi,
                    metadonnees={
                        "formule": self._formule,
                        "article_num": article_num,
                        "article_titre": article_titre,
                        "partie": len(sous_chunks) + 1,
                        "block_type": "article_partie",
                        "doc_type": "conditions_generales",
                    },
                    token_count=_approx_tokens(contenu_enrichi),
                )
            )

        return sous_chunks
