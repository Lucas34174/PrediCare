"""rendre colonnes heritees nullables

Revision ID: rag_cleanup_v1
Revises: rag_corpus_audit
Create Date: 2026-10-15 18:14:30.268119
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rag_cleanup_v1"
down_revision: str | None = "rag_corpus_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("documents_vectorises", "titre_document", nullable=True)
    # Idem pour formule_concernee si elle est NOT NULL
    op.alter_column("documents_vectorises", "formule_concernee", nullable=True)


def downgrade() -> None:
    op.alter_column("documents_vectorises", "titre_document", nullable=False)
    op.alter_column("documents_vectorises", "formule_concernee", nullable=False)
