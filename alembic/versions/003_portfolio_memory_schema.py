"""V003: Portfolio memory and learning schema

Revision ID: 003_portfolio_memory_schema
Revises: 002_decision_cache_schema
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_portfolio_memory_schema'
down_revision: Union[str, None] = '002_decision_cache_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create portfolio memory and performance tracking tables."""

    # Trade outcomes for learning feedback
    op.create_table(
        'trade_outcomes',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('asset_pair', sa.String(20), nullable=False, index=True),
        sa.Column('provider_name', sa.String(50), nullable=False, index=True),
        sa.Column('decision_timestamp', sa.DateTime(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('profit_loss_pct', sa.Float(), nullable=True),
        sa.Column('trade_direction', sa.String(10), nullable=False),
        sa.Column('is_win', sa.Boolean(), nullable=True),
        sa.Column('market_regime', sa.String(20), nullable=True),
        sa.Column('confidence_score', sa.Integer(), nullable=True),
        sa.Column('trade_opened_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('trade_closed_at', sa.DateTime(), nullable=True),
        sa.Column('hold_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )

    # Provider performance statistics
    op.create_table(
        'provider_performance',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('provider_name', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('asset_pair', sa.String(20), nullable=False, index=True),
        sa.Column('market_regime', sa.String(20), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default=sa.literal(0)),
        sa.Column('winning_trades', sa.Integer(), nullable=False, server_default=sa.literal(0)),
        sa.Column('losing_trades', sa.Integer(), nullable=False, server_default=sa.literal(0)),
        sa.Column('win_rate', sa.Float(), nullable=False, server_default=sa.literal(0.0)),
        sa.Column('avg_profit_loss_pct', sa.Float(), nullable=False, server_default=sa.literal(0.0)),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('max_drawdown_pct', sa.Float(), nullable=True),
        sa.Column('last_updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Thompson Sampling statistics
    op.create_table(
        'thompson_stats',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('provider_name', sa.String(50), nullable=False, index=True),
        sa.Column('market_regime', sa.String(20), nullable=False, index=True),
        sa.Column('alpha_wins', sa.Integer(), nullable=False, server_default=sa.literal(1)),
        sa.Column('beta_losses', sa.Integer(), nullable=False, server_default=sa.literal(1)),
        sa.Column('mean_weight', sa.Float(), nullable=False, server_default=sa.literal(0.5)),
        sa.Column('variance', sa.Float(), nullable=False, server_default=sa.literal(0.08)),
        sa.Column('last_updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for efficient queries
    op.create_index('ix_trade_outcomes_asset_provider', 'trade_outcomes', ['asset_pair', 'provider_name'])
    op.create_index('ix_trade_outcomes_timestamp', 'trade_outcomes', ['trade_opened_at'])
    op.create_index('ix_provider_performance_asset', 'provider_performance', ['asset_pair'])
    op.create_index('ix_thompson_stats_provider_regime', 'thompson_stats', ['provider_name', 'market_regime'])


def downgrade() -> None:
    """Drop portfolio memory tables."""
    op.drop_table('thompson_stats')
    op.drop_table('provider_performance')
    op.drop_table('trade_outcomes')
