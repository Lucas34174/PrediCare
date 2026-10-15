"""plateforme ia

Revision ID: 082a41d129c2
Revises: 82a5a406f960
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "082a41d129c2"
down_revision: str | None = "82a5a406f960"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONTANT = sa.BigInteger()
# Dimension du modèle d'embedding (e5-large / bge-m3 : 1024). Choix à valider (docs/decisions.md).
DIM_EMBEDDING = 1024


def upgrade() -> None:
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "facture_id",
            sa.String(20),
            sa.ForeignKey("factures.facture_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score_fraude", sa.Float(), nullable=False),
        sa.Column("est_alerte", sa.Boolean(), nullable=False),
        sa.Column("seuil_applique", sa.Float(), nullable=False),
        sa.Column("version_modele", sa.String(50), nullable=False),
        sa.Column(
            "date_prediction",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("score_fraude BETWEEN 0 AND 1", name="ck_predictions_score"),
    )
    op.create_index("ix_predictions_facture", "predictions", ["facture_id"])
    op.create_index("ix_predictions_date", "predictions", ["date_prediction"])

    op.create_table(
        "explications_shap",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "prediction_id",
            sa.BigInteger(),
            sa.ForeignKey("predictions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("top_features", postgresql.JSONB(), nullable=False),
        sa.Column("valeurs_shap", postgresql.JSONB(), nullable=True),
        sa.Column(
            "date_generation",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # gestionnaire_id sans clé étrangère : la table des utilisateurs arrive avec PB-20.
    op.create_table(
        "decisions_gestionnaire",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "facture_id",
            sa.String(20),
            sa.ForeignKey("factures.facture_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "prediction_id",
            sa.BigInteger(),
            sa.ForeignKey("predictions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("motif", sa.Text(), nullable=True),
        sa.Column("montant_final_accorde", MONTANT, nullable=True),
        sa.Column("gestionnaire_id", sa.String(50), nullable=False),
        sa.Column(
            "date_decision",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_decisions_facture", "decisions_gestionnaire", ["facture_id"])

    op.create_table(
        "documents_vectorises",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("titre_document", sa.String(255), nullable=False),
        sa.Column("formule_concernee", sa.String(20), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(DIM_EMBEDDING), nullable=False),
        sa.Column("metadonnees", postgresql.JSONB(), nullable=True),
        sa.Column(
            "date_indexation",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "semantic_cache",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("query_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_embedding", Vector(DIM_EMBEDDING), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "journal_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("type_action", sa.String(100), nullable=False),
        sa.Column("utilisateur_id", sa.String(50), nullable=True),
        sa.Column("role_utilisateur", sa.String(30), nullable=True),
        sa.Column("ressource_type", sa.String(50), nullable=True),
        sa.Column("ressource_id", sa.String(100), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("ip_source", sa.String(45), nullable=True),
        sa.Column(
            "date_action", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_journal_audit_date", "journal_audit", ["date_action"])
    op.create_index(
        "ix_journal_audit_ressource", "journal_audit", ["ressource_type", "ressource_id"]
    )


def downgrade() -> None:
    op.drop_table("journal_audit")
    op.drop_table("semantic_cache")
    op.drop_table("documents_vectorises")
    op.drop_table("decisions_gestionnaire")
    op.drop_table("explications_shap")
    op.drop_table("predictions")
