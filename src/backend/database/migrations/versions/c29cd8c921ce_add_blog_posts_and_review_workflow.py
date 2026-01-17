"""add blog_posts table and review workflow fields

Revision ID: c29cd8c921ce
Revises: b9e5a8c4d7f6
Create Date: 2026-01-16 16:00:00.000000

Implements Phase 3.1 schema changes from ADR 003:
- Creates blog_posts table for synthesized prose articles
- Adds visible_in_audits column to claim_cards
- Adds review workflow fields to topic_queue
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY


# revision identifiers, used by Alembic.
revision: str = 'c29cd8c921ce'
down_revision: Union[str, None] = 'b9e5a8c4d7f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply Phase 3.1 schema changes."""

    # Create blog_posts table
    op.create_table(
        'blog_posts',
        sa.Column('id', UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('topic_queue_id', UUID(), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('article_body', sa.Text(), nullable=False),
        sa.Column('claim_card_ids', ARRAY(UUID()), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.String(200), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['topic_queue_id'], ['topic_queue.id'], ondelete='SET NULL')
    )

    # Create indexes for blog_posts
    op.create_index('ix_blog_posts_published_at', 'blog_posts', ['published_at'])
    op.create_index('ix_blog_posts_topic_queue_id', 'blog_posts', ['topic_queue_id'])

    # Add visible_in_audits to claim_cards (default TRUE)
    op.add_column('claim_cards', sa.Column('visible_in_audits', sa.Boolean(), nullable=False, server_default='true'))

    # Add review workflow fields to topic_queue
    op.add_column('topic_queue', sa.Column('review_status', sa.String(50), nullable=False, server_default='pending_review'))
    op.add_column('topic_queue', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('topic_queue', sa.Column('admin_feedback', sa.Text(), nullable=True))
    op.add_column('topic_queue', sa.Column('blog_post_id', UUID(), nullable=True))

    # Add foreign key for blog_post_id
    op.create_foreign_key('fk_topic_queue_blog_post', 'topic_queue', 'blog_posts', ['blog_post_id'], ['id'], ondelete='SET NULL')

    # Create index for review_status
    op.create_index('ix_topic_queue_review_status', 'topic_queue', ['review_status'])


def downgrade() -> None:
    """Revert Phase 3.1 schema changes."""

    # Drop topic_queue modifications
    op.drop_index('ix_topic_queue_review_status', table_name='topic_queue')
    op.drop_constraint('fk_topic_queue_blog_post', 'topic_queue', type_='foreignkey')
    op.drop_column('topic_queue', 'blog_post_id')
    op.drop_column('topic_queue', 'admin_feedback')
    op.drop_column('topic_queue', 'reviewed_at')
    op.drop_column('topic_queue', 'review_status')

    # Drop claim_cards modifications
    op.drop_column('claim_cards', 'visible_in_audits')

    # Drop blog_posts table
    op.drop_index('ix_blog_posts_topic_queue_id', table_name='blog_posts')
    op.drop_index('ix_blog_posts_published_at', table_name='blog_posts')
    op.drop_table('blog_posts')
