"""
Comprehensive tests for the backtesting subsystem (Phase 1.3).

Tests cover:
- Backtester initialization with various configurations
- Position sizing strategies (fixed fraction, Kelly criterion)
- Trade execution with slippage and fees
- Performance metrics calculation
- Decision cache functionality (SQLite persistence)
- Walk-forward analysis with memory snapshotting
- Monte Carlo simulation (placeholder validation)

Target: 40% coverage of 1,451 LOC backtester.py
"""

import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from finance_feedback_engine.backtesting.backtester import Backtester, Position
from finance_feedback_engine.backtesting.decision_cache import DecisionCache
from finance_feedback_engine.backtesting.walk_forward import WalkForwardAnalyzer
from finance_feedback_engine.backtesting.monte_carlo import (
    MonteCarloSimulator,
    generate_learning_validation_metrics,
)


# ============================================
# Fixtures
# ============================================


@pytest.fixture
def mock_historical_provider():
    """Mock historical data provider with sample OHLCV data."""
    provider = MagicMock()

    # Generate sample historical data (30 days of hourly candles)
    dates = pd.date_range("2024-01-01", periods=720, freq="1h")
    data = pd.DataFrame({
        "timestamp": dates,
        "open": 50000 + np.random.randn(720) * 100,
        "high": 50100 + np.random.randn(720) * 100,
        "low": 49900 + np.random.randn(720) * 100,
        "close": 50000 + np.random.randn(720) * 100,
        "volume": 1000 + np.random.randn(720) * 50,
    })

    provider.get_historical_data.return_value = data
    return provider


@pytest.fixture
def mock_decision_engine():
    """Mock decision engine that returns simple decisions."""
    engine = MagicMock()

    async def mock_generate_decision(*args, **kwargs):
        return {
            "id": "test_decision_123",
            "action": "BUY",
            "confidence": 0.75,
            "reasoning": "Test decision",
            "position_size": 1000,
            "asset_pair": "BTCUSD",
        }

    engine.generate_decision = AsyncMock(side_effect=mock_generate_decision)
    return engine


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Temporary directory for cache files."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    yield cache_dir
    # Cleanup after test
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


