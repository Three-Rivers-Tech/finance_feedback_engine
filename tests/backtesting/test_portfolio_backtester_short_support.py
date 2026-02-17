from datetime import datetime
from unittest.mock import MagicMock

import pytest

from finance_feedback_engine.backtesting.portfolio_backtester import (
    PortfolioBacktester,
    PortfolioState,
)


@pytest.fixture
def portfolio_backtester():
    config = {
        "backtesting": {"fee_rate": 0.0, "slippage_rate": 0.0},
        "portfolio": {"max_positions": 5},
    }

    risk_gatekeeper = MagicMock()
    risk_gatekeeper.validate_trade.return_value = (True, "ok")

    return PortfolioBacktester(
        asset_pairs=["AAA", "BBB"],
        initial_balance=10_000.0,
        config=config,
        decision_engine=MagicMock(),
        data_provider=MagicMock(),
        risk_gatekeeper=risk_gatekeeper,
        memory_engine=MagicMock(),
    )


def test_long_and_short_positions_can_coexist(portfolio_backtester):
    bt = portfolio_backtester
    bt.portfolio_state = PortfolioState(cash=10_000.0)

    now = datetime.utcnow()
    bt._execute_buy("AAA", 1_000.0, 100.0, now, {"action": "BUY"})
    bt._execute_short("BBB", 1_000.0, 100.0, now, {"action": "SELL"})

    assert bt.portfolio_state.positions["AAA"].side == "LONG"
    assert bt.portfolio_state.positions["BBB"].side == "SHORT"

    # AAA up to 110 => +100 on long, BBB down to 90 => +100 on short
    value = bt.portfolio_state.total_value({"AAA": 110.0, "BBB": 90.0})
    assert value == pytest.approx(10_200.0)


def test_short_pnl_entry_100_exit_90_is_plus_10pct(portfolio_backtester):
    bt = portfolio_backtester
    bt.portfolio_state = PortfolioState(cash=10_000.0)

    now = datetime.utcnow()
    bt._execute_short("AAA", 1_000.0, 100.0, now, {"action": "SELL"})
    bt._close_position("AAA", 90.0, "test_close", now)

    close_trade = bt.portfolio_state.trade_history[-1]
    assert close_trade["action"] == "BUY_CLOSE"
    assert close_trade["pnl"] == pytest.approx(100.0)
    assert close_trade["pnl_pct"] == pytest.approx(10.0)


def test_short_margin_constraint_enforces_2_to_1_leverage_limit(portfolio_backtester):
    bt = portfolio_backtester
    bt.portfolio_state = PortfolioState(cash=1_000.0)

    now = datetime.utcnow()

    # First short consumes most of the 2x notional capacity
    bt._execute_short("AAA", 1_900.0, 100.0, now, {"action": "SELL"})
    # Second short request exceeds remaining capacity and should be capped/rejected
    bt._execute_short("BBB", 500.0, 100.0, now, {"action": "SELL"})

    current_prices = {"AAA": 100.0, "BBB": 100.0}
    equity = bt.portfolio_state.total_value(current_prices)
    total_short_exposure = sum(
        abs(pos.units) * current_prices.get(asset, pos.entry_price)
        for asset, pos in bt.portfolio_state.positions.items()
        if pos.side == "SHORT"
    )

    assert total_short_exposure <= (equity * 2.0) + 1e-6
