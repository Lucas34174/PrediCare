"""Table de configuration applicative dynamique (PB-25).

Revision ID: b25_app_config
Revises: merge_b22_pb19
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b25_app_config"
down_revision: str | None = "merge_b22_pb19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_config",
        sa.Column("cle", sa.String(50), primary_key=True),
        sa.Column("valeur", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_by", sa.String(50), nullable=True),
    )
    op.create_index("ix_app_config_updated_at", "app_config", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_app_config_updated_at", table_name="app_config")
    op.drop_table("app_config")
