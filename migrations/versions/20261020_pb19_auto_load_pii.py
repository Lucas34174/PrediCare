"""PB-19 — chargement automatique idempotent et métadonnées PII

Revision ID: pb19_auto_load_pii
Revises: b20_utilisateurs
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "pb19_auto_load_pii"
down_revision: str | None = "b20_utilisateurs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUTS = "('running', 'completed', 'failed', 'skipped')"


def upgrade() -> None:
    # Version de clé utilisée pour les PII. Permet une rotation future sans
    # bloquer la lecture des données historiques.
    op.add_column(
        "identites_pii",
        sa.Column(
            "pii_key_version",
            sa.SmallInteger(),
            nullable=False,
            server_default="1",
        ),
    )

    # Journal idempotent du bootstrap. Une seule ligne par jeu de données.
    op.create_table(
        "ingest_state",
        sa.Column("dataset_key", sa.String(50), primary_key=True),
        sa.Column("dataset_checksum", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "rows_loaded",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_dir", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        # Copie chiffrée d'une valeur connue : permet de vérifier, au démarrage
        # suivant, que la clé fournie est bien celle utilisée pour le chargement.
        sa.Column("pii_canary", sa.LargeBinary(), nullable=True),
        sa.CheckConstraint(f"status IN {STATUTS}", name="ck_ingest_state_status"),
    )
    op.create_index("ix_ingest_state_status", "ingest_state", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ingest_state_status", table_name="ingest_state")
    op.drop_table("ingest_state")
    op.drop_column("identites_pii", "pii_key_version")