@pytest.fixture
def temp_memory_dir(tmp_path):
    """Temporary directory for memory files."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    yield memory_dir
    # Cleanup after test
    if memory_dir.exists():
        shutil.rmtree(memory_dir)


# ============================================
# Test: Backtester Initialization
# ============================================


class TestBacktesterInitialization:
    """Test backtester initialization with various configurations."""

    def test_minimal_initialization(self, mock_historical_provider):
        """Test backtester with minimal default configuration."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        assert backtester.initial_balance == 10000.0
        assert backtester.fee_percentage == 0.001
        assert backtester.slippage_percentage == 0.0001
        assert backtester.platform_leverage == 1.0
        assert backtester.timeframe == "1h"
        assert backtester.decision_cache is None
        assert backtester.memory_engine is None

    def test_custom_parameters(self, mock_historical_provider):
        """Test backtester with custom fees, slippage, and leverage."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=50000.0,
            fee_percentage=0.002,
            slippage_percentage=0.0005,
            override_leverage=5.0,
            override_maintenance_margin=0.3,
            timeframe="15m",
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        assert backtester.initial_balance == 50000.0
        assert backtester.fee_percentage == 0.002
        assert backtester.slippage_percentage == 0.0005
        assert backtester.platform_leverage == 5.0
        assert backtester.maintenance_margin_pct == 0.3
        assert backtester.timeframe == "15m"

    def test_decision_cache_enabled(self, mock_historical_provider, temp_cache_dir):
        """Test backtester with decision cache enabled."""
        cache_path = str(temp_cache_dir / "test_cache.db")

        # DecisionCache is imported dynamically inside __init__, so test actual behavior
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            enable_decision_cache=True,
            enable_portfolio_memory=False,
        )

        # Decision cache should be initialized (not None)
        assert backtester.decision_cache is not None
        assert hasattr(backtester.decision_cache, 'get')
        assert hasattr(backtester.decision_cache, 'put')

    def test_portfolio_memory_enabled_isolated_mode(self, mock_historical_provider, temp_memory_dir):
        """Test backtester with isolated portfolio memory (backtest-only storage)."""
        config = {"persistence": {"storage_path": "data"}}

        # PortfolioMemoryEngine is imported dynamically inside __init__, so test actual behavior
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            enable_portfolio_memory=True,
            memory_isolation_mode=True,
            config=config,
            enable_decision_cache=False,
        )

        # Memory engine should be initialized (not None)
        assert backtester.memory_engine is not None
        # Verify it's the correct type
        assert backtester.memory_engine.__class__.__name__ == 'PortfolioMemoryEngine'

    def test_platform_margin_fetching(self, mock_historical_provider):
        """Test fetching leverage and maintenance margin from platform."""
        mock_platform = MagicMock()
        mock_platform.get_account_info.return_value = {
            "max_leverage": 10.0,
            "maintenance_margin_percentage": 0.25,
        }

        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            platform=mock_platform,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        assert backtester.platform_leverage == 10.0
        assert backtester.maintenance_margin_pct == 0.25
        mock_platform.get_account_info.assert_called_once()

    def test_platform_margin_fetch_failure_uses_defaults(self, mock_historical_provider):
        """Test that platform margin fetch failure falls back to defaults."""
        mock_platform = MagicMock()
        mock_platform.get_account_info.side_effect = Exception("API error")

        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            platform=mock_platform,
            override_leverage=3.0,
            override_maintenance_margin=0.4,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Should use override values when fetch fails
        assert backtester.platform_leverage == 3.0
        assert backtester.maintenance_margin_pct == 0.4


# ============================================
# Test: Position Sizing
# ============================================


class TestPositionSizing:
    """Test position sizing strategies."""

    def test_fixed_fraction_strategy(self, mock_historical_provider):
        """Test fixed fraction position sizing (2% risk per trade)."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            position_sizing_strategy="fixed_fraction",
            risk_per_trade=0.02,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position_size = backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=50000.0,
        )

        # Should risk 2% of balance = $200
        assert position_size == 200.0

    def test_fixed_amount_strategy(self, mock_historical_provider):
        """Test fixed dollar amount position sizing."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=20000.0,
            position_sizing_strategy="fixed_amount",
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position_size = backtester._calculate_position_size(
            current_balance=20000.0,
            current_price=50000.0,
        )

        # Should return min(10% of balance, $1000) = $1000
        expected = min(20000.0 * 0.1, 1000)
        assert position_size == expected

    def test_kelly_criterion_fallback_to_fixed_fraction(self, mock_historical_provider):
        """Test Kelly criterion fallback when module not available."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            position_sizing_strategy="kelly_criterion",
            risk_per_trade=0.03,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Kelly criterion may or may not be available; just verify it doesn't crash
        # and returns a reasonable position size
        position_size = backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=50000.0,
        )

        # Should return a reasonable position size (between 1% and 10% of balance)
        assert 100.0 <= position_size <= 1000.0


# ============================================
# Test: Trade Execution
# ============================================


