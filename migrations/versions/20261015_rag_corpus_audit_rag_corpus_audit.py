"""rag corpus audit

Revision ID: rag_corpus_audit
Revises: 082a41d129c2
Create Date: 2026-10-15 13:20:42.612846
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "rag_corpus_audit"
down_revision: str | None = "082a41d129c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Table documents (parent)
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("source_path", sa.Text(), nullable=False, unique=True),
        sa.Column("source_filename", sa.Text(), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("formule", sa.String(20), nullable=True),
        sa.Column("contract_id", sa.String(20), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("nb_pages", sa.SmallInteger(), nullable=True),
        sa.Column("version_modele_embedding", sa.String(50), nullable=False),
        sa.Column("metadonnees", postgresql.JSONB(), nullable=True),
        sa.Column("actif", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "date_indexation",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "date_mise_a_jour",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_type", "documents", ["doc_type"])
    op.create_index("ix_documents_formule", "documents", ["formule"])
    op.create_index("ix_documents_checksum", "documents", ["checksum_sha256"])

    # 2. Enrichir documents_vectorises
    op.add_column(
        "documents_vectorises",
        sa.Column(
            "document_id",
            sa.BigInteger(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("documents_vectorises", sa.Column("chunk_index", sa.Integer(), nullable=True))
    op.add_column("documents_vectorises", sa.Column("chunk_type", sa.String(40), nullable=True))
    op.add_column("documents_vectorises", sa.Column("token_count", sa.Integer(), nullable=True))
    op.add_column("documents_vectorises", sa.Column("contenu_enrichi", sa.Text(), nullable=True))
    op.add_column(
        "documents_vectorises",
        sa.Column("actif", sa.Boolean(), server_default="true", nullable=False),
    )

    # 3. Index HNSW pour recherche vectorielle
    op.execute(
        "CREATE INDEX ix_documents_vectorises_embedding_hnsw "
        "ON documents_vectorises USING hnsw (embedding vector_cosine_ops)"
    )

    # 4. Index full-text français
    op.execute(
        "CREATE INDEX ix_documents_vectorises_content_fts "
        "ON documents_vectorises USING gin (to_tsvector('french', contenu))"
    )

    # 5. Index JSONB
    op.execute(
        "CREATE INDEX ix_documents_vectorises_metadonnees "
        "ON documents_vectorises USING gin (metadonnees)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_vectorises_metadonnees")
    op.execute("DROP INDEX IF EXISTS ix_documents_vectorises_content_fts")
    op.execute("DROP INDEX IF EXISTS ix_documents_vectorises_embedding_hnsw")
    op.drop_column("documents_vectorises", "actif")
    op.drop_column("documents_vectorises", "contenu_enrichi")
    op.drop_column("documents_vectorises", "token_count")
    op.drop_column("documents_vectorises", "chunk_type")
    op.drop_column("documents_vectorises", "chunk_index")
    op.drop_column("documents_vectorises", "document_id")
    op.drop_index("ix_documents_checksum", "documents")
    op.drop_index("ix_documents_formule", "documents")
    op.drop_index("ix_documents_type", "documents")
    op.drop_table("documents")