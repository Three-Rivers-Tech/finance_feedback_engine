"""Tests for backtesting configuration manager."""

import pytest
from datetime import datetime, timedelta
from finance_feedback_engine.backtesting.config_manager import (
    BacktestConfiguration,
    BacktestScenario,
    BacktestResultComparison,
    BacktestConfigurationManager,
)


class TestBacktestConfiguration:
    """Test BacktestConfiguration dataclass."""

    def test_default_configuration(self):
        """Test creation with minimal required parameters."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        assert config.asset_pair == "BTCUSD"
        assert config.start_date == "2024-01-01"
        assert config.end_date == "2024-03-01"
        assert config.initial_balance == 10000.0
        assert config.fee_percentage == 0.001
        assert config.slippage_percentage == 0.0005

    def test_custom_configuration(self):
        """Test creation with custom parameters."""
        config = BacktestConfiguration(
            asset_pair="ETHUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            initial_balance=50000.0,
            fee_percentage=0.002,
            max_position_size=0.2,
        )
        
        assert config.initial_balance == 50000.0
        assert config.fee_percentage == 0.002
        assert config.max_position_size == 0.2

    def test_validate_valid_config(self):
        """Test validation passes for valid config."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        errors = config.validate()
        assert errors == []

    def test_validate_invalid_dates(self):
        """Test validation catches invalid date ranges."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-03-01",
            end_date="2024-01-01"  # End before start
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any("date" in err.lower() for err in errors)

    def test_validate_negative_balance(self):
        """Test validation catches negative initial balance."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            initial_balance=-1000.0
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any("balance" in err.lower() for err in errors)

    def test_validate_invalid_percentages(self):
        """Test validation catches invalid percentage values."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            fee_percentage=-0.01,  # Negative fee
            stop_loss_percentage=1.5,  # >100%
        )
        
        errors = config.validate()
        assert len(errors) > 0

    def test_validate_zero_max_position_size(self):
        """Test validation catches zero/negative position size."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            max_position_size=0.0
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any("position" in err.lower() for err in errors)

    def test_validate_invalid_timeframe(self):
        """Test validation catches invalid timeframe."""
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            timeframe="2h"  # Not in valid list
        )
        
        errors = config.validate()
        assert len(errors) > 0
        assert any("timeframe" in err.lower() for err in errors)


class TestBacktestScenario:
    """Test BacktestScenario for parameter variations."""

    def test_create_scenario(self):
        """Test creating a backtest scenario."""
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        scenario = BacktestScenario(
            name="Test Scenario",
            description="Testing parameter variations",
            base_config=base_config
        )
        
        assert scenario.name == "Test Scenario"
        assert scenario.base_config.asset_pair == "BTCUSD"
        assert len(scenario.parameter_variations) == 0

    def test_add_variation(self):
        """Test adding parameter variations."""
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        scenario = BacktestScenario(
            name="Stop Loss Test",
            description="Test different stop loss percentages",
            base_config=base_config
        )
        
        scenario.add_variation(stop_loss_percentage=0.01)
        scenario.add_variation(stop_loss_percentage=0.02)
        scenario.add_variation(stop_loss_percentage=0.03)
        
        assert len(scenario.parameter_variations) == 3
        assert scenario.parameter_variations[0]["stop_loss_percentage"] == 0.01

    def test_get_all_configurations(self):
        """Test generating all configuration variations."""
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            initial_balance=10000.0
        )
        
        scenario = BacktestScenario(
            name="Multi-Parameter Test",
            description="Test multiple parameters",
            base_config=base_config
        )
        
        scenario.add_variation(stop_loss_percentage=0.02, take_profit_percentage=0.05)
        scenario.add_variation(stop_loss_percentage=0.03, take_profit_percentage=0.08)
        
        configs = scenario.get_all_configurations()
        
        assert len(configs) == 2
        assert configs[0].stop_loss_percentage == 0.02
        assert configs[0].take_profit_percentage == 0.05
        assert configs[1].stop_loss_percentage == 0.03
        assert configs[1].take_profit_percentage == 0.08


class TestBacktestResultComparison:
    """Test BacktestResultComparison for analyzing results."""

    def test_add_result(self):
        """Test adding backtest results."""
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        scenario = BacktestScenario(
            name="Test",
            description="Test comparison",
            base_config=base_config
        )
        
        comparison = BacktestResultComparison(scenario)
        
        config1 = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            stop_loss_percentage=0.02
        )
        result1 = {
            "total_return": 0.15,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.08
        }
        
        comparison.add_result(config1, result1)
        assert len(comparison.results) == 1

    def test_compare_performance(self):
        """Test comparing performance across configurations."""
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        scenario = BacktestScenario(
            name="Performance Test",
            description="Compare different configs",
            base_config=base_config
        )
        
        comparison = BacktestResultComparison(scenario)
        
        # Add multiple results
        for sl_pct in [0.01, 0.02, 0.03]:
            config = BacktestConfiguration(
                asset_pair="BTCUSD",
                start_date="2024-01-01",
                end_date="2024-03-01",
                stop_loss_percentage=sl_pct
            )
            result = {
                "total_return": 0.10 + sl_pct,
                "sharpe_ratio": 1.0 + sl_pct * 10,
                "max_drawdown": 0.05 + sl_pct
            }
            comparison.add_result(config, result)
        
        performance = comparison.compare_performance()
        
        assert "best_configuration" in performance
        assert "configs" in performance
        assert "performance_metrics" in performance


class TestBacktestConfigurationManager:
    """Test BacktestConfigurationManager for managing multiple scenarios."""

    def test_initialization(self):
        """Test scenario manager initialization."""
        manager = BacktestConfigurationManager()
        assert manager is not None

    def test_create_scenario(self):
        """Test creating a scenario through manager."""
        manager = BacktestConfigurationManager()
        
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        scenario = manager.create_scenario(
            name="Manager Test",
            description="Test scenario creation",
            base_config=base_config
        )
        
        assert scenario.name == "Manager Test"
        assert scenario.base_config.asset_pair == "BTCUSD"

    def test_create_multiple_scenarios(self):
        """Test creating multiple scenarios."""
        manager = BacktestConfigurationManager()
        
        config1 = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        config2 = BacktestConfiguration(
            asset_pair="ETHUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )
        
        scenario1 = manager.create_scenario(
            name="Scenario 1",
            description="First scenario",
            base_config=config1
        )
        
        scenario2 = manager.create_scenario(
            name="Scenario 2",
            description="Second scenario",
            base_config=config2
        )
        
        assert scenario1.base_config.asset_pair == "BTCUSD"
        assert scenario2.base_config.asset_pair == "ETHUSD"

    def test_run_scenario_comparison(self):
        """Test running a scenario comparison."""
        manager = BacktestConfigurationManager()
        
        # This would require actual backtest execution
        # For now, just test that method exists and accepts parameters
        scenario_name = "Test Scenario"
        
        # Check method signature exists
        assert hasattr(manager, 'run_scenario_comparison')
        assert callable(manager.run_scenario_comparison)
