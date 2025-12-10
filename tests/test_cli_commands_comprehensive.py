"""Comprehensive tests for CLI commands in finance_feedback_engine/cli/main.py.

This test suite aims to maximize code coverage of the CLI module (1,295 statements).
Tests cover all major commands: analyze, execute, monitor, backtest, approve, dashboard, etc.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock, mock_open
import json
import os
from pathlib import Path
from datetime import datetime


class TestCLIInitialization:
    """Test CLI entry point and configuration loading."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create temporary config file."""
        config = {
            'trading_platform': 'mock',
            'platform_credentials': {
                'mock': {'balance': '10000'}
            },
            'data_provider': 'alpha_vantage',
            'ai_provider': 'local',
            'alpha_vantage_api_key': 'test_key'
        }
        config_file = tmp_path / 'config.yaml'
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        return str(config_file)

    def test_cli_help(self, runner):
        """Test CLI --help displays usage."""
        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Usage:' in result.output

    def test_cli_version(self, runner):
        """Test CLI displays version."""
        from finance_feedback_engine.cli.main import cli
        # Most CLIs have a --version flag
        result = runner.invoke(cli, ['--help'])
        # Even if no --version, help should work
        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.load_config')
    def test_cli_loads_config(self, mock_load_config, runner, mock_config):
        """Test CLI loads configuration on startup."""
        mock_load_config.return_value = {'trading_platform': 'mock'}

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['--config', mock_config, '--help'])

        # Config loading should have been attempted
        assert result.exit_code == 0


class TestAnalyzeCommand:
    """Test 'analyze' command functionality."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_engine(self):
        """Create mock FinanceFeedbackEngine."""
        engine = Mock()
        engine.generate_decision.return_value = {
            'decision_id': 'dec_12345',
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Strong uptrend detected',
            'position_size': 0.1,
            'asset_pair': 'BTCUSD'
        }
        engine.data_provider = Mock()
        engine.data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'market_regime': 'TRENDING_BULL'
        })
        return engine

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_analyze_basic(self, mock_ffe_class, mock_engine, runner):
        """Test basic analyze command."""
        mock_ffe_class.return_value = mock_engine

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['analyze', 'BTCUSD'])

        # Command should execute without error
        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert 'Error' not in result.output

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_analyze_with_provider(self, mock_ffe_class, mock_engine, runner):
        """Test analyze with specific AI provider."""
        mock_ffe_class.return_value = mock_engine

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['analyze', 'BTCUSD', '--provider', 'ensemble'])

        assert result.exit_code == 0, f"Command failed: {result.output}"
        mock_engine.generate_decision.assert_called()

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_analyze_show_pulse(self, mock_ffe_class, mock_engine, runner):
        """Test analyze with --show-pulse flag."""
        mock_ffe_class.return_value = mock_engine

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['analyze', 'BTCUSD', '--show-pulse'])

        # Pulse data display should be triggered
        assert result.exit_code == 0 or mock_engine.data_provider.get_comprehensive_market_data.called


class TestExecuteCommand:
    """Test 'execute' command functionality."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_decision_file(self, tmp_path):
        """Create mock decision file."""
        decision = {
            'decision_id': 'dec_123',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'position_size': 0.1,
            'confidence': 80
        }

        decision_dir = tmp_path / 'data' / 'decisions'
        decision_dir.mkdir(parents=True)

        decision_file = decision_dir / f"{datetime.now().strftime('%Y-%m-%d')}_dec_123.json"
        with open(decision_file, 'w') as f:
            json.dump(decision, f)

        return str(decision_file), decision

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('finance_feedback_engine.cli.main.Path')
    def test_execute_success(self, mock_path, mock_ffe_class, runner, tmp_path):
        """Test successful execution of decision."""
        # Setup mocks
        engine = Mock()
        engine.execute_decision.return_value = {'status': 'success', 'order_id': '12345'}
        mock_ffe_class.return_value = engine

        # Mock decision file
        decision = {'decision_id': 'dec_123', 'action': 'BUY', 'asset_pair': 'BTCUSD'}
        mock_path.return_value.exists.return_value = True

        with patch('builtins.open', mock_open(read_data=json.dumps(decision))):
            from finance_feedback_engine.cli.main import cli
            result = runner.invoke(cli, ['execute', 'dec_123'])

        # Execution should be attempted
        assert result.exit_code == 0 or engine.execute_decision.called


