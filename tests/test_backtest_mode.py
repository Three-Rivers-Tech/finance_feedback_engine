"""Tests for DecisionEngine with mock provider (fast testing)."""

import pytest
from finance_feedback_engine.decision_engine.engine import DecisionEngine


@pytest.fixture
def mock_config():
    """Config using mock provider for fast deterministic testing."""
    return {
        'ai_provider': 'mock',  # Use mock provider instead of backtest_mode
        'position_sizing': {
            'risk_percentage': 0.01,
            'stop_loss_percentage': 0.02
        }
    }


@pytest.fixture
def mock_market_data():
    """Sample market data with historical prices."""
    return {
        'close': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'open': 49500.0,
        'volume': 1000000,
        'timestamp': '2024-01-15T12:00:00Z',
        'market_regime': 'TRENDING_BULL',
        'market_regime_data': {'adx': 35.0, 'atr': 500.0},
        'historical_data': [
            {'close': 48000.0}, {'close': 48200.0}, {'close': 48500.0},
            {'close': 48800.0}, {'close': 49000.0}, {'close': 49200.0},
            {'close': 49500.0}, {'close': 49700.0}, {'close': 49900.0},
            {'close': 50100.0}, {'close': 50300.0}, {'close': 50500.0},
            {'close': 50700.0}, {'close': 50900.0}, {'close': 51000.0},
            {'close': 50800.0}, {'close': 50600.0}, {'close': 50400.0},
            {'close': 50200.0}, {'close': 50000.0}  # 20 candles for SMA(20)
        ]
    }


def test_backtest_mode_parameter(mock_config):
    """Test that backtest_mode parameter is accepted but deprecated."""
    # backtest_mode flag is now deprecated - logs warning but accepted
    engine = DecisionEngine(mock_config, backtest_mode=True)
    assert engine.backtest_mode is True  # Stored but not used

    engine_normal = DecisionEngine(mock_config, backtest_mode=False)
    assert engine_normal.backtest_mode is False


def test_mock_provider_decisions(mock_config, mock_market_data):
    """Test that mock provider generates valid random decisions."""
    engine = DecisionEngine(mock_config)

    decision = engine.generate_decision(
        asset_pair='BTCUSD',
        market_data=mock_market_data,
        balance={'USD': 10000.0}
    )

    # Mock provider returns random but valid decisions
    assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    assert 0 <= decision['confidence'] <= 100
    assert 'Mock AI' in decision['reasoning']
    assert decision['backtest_mode'] is False  # Not using old backtest logic
    assert 'position_size' in decision or 'recommended_position_size' in decision
def test_mock_provider_bear_market(mock_config):
    """Test mock provider handles bear market data."""
    engine = DecisionEngine(mock_config)

    # Downtrend scenario: price < SMA
    market_data = {
        'close': 48000.0,
        'high': 48500.0,
        'low': 47500.0,
        'open': 48200.0,
        'volume': 900000,
        'timestamp': '2024-01-15T12:00:00Z',
        'market_regime': 'TRENDING_BEAR',
        'market_regime_data': {'adx': 40.0, 'atr': 600.0},
        'historical_data': [
            {'close': 50000.0}, {'close': 49800.0}, {'close': 49600.0},
            {'close': 49400.0}, {'close': 49200.0}, {'close': 49000.0},
            {'close': 48800.0}, {'close': 48600.0}, {'close': 48400.0},
            {'close': 48200.0}, {'close': 48100.0}, {'close': 48050.0},
            {'close': 48030.0}, {'close': 48020.0}, {'close': 48010.0},
            {'close': 48005.0}, {'close': 48003.0}, {'close': 48002.0},
            {'close': 48001.0}, {'close': 48000.0}  # SMA(20) ~48600
        ]
    }

    decision = engine.generate_decision(
        asset_pair='BTCUSD',
        market_data=market_data,
        balance={'USD': 10000.0}
    )

    # Mock returns random actions - just verify it's valid
    assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    assert 0 <= decision['confidence'] <= 100
    assert decision['backtest_mode'] is False  # Not using old backtest logic


def test_mock_provider_ranging_market(mock_config):
    """Test mock provider handles ranging market data."""
    engine = DecisionEngine(mock_config)

    # Low ADX, ranging market
    market_data = {
        'close': 49500.0,
        'high': 50000.0,
        'low': 49000.0,
        'open': 49200.0,
        'volume': 800000,
        'timestamp': '2024-01-15T12:00:00Z',
        'market_regime': 'LOW_VOLATILITY_RANGING',
        'market_regime_data': {'adx': 18.0, 'atr': 200.0},
        'historical_data': [
            {'close': 49500.0} for _ in range(20)  # Flat prices
        ]
    }

    decision = engine.generate_decision(
        asset_pair='BTCUSD',
        market_data=market_data,
        balance={'USD': 10000.0}
    )

    # Mock returns random actions - just verify it's valid
    assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    assert 0 <= decision['confidence'] <= 100


def test_mock_provider_no_historical_data(mock_config):
    """Test mock provider handles missing historical data."""
    engine = DecisionEngine(mock_config)

    market_data = {
        'close': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'open': 49500.0,
        'volume': 1000000,
        'timestamp': '2024-01-15T12:00:00Z',
        'market_regime': 'UNKNOWN',
        'market_regime_data': {'adx': 30.0},
        'historical_data': []  # No history
    }

    decision = engine.generate_decision(
        asset_pair='BTCUSD',
        market_data=market_data,
        balance={'USD': 10000.0}
    )

    # Mock provider should handle missing data gracefully
    assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    assert decision['backtest_mode'] is False


def test_mock_provider_invalid_close_price(mock_config):
    """Test mock provider handles invalid close price."""
    engine = DecisionEngine(mock_config)

    market_data = {
        'close': 0,  # Invalid
        'high': 51000.0,
        'low': 49000.0,
        'open': 49500.0,
        'timestamp': '2024-01-15T12:00:00Z',
        'historical_data': []
    }

    decision = engine.generate_decision(
        asset_pair='BTCUSD',
        market_data=market_data,
        balance={'USD': 10000.0}
    )

    # Mock provider should still return valid decision
    assert decision['action'] in ['BUY', 'SELL', 'HOLD']
    assert decision['confidence'] >= 0


def test_normal_mode_not_affected(mock_config, mock_market_data):
    """Test that normal mode (backtest_mode=False) doesn't use rule-based logic."""
    engine = DecisionEngine(mock_config, backtest_mode=False)

    # This would normally query AI provider (will fail in test without mock)
    # Just verify the parameter is respected
    assert engine.backtest_mode is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
