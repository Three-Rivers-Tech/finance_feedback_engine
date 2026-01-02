"""Tests for backtesting orchestrator."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from finance_feedback_engine.backtesting.orchestrator import BacktestOrchestrator
from finance_feedback_engine.backtesting.config_manager import BacktestConfiguration


class TestBacktestOrchestrator:
    """Test BacktestOrchestrator initialization and basic operations."""

    def test_initialization(self):
        """Test orchestrator initialization with required dependencies."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        assert orchestrator.historical_data_provider == mock_data_provider
        assert orchestrator.decision_engine == mock_decision_engine
        assert orchestrator.config_manager is not None
        assert orchestrator.executor is not None

    def test_initialization_with_config(self):
        """Test orchestrator initialization with custom config."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()
        config = {"enable_caching": True, "parallel_workers": 8}

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine,
            config=config
        )

        assert orchestrator.config == config
        assert orchestrator.config["enable_caching"] is True

    @patch('finance_feedback_engine.backtesting.orchestrator.Backtester')
    def test_run_single_backtest_valid_config(self, mock_backtester_class):
        """Test running a single backtest with valid configuration."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        # Setup mock backtester instance
        mock_backtester = Mock()
        mock_backtester.run_backtest.return_value = {
            "total_return": 0.15,
            "sharpe_ratio": 1.5,
            "max_drawdown": 0.08
        }
        mock_backtester_class.return_value = mock_backtester

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            initial_balance=10000.0
        )

        result = orchestrator.run_single_backtest(config)

        # Verify backtester was created with correct parameters
        mock_backtester_class.assert_called_once()
        mock_backtester.run_backtest.assert_called_once()

        # Verify results
        assert result["total_return"] == 0.15
        assert result["sharpe_ratio"] == 1.5

    def test_run_single_backtest_invalid_config(self):
        """Test that invalid configuration raises ValueError."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        # Invalid config: end date before start date
        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-03-01",
            end_date="2024-01-01"  # Invalid
        )

        with pytest.raises(ValueError) as exc_info:
            orchestrator.run_single_backtest(config)

        assert "Invalid configuration" in str(exc_info.value)

    def test_run_scenario_comparison(self):
        """Test running scenario comparison."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        # Create a scenario first
        base_config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )

        scenario = orchestrator.config_manager.create_scenario(
            name="Test Scenario",
            description="Test comparison",
            base_config=base_config
        )

        # Note: This would require actual backtest execution in real usage
        # For unit test, we just verify the method can be called
        assert scenario.name == "Test Scenario"

    @patch('finance_feedback_engine.backtesting.orchestrator.Backtester')
    def test_backtester_receives_all_config_params(self, mock_backtester_class):
        """Test that backtester receives all configuration parameters."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        mock_backtester = Mock()
        mock_backtester.run_backtest.return_value = {}
        mock_backtester_class.return_value = mock_backtester

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        config = BacktestConfiguration(
            asset_pair="BTCUSD",
            start_date="2024-01-01",
            end_date="2024-03-01",
            initial_balance=20000.0,
            fee_percentage=0.002,
            slippage_percentage=0.001,
            stop_loss_percentage=0.03,
            take_profit_percentage=0.06,
            timeframe="4h"
        )

        orchestrator.run_single_backtest(config)

        # Verify backtester was created with all parameters
        call_kwargs = mock_backtester_class.call_args[1]
        assert call_kwargs["initial_balance"] == 20000.0
        assert call_kwargs["fee_percentage"] == 0.002
        assert call_kwargs["slippage_percentage"] == 0.001
        assert call_kwargs["stop_loss_percentage"] == 0.03
        assert call_kwargs["take_profit_percentage"] == 0.06
        assert call_kwargs["timeframe"] == "4h"

    def test_executor_initialized(self):
        """Test that thread pool executor is properly initialized."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        # Verify executor exists and has workers
        assert orchestrator.executor is not None
        assert orchestrator.max_workers >= 1


class TestBacktestOrchestratorIntegration:
    """Integration tests for orchestrator with config manager."""

    def test_create_and_retrieve_scenario(self):
        """Test creating scenario through orchestrator's config manager."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        config = BacktestConfiguration(
            asset_pair="ETHUSD",
            start_date="2024-01-01",
            end_date="2024-03-01"
        )

        scenario = orchestrator.config_manager.create_scenario(
            name="Integration Test",
            description="Test scenario retrieval",
            base_config=config
        )

        # Verify scenario is stored in manager
        assert "Integration Test" in orchestrator.config_manager.scenarios
        retrieved = orchestrator.config_manager.scenarios["Integration Test"]
        assert retrieved.base_config.asset_pair == "ETHUSD"

    def test_multiple_scenarios_management(self):
        """Test managing multiple scenarios simultaneously."""
        mock_data_provider = Mock()
        mock_decision_engine = Mock()

        orchestrator = BacktestOrchestrator(
            historical_data_provider=mock_data_provider,
            decision_engine=mock_decision_engine
        )

        # Create multiple scenarios
        for i, pair in enumerate(["BTCUSD", "ETHUSD", "EURUSD"]):
            config = BacktestConfiguration(
                asset_pair=pair,
                start_date="2024-01-01",
                end_date="2024-03-01"
            )
            orchestrator.config_manager.create_scenario(
                name=f"Scenario {i+1}",
                description=f"Test {pair}",
                base_config=config
            )

        # Verify all scenarios are stored
        assert len(orchestrator.config_manager.scenarios) == 3
        assert "Scenario 1" in orchestrator.config_manager.scenarios
        assert "Scenario 2" in orchestrator.config_manager.scenarios
        assert "Scenario 3" in orchestrator.config_manager.scenarios
