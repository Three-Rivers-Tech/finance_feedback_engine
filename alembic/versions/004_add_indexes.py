"""V004: Add performance indexes and constraints

Revision ID: 004_add_indexes
Revises: 003_portfolio_memory_schema
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_indexes'
down_revision: Union[str, None] = '003_portfolio_memory_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes and constraints."""

    # Partial indexes for active records (faster queries on large tables)
    op.execute(
        "CREATE INDEX ix_api_keys_active ON api_keys(key_hash) "
        "WHERE is_active = true"
    )

    # Covering indexes for frequently accessed columns
    op.execute(
        "CREATE INDEX ix_trade_outcomes_perf ON trade_outcomes(asset_pair, trade_opened_at) "
        "INCLUDE (profit_loss_pct, is_win, provider_name)"
    )

    # Add constraints for data integrity
    op.execute(
        "ALTER TABLE provider_performance ADD CONSTRAINT check_win_rate "
        "CHECK (win_rate >= 0 AND win_rate <= 100)"
    )

    op.execute(
        "ALTER TABLE cache_stats ADD CONSTRAINT check_hit_rate "
        "CHECK (hit_rate >= 0 AND hit_rate <= 1)"
    )

    op.execute(
        "ALTER TABLE api_keys ADD CONSTRAINT check_rate_limit "
        "CHECK (rate_limit_per_minute > 0)"
    )

    # Add unique constraints for data consistency
    op.execute(
        "ALTER TABLE provider_performance ADD CONSTRAINT unique_provider_asset_regime "
        "UNIQUE (provider_name, asset_pair, market_regime)"
    )


def downgrade() -> None:
    """Drop performance indexes and constraints."""

    # Drop constraints
    op.execute("ALTER TABLE provider_performance DROP CONSTRAINT unique_provider_asset_regime")
    op.execute("ALTER TABLE api_keys DROP CONSTRAINT check_rate_limit")
    op.execute("ALTER TABLE cache_stats DROP CONSTRAINT check_hit_rate")
    op.execute("ALTER TABLE provider_performance DROP CONSTRAINT check_win_rate")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_trade_outcomes_perf")
    op.execute("DROP INDEX IF EXISTS ix_api_keys_active")
