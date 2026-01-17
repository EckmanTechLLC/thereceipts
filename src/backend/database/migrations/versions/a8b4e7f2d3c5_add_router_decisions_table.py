"""add router_decisions table

Revision ID: a8b4e7f2d3c5
Revises: f01c3b619027
Create Date: 2026-01-14 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY


# revision identifiers, used by Alembic.
revision: str = 'a8b4e7f2d3c5'
down_revision: Union[str, None] = 'f01c3b619027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create router_decisions table for tracking routing decisions."""

    # Create router_decisions table
    op.create_table(
        'router_decisions',
        sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('reformulated_question', sa.Text(), nullable=False),
        sa.Column('conversation_context', JSONB(), nullable=True),
        sa.Column('mode_selected', sa.Enum('EXACT_MATCH', 'CONTEXTUAL', 'NOVEL_CLAIM', name='routing_mode'), nullable=False),
        sa.Column('claim_cards_referenced', ARRAY(UUID()), nullable=True),
        sa.Column('search_candidates', JSONB(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for common queries
    op.create_index('ix_router_decisions_mode_selected', 'router_decisions', ['mode_selected'])
    op.create_index('ix_router_decisions_created_at', 'router_decisions', ['created_at'])


def downgrade() -> None:
    """Drop router_decisions table and enum type."""
    op.drop_index('ix_router_decisions_created_at', table_name='router_decisions')
    op.drop_index('ix_router_decisions_mode_selected', table_name='router_decisions')
    op.drop_table('router_decisions')
    op.execute("DROP TYPE IF EXISTS routing_mode")