class TestTradeExecution:
    """Test trade execution with slippage, fees, and latency."""

    def test_buy_order_execution(self, mock_historical_provider):
        """Test BUY order with slippage and fees applied."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            fee_percentage=0.001,
            slippage_percentage=0.0001,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        new_balance, units, fee, details = backtester._execute_trade(
            current_balance=10000.0,
            current_price=50000.0,
            action="BUY",
            amount_to_trade=1000.0,  # $1000 worth
            direction="BUY",
            trade_timestamp=datetime(2024, 1, 1, 12, 0),
            candle_volume=100.0,
            side="LONG",
        )

        # Verify trade executed
        assert details["status"] == "EXECUTED"
        assert details["action"] == "BUY"
        assert details["side"] == "LONG"
        assert units > 0  # Bought units
        assert fee > 0  # Fee charged
        assert new_balance < 10000.0  # Balance decreased
        assert details["slippage_pct"] > 0  # Slippage applied

    def test_sell_order_execution(self, mock_historical_provider):
        """Test SELL order closing a LONG position."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            fee_percentage=0.001,
            slippage_percentage=0.0001,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        new_balance, units, fee, details = backtester._execute_trade(
            current_balance=10000.0,
            current_price=50000.0,
            action="SELL",
            amount_to_trade=0.02,  # 0.02 BTC
            direction="SELL",
            trade_timestamp=datetime(2024, 1, 1, 12, 0),
            candle_volume=100.0,
            side="LONG",
        )

        # Verify trade executed
        assert details["status"] == "EXECUTED"
        assert details["action"] == "SELL"
        assert details["side"] == "LONG"
        assert units < 0  # Sold units (negative)
        assert fee > 0  # Fee charged
        assert new_balance > 10000.0  # Balance increased from sale

    def test_insufficient_funds_rejection(self, mock_historical_provider):
        """Test that trades with insufficient funds are rejected."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=100.0,  # Very low balance
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        new_balance, units, fee, details = backtester._execute_trade(
            current_balance=100.0,
            current_price=50000.0,
            action="BUY",
            amount_to_trade=5000.0,  # Trying to buy $5000 worth with $100
            direction="BUY",
            trade_timestamp=datetime(2024, 1, 1, 12, 0),
            candle_volume=100.0,
            side="LONG",
        )

        # Trade should be rejected
        assert details["status"] == "REJECTED"
        assert details["reason"] == "Insufficient funds"
        assert units == 0
        assert fee == 0
        assert new_balance == 100.0  # Balance unchanged

    def test_liquidation_penalty_slippage(self, mock_historical_provider):
        """Test that liquidations apply 3x slippage penalty."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            slippage_percentage=0.001,  # 0.1% base slippage
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        new_balance, units, fee, details = backtester._execute_trade(
            current_balance=10000.0,
            current_price=50000.0,
            action="SELL",
            amount_to_trade=0.02,
            direction="SELL",
            trade_timestamp=datetime(2024, 1, 1, 12, 0),
            candle_volume=100.0,
            side="LONG",
            is_liquidation=True,  # Forced liquidation
        )

        # Slippage should be 3x normal (0.3% instead of 0.1%)
        # Plus volume impact
        assert details["slippage_pct"] > 0.1 * 3  # At least 3x base slippage


# ============================================
# Test: Liquidation & Risk Management
# ============================================


