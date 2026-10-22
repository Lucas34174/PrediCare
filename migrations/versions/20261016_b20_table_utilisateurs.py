"""cree la table utilisateurs (PB-20)

Revision ID: b20_utilisateurs
Revises: rag_cleanup_v1
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b20_utilisateurs"
down_revision: str | None = "rag_cleanup_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = "('assure', 'professionnel_sante', 'gestionnaire', 'administrateur')"


def upgrade() -> None:
    op.create_table(
        "utilisateurs",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("identifiant", sa.String(100), nullable=False, unique=True),
        sa.Column("mot_de_passe_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("nom_complet", sa.String(255), nullable=False),
        sa.Column(
            "assure_id",
            sa.String(20),
            sa.ForeignKey("assures.assure_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prestataire_id",
            sa.String(20),
            sa.ForeignKey("prestataires.prestataire_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actif", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "date_creation",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(f"role IN {ROLES}", name="ck_utilisateurs_role"),
    )
    op.create_index("ix_utilisateurs_identifiant", "utilisateurs", ["identifiant"])


def downgrade() -> None:
    op.drop_index("ix_utilisateurs_identifiant", table_name="utilisateurs")
    op.drop_table("utilisateurs")