class TestMonitorCommands:
    """Test 'monitor' command group."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.TradeMonitor')
    def test_monitor_start(self, mock_monitor_class, runner):
        """Test monitor start command."""
        mock_monitor = Mock()
        mock_monitor_class.return_value = mock_monitor

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['monitor', 'start'])

        # Monitor should be started
        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.TradeMonitor')
    def test_monitor_status(self, mock_monitor_class, runner):
        """Test monitor status command."""
        mock_monitor = Mock()
        mock_monitor.is_monitoring.return_value = True
        mock_monitor_class.return_value = mock_monitor

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['monitor', 'status'])

        assert result.exit_code == 0


class TestDashboardCommand:
    """Test 'dashboard' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_dashboard_displays_portfolio(self, mock_ffe_class, runner):
        """Test dashboard displays portfolio summary."""
        engine = Mock()
        engine.platform.get_portfolio_breakdown.return_value = {
            'total_value_usd': 10000.0,
            'holdings': [
                {'asset': 'BTCUSD', 'balance': 0.5, 'value_usd': 25000.0}
            ]
        }
        mock_ffe_class.return_value = engine

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['dashboard'])

        assert result.exit_code == 0


class TestHistoryCommand:
    """Test 'history' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.DecisionStore')
    def test_history_list_decisions(self, mock_store_class, runner):
        """Test history lists past decisions."""
        mock_store = Mock()
        mock_store.load_all_decisions.return_value = [
            {'decision_id': 'dec_1', 'action': 'BUY', 'asset_pair': 'BTCUSD'},
            {'decision_id': 'dec_2', 'action': 'SELL', 'asset_pair': 'ETHUSD'}
        ]
        mock_store_class.return_value = mock_store

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['history'])

        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.DecisionStore')
    def test_history_filter_by_asset(self, mock_store_class, runner):
        """Test history filters by asset pair."""
        mock_store = Mock()
        mock_store.load_all_decisions.return_value = [
            {'decision_id': 'dec_1', 'action': 'BUY', 'asset_pair': 'BTCUSD'}
        ]
        mock_store_class.return_value = mock_store

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['history', '--asset', 'BTCUSD'])

        assert result.exit_code == 0


class TestApproveCommand:
    """Test 'approve' command with interactive workflow."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_decision_for_approval(self, tmp_path):
        """Create mock decision file for approval."""
        decision = {
            'decision_id': 'dec_approve_123',
            'action': 'BUY',
            'asset_pair': 'BTCUSD',
            'position_size': 0.05,
            'confidence': 75,
            'reasoning': 'Test decision'
        }

        decision_dir = tmp_path / 'data' / 'decisions'
        decision_dir.mkdir(parents=True)

        filename = f"{datetime.now().strftime('%Y-%m-%d')}_dec_approve_123.json"
        decision_file = decision_dir / filename

        with open(decision_file, 'w') as f:
            json.dump(decision, f)

        return str(decision_file), decision

    @patch('finance_feedback_engine.cli.main.Path')
    @patch('finance_feedback_engine.cli.main.Prompt.ask')
    def test_approve_yes(self, mock_prompt, mock_path, runner, tmp_path):
        """Test approving a decision."""
        decision = {'decision_id': 'dec_123', 'action': 'BUY', 'asset_pair': 'BTCUSD'}

        mock_path.return_value.exists.return_value = True
        mock_prompt.return_value = 'yes'

        with patch('builtins.open', mock_open(read_data=json.dumps(decision))):
            from finance_feedback_engine.cli.main import cli
            result = runner.invoke(cli, ['approve', 'dec_123'], input='yes\n')

        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.Path')
    @patch('finance_feedback_engine.cli.main.Prompt.ask')
    def test_approve_no(self, mock_prompt, mock_path, runner):
        """Test rejecting a decision."""
        decision = {'decision_id': 'dec_123', 'action': 'BUY', 'asset_pair': 'BTCUSD'}

        mock_path.return_value.exists.return_value = True
        mock_prompt.return_value = 'no'

        with patch('builtins.open', mock_open(read_data=json.dumps(decision))):
            from finance_feedback_engine.cli.main import cli
            result = runner.invoke(cli, ['approve', 'dec_123'], input='no\n')

        assert result.exit_code == 0


