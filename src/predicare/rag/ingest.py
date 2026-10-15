"""Orchestration de l'ingestion d'un fichier dans le corpus RAG.

Flux :
  1. Calcul du SHA256 → skip si déjà indexé (idempotence)
  2. Détection du type via nom de fichier
  3. Parsing spécialisé
  4. Chunking spécialisé
  5. Embedding batch (Ollama/BGE-M3)
  6. Insertion transactionnelle (documents + documents_vectorises)
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import re

from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicare.rag.chunkers.article_chunker import ArticleChunker
from predicare.rag.chunkers.bareme_chunker import BaremeChunker
from predicare.rag.config import RagConfig
from predicare.rag.embedder import Embedder
from predicare.rag.parsers.bareme import BaremeParser
from predicare.rag.parsers.base import ParsedDocument
from predicare.rag.parsers.conditions_generales import ConditionsGeneralesParser
from predicare.rag.chunkers.beneficiaire_chunker import BeneficiaireChunker
from predicare.rag.parsers.conditions_particulieres import ConditionsParticulieresParser


logger = logging.getLogger(__name__)


# Table de correspondance nom de fichier → (parser, chunker)
# Étendue au fur et à mesure des types supportés.
MOTIFS_PAR_TYPE: list[tuple[re.Pattern, type, type]] = [
    (
        re.compile(r"^Bareme_Reference_Actes\.pdf$"),
        BaremeParser,
        BaremeChunker,
    ),
    (
        re.compile(r"^Conditions_Generales_(CONFORT|ESSENTIEL|PREMIUM)\.pdf$"),
        ConditionsGeneralesParser,
        ArticleChunker,
    ),
    (
        re.compile(r"^CP_CTR-\d+\.pdf$"),
        ConditionsParticulieresParser,
        BeneficiaireChunker,
    ),
    (
        re.compile(r"^Guide_Reseau_Soins_.*\.pdf$"),
        GuideReseauParser,
        PrestataireChunker,
    ),
]


def detecter_type(path: Path) -> tuple[type, type] | None:
    """Détecte le parser + chunker selon le nom du fichier (par motif)."""
    for pattern, parser_cls, chunker_cls in MOTIFS_PAR_TYPE:
        if pattern.match(path.name):
            return parser_cls, chunker_cls
    return None


def calculer_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def construire_chunker(chunker_cls, parsed: ParsedDocument):
    """Instancie le chunker avec les paramètres adaptés."""
    if chunker_cls is ArticleChunker:
        return chunker_cls(formule=parsed.metadata.get("formule"))
    return chunker_cls()


class Ingestor:
    def __init__(self, engine: Engine, config: RagConfig) -> None:
        self._engine = engine
        self._config = config
        self._embedder = Embedder(config)

    def ingest_file(self, path: Path) -> dict:
        """Ingère un fichier. Retourne un rapport (résumé du résultat)."""
        if not path.exists():
            raise FileNotFoundError(path)

        checksum = calculer_checksum(path)
        logger.info("Fichier %s | checksum=%s", path.name, checksum[:12])

        # 1. Idempotence
        with self._engine.begin() as conn:
            existing = conn.execute(
                text(
                    "SELECT id FROM documents "
                    "WHERE source_path = :p AND checksum_sha256 = :c AND actif = true"
                ),
                {"p": str(path), "c": checksum},
            ).scalar()
        if existing:
            logger.info("Déjà indexé (document_id=%s) → skip", existing)
            return {"status": "skipped", "document_id": existing}

        # 2. Détection + parsing + chunking
        detected = detecter_type(path)
        if not detected:
            raise ValueError(f"Aucun parser pour {path.name}")
        parser_cls, chunker_cls = detected
        parser = parser_cls()
        parsed = parser.parse(path)
        chunker = construire_chunker(chunker_cls, parsed)

        chunks = chunker.chunk(parsed.raw_blocks)
        logger.info("Parsing : %d blocs → %d chunks", len(parsed.raw_blocks), len(chunks))

        # 3. Embedding
        texts = [c.contenu_enrichi for c in chunks]
        vectors = self._embedder.embed_batch(texts)

        # 4. Insertion transactionnelle
        with self._engine.begin() as conn:
            # Désactiver l'ancien document s'il existe
            conn.execute(
                text(
                    "UPDATE documents SET actif = false, date_mise_a_jour = now() "
                    "WHERE source_path = :p AND actif = true"
                ),
                {"p": str(path)},
            )

            # Insertion du document parent
            doc_id = conn.execute(
                text(
                    """
                    INSERT INTO documents (
                        source_path, source_filename, doc_type, formule,
                        contract_id, checksum_sha256, nb_pages,
                        version_modele_embedding, metadonnees
                    ) VALUES (
                        :source_path, :source_filename, :doc_type, :formule,
                        :contract_id, :checksum, :nb_pages,
                        :version, :metadata
                    ) RETURNING id
                    """
                ),
                {
                    "source_path": str(path),
                    "source_filename": path.name,
                    "doc_type": parsed.doc_type,
                    "formule": parsed.metadata.get("formule"),
                    "contract_id": parsed.metadata.get("contract_id"),
                    "checksum": checksum,
                    "nb_pages": parsed.nb_pages,
                    "version": self._config.version_modele_embedding,
                    "metadata": _json(parsed.metadata),
                },
            ).scalar_one()

            # Insertion des chunks
            for chunk, vector in zip(chunks, vectors, strict=True):
                conn.execute(
                    text(
                        """
                        INSERT INTO documents_vectorises (
                            document_id, chunk_index, chunk_type,
                            contenu, contenu_enrichi, token_count,
                            embedding, metadonnees
                        ) VALUES (
                            :doc_id, :chunk_index, :chunk_type,
                            :contenu, :contenu_enrichi, :token_count,
                            :embedding, :metadata
                        )
                        """
                    ),
                    {
                        "doc_id": doc_id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_type": chunk.chunk_type,
                        "contenu": chunk.contenu_enrichi,  # brut et enrichi identiques ici
                        "contenu_enrichi": chunk.contenu_enrichi,
                        "token_count": chunk.token_count,
                        "embedding": vector,
                        "metadata": _json(chunk.metadonnees),
                    },
                )

        logger.info("Ingestion terminée : document_id=%s, %d chunks", doc_id, len(chunks))
        return {
            "status": "indexed",
            "document_id": doc_id,
            "nb_chunks": len(chunks),
            "checksum": checksum,
        }

    def close(self) -> None:
        self._embedder.close()


def _json(data: dict) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)
