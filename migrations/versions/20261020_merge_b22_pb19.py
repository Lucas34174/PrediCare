"""merge b22_predictions_alignement et pb19_auto_load_pii

Revision ID: merge_b22_pb19
Revises: b22_predictions_alignement, pb19_auto_load_pii
Create Date: 2026-10-20
"""

from collections.abc import Sequence

revision: str = "merge_b22_pb19"
down_revision: tuple[str, str] = ("b22_predictions_alignement", "pb19_auto_load_pii")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
