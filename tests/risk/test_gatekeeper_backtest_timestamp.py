"""Test RiskGatekeeper timestamp parsing in backtest vs live mode."""

import datetime

import pytest

from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper


@pytest.mark.external_service
def test_backtest_mode_raises_on_invalid_timestamp():
    """
    Verify that RiskGatekeeper in backtest mode raises ValueError on timestamp parse failure.

    This prevents silent fallback to live market status which corrupts backtest results.
    """
    gatekeeper = RiskGatekeeper(is_backtest=True)

    decision = {
        "id": "test-1",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 100,
        "suggested_amount": 1000,
        "entry_price": 50000,
    }

    # Invalid timestamp that can't be parsed
    context = {
        "asset_pair": "BTCUSD",
        "asset_type": "crypto",
        "timestamp": "invalid-timestamp-format",
        "recent_performance": {"total_pnl": 0.0},
        "holdings": {},
        "market_data_timestamp": datetime.datetime.now().isoformat(),
    }

    # Should raise ValueError in backtest mode
    with pytest.raises(ValueError) as exc_info:
        gatekeeper.validate_trade(decision, context)

    # Verify error message is descriptive
    assert "backtest mode" in str(exc_info.value).lower()
    assert "BTCUSD" in str(exc_info.value)
    assert "invalid-timestamp-format" in str(exc_info.value)


def test_live_mode_falls_back_on_invalid_timestamp():
    """
    Verify that RiskGatekeeper in live mode falls back to current market status on parse failure.

    This maintains backward compatibility for live trading where timestamp parsing is best-effort.
    """
    gatekeeper = RiskGatekeeper(is_backtest=False)

    decision = {
        "id": "test-2",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 100,
        "suggested_amount": 1000,
        "entry_price": 50000,
    }

    # Invalid timestamp
    context = {
        "asset_pair": "BTCUSD",
        "asset_type": "crypto",
        "timestamp": "invalid-timestamp-format",
        "recent_performance": {"total_pnl": 0.0},
        "holdings": {},
        "market_data_timestamp": datetime.datetime.now().isoformat(),
    }

    # Should NOT raise - falls back to live market status
    # (may still fail validation for other reasons like stale data, but not timestamp parsing)
    try:
        is_valid, reason = gatekeeper.validate_trade(decision, context)
        # If it passes validation, that's fine (crypto is 24/7)
        # If it fails for other reasons, that's also fine
        assert isinstance(is_valid, bool)
        assert isinstance(reason, str)
    except ValueError as e:
        # Should NOT be a timestamp parsing error in live mode
        # Only fail if the error is related to timestamp parsing
        if "timestamp" in str(e).lower() or "parse" in str(e).lower():
            pytest.fail(
                f"Live mode should not raise on timestamp parse errors, got: {e}"
            )
        # Other validation errors are acceptable - just verify it's a ValueError
        raise


def test_backtest_mode_accepts_valid_iso_timestamp():
    """
    Verify that RiskGatekeeper in backtest mode successfully parses valid ISO timestamps.
    """
    gatekeeper = RiskGatekeeper(is_backtest=True)

    decision = {
        "id": "test-3",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 100,
        "suggested_amount": 1000,
        "entry_price": 50000,
    }

    # Valid ISO timestamp (recent to avoid data freshness issues)
    recent_timestamp = datetime.datetime.now().isoformat()
    context = {
        "asset_pair": "BTCUSD",
        "asset_type": "crypto",
        "timestamp": recent_timestamp,
        "recent_performance": {"total_pnl": 0.0},
        "holdings": {},
        "market_data_timestamp": recent_timestamp,
    }

    # Should process without timestamp parsing errors
    # (may still fail validation for other reasons, but timestamp parsing should work)
    try:
        is_valid, reason = gatekeeper.validate_trade(decision, context)
        # Just verify it doesn't raise on valid timestamp
        assert isinstance(is_valid, bool)
    except ValueError as e:
        if "timestamp" in str(e).lower() or "parse" in str(e).lower():
            pytest.fail(
                f"Should not raise timestamp parsing error for valid ISO format: {e}"
            )
        # Other validation errors are acceptable
        raise


def test_backtest_mode_accepts_valid_unix_timestamp():
    """
    Verify that RiskGatekeeper in backtest mode successfully parses Unix timestamps.
    """
    gatekeeper = RiskGatekeeper(is_backtest=True)

    decision = {
        "id": "test-4",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 100,
        "suggested_amount": 1000,
        "entry_price": 50000,
    }

    # Unix timestamp (recent to avoid data freshness issues)
    unix_timestamp = int(datetime.datetime.now().timestamp())
    recent_iso = datetime.datetime.now().isoformat()

    context = {
        "asset_pair": "BTCUSD",
        "asset_type": "crypto",
        "timestamp": unix_timestamp,
        "recent_performance": {"total_pnl": 0.0},
        "holdings": {},
        "market_data_timestamp": recent_iso,
    }

    # Should process without timestamp parsing errors
    try:
        is_valid, reason = gatekeeper.validate_trade(decision, context)
        # Just verify it doesn't raise on valid timestamp
        assert isinstance(is_valid, bool)
    except ValueError as e:
        if "timestamp" in str(e).lower() or "parse" in str(e).lower():
            pytest.fail(
                f"Should not raise timestamp parsing error for valid Unix timestamp: {e}"
            )
        # Other validation errors are acceptable
        raise