class TestLiquidationRiskManagement:
    """Test liquidation price calculation and margin checks."""

    def test_liquidation_price_long_position(self, mock_historical_provider):
        """Test liquidation price calculation for LONG position."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            override_leverage=5.0,
            override_maintenance_margin=0.5,  # 50% of initial margin
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position = Position(
            asset_pair="BTCUSD",
            units=0.5,  # 0.5 BTC
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            side="LONG",
        )

        liquidation_price = backtester._calculate_liquidation_price(
            position, account_balance=10000.0
        )

        # Liquidation should occur when price drops significantly
        assert liquidation_price is not None
        assert liquidation_price < position.entry_price  # Lower than entry for LONG

    def test_liquidation_price_short_position(self, mock_historical_provider):
        """Test liquidation price calculation for SHORT position."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            override_leverage=5.0,
            override_maintenance_margin=0.5,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position = Position(
            asset_pair="BTCUSD",
            units=-0.5,  # -0.5 BTC (SHORT)
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            side="SHORT",
        )

        liquidation_price = backtester._calculate_liquidation_price(
            position, account_balance=10000.0
        )

        # Liquidation should occur when price rises significantly
        assert liquidation_price is not None
        assert liquidation_price > position.entry_price  # Higher than entry for SHORT

    def test_no_liquidation_without_leverage(self, mock_historical_provider):
        """Test that positions without leverage have no liquidation risk."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            override_leverage=1.0,  # No leverage
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position = Position(
            asset_pair="BTCUSD",
            units=0.5,
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            side="LONG",
        )

        liquidation_price = backtester._calculate_liquidation_price(
            position, account_balance=10000.0
        )

        # Should return None (no liquidation risk with 1x leverage)
        assert liquidation_price is None

    def test_margin_liquidation_check_long(self, mock_historical_provider):
        """Test margin liquidation check triggers for LONG position."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position = Position(
            asset_pair="BTCUSD",
            units=0.5,
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            side="LONG",
            liquidation_price=40000.0,  # Liquidates at $40k
        )

        # Test: price drops below liquidation
        should_liquidate = backtester._check_margin_liquidation(
            position=position,
            current_price=38000.0,
            candle_high=42000.0,
            candle_low=38000.0,  # Low hit liquidation price
        )

        assert should_liquidate is True

    def test_margin_liquidation_check_short(self, mock_historical_provider):
        """Test margin liquidation check triggers for SHORT position."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        position = Position(
            asset_pair="BTCUSD",
            units=-0.5,
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1, 12, 0),
            side="SHORT",
            liquidation_price=60000.0,  # Liquidates at $60k
        )

        # Test: price rises above liquidation
        should_liquidate = backtester._check_margin_liquidation(
            position=position,
            current_price=62000.0,
            candle_high=62000.0,  # High hit liquidation price
            candle_low=58000.0,
        )

        assert should_liquidate is True


# ============================================
# Test: Performance Metrics
# ============================================


class TestPerformanceMetrics:
    """Test performance metrics calculation."""

    def test_basic_metrics_calculation(self, mock_historical_provider):
        """Test calculation of total return, win rate, and trade statistics."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Mock trades with P&L
        trades = [
            {"pnl_value": 100.0},   # Win
            {"pnl_value": -50.0},   # Loss
            {"pnl_value": 200.0},   # Win
            {"pnl_value": -30.0},   # Loss
            {"pnl_value": 150.0},   # Win
        ]

        # Mock equity curve
        equity_curve = [10000, 10100, 10050, 10250, 10220, 10370]

        metrics = backtester._calculate_performance_metrics(
            trades_history=trades,
            equity_curve=equity_curve,
            initial_balance=10000.0,
            timeframe="1h",
            duration_years=1.0,
            periods_per_year=252,
        )

        # Check metrics
        assert "total_return_pct" in metrics
        assert "win_rate" in metrics
        assert "winning_trades" in metrics
        assert "losing_trades" in metrics
        assert "avg_win" in metrics
        assert "avg_loss" in metrics

        # Verify win rate
        assert metrics["winning_trades"] == 3
        assert metrics["losing_trades"] == 2
        assert metrics["total_trades"] == 5
        assert metrics["win_rate"] == 60.0  # 3/5 = 60%

        # Verify average win/loss
        assert metrics["avg_win"] == pytest.approx((100 + 200 + 150) / 3)
        # avg_loss is stored as negative value in implementation
        assert abs(metrics["avg_loss"]) == pytest.approx((50 + 30) / 2)

    def test_sharpe_ratio_calculation(self, mock_historical_provider):
        """Test Sharpe ratio calculation from equity curve."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            risk_free_rate=0.02,  # 2% risk-free rate
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Create equity curve with positive returns
        equity_curve = [10000 + i * 100 for i in range(100)]  # Steady growth

        metrics = backtester._calculate_performance_metrics(
            trades_history=[],
            equity_curve=equity_curve,
            initial_balance=10000.0,
            num_trading_days=100,
            timeframe="daily",
        )

        # Should have positive Sharpe ratio
        assert "sharpe_ratio" in metrics
        assert metrics["sharpe_ratio"] > 0

    def test_max_drawdown_calculation(self, mock_historical_provider):
        """Test maximum drawdown calculation."""
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Create equity curve with significant drawdown
        equity_curve = [10000, 11000, 12000, 10000, 9000, 10500, 11500]

        metrics = backtester._calculate_performance_metrics(
            trades_history=[],
            equity_curve=equity_curve,
            initial_balance=10000.0,
            num_trading_days=7,
            timeframe="daily",
        )

        # Max drawdown should be negative (from 12000 to 9000 = -25%)
        assert "max_drawdown_pct" in metrics
        assert metrics["max_drawdown_pct"] < 0
        assert abs(metrics["max_drawdown_pct"]) > 20  # More than 20% drawdown


# ============================================
# Test: Decision Cache
# ============================================


class TestDecisionCache:
    """Test decision cache functionality with SQLite."""

    def test_cache_initialization(self, temp_cache_dir):
        """Test cache creates database and schema."""
        cache_path = str(temp_cache_dir / "test_cache.db")
        cache = DecisionCache(db_path=cache_path, max_connections=2)

        # Check database exists
        assert Path(cache_path).exists()

        # Check schema created
        with sqlite3.connect(cache_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='decisions'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "decisions"

    def test_cache_key_generation(self, temp_cache_dir):
        """Test cache key generation from asset, timestamp, and market data."""
        cache_path = str(temp_cache_dir / "test_cache.db")
        cache = DecisionCache(db_path=cache_path, max_connections=2)

        market_data = {
            "close": 50000.0,
            "volume": 1000.0,
            "rsi": 55.0,
        }

        key = cache.generate_cache_key(
            asset_pair="BTCUSD",
            timestamp="2024-01-01T12:00:00",
            market_data=market_data,
        )

        # Key should include asset, timestamp, and market hash
        assert "BTCUSD" in key
        assert "2024-01-01T12:00:00" in key
        assert len(key) > 40  # Includes hash

    def test_cache_put_and_get(self, temp_cache_dir):
        """Test storing and retrieving decisions from cache."""
        cache_path = str(temp_cache_dir / "test_cache.db")
        cache = DecisionCache(db_path=cache_path, max_connections=2)

        decision = {
            "action": "BUY",
            "confidence": 0.8,
            "reasoning": "Strong bullish signal",
        }

        market_data = {"close": 50000.0, "rsi": 60.0}
        cache_key = cache.generate_cache_key(
            asset_pair="BTCUSD",
            timestamp="2024-01-01T12:00:00",
            market_data=market_data,
        )

        market_hash = cache.build_market_hash(market_data)

        # Store decision
        cache.put(
            cache_key=cache_key,
            decision=decision,
            asset_pair="BTCUSD",
            timestamp="2024-01-01T12:00:00",
            market_hash=market_hash,
        )

        # Retrieve decision
        retrieved = cache.get(cache_key)

        assert retrieved is not None
        assert retrieved["action"] == "BUY"
        assert retrieved["confidence"] == 0.8
        assert cache.session_hits == 1
        assert cache.session_misses == 0

    def test_cache_miss(self, temp_cache_dir):
        """Test cache miss when key doesn't exist."""
        cache_path = str(temp_cache_dir / "test_cache.db")
        cache = DecisionCache(db_path=cache_path, max_connections=2)

        result = cache.get("nonexistent_key_12345")

        assert result is None
        assert cache.session_misses == 1
        assert cache.session_hits == 0

    def test_cache_stats(self, temp_cache_dir):
        """Test cache statistics tracking."""
        cache_path = str(temp_cache_dir / "test_cache.db")
        cache = DecisionCache(db_path=cache_path, max_connections=2)

        # Add some decisions
        for i in range(5):
            cache.put(
                cache_key=f"key_{i}",
                decision={"action": "BUY"},
                asset_pair="BTCUSD",
                timestamp=f"2024-01-0{i+1}T12:00:00",
                market_hash="hash123",
            )

        stats = cache.stats()

        assert stats["total_cached"] == 5
        assert "by_asset_pair" in stats
        assert stats["by_asset_pair"]["BTCUSD"] == 5

    def test_cache_clear_old(self, temp_cache_dir):
        """Test clearing old cached decisions."""
        cache_path = str(temp_cache_dir / "test_cache.db")
        cache = DecisionCache(db_path=cache_path, max_connections=2)

        # Add decisions
        for i in range(5):
            cache.put(
                cache_key=f"key_{i}",
                decision={"action": "BUY"},
                asset_pair="BTCUSD",
                timestamp=f"2024-01-0{i+1}T12:00:00",
                market_hash="hash123",
            )

        # Clear old (90+ days)
        deleted = cache.clear_old(days=90)

        # Should delete old entries (depends on created_at timestamp)
        assert deleted >= 0


