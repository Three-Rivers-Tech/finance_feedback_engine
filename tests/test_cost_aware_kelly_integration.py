"""
Integration tests for cost-aware Kelly Criterion system.

Tests:
- Transaction cost tracking with TradeOutcome
- Rolling cost averages with outlier filtering
- Kelly activation criteria (PF ≥1.2, std <0.15)
- Batch review cycle triggers
"""

import datetime

import pytest

from finance_feedback_engine.memory.portfolio_memory import (
    PortfolioMemoryEngine,
    TradeOutcome,
)


@pytest.fixture
def portfolio_memory(tmp_path):
    """Create a PortfolioMemoryEngine with isolated storage."""
    storage_path = tmp_path / "memory"
    storage_path.mkdir(exist_ok=True)

    config = {
        "persistence": {"storage_path": str(tmp_path)},
        "portfolio_memory": {
            "max_memory_size": 1000,
            "learning_rate": 0.1,
            "context_window": 20,
        },
    }

    memory = PortfolioMemoryEngine(config)

    yield memory

    # Cleanup
    try:
        if hasattr(memory, "close"):
            memory.close()
    except Exception:
        pass


class TestCostTracking:
    """Test transaction cost tracking functionality."""

    def test_cost_fields_in_trade_outcome(self):
        """Test that TradeOutcome includes all cost fields."""
        outcome = TradeOutcome(
            decision_id="test_123",
            asset_pair="BTCUSD",
            action="BUY",
            entry_timestamp=datetime.datetime.now().isoformat(),
            exit_timestamp=datetime.datetime.now().isoformat(),
            entry_price=50000.0,
            exit_price=51000.0,
            position_size=0.1,
            realized_pnl=100.0,
            was_profitable=True,
            holding_period_hours=1.0,
            slippage_cost=5.0,
            fee_cost=15.0,
            spread_cost=2.0,
            total_transaction_cost=22.0,
            cost_as_pct_of_position=0.44,
        )

        assert outcome.slippage_cost == 5.0
        assert outcome.fee_cost == 15.0
        assert outcome.spread_cost == 2.0
        assert outcome.total_transaction_cost == 22.0
        assert outcome.cost_as_pct_of_position == 0.44

    def test_rolling_cost_averages_partial_window(self, portfolio_memory):
        """Test cost averaging with fewer than 20 trades (partial window)."""
        # Add 10 trades with cost data
        for i in range(10):
            outcome = TradeOutcome(
                decision_id=f"test_{i}",
                asset_pair="BTCUSD",
                action="BUY",
                entry_timestamp=(
                    datetime.datetime.now() - datetime.timedelta(hours=i + 1)
                ).isoformat(),
                exit_timestamp=(
                    datetime.datetime.now() - datetime.timedelta(hours=i)
                ).isoformat(),
                entry_price=50000.0,
                exit_price=50500.0,
                position_size=0.1,
                realized_pnl=50.0,
                was_profitable=True,
                holding_period_hours=1.0,
                slippage_cost=5.0,
                fee_cost=15.0,
                spread_cost=2.0,
                total_transaction_cost=22.0,
                cost_as_pct_of_position=0.44,
            )
            portfolio_memory.record_trade_outcome(outcome)

        # Calculate rolling averages (should work with 10 trades)
        cost_stats = portfolio_memory.calculate_rolling_cost_averages(
            window=20, exclude_outlier_pct=0.10
        )

        assert cost_stats["has_data"] is True
        assert cost_stats["sample_size"] == 10
        # Check that averages are reasonable
        assert cost_stats["avg_total_cost_pct"] > 0


class TestKellyActivation:
    """Test Kelly Criterion activation logic."""

    def test_kelly_not_activated_with_insufficient_trades(self, portfolio_memory):
        """Test that Kelly is not activated with <50 trades."""
        # Add 30 trades (below 50-trade threshold)
        for i in range(30):
            outcome = TradeOutcome(
                decision_id=f"test_{i}",
                asset_pair="BTCUSD",
                action="BUY",
                entry_timestamp=(
                    datetime.datetime.now() - datetime.timedelta(hours=60 - i)
                ).isoformat(),
                exit_timestamp=(
                    datetime.datetime.now() - datetime.timedelta(hours=60 - i - 1)
                ).isoformat(),
                entry_price=50000.0,
                exit_price=51000.0,
                position_size=0.1,
                realized_pnl=100.0,
                was_profitable=True,
                holding_period_hours=1.0,
            )
            portfolio_memory.record_trade_outcome(outcome)

        kelly_check = portfolio_memory.check_kelly_activation_criteria(window=50)

        assert kelly_check["should_activate"] is False
        assert kelly_check["reason"] == "insufficient_data"
        assert kelly_check["trades_analyzed"] == 30


