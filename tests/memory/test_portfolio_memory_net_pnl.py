"""Test that portfolio memory records NET P&L (after fees/slippage)."""
import pytest
from datetime import datetime, timezone
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


@pytest.fixture
def memory_engine(tmp_path):
    config = {"persistence": {"storage_path": str(tmp_path)}}
    return PortfolioMemoryEngine(config)


def test_pnl_subtracts_fees_and_slippage(memory_engine):
    """Verify recorded P&L includes fees and slippage deductions."""
    decision = {
        "id": "test_001",
        "action": "BUY",
        "asset_pair": "BTCUSD",
        "entry_price": 50000,
        "recommended_position_size": 1.0,
        "timestamp": datetime.now(timezone.utc)
        "fee_cost": 150,
        "slippage_cost": 100,
    }

    outcome = memory_engine.record_trade_outcome(
        decision=decision,
        exit_price=51000,
        exit_timestamp=datetime.now(timezone.utc),
    )

    # Gross would be $1000, but net = 1000 - 150 - 100 = $750
    assert abs(outcome.realized_pnl - 750.0) < 0.01
    assert outcome.was_profitable is True
    assert outcome.fee_cost == 150
    assert outcome.slippage_cost == 100


def test_marginal_profit_becomes_loss_with_costs(memory_engine):
    """CRITICAL: Small gross profit becomes net loss after costs."""
    decision = {
        "id": "test_002",
        "action": "BUY",
        "asset_pair": "BTCUSD",
        "entry_price": 50000,
        "recommended_position_size": 1.0,
        "timestamp": datetime.now(timezone.utc),
        "fee_cost": 150,
        "slippage_cost": 100,
    }

    outcome = memory_engine.record_trade_outcome(
        decision=decision,
        exit_price=50200,  # Gross profit $200
        exit_timestamp=datetime.now(timezone.utc),
    )

    # Net = 200 - 250 = -$50 (LOSS)
    assert outcome.realized_pnl == -50.0
    assert outcome.was_profitable is False