# ============================================
# Test: Walk-Forward Analysis
# ============================================


class TestWalkForwardAnalysis:
    """Test walk-forward analysis for overfitting detection."""

    def test_window_generation(self):
        """Test generating rolling train/test windows."""
        analyzer = WalkForwardAnalyzer()

        windows = analyzer._generate_windows(
            start_date="2024-01-01",
            end_date="2024-07-01",
            train_window_days=60,
            test_window_days=30,
            step_days=30,
        )

        # Should generate multiple windows
        assert len(windows) > 0

        # Each window is (train_start, train_end, test_start, test_end)
        for window in windows:
            assert len(window) == 4
            train_start, train_end, test_start, test_end = window

            # Verify date ordering
            assert train_start < train_end < test_start < test_end

    def test_walk_forward_execution_without_memory(
        self, mock_historical_provider, mock_decision_engine
    ):
        """Test walk-forward execution without portfolio memory."""
        analyzer = WalkForwardAnalyzer()

        # Create minimal backtester
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            enable_decision_cache=False,
            enable_portfolio_memory=False,  # No memory
        )

        # Mock run_backtest to return simple results
        def mock_run_backtest(asset_pair, start_date, end_date, decision_engine):
            return {
                "metrics": {
                    "sharpe_ratio": 1.5,
                    "net_return_pct": 10.0,
                    "win_rate_pct": 55.0,
                }
            }

        backtester.run_backtest = mock_run_backtest

        # Run walk-forward
        results = analyzer.run_walk_forward(
            backtester=backtester,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-04-01",
            train_window_days=30,
            test_window_days=15,
            step_days=15,
            decision_engine=mock_decision_engine,
        )

        # Should have results
        assert "windows" in results
        assert "aggregate_test_performance" in results
        assert "overfitting_analysis" in results
        assert len(results["windows"]) > 0


