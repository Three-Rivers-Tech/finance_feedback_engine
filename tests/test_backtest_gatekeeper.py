"""Test that RiskGatekeeper blocks trades after drawdown is exceeded."""

import datetime

import pytest

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


@pytest.mark.external_service
def test_risk_gatekeeper_blocks_after_drawdown():
    """
    Verify RiskGatekeeper blocks trades when portfolio drawdown exceeds limit.

    Setup: Create a decision and monitoring context where portfolio has dropped 10%.
    Gatekeeper configured with 5% max drawdown.
    Expected: validate_trade returns False with drawdown message.
    """
    # Create a gatekeeper with 5% drawdown limit
    gatekeeper = RiskGatekeeper(max_drawdown_pct=0.05, is_backtest=True)

    # Create a trade decision (BUY action)
    decision = {
        "id": "test-1",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 100,
        "suggested_amount": 1000,
        "entry_price": 50000,
    }

    # Create monitoring context simulating a 10% portfolio drop (exceeds 5% limit)
    # recent_performance.total_pnl = -0.10 means 10% loss
    now_iso = datetime.datetime.now().isoformat()
    context = {
        "asset_pair": "BTCUSD",
        "asset_type": "crypto",
        "recent_performance": {
            "total_pnl": -0.10,  # Portfolio down 10%
        },
        "holdings": {},
        "market_data_timestamp": now_iso,
    }

    # Validate trade - should be REJECTED due to drawdown
    is_approved, reason = gatekeeper.validate_trade(decision, context)

    # Assert: Trade should be rejected
    assert (
        not is_approved
    ), f"Expected trade to be rejected but got approved. Reason: {reason}"
    assert (
        "drawdown" in reason.lower() or "exceeded" in reason.lower()
    ), f"Expected drawdown-related message but got: {reason}"


def test_risk_gatekeeper_allows_within_limit():
    """
    Verify RiskGatekeeper allows trades when portfolio drawdown is within limit.

    Setup: Portfolio down 3%, gatekeeper limit 5%.
    Expected: Trade approved.
    """
    gatekeeper = RiskGatekeeper(max_drawdown_pct=0.05, is_backtest=True)

    decision = {
        "id": "test-2",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 100,
        "suggested_amount": 1000,
        "entry_price": 50000,
    }

    context = {
        "asset_pair": "BTCUSD",
        "asset_type": "crypto",
        "recent_performance": {
            "total_pnl": -0.03,  # Portfolio down 3%, within 5% limit
        },
        "holdings": {},
        "market_data_timestamp": datetime.datetime.now().isoformat(),
    }

    is_approved, reason = gatekeeper.validate_trade(decision, context)

    # Assert: Trade should be approved
    assert (
        is_approved
    ), f"Expected trade to be approved but got rejected. Reason: {reason}"