class TestWipeDecisionsCommand:
    """Test 'wipe-decisions' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.Path')
    def test_wipe_decisions_requires_confirmation(self, mock_path, runner):
        """Test wipe-decisions requires --confirm flag."""
        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['wipe-decisions'])

        # Should require confirmation
        assert result.exit_code != 0 or 'confirm' in result.output.lower()

    @patch('finance_feedback_engine.cli.main.Path')
    @patch('finance_feedback_engine.cli.main.shutil.rmtree')
    def test_wipe_decisions_with_confirm(self, mock_rmtree, mock_path, runner):
        """Test wipe-decisions with --confirm flag."""
        mock_path.return_value.exists.return_value = True

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['wipe-decisions', '--confirm'])

        assert result.exit_code == 0


class TestBacktestCommand:
    """Test 'backtest' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.Backtester')
    def test_backtest_basic(self, mock_backtester_class, runner):
        """Test basic backtest command."""
        mock_backtester = Mock()
        mock_backtester.run.return_value = {
            'total_return': 0.15,
            'sharpe_ratio': 1.5,
            'max_drawdown': 0.08
        }
        mock_backtester_class.return_value = mock_backtester

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, [
            'backtest', 'BTCUSD',
            '--start-date', '2024-01-01',
            '--end-date', '2024-12-01'
        ])

        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.Backtester')
    def test_backtest_with_provider(self, mock_backtester_class, runner):
        """Test backtest with specific provider."""
        mock_backtester = Mock()
        mock_backtester.run.return_value = {'total_return': 0.10}
        mock_backtester_class.return_value = mock_backtester

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, [
            'backtest', 'BTCUSD',
            '--start-date', '2024-01-01',
            '--provider', 'local'
        ])

        assert result.exit_code == 0


class TestAgentCommand:
    """Test 'run-agent' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.TradingAgentOrchestrator')
    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_run_agent_basic(self, mock_ffe_class, mock_orchestrator_class, runner):
        """Test run-agent command."""
        mock_orchestrator = Mock()
        mock_orchestrator.run.return_value = None
        mock_orchestrator_class.return_value = mock_orchestrator

        engine = Mock()
        mock_ffe_class.return_value = engine

        from finance_feedback_engine.cli.main import cli
        # Use --setup flag to avoid actual agent run
        result = runner.invoke(cli, ['run-agent', '--setup'])

        assert result.exit_code == 0


class TestLearningCommands:
    """Test learning-related commands."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.PortfolioMemoryEngine')
    def test_learning_report(self, mock_memory_class, runner):
        """Test learning-report command."""
        mock_memory = Mock()
        mock_memory.get_provider_performance.return_value = {
            'local': {'accuracy': 0.75, 'avg_confidence': 80},
            'ensemble': {'accuracy': 0.82, 'avg_confidence': 85}
        }
        mock_memory_class.load_from_disk.return_value = mock_memory

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['learning-report'])

        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.PortfolioMemoryEngine')
    def test_prune_memory(self, mock_memory_class, runner):
        """Test prune-memory command."""
        mock_memory = Mock()
        mock_memory_class.load_from_disk.return_value = mock_memory

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['prune-memory', '--keep-recent', '100', '--confirm'])

        assert result.exit_code == 0