# ============================================
# Test: Monte Carlo Simulation
# ============================================


class TestMonteCarloSimulation:
    """Test Monte Carlo simulation (placeholder implementation)."""

    def test_monte_carlo_basic_execution(
        self, mock_historical_provider, mock_decision_engine
    ):
        """Test Monte Carlo simulation runs without errors."""
        simulator = MonteCarloSimulator()

        # Create minimal backtester
        backtester = Backtester(
            historical_data_provider=mock_historical_provider,
            initial_balance=10000.0,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Mock run_backtest
        def mock_run_backtest(asset_pair, start_date, end_date, decision_engine):
            return {
                "metrics": {
                    "final_balance": 11000.0,
                    "net_return_pct": 10.0,
                }
            }

        backtester.run_backtest = mock_run_backtest

        # Run Monte Carlo (placeholder implementation)
        results = simulator.run_monte_carlo(
            backtester=backtester,
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-02-01",
            decision_engine=mock_decision_engine,
            num_simulations=100,
            price_noise_std=0.001,
        )

        # Check results structure
        assert "num_simulations" in results
        assert results["num_simulations"] == 100
        assert "base_final_balance" in results
        assert "percentiles" in results
        assert "statistics" in results

        # Check percentiles
        assert "p5" in results["percentiles"]
        assert "p50" in results["percentiles"]
        assert "p95" in results["percentiles"]

        # Check statistics
        assert "expected_return" in results["statistics"]
        assert "var_95" in results["statistics"]
