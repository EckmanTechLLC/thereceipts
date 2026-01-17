"""add claim_type_category to claim_cards

Revision ID: b9e5a8c4d7f6
Revises: a8b4e7f2d3c5
Create Date: 2026-01-14 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e5a8c4d7f6'
down_revision: Union[str, None] = 'a8b4e7f2d3c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add claim_type_category column to claim_cards table."""
    op.add_column('claim_cards', sa.Column('claim_type_category', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove claim_type_category column from claim_cards table."""
    op.drop_column('claim_cards', 'claim_type_category')
