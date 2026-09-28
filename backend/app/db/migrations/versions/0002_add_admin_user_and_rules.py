"""placeholder migration - keep for future data seeds or truncate

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Placeholder for future data seed or data-only migration.
    pass


def downgrade() -> None:
    pass