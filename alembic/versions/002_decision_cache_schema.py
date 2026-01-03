"""V002: Decision cache schema

Revision ID: 002_decision_cache_schema
Revises: 001_initial_auth_schema
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_decision_cache_schema'
down_revision: Union[str, None] = '001_initial_auth_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create decision cache tables."""

    # Decision cache table for backtesting optimization
    op.create_table(
        'decision_cache',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('asset_pair', sa.String(20), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('decision_hash', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('decision_json', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=False),
        sa.Column('market_regime', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True, index=True),
    )

    # Create composite index for efficient lookups
    op.create_index('ix_decision_cache_asset_timestamp', 'decision_cache', ['asset_pair', 'timestamp'])
    op.create_index('ix_decision_cache_expires', 'decision_cache', ['expires_at'])

    # Cache statistics for monitoring
    op.create_table(
        'cache_stats',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('asset_pair', sa.String(20), nullable=False, index=True),
        sa.Column('total_entries', sa.Integer(), nullable=False, server_default=sa.literal(0)),
        sa.Column('hits', sa.Integer(), nullable=False, server_default=sa.literal(0)),
        sa.Column('misses', sa.Integer(), nullable=False, server_default=sa.literal(0)),
        sa.Column('hit_rate', sa.Float(), nullable=False, server_default=sa.literal(0.0)),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop decision cache tables."""
    op.drop_table('cache_stats')
    op.drop_table('decision_cache')
