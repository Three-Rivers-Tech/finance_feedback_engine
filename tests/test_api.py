"""Pytest-based tests for the Finance Feedback Engine API."""

from unittest.mock import patch

import pytest

from finance_feedback_engine import FinanceFeedbackEngine


@pytest.fixture
def mock_engine():
    """Fixture to create a FinanceFeedbackEngine with a mocked platform."""
    config = {
        "alpha_vantage_api_key": "demo",
        "trading_platform": "mock",  # Use mock platform to avoid real API calls
        "decision_engine": {
            "ai_provider": "local",
            "model_name": "default",
        },
        "persistence": {"storage_path": "/tmp/test_decisions"},
    }
    engine = FinanceFeedbackEngine(config)
    return engine


def test_engine_initialization(mock_engine):
    """Test that the engine initializes successfully."""
    assert mock_engine is not None
    # Platform should be mock by config; no name attribute required
    assert mock_engine.trading_platform is not None


@pytest.mark.asyncio
async def test_analyze_asset(mock_engine):
    """Test the analyze_asset method (async)."""
    from unittest.mock import AsyncMock

    # Mock the underlying async data provider call
    async def mock_market_data(*args, **kwargs):
        return {
            "open": 50000.0,
            "high": 51000.0,
            "low": 49000.0,
            "close": 50500.0,
            "volume": 1000000,
        }

    # Mock the decision generation to avoid AI/network calls (must be AsyncMock)
    mock_gen = AsyncMock(return_value={"action": "HOLD", "confidence": 50})

    with patch.object(
        mock_engine.data_provider,
        "get_comprehensive_market_data",
        side_effect=mock_market_data,
    ), patch.object(mock_engine.decision_engine, "generate_decision", mock_gen):
        decision = await mock_engine.analyze_asset("BTCUSD")
        assert decision is not None
        assert "action" in decision
        mock_gen.assert_called_once()


def test_get_balance(mock_engine):
    """Test the get_balance method using the mock platform."""
    balance = mock_engine.get_balance()
    assert isinstance(balance, dict)
    # MockPlatform returns FUTURES_USD, SPOT_USD, SPOT_USDC keys
    assert any(k in balance for k in ("FUTURES_USD", "SPOT_USD", "SPOT_USDC"))


def test_get_decision_history(mock_engine):
    """Test the get_decision_history method."""
    history = mock_engine.get_decision_history(limit=3)
    assert isinstance(history, list)