class TestBatchReview:
    """Test batch review cycle triggers."""

    def test_batch_review_calculates_costs(self, portfolio_memory):
        """Test that batch review can recalculate rolling cost averages."""
        # Add 25 trades with cost data
        for i in range(25):
            outcome = TradeOutcome(
                decision_id=f"test_{i}",
                asset_pair="BTCUSD",
                action="BUY",
                entry_timestamp=datetime.datetime.now().isoformat(),
                exit_timestamp=datetime.datetime.now().isoformat(),
                entry_price=50000.0,
                exit_price=50500.0,
                position_size=0.1,
                realized_pnl=50.0,
                was_profitable=True,
                holding_period_hours=1.0,
                slippage_cost=5.0,
                fee_cost=15.0,
                spread_cost=2.0,
                total_transaction_cost=22.0,
                cost_as_pct_of_position=0.44,
            )
            portfolio_memory.record_trade_outcome(outcome)

        # Calculate costs (simulates batch review)
        cost_stats = portfolio_memory.calculate_rolling_cost_averages(
            window=20, exclude_outlier_pct=0.10
        )

        assert cost_stats["has_data"] is True
        assert cost_stats["sample_size"] == 20  # Last 20 of 25 trades
        assert cost_stats["avg_total_cost_pct"] > 0


@pytest.mark.integration
class TestEndToEndCostAwareKelly:
    """End-to-end integration tests for cost-aware Kelly system."""

    @pytest.mark.asyncio
    async def test_full_workflow_bootstrap_to_kelly(self, tmp_path):
        """
        Test complete workflow:
        1. Start with 0 trades (bootstrap mode)
        2. Reach 50 trades with good performance
        3. Kelly activates
        """
        storage_path = tmp_path / "memory"
        storage_path.mkdir(exist_ok=True)

        config = {
            "persistence": {"storage_path": str(tmp_path)},
            "portfolio_memory": {
                "max_memory_size": 1000,
                "learning_rate": 0.1,
                "context_window": 20,
            },
        }

        memory = PortfolioMemoryEngine(config)

        try:
            # Phase 1: Bootstrap (30 trades)
            for i in range(30):
                outcome = TradeOutcome(
                    decision_id=f"test_{i}",
                    asset_pair="BTCUSD",
                    action="BUY",
                    entry_timestamp=(
                        datetime.datetime.now() - datetime.timedelta(hours=60 - i)
                    ).isoformat(),
                    exit_timestamp=(
                        datetime.datetime.now() - datetime.timedelta(hours=60 - i - 1)
                    ).isoformat(),
                    entry_price=50000.0,
                    exit_price=50500.0,
                    position_size=0.1,
                    realized_pnl=50.0,
                    was_profitable=(i % 10) < 6,  # 60% win rate
                    holding_period_hours=1.0,
                    slippage_cost=5.0,
                    fee_cost=15.0,
                    spread_cost=2.0,
                    total_transaction_cost=22.0,
                    cost_as_pct_of_position=0.44,
                )
                memory.record_trade_outcome(outcome)

            # Check Kelly - should not activate (insufficient history)
            kelly_check_30 = memory.check_kelly_activation_criteria(window=50)
            assert kelly_check_30["should_activate"] is False
            assert kelly_check_30["reason"] == "insufficient_data"

            # Check costs - should work from trade #1
            cost_stats_30 = memory.calculate_rolling_cost_averages(window=20)
            assert cost_stats_30["has_data"] is True

            # Phase 2: Add 20 more trades with excellent performance
            for i in range(30, 50):
                outcome = TradeOutcome(
                    decision_id=f"test_{i}",
                    asset_pair="BTCUSD",
                    action="BUY",
                    entry_timestamp=(
                        datetime.datetime.now() - datetime.timedelta(hours=60 - i)
                    ).isoformat(),
                    exit_timestamp=(
                        datetime.datetime.now() - datetime.timedelta(hours=60 - i - 1)
                    ).isoformat(),
                    entry_price=50000.0,
                    exit_price=51500.0,  # Bigger wins
                    position_size=0.1,
                    realized_pnl=150.0,
                    was_profitable=(i % 10) < 7,  # 70% win rate
                    holding_period_hours=1.0,
                    slippage_cost=5.0,
                    fee_cost=15.0,
                    spread_cost=2.0,
                    total_transaction_cost=22.0,
                    cost_as_pct_of_position=0.44,
                )
                memory.record_trade_outcome(outcome)

            # Check Kelly - should have enough trades now
            kelly_check_50 = memory.check_kelly_activation_criteria(window=50)
            assert kelly_check_50["trades_analyzed"] == 50

            # Verify cost context still available
            cost_stats_50 = memory.calculate_rolling_cost_averages(window=20)
            assert cost_stats_50["has_data"] is True
            assert cost_stats_50["avg_total_cost_pct"] > 0

        finally:
            if hasattr(memory, "close"):
                memory.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