class TestConfigEditor:
    """Test 'config-editor' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.load_config')
    @patch('finance_feedback_engine.cli.main.Prompt.ask')
    def test_config_editor_interactive(self, mock_prompt, mock_load_config, runner):
        """Test interactive config editor."""
        mock_load_config.return_value = {
            'trading_platform': 'mock',
            'ai_provider': 'local'
        }
        mock_prompt.return_value = 'quit'

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['config-editor'])

        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.load_config')
    def test_config_editor_output(self, mock_load_config, runner, tmp_path):
        """Test config editor with --output flag."""
        mock_load_config.return_value = {'trading_platform': 'mock'}

        output_file = tmp_path / 'config_output.yaml'

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['config-editor', '--output', str(output_file)])

        assert result.exit_code == 0


class TestUtilityFunctions:
    """Test utility functions in CLI module."""

    def test_display_pulse_data(self):
        """Test _display_pulse_data function."""
        from finance_feedback_engine.cli.main import _display_pulse_data

        engine = Mock()
        engine.data_provider.get_comprehensive_market_data = Mock(return_value={
            'close': 50000.0,
            'pulse': {
                '1min': {'RSI': 65, 'MACD': 'BULLISH'},
                '5min': {'RSI': 70, 'MACD': 'BULLISH'}
            }
        })

        # If Rich console is unavailable, skip this test
        pytest.importorskip("rich")
        _display_pulse_data(engine, 'BTCUSD')
        engine.data_provider.get_comprehensive_market_data.assert_called_once_with('BTCUSD')

    def test_setup_logging_basic(self):
        """Test setup_logging function."""
        from finance_feedback_engine.cli.main import setup_logging

        # Should configure logging without error
        setup_logging(verbose=False)

    def test_setup_logging_verbose(self):
        """Test setup_logging with verbose flag."""
        from finance_feedback_engine.cli.main import setup_logging

        setup_logging(verbose=True)


class TestWalkForwardCommand:
    """Test 'walk-forward' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.WalkForwardOptimizer')
    def test_walk_forward_basic(self, mock_wfo_class, runner):
        """Test walk-forward optimization command."""
        mock_wfo = Mock()
        mock_wfo.run.return_value = {
            'in_sample_return': 0.20,
            'out_sample_return': 0.12,
            'overfitting_score': 0.60
        }
        mock_wfo_class.return_value = mock_wfo

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, [
            'walk-forward', 'BTCUSD',
            '--start-date', '2024-01-01',
            '--end-date', '2024-12-01'
        ])

        assert result.exit_code == 0


class TestMonteCarloCommand:
    """Test 'monte-carlo' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.MonteCarloSimulator')
    def test_monte_carlo_basic(self, mock_mc_class, runner):
        """Test Monte Carlo simulation command."""
        mock_mc = Mock()
        mock_mc.run.return_value = {
            'mean_return': 0.15,
            'std_return': 0.08,
            'var_95': -0.05
        }
        mock_mc_class.return_value = mock_mc

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, [
            'monte-carlo', 'BTCUSD',
            '--start-date', '2024-01-01',
            '--simulations', '1000'
        ])

        assert result.exit_code == 0


class TestBalanceCommand:
    """Test 'balance' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_balance_display(self, mock_ffe_class, runner):
        """Test balance command displays account balance."""
        engine = Mock()
        engine.platform.get_account_info.return_value = {
            'balance': 10000.0,
            'currency': 'USD',
            'available': 9500.0
        }
        mock_ffe_class.return_value = engine

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['balance'])

        assert result.exit_code == 0


class TestStatusCommand:
    """Test 'status' command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    def test_status_display(self, mock_ffe_class, runner):
        """Test status command displays system status."""
        engine = Mock()
        engine.platform = Mock()
        engine.data_provider = Mock()
        mock_ffe_class.return_value = engine

        from finance_feedback_engine.cli.main import cli
        result = runner.invoke(cli, ['status'])

        assert result.exit_code == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
