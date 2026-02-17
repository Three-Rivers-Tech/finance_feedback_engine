"""
Integration test fixtures and shared utilities.

Provides mock trading environments, test databases, and fixtures
for end-to-end trading workflow testing.
"""

import asyncio
import logging
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.trading_platforms.mock_platform import MockTradingPlatform
from finance_feedback_engine.trading_platforms.unified_platform import UnifiedTradingPlatform

logger = logging.getLogger(__name__)


# =============================================================================
# Test Data Constants
# =============================================================================

MOCK_BTCUSD_PRICE = Decimal("42000.00")
MOCK_ETHUSD_PRICE = Decimal("2500.00")
MOCK_EURUSD_PRICE = Decimal("1.0850")


# =============================================================================
# Mock API Response Fixtures
# =============================================================================

@pytest.fixture
def mock_coinbase_order_response():
    """Mock Coinbase order creation response."""
    return {
        "success": True,
        "order_id": "test-coinbase-order-123",
        "client_order_id": "test-client-order-123",
        "product_id": "BTC-USD",
        "side": "BUY",
        "order_type": "market",
        "size": "0.01",
        "filled_size": "0.01",
        "average_filled_price": "42000.00",
        "status": "FILLED",
        "created_time": "2024-02-16T20:00:00Z",
        "completion_time": "2024-02-16T20:00:01Z",
    }


@pytest.fixture
def mock_oanda_order_response():
    """Mock Oanda order creation response."""
    return {
        "orderFillTransaction": {
            "id": "test-oanda-order-456",
            "type": "ORDER_FILL",
            "instrument": "EUR_USD",
            "units": "1000",
            "price": "1.0850",
            "pl": "0.00",
            "time": "2024-02-16T20:00:00Z",
        },
        "relatedTransactionIDs": ["test-oanda-order-456"],
    }


@pytest.fixture
def mock_coinbase_positions():
    """Mock Coinbase active positions."""
    return [
        {
            "product_id": "BTC-USD",
            "side": "BUY",
            "size": "0.01",
            "entry_price": "41000.00",
            "current_price": "42000.00",
            "unrealized_pnl": "10.00",
            "entry_time": "2024-02-16T19:00:00Z",
        }
    ]


@pytest.fixture
def mock_oanda_positions():
    """Mock Oanda active positions."""
    return [
        {
            "instrument": "EUR_USD",
            "long": {
                "units": "1000",
                "averagePrice": "1.0800",
                "unrealizedPL": "5.00",
            },
            "pl": "0.00",
        }
    ]


# =============================================================================
# Mock Trading Platform Fixtures
# =============================================================================

@pytest.fixture
def mock_unified_provider():
    """Mock UnifiedDataProvider for price fetching."""
    provider = MagicMock()
    
    # Mock get_current_price to return realistic prices
    def get_price(asset_pair: str) -> Dict[str, Any]:
        prices = {
            "BTC-USD": {"price": str(MOCK_BTCUSD_PRICE), "provider": "coinbase"},
            "BTCUSD": {"price": str(MOCK_BTCUSD_PRICE), "provider": "coinbase"},
            "ETH-USD": {"price": str(MOCK_ETHUSD_PRICE), "provider": "coinbase"},
            "ETHUSD": {"price": str(MOCK_ETHUSD_PRICE), "provider": "coinbase"},
            "EUR_USD": {"price": str(MOCK_EURUSD_PRICE), "provider": "oanda"},
            "EURUSD": {"price": str(MOCK_EURUSD_PRICE), "provider": "oanda"},
        }
        return prices.get(asset_pair, {"price": "0.0", "provider": "unknown"})
    
    provider.get_current_price = MagicMock(side_effect=get_price)
    return provider


@pytest.fixture
def mock_coinbase_platform():
    """Mock Coinbase trading platform."""
    platform = MagicMock(spec=MockTradingPlatform)
    platform.platform_name = "coinbase"
    
    # Mock order placement
    platform.place_order.return_value = {
        "success": True,
        "order_id": "test-coinbase-order-123",
        "filled_size": "0.01",
        "average_filled_price": "42000.00",
    }
    
    # Mock position fetching
    platform.get_active_positions.return_value = []
    
    # Mock account info
    platform.get_account_info.return_value = {
        "account_id": "test-coinbase-account",
        "available_balance": 10000.0,
        "currency": "USD",
    }
    
    return platform


@pytest.fixture
def mock_oanda_platform():
    """Mock Oanda trading platform."""
    platform = MagicMock()
    platform.platform_name = "oanda"
    
    # Mock order placement
    platform.place_order.return_value = {
        "success": True,
        "order_id": "test-oanda-order-456",
        "filled_size": "1000",
        "average_filled_price": "1.0850",
    }
    
    # Mock position fetching
    platform.get_active_positions.return_value = []
    
    # Mock account info
    platform.get_account_info.return_value = {
        "account_id": "test-oanda-account",
        "balance": 10000.0,
        "currency": "USD",
    }
    
    return platform


# =============================================================================
# Trade Outcome Recorder Fixtures
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def trade_outcome_recorder(temp_data_dir, mock_unified_provider):
    """Trade outcome recorder with mock data provider."""
    recorder = TradeOutcomeRecorder(
        data_dir=str(temp_data_dir),
        use_async=False,  # Use sync mode for easier testing
        unified_provider=mock_unified_provider,
    )
    yield recorder
    # Cleanup is automatic with temp_data_dir


