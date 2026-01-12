"""Comprehensive tests for Backtester class.

Covers:
- Initialization and configuration
- Trade execution with fees and slippage
- Position sizing strategies
- Margin liquidation calculations
- Performance metrics calculation
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from finance_feedback_engine.backtesting.backtester import Backtester, Position


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_historical_data_provider():
    """Mock historical data provider."""
    rng = np.random.default_rng(0)
    provider = MagicMock()
    provider.get_historical_data.return_value = pd.DataFrame({
        "timestamp": pd.date_range(start="2024-01-01", periods=100, freq="1h"),
        "open": rng.uniform(40000, 45000, 100),
        "high": rng.uniform(45000, 46000, 100),
        "low": rng.uniform(39000, 40000, 100),
        "close": rng.uniform(40000, 45000, 100),
        "volume": rng.uniform(100, 1000, 100),
    })
    return provider


@pytest.fixture
def mock_platform():
    """Mock trading platform with leverage info."""
    platform = MagicMock()
    platform.get_account_info.return_value = {
        "max_leverage": 10.0,
        "maintenance_margin_percentage": 0.05,
    }
    return platform


@pytest.fixture
def basic_backtester(mock_historical_data_provider):
    """Create a basic backtester with minimal configuration."""
    return Backtester(
        historical_data_provider=mock_historical_data_provider,
        initial_balance=10000.0,
        fee_percentage=0.001,
        slippage_percentage=0.0001,
        enable_decision_cache=False,
        enable_portfolio_memory=False,
    )


@pytest.fixture
def leveraged_backtester(mock_historical_data_provider, mock_platform):
    """Create a backtester with platform leverage."""
    return Backtester(
        historical_data_provider=mock_historical_data_provider,
        platform=mock_platform,
        initial_balance=10000.0,
        fee_percentage=0.001,
        slippage_percentage=0.0001,
        enable_decision_cache=False,
        enable_portfolio_memory=False,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestBacktesterInitialization:
    """Tests for Backtester initialization."""

    def test_init_with_minimal_params(self, mock_historical_data_provider):
        """Should initialize with minimal required parameters."""
        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )
        assert bt.initial_balance == 10000.0
        assert bt.fee_percentage == 0.001
        assert bt.platform_leverage == 1.0

    def test_init_with_custom_params(self, mock_historical_data_provider):
        """Should initialize with custom parameters."""
        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            initial_balance=50000.0,
            fee_percentage=0.002,
            slippage_percentage=0.0005,
            stop_loss_percentage=0.03,
            take_profit_percentage=0.10,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )
        assert bt.initial_balance == 50000.0
        assert bt.fee_percentage == 0.002
        assert bt.slippage_percentage == 0.0005
        assert bt.stop_loss_percentage == 0.03
        assert bt.take_profit_percentage == 0.10

    def test_init_with_platform_leverage(self, mock_historical_data_provider, mock_platform):
        """Should fetch leverage from platform."""
        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            platform=mock_platform,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )
        assert bt.platform_leverage == 10.0
        assert bt.maintenance_margin_pct == 0.05

    def test_init_with_override_leverage(self, mock_historical_data_provider, mock_platform):
        """Should use override leverage instead of platform leverage."""
        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            platform=mock_platform,
            override_leverage=5.0,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )
        assert bt.platform_leverage == 5.0

    def test_init_with_platform_error(self, mock_historical_data_provider):
        """Should handle platform error gracefully."""
        bad_platform = MagicMock()
        bad_platform.get_account_info.side_effect = Exception("API error")

        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            platform=bad_platform,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )
        # Should fall back to defaults
        assert bt.platform_leverage == 1.0

    def test_init_position_sizing_strategy(self, mock_historical_data_provider):
        """Should accept different position sizing strategies."""
        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            position_sizing_strategy="risk_parity",
            risk_per_trade=0.01,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )
        assert bt.position_sizing_strategy == "risk_parity"
        assert bt.risk_per_trade == 0.01


# =============================================================================
# Trade Execution Tests
# =============================================================================


class TestTradeExecution:
    """Tests for _execute_trade method."""

    def test_execute_buy_trade_success(self, basic_backtester):
        """Should execute a successful BUY trade."""
        with patch("numpy.random.lognormal", return_value=0.5):  # Fixed latency
            new_balance, units, fee, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
            )

        assert new_balance < 10000.0  # Balance decreased
        assert units > 0  # Bought units
        assert fee > 0  # Fee charged
        assert details["status"] == "EXECUTED"
        assert details["action"] == "BUY"
        assert details["side"] == "LONG"

    def test_execute_sell_trade_success(self, basic_backtester):
        """Should execute a successful SELL trade."""
        with patch("numpy.random.lognormal", return_value=0.5):
            new_balance, units, fee, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="SELL",
                amount_to_trade=10.0,  # 10 units to sell
                direction="SELL",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",  # Closing LONG
            )

        assert new_balance > 10000.0  # Balance increased from sale
        assert units < 0  # Sold units (negative)
        assert fee > 0  # Fee charged
        assert details["status"] == "EXECUTED"
        assert details["action"] == "SELL"

    def test_execute_trade_insufficient_funds(self, basic_backtester):
        """Should reject trade with insufficient funds."""
        new_balance, units, fee, details = basic_backtester._execute_trade(
            current_balance=100.0,  # Small balance
            current_price=100.0,
            action="BUY",
            amount_to_trade=1000.0,  # Try to buy more than available
            direction="BUY",
            trade_timestamp=datetime(2024, 1, 1),
            side="LONG",
        )

        assert new_balance == 100.0  # Balance unchanged
        assert units == 0.0
        assert details["status"] == "REJECTED"
        assert "Insufficient" in details["reason"]

    def test_execute_trade_with_slippage(self, basic_backtester):
        """Should apply slippage to trade execution."""
        basic_backtester.slippage_percentage = 0.01  # 1% slippage

        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
            )

        assert details["slippage_pct"] > 0
        assert details["effective_price"] > 100.0  # BUY has higher effective price

    def test_execute_trade_with_volume_slippage(self, basic_backtester):
        """Should apply volume-based slippage."""
        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                candle_volume=100.0,  # Low volume = high slippage
                side="LONG",
            )

        assert details["slippage_pct"] > 0

    def test_execute_liquidation_trade(self, basic_backtester):
        """Should apply 3x slippage for liquidation trades."""
        basic_backtester.slippage_percentage = 0.01

        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, normal_details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="SELL",
                amount_to_trade=10.0,
                direction="SELL",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
                is_liquidation=False,
            )

        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, liquidation_details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="SELL",
                amount_to_trade=10.0,
                direction="SELL",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
                is_liquidation=True,
            )

        assert liquidation_details["slippage_pct"] > normal_details["slippage_pct"]
        assert liquidation_details["is_liquidation"] is True

    def test_execute_short_position_open(self, basic_backtester):
        """Should open a SHORT position correctly."""
        with patch("numpy.random.lognormal", return_value=0.5):
            new_balance, units, fee, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="SELL",
                amount_to_trade=10.0,  # 10 units to short
                direction="SELL",
                trade_timestamp=datetime(2024, 1, 1),
                side="SHORT",  # Opening SHORT
            )

        assert units < 0  # Short position has negative units
        assert details["side"] == "SHORT"
        assert details["status"] == "EXECUTED"

    def test_execute_short_position_close(self, basic_backtester):
        """Should close a SHORT position correctly."""
        with patch("numpy.random.lognormal", return_value=0.5):
            new_balance, units, fee, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,  # Buy back to close short
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                side="SHORT",  # Closing SHORT
            )

        assert units > 0  # Buying back (positive units)
        assert details["side"] == "SHORT"

    def test_execute_trade_limit_order(self, basic_backtester):
        """Should apply reduced slippage for limit orders."""
        basic_backtester.slippage_percentage = 0.01

        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, market_details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
                order_type="market",
            )

        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, limit_details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
                order_type="limit",
            )

        # Limit orders should have lower slippage
        assert limit_details["slippage_pct"] < market_details["slippage_pct"]

    def test_execute_trade_latency_simulation(self, basic_backtester):
        """Should simulate order latency."""
        with patch("numpy.random.lognormal", return_value=0.5):
            _, _, _, details = basic_backtester._execute_trade(
                current_balance=10000.0,
                current_price=100.0,
                action="BUY",
                amount_to_trade=1000.0,
                direction="BUY",
                trade_timestamp=datetime(2024, 1, 1),
                side="LONG",
            )

        assert "latency_seconds" in details
        assert details["latency_seconds"] > 0


# =============================================================================
# Position Sizing Tests
# =============================================================================


class TestPositionSizing:
    """Tests for _calculate_position_size method."""

    def test_fixed_fraction_sizing(self, basic_backtester):
        """Should calculate position size using fixed fraction method."""
        basic_backtester.position_sizing_strategy = "fixed_fraction"
        basic_backtester.risk_per_trade = 0.02  # 2% risk

        size = basic_backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=100.0,
            stop_loss_price=98.0,  # Stop loss at $98 (2% below $100)
            volatility=0.02,
        )

        assert size > 0
        # Fixed fraction: risk_amount = balance * risk_per_trade = 10000 * 0.02 = 200
        assert size == 10000.0 * 0.02  # 200

    def test_kelly_criterion_sizing(self, basic_backtester):
        """Should calculate position size using Kelly criterion."""
        basic_backtester.position_sizing_strategy = "kelly_criterion"

        size = basic_backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=100.0,
            stop_loss_price=98.0,
            volatility=0.02,
        )

        assert size > 0

    def test_risk_parity_sizing(self, basic_backtester):
        """Should calculate position size using risk parity."""
        basic_backtester.position_sizing_strategy = "risk_parity"

        size = basic_backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=100.0,
            stop_loss_price=98.0,
            volatility=0.02,  # 2% volatility
        )

        assert size > 0

    def test_position_size_default_strategy(self, basic_backtester):
        """Should use default fixed_fraction strategy."""
        basic_backtester.risk_per_trade = 0.02

        size = basic_backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=100.0,
        )

        # Default fixed_fraction: risk_amount = balance * risk_per_trade
        assert size > 0
        assert size == 10000.0 * 0.02

    def test_position_size_with_leverage(self, leveraged_backtester):
        """Should apply leverage to position sizing."""
        leveraged_backtester.risk_per_trade = 0.02

        size = leveraged_backtester._calculate_position_size(
            current_balance=10000.0,
            current_price=100.0,
            stop_loss_price=98.0,
            volatility=0.02,
        )

        # With leverage, position should be calculated
        assert size > 0


# =============================================================================
# Liquidation Tests
# =============================================================================


class TestLiquidationCalculations:
    """Tests for liquidation price calculations."""

    def test_calculate_liquidation_price_long(self, leveraged_backtester):
        """Should calculate liquidation price for LONG position."""
        position = Position(
            asset_pair="BTCUSD",
            units=1.0,
            entry_price=100.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="LONG",
        )

        liq_price = leveraged_backtester._calculate_liquidation_price(
            position=position,
            account_balance=1000.0,
        )

        # Liquidation price should be below entry for LONG
        assert liq_price is not None
        assert liq_price < position.entry_price

    def test_calculate_liquidation_price_short(self, leveraged_backtester):
        """Should calculate liquidation price for SHORT position."""
        position = Position(
            asset_pair="BTCUSD",
            units=-1.0,  # Negative for SHORT
            entry_price=100.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="SHORT",
        )

        liq_price = leveraged_backtester._calculate_liquidation_price(
            position=position,
            account_balance=1000.0,
        )

        # Liquidation price should be above entry for SHORT
        assert liq_price is not None
        assert liq_price > position.entry_price

    def test_check_margin_liquidation_not_triggered(self, leveraged_backtester):
        """Should not trigger liquidation when price is safe."""
        position = Position(
            asset_pair="BTCUSD",
            units=1.0,
            entry_price=100.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="LONG",
            liquidation_price=80.0,  # Liquidation at $80
        )

        # Current price 95, candle stayed above liquidation price
        should_liquidate = leveraged_backtester._check_margin_liquidation(
            position=position,
            current_price=95.0,
            candle_high=96.0,
            candle_low=93.0,  # Low is 93, above liquidation price 80
        )

        assert should_liquidate is False

    def test_check_margin_liquidation_triggered(self, leveraged_backtester):
        """Should trigger liquidation when candle low breaches threshold."""
        position = Position(
            asset_pair="BTCUSD",
            units=1.0,
            entry_price=100.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="LONG",
            liquidation_price=80.0,
        )

        # Candle low hit liquidation price
        should_liquidate = leveraged_backtester._check_margin_liquidation(
            position=position,
            current_price=82.0,  # Closed above liquidation
            candle_high=85.0,
            candle_low=75.0,  # Low hit liquidation price
        )

        assert should_liquidate is True

    def test_check_short_liquidation(self, leveraged_backtester):
        """Should trigger liquidation for SHORT when price rises."""
        position = Position(
            asset_pair="BTCUSD",
            units=-1.0,
            entry_price=100.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="SHORT",
            liquidation_price=120.0,  # Liquidation at $120
        )

        # Candle high at $115 - below liquidation
        assert leveraged_backtester._check_margin_liquidation(
            position, 112.0, candle_high=115.0, candle_low=110.0
        ) is False

        # Candle high at $125 - above liquidation
        assert leveraged_backtester._check_margin_liquidation(
            position, 122.0, candle_high=125.0, candle_low=118.0
        ) is True

    def test_check_margin_liquidation_no_liquidation_price(self, leveraged_backtester):
        """Should return False if position has no liquidation price."""
        position = Position(
            asset_pair="BTCUSD",
            units=1.0,
            entry_price=100.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="LONG",
            liquidation_price=None,  # No liquidation price
        )

        should_liquidate = leveraged_backtester._check_margin_liquidation(
            position=position,
            current_price=50.0,  # Price dropped dramatically
            candle_high=60.0,
            candle_low=45.0,
        )

        assert should_liquidate is False


# =============================================================================
# Performance Metrics Tests
# =============================================================================


class TestPerformanceMetrics:
    """Tests for _calculate_performance_metrics method."""

    def test_calculate_metrics_profitable(self, basic_backtester):
        """Should calculate metrics for profitable backtest."""
        equity_curve = [10000, 10500, 11000, 10800, 11500, 12000]
        trades = [
            {"pnl_value": 500, "status": "EXECUTED"},
            {"pnl_value": 500, "status": "EXECUTED"},
            {"pnl_value": -200, "status": "EXECUTED"},
            {"pnl_value": 700, "status": "EXECUTED"},
            {"pnl_value": 500, "status": "EXECUTED"},
        ]

        metrics = basic_backtester._calculate_performance_metrics(
            trades_history=trades,
            equity_curve=equity_curve,
            initial_balance=10000,
            timeframe="1h",
            duration_years=0.1,
            periods_per_year=365 * 24,  # Hourly
        )

        assert "total_return_pct" in metrics
        assert metrics["total_return_pct"] == pytest.approx(20.0, rel=0.01)  # 20% return

    def test_calculate_metrics_losing(self, basic_backtester):
        """Should calculate metrics for losing backtest."""
        equity_curve = [10000, 9500, 9000, 9200, 8800, 8500]
        trades = [
            {"pnl_value": -500, "status": "EXECUTED"},
            {"pnl_value": -500, "status": "EXECUTED"},
            {"pnl_value": 200, "status": "EXECUTED"},
            {"pnl_value": -400, "status": "EXECUTED"},
            {"pnl_value": -300, "status": "EXECUTED"},
        ]

        metrics = basic_backtester._calculate_performance_metrics(
            trades_history=trades,
            equity_curve=equity_curve,
            initial_balance=10000,
            timeframe="1h",
            duration_years=0.1,
            periods_per_year=365 * 24,
        )

        assert metrics["total_return_pct"] == pytest.approx(-15.0, rel=0.01)  # -15% return

    def test_calculate_sharpe_ratio(self, basic_backtester):
        """Should calculate Sharpe ratio."""
        # Steady positive returns
        equity_curve = [10000 + i * 100 for i in range(50)]
        trades = [{"pnl_value": 100, "status": "EXECUTED"} for _ in range(49)]

        metrics = basic_backtester._calculate_performance_metrics(
            trades_history=trades,
            equity_curve=equity_curve,
            initial_balance=10000,
            timeframe="1h",
            duration_years=0.5,
            periods_per_year=365 * 24,
        )

        assert "sharpe_ratio" in metrics
        # Consistent returns should have a Sharpe ratio

    def test_calculate_max_drawdown(self, basic_backtester):
        """Should calculate maximum drawdown."""
        # Equity curve with significant drawdown
        equity_curve = [10000, 12000, 11000, 9000, 10000, 11000]
        trades = [
            {"pnl_value": 2000, "status": "EXECUTED"},
            {"pnl_value": -1000, "status": "EXECUTED"},
            {"pnl_value": -2000, "status": "EXECUTED"},
            {"pnl_value": 1000, "status": "EXECUTED"},
            {"pnl_value": 1000, "status": "EXECUTED"},
        ]

        metrics = basic_backtester._calculate_performance_metrics(
            trades_history=trades,
            equity_curve=equity_curve,
            initial_balance=10000,
            timeframe="1h",
            duration_years=0.1,
            periods_per_year=365 * 24,
        )

        assert "max_drawdown_pct" in metrics
        # Drawdown from 12000 to 9000 = 25%
        assert metrics["max_drawdown_pct"] <= -20.0  # Negative percentage

    def test_calculate_metrics_single_point_equity_curve(self, basic_backtester):
        """Should handle case with single point equity curve."""
        equity_curve = [10000]
        trades = []

        metrics = basic_backtester._calculate_performance_metrics(
            trades_history=trades,
            equity_curve=equity_curve,
            initial_balance=10000,
            timeframe="1h",
            duration_years=0.0,
            periods_per_year=365 * 24,
        )

        assert metrics["total_return_pct"] == 0.0


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_periods_per_year_minute_timeframes(self):
        """Should return correct periods per year for minute timeframes."""
        # Note: uses "1min", "5min" format (not "1m", "5m")
        assert Backtester._get_periods_per_year("1min") == 365 * 24 * 60  # 525,600
        assert Backtester._get_periods_per_year("5min") == 365 * 24 * 12  # 105,120
        assert Backtester._get_periods_per_year("15min") == 365 * 24 * 4  # 35,040
        assert Backtester._get_periods_per_year("30min") == 365 * 24 * 2  # 17,520

    def test_get_periods_per_year_hourly_timeframes(self):
        """Should return correct periods per year for hourly timeframes."""
        assert Backtester._get_periods_per_year("1h") == 365 * 24  # 8,760
        assert Backtester._get_periods_per_year("4h") == 365 * 6  # 2,190

    def test_get_periods_per_year_daily_timeframes(self):
        """Should return correct periods per year for daily/weekly/monthly."""
        # Uses trading days (252) for daily
        assert Backtester._get_periods_per_year("1d") == 252
        assert Backtester._get_periods_per_year("daily") == 252
        assert Backtester._get_periods_per_year("weekly") == 52
        assert Backtester._get_periods_per_year("monthly") == 12

    def test_get_periods_per_year_unknown_defaults_to_252(self):
        """Should return 252 for unknown timeframes."""
        assert Backtester._get_periods_per_year("unknown") == 252
        assert Backtester._get_periods_per_year("2w") == 252

    def test_is_enhanced_slippage_enabled(self, basic_backtester):
        """Should check enhanced slippage via features config."""
        # Enhanced slippage is enabled via features.enhanced_slippage_model
        basic_backtester.config = {"features": {"enhanced_slippage_model": True}}
        assert basic_backtester._is_enhanced_slippage_enabled() is True

        basic_backtester.config = {"features": {"enhanced_slippage_model": False}}
        assert basic_backtester._is_enhanced_slippage_enabled() is False

        basic_backtester.config = {}
        assert basic_backtester._is_enhanced_slippage_enabled() is False

    def test_get_slippage_model(self, basic_backtester):
        """Should return slippage model from config."""
        basic_backtester.config = {"backtesting": {"slippage_model": "realistic"}}
        assert basic_backtester._get_slippage_model() == "realistic"

        basic_backtester.config = {}
        assert basic_backtester._get_slippage_model() == "basic"

    def test_get_fee_model(self, basic_backtester):
        """Should return fee model from config."""
        basic_backtester.config = {"backtesting": {"fee_model": "tiered"}}
        assert basic_backtester._get_fee_model() == "tiered"

        # Default is "simple" not "fixed"
        basic_backtester.config = {}
        assert basic_backtester._get_fee_model() == "simple"


# =============================================================================
# Position Dataclass Tests
# =============================================================================


class TestPositionDataclass:
    """Tests for Position dataclass."""

    def test_position_creation_long(self):
        """Should create LONG position correctly."""
        pos = Position(
            asset_pair="BTCUSD",
            units=1.0,
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="LONG",
        )
        assert pos.units == 1.0
        assert pos.side == "LONG"
        assert pos.stop_loss_price is None

    def test_position_creation_short(self):
        """Should create SHORT position correctly."""
        pos = Position(
            asset_pair="BTCUSD",
            units=-1.0,
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="SHORT",
            stop_loss_price=55000.0,
            take_profit_price=45000.0,
        )
        assert pos.units == -1.0
        assert pos.side == "SHORT"
        assert pos.stop_loss_price == 55000.0
        assert pos.take_profit_price == 45000.0

    def test_position_with_liquidation_price(self):
        """Should track liquidation price."""
        pos = Position(
            asset_pair="BTCUSD",
            units=1.0,
            entry_price=50000.0,
            entry_timestamp=datetime(2024, 1, 1),
            side="LONG",
            liquidation_price=40000.0,
        )
        assert pos.liquidation_price == 40000.0


# =============================================================================
# Fee Calculation Tests
# =============================================================================


class TestFeeCalculation:
    """Tests for _calculate_fees method."""

    def test_calculate_fees_default_platform(self, basic_backtester):
        """Should calculate default fees for unknown platform."""
        fee_rate = basic_backtester._calculate_fees(
            platform="unknown",
            size=1000.0,
            is_maker=False,
        )
        assert fee_rate == 0.001  # Default 0.1%

    def test_calculate_fees_coinbase_maker_vs_taker(self, basic_backtester):
        """Coinbase maker fees should be lower than taker fees."""
        maker_fee = basic_backtester._calculate_fees(
            platform="coinbase",
            size=1000.0,
            is_maker=True,
        )
        taker_fee = basic_backtester._calculate_fees(
            platform="coinbase",
            size=1000.0,
            is_maker=False,
        )
        assert maker_fee == 0.0025  # 0.25% maker
        assert taker_fee == 0.004  # 0.4% taker
        assert maker_fee < taker_fee

    def test_calculate_fees_oanda(self, basic_backtester):
        """Oanda should use spread-based pricing."""
        fee_rate = basic_backtester._calculate_fees(
            platform="oanda",
            size=1000.0,
            is_maker=False,
        )
        assert fee_rate == 0.001  # 0.1% spread approximation

    def test_calculate_fees_zero_size(self, basic_backtester):
        """Should return 0 for zero size trades."""
        fee_rate = basic_backtester._calculate_fees(
            platform="coinbase",
            size=0.0,
            is_maker=False,
        )
        assert fee_rate == 0.0


# =============================================================================
# Close and Cleanup Tests
# =============================================================================


class TestCleanup:
    """Tests for close and cleanup methods."""

    def test_close_method(self, basic_backtester):
        """Should close resources cleanly."""
        # Should not raise
        basic_backtester.close()

    def test_close_with_decision_cache(self, mock_historical_data_provider):
        """Should close decision cache if present."""
        with patch("finance_feedback_engine.backtesting.decision_cache.DecisionCache") as MockCache:
            mock_cache = MagicMock()
            MockCache.return_value = mock_cache

            bt = Backtester(
                historical_data_provider=mock_historical_data_provider,
                enable_decision_cache=True,
                enable_portfolio_memory=False,
            )
            bt.close()

            mock_cache.close.assert_called_once()


# =============================================================================
# Realistic Slippage Tests
# =============================================================================


class TestRealisticSlippage:
    """Tests for _calculate_realistic_slippage method."""

    def test_major_crypto_base_slippage(self, basic_backtester):
        """Major crypto (BTC, ETH) should have 2 bps base slippage."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)  # Normal trading hours

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=500,  # Small size
            timestamp=timestamp,
        )

        # Base 2 bps + 0.5 bps volume impact for small trades = 2.5 bps
        assert slippage == pytest.approx(0.00025, rel=0.01)

    def test_major_forex_base_slippage(self, basic_backtester):
        """Major forex pairs should have 1 bp base slippage."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="EURUSD",
            size=500,  # Small size
            timestamp=timestamp,
        )

        # Base 1 bp + 0.5 bps volume impact = 1.5 bps
        assert slippage == pytest.approx(0.00015, rel=0.01)

    def test_exotic_pair_base_slippage(self, basic_backtester):
        """Exotic pairs/altcoins should have 5 bps base slippage."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="SOLUSD",  # Altcoin
            size=500,
            timestamp=timestamp,
        )

        # Base 5 bps + 0.5 bps volume impact = 5.5 bps
        assert slippage == pytest.approx(0.00055, rel=0.01)

    def test_volume_impact_small_trade(self, basic_backtester):
        """Small trades (<1000) should have 0.5 bps volume impact."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=999,  # Just under small threshold
            timestamp=timestamp,
        )

        # 2 bps base + 0.5 bps small volume = 2.5 bps
        assert slippage == pytest.approx(0.00025, rel=0.01)

    def test_volume_impact_medium_trade(self, basic_backtester):
        """Medium trades (1000-10000) should have 1 bp volume impact."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=5000,
            timestamp=timestamp,
        )

        # 2 bps base + 1 bp medium volume = 3 bps
        assert slippage == pytest.approx(0.0003, rel=0.01)

    def test_volume_impact_large_trade(self, basic_backtester):
        """Large trades (>10000) should have 3 bps volume impact."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=50000,
            timestamp=timestamp,
        )

        # 2 bps base + 3 bps large volume = 5 bps
        assert slippage == pytest.approx(0.0005, rel=0.01)

    def test_low_liquidity_hours_multiplier(self, basic_backtester):
        """Low liquidity hours (0-2, 20-23 UTC) should have 1.5x multiplier."""
        # Hour 1 is low liquidity
        timestamp_low_liq = datetime(2024, 1, 1, 1, 0, 0)
        # Hour 12 is normal liquidity
        timestamp_normal = datetime(2024, 1, 1, 12, 0, 0)

        slippage_low = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=500,
            timestamp=timestamp_low_liq,
        )

        slippage_normal = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=500,
            timestamp=timestamp_normal,
        )

        # Low liquidity should be 1.5x normal
        assert slippage_low == pytest.approx(slippage_normal * 1.5, rel=0.01)

    def test_zero_size_returns_zero(self, basic_backtester):
        """Zero size should return zero slippage."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=0,
            timestamp=timestamp,
        )

        assert slippage == 0.0

    def test_negative_size_uses_absolute_value(self, basic_backtester):
        """Negative size should use absolute value."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)

        slippage_pos = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=500,
            timestamp=timestamp,
        )

        slippage_neg = basic_backtester._calculate_realistic_slippage(
            asset_pair="BTCUSD",
            size=-500,
            timestamp=timestamp,
        )

        assert slippage_pos == slippage_neg


# =============================================================================
# Enhanced Slippage Integration Tests
# =============================================================================


class TestEnhancedSlippageIntegration:
    """Tests for enhanced slippage model integration in trade execution."""

    def test_realistic_slippage_used_when_enabled(self, basic_backtester):
        """Should use realistic slippage when enhanced model is enabled."""
        basic_backtester.config = {"features": {"enhanced_slippage_model": True}}
        basic_backtester.slippage_percentage = 0.01  # This should be ignored

        assert basic_backtester._is_enhanced_slippage_enabled() is True

    def test_basic_slippage_used_when_disabled(self, basic_backtester):
        """Should use basic slippage when enhanced model is disabled."""
        basic_backtester.config = {}

        assert basic_backtester._is_enhanced_slippage_enabled() is False


# =============================================================================
# Config Attribute Tests
# =============================================================================


class TestBacktesterConfig:
    """Tests for backtester configuration attributes."""

    def test_default_config_is_empty_dict(self, basic_backtester):
        """Default config should be empty dict."""
        assert basic_backtester.config == {}

    def test_config_can_be_set(self, basic_backtester):
        """Config should be settable."""
        basic_backtester.config = {"key": "value"}
        assert basic_backtester.config == {"key": "value"}

    def test_risk_free_rate_default(self, basic_backtester):
        """Risk-free rate should have sensible default."""
        # Used in Sharpe ratio calculation
        assert hasattr(basic_backtester, "risk_free_rate")

    def test_timeframe_attribute(self, basic_backtester):
        """Should have timeframe attribute."""
        assert hasattr(basic_backtester, "timeframe")


# =============================================================================
# Run Method Empty Data Tests
# =============================================================================


class TestRunBacktestEdgeCases:
    """Tests for run_backtest() method edge cases."""

    def test_run_backtest_with_empty_data_returns_empty_result(self, mock_historical_data_provider):
        """run_backtest should return empty result when no data available."""
        # Configure mock to return empty DataFrame
        mock_historical_data_provider.get_historical_data.return_value = pd.DataFrame()

        bt = Backtester(
            historical_data_provider=mock_historical_data_provider,
            enable_decision_cache=False,
            enable_portfolio_memory=False,
        )

        # Mock decision engine (required argument)
        mock_decision_engine = MagicMock()

        result = bt.run_backtest(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-01-31",
            decision_engine=mock_decision_engine,
        )

        assert result["metrics"]["net_return_pct"] == 0
        assert result["metrics"]["total_trades"] == 0
        assert result["trades"] == []
