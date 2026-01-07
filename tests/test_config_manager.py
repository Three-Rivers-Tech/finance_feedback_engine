"""Tests for backtesting configuration manager."""

import pytest
import pytest

from finance_feedback_engine.backtesting.config_manager import (

from finance_feedback_engine.backtesting.config_manager import (
    BacktestConfiguration,
)


class TestBacktestConfiguration:
    """Test suite for BacktestConfiguration."""

    def test_default_initialization(self):
        """Test default initialization of BacktestConfiguration."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        assert config.asset_pair == "BTCUSD"
        assert config.start_date == "2024-01-01"
        assert config.end_date == "2024-12-31"
        assert config.initial_balance == 10000.0
        assert config.fee_percentage == 0.001
        assert config.slippage_percentage == 0.0005
        assert config.max_position_size == 0.1

    def test_custom_initialization(self):
        """Test initialization with custom parameters."""
        config = BacktestConfiguration(
            asset_pair="ETHUSD",
            start_date="2024-01-01",
            end_date="2024-06-30",
            initial_balance=50000.0,
            fee_percentage=0.002,
            slippage_percentage=0.001,
            stop_loss_percentage=0.03,
            take_profit_percentage=0.06,
            max_position_size=0.2,
        )

        assert config.asset_pair == "ETHUSD"
        assert config.initial_balance == 50000.0
        assert config.fee_percentage == 0.002
        assert config.slippage_percentage == 0.001
        assert config.stop_loss_percentage == 0.03
        assert config.take_profit_percentage == 0.06
        assert config.max_position_size == 0.2

    def test_validate_valid_config(self):
        """Test validation of valid configuration."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        errors = config.validate()

        assert len(errors) == 0

    def test_validate_invalid_date_format(self):
        """Test validation with invalid date format."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024/01/01",  # Wrong format
            end_date="2024-12-31",
        )

        errors = config.validate()

        assert any("Invalid date format" in error for error in errors)

    def test_validate_start_after_end(self):
        """Test validation when start date is after end date."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-12-31",
            end_date="2024-01-01",
        )

        errors = config.validate()

        assert any("Start date must be before end date" in error for error in errors)

    def test_validate_negative_initial_balance(self):
        """Test validation with negative initial balance."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            initial_balance=-1000.0,
        )

        errors = config.validate()

        assert any("Initial balance must be positive" in error for error in errors)

    def test_validate_invalid_fee_percentage(self):
        """Test validation with invalid fee percentage."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            fee_percentage=0.15,  # Too high
        )

        errors = config.validate()

        assert any("Fee percentage" in error for error in errors)

    def test_validate_invalid_slippage_percentage(self):
        """Test validation with invalid slippage percentage."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            slippage_percentage=-0.01,  # Negative
        )

        errors = config.validate()

        assert any("Slippage percentage" in error for error in errors)

    def test_validate_invalid_stop_loss_percentage(self):
        """Test validation with invalid stop loss percentage."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            stop_loss_percentage=0.6,  # Too high
        )

        errors = config.validate()

        assert any("Stop loss percentage" in error for error in errors)

    def test_validate_invalid_take_profit_percentage(self):
        """Test validation with invalid take profit percentage."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            take_profit_percentage=1.5,  # Too high
        )

        errors = config.validate()

        assert any("Take profit percentage" in error for error in errors)

    def test_validate_invalid_max_position_size(self):
        """Test validation with invalid max position size."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            max_position_size=1.5,  # Over 100%
        )

        errors = config.validate()

        assert any("Max position size" in error for error in errors)

    def test_validate_invalid_max_daily_trades(self):
        """Test validation with invalid max daily trades."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            max_daily_trades=0,  # Must be positive
        )

        errors = config.validate()

        assert any("Max daily trades must be positive" in error for error in errors)

    def test_validate_invalid_timeframe(self):
        """Test validation with invalid timeframe."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            timeframe="2h",  # Not in valid list
        )

        errors = config.validate()

        assert any("Timeframe must be one of" in error for error in errors)

    def test_valid_timeframes(self):
        """Test that all valid timeframes pass validation."""
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]

        for timeframe in valid_timeframes:
            config = BacktestConfiguration(
                asset_pair="BTCUSD",
                start_date="2024-01-01",
                end_date="2024-12-31",
                timeframe=timeframe,
            )

            errors = config.validate()

            # Should not have timeframe errors
            assert not any("Timeframe" in error for error in errors)

    def test_position_sizing_strategies(self):
        """Test different position sizing strategies."""
        strategies = ["fixed_fraction", "kelly_criterion", "fixed_amount"]

        for strategy in strategies:
            config = BacktestConfiguration(
                asset_pair="BTCUSD",
                start_date="2024-01-01",
                end_date="2024-12-31",
                position_sizing_strategy=strategy,
            )

            assert config.position_sizing_strategy == strategy

    def test_risk_management_flags(self):
        """Test risk management configuration flags."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            enable_risk_management=False,
            enable_position_sizing=False,
        )

        assert config.enable_risk_management is False
        assert config.enable_position_sizing is False

    def test_validation_flags(self):
        """Test validation configuration flags."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            validation_enabled=True,
            walk_forward_enabled=True,
            monte_carlo_enabled=True,
            monte_carlo_iterations=500,
        )

        assert config.validation_enabled is True
        assert config.walk_forward_enabled is True
        assert config.monte_carlo_enabled is True
        assert config.monte_carlo_iterations == 500

    def test_performance_analytics_flags(self):
        """Test performance analytics configuration."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            generate_performance_report=True,
            generate_visualizations=True,
            visualization_types=["equity_curve", "pnl_distribution", "drawdown"],
        )

        assert config.generate_performance_report is True
        assert config.generate_visualizations is True
        assert "equity_curve" in config.visualization_types
        assert "pnl_distribution" in config.visualization_types
        assert "drawdown" in config.visualization_types

    def test_strategy_parameters(self):
        """Test strategy parameters configuration."""
        strategy_params = {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "ma_fast": 12,
            "ma_slow": 26,
        }

        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            strategy_name="rsi_ma_strategy",
            strategy_parameters=strategy_params,
        )

        assert config.strategy_name == "rsi_ma_strategy"
        assert config.strategy_parameters == strategy_params
        assert config.strategy_parameters["rsi_period"] == 14

    def test_random_seed(self):
        """Test random seed configuration for reproducibility."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            random_seed=42,
        )

        assert config.random_seed == 42

    def test_multi_timeframe_analysis(self):
        """Test multi-timeframe analysis configuration."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            use_multi_timeframe_analysis=True,
            timeframe="1h",
        )

        assert config.use_multi_timeframe_analysis is True
        assert config.timeframe == "1h"

    def test_portfolio_parameters(self):
        """Test portfolio management parameters."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            max_drawdown_percentage=0.20,
            correlation_threshold=0.8,
            max_correlated_assets=3,
        )

        assert config.max_drawdown_percentage == 0.20
        assert config.correlation_threshold == 0.8
        assert config.max_correlated_assets == 3

    def test_transaction_costs(self):
        """Test transaction cost parameters."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            fee_percentage=0.002,
            slippage_percentage=0.001,
            slippage_impact_factor=0.02,
            commission_per_trade=1.0,
        )

        assert config.fee_percentage == 0.002
        assert config.slippage_percentage == 0.001
        assert config.slippage_impact_factor == 0.02
        assert config.commission_per_trade == 1.0

    def test_lookback_period(self):
        """Test lookback period configuration."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            lookback_period=100,
        )

        assert config.lookback_period == 100

    def test_multiple_validation_errors(self):
        """Test that multiple validation errors are collected."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-12-31",  # After end date
            end_date="2024-01-01",
            initial_balance=-1000.0,  # Negative
            fee_percentage=0.15,  # Too high
            timeframe="2h",  # Invalid
        )

        errors = config.validate()

        # Should have multiple errors
        assert len(errors) >= 4

    def test_edge_case_dates(self):
        """Test edge case date configurations."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-01-02",  # Only one day difference
        )

        errors = config.validate()

        # Should be valid
        assert len(errors) == 0

    def test_zero_fees(self):
        """Test configuration with zero fees."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-12-31",
            fee_percentage=0.0,
            slippage_percentage=0.0,
            commission_per_trade=0.0,
        )

        errors = config.validate()

        assert len(errors) == 0
