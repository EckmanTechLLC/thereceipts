"""add_verified_sources_table_and_source_verification_columns

Revision ID: d6638e843688
Revises: c29cd8c921ce
Create Date: 2026-01-17 14:18:20.072384

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'd6638e843688'
down_revision: Union[str, None] = 'c29cd8c921ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create verified_sources table (Tier 0 library for reusable source metadata)
    op.create_table(
        'verified_sources',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),  # book, paper, ancient_text
        sa.Column('title', sa.String(length=1000), nullable=False),
        sa.Column('author', sa.String(length=500), nullable=False),
        sa.Column('publisher', sa.String(length=500), nullable=True),
        sa.Column('publication_date', sa.String(length=100), nullable=True),
        sa.Column('isbn', sa.String(length=50), nullable=True),
        sa.Column('doi', sa.String(length=200), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('content_snippet', sa.Text(), nullable=True),
        sa.Column('topic_keywords', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column('verification_method', sa.String(length=50), nullable=False),  # google_books, semantic_scholar, etc.
        sa.Column('verification_status', sa.String(length=50), nullable=False),  # verified, partially_verified
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for verified_sources
    op.create_index('ix_verified_sources_source_type', 'verified_sources', ['source_type'], unique=False)
    op.create_index('ix_verified_sources_title', 'verified_sources', ['title'], unique=False)
    op.create_index('ix_verified_sources_author', 'verified_sources', ['author'], unique=False)

    # Add verification columns to sources table
    op.add_column('sources', sa.Column('verification_method', sa.String(length=50), nullable=True))
    op.add_column('sources', sa.Column('verification_status', sa.String(length=50), nullable=True))
    op.add_column('sources', sa.Column('content_type', sa.String(length=50), nullable=True))
    op.add_column('sources', sa.Column('url_verified', sa.Boolean(), nullable=False, server_default='false'))

    # Create indexes for new sources columns
    op.create_index('ix_sources_verification_method', 'sources', ['verification_method'], unique=False)
    op.create_index('ix_sources_verification_status', 'sources', ['verification_status'], unique=False)


def downgrade() -> None:
    # Drop indexes from sources
    op.drop_index('ix_sources_verification_status', table_name='sources')
    op.drop_index('ix_sources_verification_method', table_name='sources')

    # Drop columns from sources
    op.drop_column('sources', 'url_verified')
    op.drop_column('sources', 'content_type')
    op.drop_column('sources', 'verification_status')
    op.drop_column('sources', 'verification_method')

    # Drop indexes from verified_sources
    op.drop_index('ix_verified_sources_author', table_name='verified_sources')
    op.drop_index('ix_verified_sources_title', table_name='verified_sources')
    op.drop_index('ix_verified_sources_source_type', table_name='verified_sources')

    # Drop verified_sources table
    op.drop_table('verified_sources')
