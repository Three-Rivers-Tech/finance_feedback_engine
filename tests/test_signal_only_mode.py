import pytest

from finance_feedback_engine.decision_engine.engine import DecisionEngine

pytestmark = pytest.mark.skip(reason="Signal-only mode deprecated; tests removed")
config = {"decision_engine": {"ai_provider": "local", "model_name": "test-model"}}

config_signal_only = {
    "decision_engine": {"ai_provider": "local", "model_name": "test-model"},
    "signal_only_default": True,
}

MARKET_DATA = {
    "type": "crypto",
    "date": "2025-11-22",
    "open": 95000.0,
    "high": 96500.0,
    "low": 94800.0,
    "close": 96200.0,
    "volume": 1234567,
    "market_cap": 1900000000000,
    "price_range": 1700.0,
    "price_range_pct": 1.77,
    "trend": "bullish",
    "body_size": 1200.0,
    "body_pct": 1.25,
    "upper_wick": 300.0,
    "lower_wick": 200.0,
    "close_position_in_range": 0.82,
    "rsi": 62.5,
    "rsi_signal": "neutral",
}


def safe_balance(val):
    return val if isinstance(val, dict) else {}


def safe_dict(val):
    return val if isinstance(val, dict) or val is None else None


@pytest.fixture
def engine():
    return DecisionEngine(config)


@pytest.fixture
def engine_signal_only():
    return DecisionEngine(config_signal_only)


@pytest.mark.asyncio
async def test_valid_balance_enables_position_sizing(engine):
    """Test 1: Valid balance should provide position sizing."""
    context = {
        "asset_pair": "BTCUSD",
        "market_data": MARKET_DATA,
        "balance": {"coinbase_USD": 10000.0, "coinbase_BTC": 0.1},
        "portfolio": None,
        "memory_context": None,
    }
    decision = await engine.generate_decision(
        asset_pair=context["asset_pair"],
        market_data=context["market_data"],
        balance=safe_balance(context.get("balance")),
        portfolio=safe_dict(context.get("portfolio")),
        memory_context=safe_dict(context.get("memory_context")),
    )
    assert decision["signal_only"] is False
    assert decision["recommended_position_size"] is not None
    assert decision["recommended_position_size"] > 0


@pytest.mark.asyncio
async def test_empty_balance_enables_signal_only_mode(engine):
    """Test 2: Empty balance should enable signal-only mode."""
    context = {
        "asset_pair": "BTCUSD",
        "market_data": MARKET_DATA,
        "balance": {},
        "portfolio": None,
        "memory_context": None,
    }
    decision = await engine.generate_decision(
        asset_pair=context["asset_pair"],
        market_data=context["market_data"],
        balance=safe_balance(context.get("balance")),
        portfolio=safe_dict(context.get("portfolio")),
        memory_context=safe_dict(context.get("memory_context")),
    )
    assert decision["signal_only"] is True
    assert decision["recommended_position_size"] is None


@pytest.mark.asyncio
async def test_zero_balance_enables_signal_only_mode(engine):
    """Test 3: Zero balance should enable signal-only mode."""
    context = {
        "asset_pair": "BTCUSD",
        "market_data": MARKET_DATA,
        "balance": {"USD": 0.0, "BTC": 0.0},
        "portfolio": None,
        "memory_context": None,
    }
    decision = await engine.generate_decision(
        asset_pair=context["asset_pair"],
        market_data=context["market_data"],
        balance=safe_balance(context.get("balance")),
        portfolio=safe_dict(context.get("portfolio")),
        memory_context=safe_dict(context.get("memory_context")),
    )
    assert decision["signal_only"] is True
    assert decision["recommended_position_size"] is None


@pytest.mark.asyncio
async def test_none_balance_enables_signal_only_mode(engine):
    """Test 4: None balance should enable signal-only mode."""
    context = {
        "asset_pair": "BTCUSD",
        "market_data": MARKET_DATA,
        "balance": None,
        "portfolio": None,
        "memory_context": None,
    }
    decision = await engine.generate_decision(
        asset_pair=context["asset_pair"],
        market_data=context["market_data"],
        balance=context.get("balance"),
        portfolio=safe_dict(context.get("portfolio")),
        memory_context=safe_dict(context.get("memory_context")),
    )
    assert decision["signal_only"] is True
    assert decision["recommended_position_size"] is None


@pytest.mark.asyncio
async def test_signal_only_default_overrides_balance(engine_signal_only):
    """Test 5: signal_only_default=True should force signal-only mode even with a valid balance."""
    context = {
        "asset_pair": "BTCUSD",
        "market_data": MARKET_DATA,
        "balance": {"coinbase_USD": 10000.0},
        "portfolio": None,
        "memory_context": None,
    }
    decision = await engine_signal_only.generate_decision(
        asset_pair=context["asset_pair"],
        market_data=context["market_data"],
        balance=safe_balance(context.get("balance")),
        portfolio=safe_dict(context.get("portfolio")),
        memory_context=safe_dict(context.get("memory_context")),
    )
    assert decision["signal_only"] is True
    assert decision["recommended_position_size"] is None