# =============================================================================
# Risk Gatekeeper Fixtures
# =============================================================================

@pytest.fixture
def risk_gatekeeper():
    """Risk gatekeeper with standard test configuration."""
    return RiskGatekeeper(
        max_drawdown_pct=0.05,
        correlation_threshold=0.7,
        max_correlated_assets=2,
        max_var_pct=0.05,
        var_confidence=0.95,
        is_backtest=False,
    )


@pytest.fixture
def strict_risk_gatekeeper():
    """Risk gatekeeper with strict limits for testing rejections."""
    return RiskGatekeeper(
        max_drawdown_pct=0.01,  # 1% max drawdown
        correlation_threshold=0.5,  # Lower correlation threshold
        max_correlated_assets=1,  # Only 1 correlated asset allowed
        max_var_pct=0.01,  # 1% max VaR
        var_confidence=0.99,  # 99% confidence
        is_backtest=False,
    )


# =============================================================================
# Decision Engine Fixtures
# =============================================================================

@pytest.fixture
def test_decision():
    """Standard test decision for integration tests."""
    return {
        "action": "BUY",
        "asset_pair": "BTC-USD",
        "suggested_amount": 100.0,
        "recommended_position_size": 0.01,
        "confidence": 0.75,
        "reasoning": "Test decision for integration testing",
        "risk_score": 0.3,
        "market_data": {
            "current_price": 42000.0,
            "asset_type": "crypto",
            "market_status": {"is_open": True, "session": "24/7"},
            "data_freshness": {"is_fresh": True, "age_minutes": 0},
        },
    }


@pytest.fixture
def test_decision_sell():
    """Test SELL decision."""
    return {
        "action": "SELL",
        "asset_pair": "BTC-USD",
        "suggested_amount": 100.0,
        "recommended_position_size": 0.01,
        "confidence": 0.70,
        "reasoning": "Test sell decision for integration testing",
        "risk_score": 0.4,
        "market_data": {
            "current_price": 42000.0,
            "asset_type": "crypto",
            "market_status": {"is_open": True, "session": "24/7"},
            "data_freshness": {"is_fresh": True, "age_minutes": 0},
        },
    }


# =============================================================================
# FFE Engine Fixtures
# =============================================================================

@pytest.fixture
def ffe_test_config(temp_data_dir):
    """FFE configuration for integration testing."""
    return {
        "alpha_vantage_api_key": "test_api_key",
        "trading_platform": "unified",
        "platforms": [],  # Use paper trading
        "paper_trading_defaults": {
            "enabled": True,
            "initial_cash_usd": 10000.0,
        },
        "decision_engine": {
            "use_ollama": False,
            "debate_mode": False,
            "quicktest_mode": True,
            "local_models": [],
        },
        "persistence": {
            "enabled": True,
            "data_dir": str(temp_data_dir),
        },
        "risk_management": {
            "max_drawdown_pct": 0.05,
            "max_var_pct": 0.05,
            "correlation_threshold": 0.7,
        },
    }


@pytest.fixture
def ffe_engine(ffe_test_config):
    """FFE engine instance for integration testing."""
    # Patch model installation to skip in tests
    with patch("finance_feedback_engine.core.ensure_models_installed"):
        engine = FinanceFeedbackEngine(config=ffe_test_config)
        yield engine


# =============================================================================
# Time-Based Position Fixtures
# =============================================================================

@pytest.fixture
def position_held_1min():
    """Position held for 1 minute."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    entry_time = now - timedelta(minutes=1)
    
    return {
        "product_id": "BTC-USD",
        "side": "BUY",
        "size": "0.01",
        "entry_price": "41000.00",
        "current_price": "42000.00",
        "entry_time": entry_time.isoformat(),
    }


@pytest.fixture
def position_held_1hr():
    """Position held for 1 hour."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    entry_time = now - timedelta(hours=1)
    
    return {
        "product_id": "ETH-USD",
        "side": "BUY",
        "size": "1.0",
        "entry_price": "2400.00",
        "current_price": "2500.00",
        "entry_time": entry_time.isoformat(),
    }


@pytest.fixture
def position_held_1day():
    """Position held for 1 day."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    entry_time = now - timedelta(days=1)
    
    return {
        "product_id": "EUR_USD",
        "side": "LONG",
        "size": "10000",
        "entry_price": "1.0800",
        "current_price": "1.0850",
        "entry_time": entry_time.isoformat(),
    }


# =============================================================================
# State Machine Fixtures
# =============================================================================

@pytest.fixture
def state_transitions():
    """Valid state transitions for testing state machine."""
    return [
        ("IDLE", "ANALYZING"),
        ("ANALYZING", "EXECUTING"),
        ("EXECUTING", "LEARNING"),
        ("LEARNING", "IDLE"),
    ]


@pytest.fixture
def invalid_state_transitions():
    """Invalid state transitions for testing state machine."""
    return [
        ("IDLE", "EXECUTING"),  # Skip ANALYZING
        ("ANALYZING", "LEARNING"),  # Skip EXECUTING
        ("EXECUTING", "IDLE"),  # Skip LEARNING
    ]
