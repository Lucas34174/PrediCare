"""alignement colonne est_anomalie table predictions (PB-22)

Revision ID: b22_predictions_alignement
Revises: b20_utilisateurs
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b22_predictions_alignement"
down_revision: str | None = "b20_utilisateurs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Renomme est_alerte -> est_anomalie pour correspondre au contrat d'interface
    op.alter_column("predictions", "est_alerte", new_column_name="est_anomalie")


def downgrade() -> None:
    op.alter_column("predictions", "est_anomalie", new_column_name="est_alerte")
