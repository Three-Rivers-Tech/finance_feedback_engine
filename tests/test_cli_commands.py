"""
Comprehensive CLI Command Tests

Tests all CLI commands to ensure they work correctly with various inputs,
handle errors gracefully, and provide expected outputs.
"""

import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch, MagicMock, mock_open
from finance_feedback_engine.cli.main import cli


# ============================================================================
# ANALYZE COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_analyze_basic_btcusd(mock_engine_class, test_config_path):
    """Test basic analyze command with BTCUSD."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_decision = {
        'id': 'test-123',
        'asset_pair': 'BTCUSD',
        'action': 'BUY',
        'confidence': 75,
        'reasoning': 'Test reasoning',
        'signal_only': False,
        'position_type': 'LONG',
        'entry_price': 50000.0,
        'recommended_position_size': 0.1
    }
    mock_engine.analyze_asset.return_value = mock_decision
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'analyze', 'BTCUSD'
    ])
    
    assert result.exit_code == 0
    assert 'BUY' in result.output or 'BTCUSD' in result.output


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_analyze_with_ensemble_provider(mock_engine_class, test_config_path):
    """Test analyze command with ensemble provider specified."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_decision = {
        'id': 'test-124',
        'asset_pair': 'ETHUSD',
        'action': 'SELL',
        'confidence': 65,
        'reasoning': 'Ensemble decision',
        'signal_only': False
    }
    mock_engine.analyze_asset.return_value = mock_decision
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'analyze', 'ETHUSD', '--provider', 'ensemble'
    ])
    
    assert result.exit_code == 0


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_analyze_invalid_asset_pair(mock_engine_class, test_config_path):
    """Test analyze command with invalid asset pair."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    mock_engine.analyze_asset.side_effect = ValueError("Invalid asset pair")
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'analyze', 'INVALID'
    ])
    
    # Should handle error gracefully
    assert result.exit_code != 0 or 'error' in result.output.lower()


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_analyze_signal_only_mode(mock_engine_class, test_config_path):
    """Test analyze command returns signal-only decision."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_decision = {
        'id': 'test-125',
        'asset_pair': 'BTCUSD',
        'action': 'BUY',
        'confidence': 80,
        'reasoning': 'Signal only',
        'signal_only': True,
        'recommended_position_size': None
    }
    mock_engine.analyze_asset.return_value = mock_decision
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'analyze', 'BTCUSD'
    ])
    
    assert result.exit_code == 0
    assert 'signal' in result.output.lower() or 'Signal' in result.output


# ============================================================================
# BALANCE COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_balance_display_mock_platform(mock_engine_class, test_config_path):
    """Test balance command displays balances from mock platform."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_balance = {
        'USD': 10000.50,
        'BTC': 0.5,
        'ETH': 2.0
    }
    mock_engine.get_balance.return_value = mock_balance
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'balance'
    ])
    
    assert result.exit_code == 0
    assert 'USD' in result.output or 'Balance' in result.output


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_balance_no_platform_error(mock_engine_class, test_config_path):
    """Test balance command handles platform errors gracefully."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    mock_engine.get_balance.side_effect = Exception("Platform unavailable")
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'balance'
    ])
    
    # Should handle error
    assert 'error' in result.output.lower() or result.exit_code != 0


# ============================================================================
# EXECUTE COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_execute_with_decision_id(mock_engine_class, test_config_path):
    """Test execute command with specific decision ID."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_result = {
        'success': True,
        'platform': 'mock',
        'order_id': 'order-123'
    }
    mock_engine.execute_decision.return_value = mock_result
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'execute', 'test-decision-123'
    ])
    
    assert result.exit_code == 0 or 'success' in result.output.lower()


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
@patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
def test_execute_interactive_selection(
    mock_store_class,
    mock_engine_class,
    test_config_path
):
    """Test execute command with interactive decision selection."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    
    mock_decisions = [
        {'id': 'dec-1', 'asset_pair': 'BTCUSD', 'action': 'BUY'},
        {'id': 'dec-2', 'asset_pair': 'ETHUSD', 'action': 'SELL'}
    ]
    mock_store.get_decision_history.return_value = mock_decisions
    
    # Simulate user selecting first decision
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'execute'
    ], input='1\n')
    
    # Should show decision list
    assert 'BTCUSD' in result.output or 'ETHUSD' in result.output


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_execute_signal_only_rejection(
    mock_engine_class,
    test_config_path
):
    """Test execute command rejects signal-only decisions."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    mock_engine.execute_decision.side_effect = ValueError(
        "Cannot execute signal-only decision"
    )
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'execute', 'signal-only-123'
    ])
    
    # Should reject signal-only
    assert result.exit_code != 0 or 'signal' in result.output.lower()


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_execute_invalid_id(mock_engine_class, test_config_path):
    """Test execute command with non-existent decision ID."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    mock_engine.execute_decision.side_effect = FileNotFoundError(
        "Decision not found"
    )
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'execute', 'nonexistent-id'
    ])
    
    assert result.exit_code != 0 or 'not found' in result.output.lower()


# ============================================================================
# BACKTEST COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_backtest_date_range(
    mock_engine_class,
    test_config_path
):
    """Test backtest command with date range."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_engine.backtest.return_value = {
        'total_return': 0.15,
        'sharpe_ratio': 1.5,
        'max_drawdown': 0.08
    }
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'backtest', 'BTCUSD',
        '--start', '2024-01-01',
        '--end', '2024-12-01'
    ])
    
    # Should complete successfully
    assert result.exit_code == 0 or 'return' in result.output.lower()


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_backtest_invalid_dates(mock_engine_class, test_config_path):
    """Test backtest command with invalid date format."""
    runner = CliRunner()
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'backtest', 'BTCUSD',
        '--start', 'invalid-date',
        '--end', '2024-12-01'
    ])
    
    # Should fail validation
    assert result.exit_code != 0


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_backtest_strategy_selection(
    mock_engine_class,
    test_config_path
):
    """Test backtest command with strategy parameter."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_engine.backtest.return_value = {'total_return': 0.20}
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'backtest', 'BTCUSD',
        '--start', '2024-01-01',
        '--end', '2024-12-01',
        '--strategy', 'sma_crossover'
    ])
    
    assert result.exit_code == 0


# ============================================================================
# CONFIG-EDITOR COMMAND TESTS
# ============================================================================

@patch('builtins.open', new_callable=mock_open, read_data='test: value\n')
@patch('click.prompt')
@patch('click.confirm')
@patch('yaml.safe_load')
@patch('yaml.safe_dump')
def test_config_editor_create_new(
    mock_dump,
    mock_load,
    mock_confirm,
    mock_prompt,
    mock_file,
    tmp_path
):
    """Test config-editor creating a new config file."""
    runner = CliRunner()
    
    output_path = tmp_path / "new_config.yaml"
    mock_load.return_value = {'test': 'value'}
    mock_confirm.return_value = True
    
    result = runner.invoke(cli, [
        'config-editor',
        '--output', str(output_path)
    ])
    
    # Should complete
    assert result.exit_code == 0 or mock_dump.called


@patch('builtins.open', new_callable=mock_open)
@patch('yaml.safe_load')
def test_config_editor_edit_existing(
    mock_load,
    mock_file,
    test_config_path
):
    """Test config-editor editing existing config."""
    runner = CliRunner()
    
    mock_load.return_value = {
        'trading_platform': 'mock',
        'alpha_vantage_api_key': 'demo'
    }
    
    result = runner.invoke(cli, [
        'config-editor',
        '--output', str(test_config_path)
    ], input='\n\n\n')  # Accept defaults
    
    # Should read config
    assert result.exit_code == 0 or mock_load.called


@patch('builtins.open', side_effect=Exception("Invalid YAML"))
def test_config_editor_invalid_yaml(mock_file):
    """Test config-editor handling invalid YAML."""
    runner = CliRunner()
    
    result = runner.invoke(cli, ['config-editor'])
    
    # Should handle error
    assert result.exit_code != 0 or 'error' in result.output.lower()


@patch('click.confirm')
def test_config_editor_cancel(mock_confirm):
    """Test config-editor cancellation."""
    runner = CliRunner()
    
    mock_confirm.return_value = False
    
    result = runner.invoke(cli, ['config-editor'])
    
    # User cancelled
    assert 'cancel' in result.output.lower() or result.exit_code == 0


# ============================================================================
# INSTALL-DEPS COMMAND TESTS
# ============================================================================

def test_install_deps_check_only():
    """Test install-deps in check-only mode."""
    runner = CliRunner()
    
    # Mock Path.exists to say requirements.txt exists
    # Mock requirements file content
    with patch('finance_feedback_engine.cli.main._parse_requirements_file') as mock_parse:
        mock_parse.return_value = ['click']
        
        # Mock pip list output with subprocess.run at the module level
        with patch('finance_feedback_engine.cli.main.subprocess.run') as mock_subprocess:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps([
                {'name': 'click', 'version': '8.1.0'}
            ])
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            result = runner.invoke(cli, ['install-deps'])
            
            # Should check dependencies
            assert result.exit_code == 0 or 'click' in result.output


def test_install_deps_auto_install():
    """Test install-deps with auto-install flag."""
    runner = CliRunner()
    
    # Mock requirements file content
    with patch('finance_feedback_engine.cli.main._parse_requirements_file') as mock_parse:
        mock_parse.return_value = ['click']
        
        # Mock pip list output with subprocess.run at the module level
        with patch('finance_feedback_engine.cli.main.subprocess.run') as mock_subprocess:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps([])
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result
            
            result = runner.invoke(cli, ['install-deps', '--auto-install'])
            
            # Should attempt installation
            assert result.exit_code == 0


@patch('pathlib.Path.exists')
def test_install_deps_missing_requirements(mock_exists):
    """Test install-deps when requirements.txt is missing."""
    runner = CliRunner()
    
    mock_exists.return_value = False
    
    result = runner.invoke(cli, ['install-deps'])
    
    # Should handle missing file
    assert 'requirements.txt' in result.output or result.exit_code != 0


# ============================================================================
# WIPE-DECISIONS COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
@patch('click.confirm')
def test_wipe_decisions_with_confirm(mock_confirm, mock_store_class):
    """Test wipe-decisions with confirmation."""
    runner = CliRunner()
    
    mock_confirm.return_value = True
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    
    result = runner.invoke(cli, ['wipe-decisions', '--confirm'])
    
    # Should wipe decisions
    assert result.exit_code == 0


@patch('click.confirm')
def test_wipe_decisions_cancel(mock_confirm):
    """Test wipe-decisions cancellation."""
    runner = CliRunner()
    
    mock_confirm.return_value = False
    
    result = runner.invoke(cli, ['wipe-decisions'])
    
    # Should cancel
    assert 'cancel' in result.output.lower() or 'abort' in result.output.lower()


# ============================================================================
# RUN-AGENT COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.agent.trading_loop_agent.TradingLoopAgent')
@patch('asyncio.get_event_loop')
def test_run_agent_basic_params(mock_loop, mock_agent_class, test_config_path):
    """Test run-agent command with basic parameters."""
    runner = CliRunner()
    
    mock_agent = Mock()
    mock_agent_class.return_value = mock_agent
    
    mock_event_loop = Mock()
    mock_loop.return_value = mock_event_loop
    mock_event_loop.run_until_complete.return_value = None
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'run-agent',
        '--take-profit', '0.05',
        '--stop-loss', '0.02'
    ])
    
    # Should attempt to start agent
    assert result.exit_code == 0 or mock_agent_class.called


@patch('finance_feedback_engine.agent.trading_loop_agent.TradingLoopAgent')
def test_run_agent_kill_switch_triggers(mock_agent_class, test_config_path):
    """Test run-agent with kill-switch parameters."""
    runner = CliRunner()
    
    mock_agent = Mock()
    mock_agent_class.return_value = mock_agent
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'run-agent',
        '--max-drawdown', '0.15'
    ])
    
    # Should set kill-switch
    assert result.exit_code == 0 or mock_agent_class.called


@patch('finance_feedback_engine.agent.trading_loop_agent.TradingLoopAgent')
@patch('asyncio.get_event_loop')
def test_run_agent_keyboard_interrupt(
    mock_loop,
    mock_agent_class,
    test_config_path
):
    """Test run-agent handles keyboard interrupt gracefully."""
    runner = CliRunner()
    
    mock_agent = Mock()
    mock_agent_class.return_value = mock_agent
    
    mock_event_loop = Mock()
    mock_loop.return_value = mock_event_loop
    mock_event_loop.run_until_complete.side_effect = KeyboardInterrupt()
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'run-agent'
    ])
    
    # Should handle interrupt
    assert 'stopped' in result.output.lower() or result.exit_code == 0


# ============================================================================
# MONITOR COMMAND TESTS
# ============================================================================

def test_monitor_start_deprecated():
    """Test monitor start command shows deprecation warning."""
    runner = CliRunner()
    
    result = runner.invoke(cli, ['monitor', 'start'])
    
    # Should show deprecation
    assert 'deprecated' in result.output.lower() or result.exit_code == 0


def test_monitor_status():
    """Test monitor status command."""
    runner = CliRunner()
    
    result = runner.invoke(cli, ['monitor', 'status'])
    
    # Should show status
    assert result.exit_code == 0 or 'monitor' in result.output.lower()


@patch('pathlib.Path.glob')
def test_monitor_metrics_display(mock_glob, tmp_path):
    """Test monitor metrics command displays metrics."""
    runner = CliRunner()
    
    # Mock metrics file
    metrics_file = tmp_path / "metrics.json"
    metrics_file.write_text(json.dumps({
        'total_trades': 10,
        'win_rate': 0.6
    }))
    
    mock_glob.return_value = [metrics_file]
    
    result = runner.invoke(cli, ['monitor', 'metrics'])
    
    # Should display metrics
    assert result.exit_code == 0


# ============================================================================
# DASHBOARD COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
@patch('finance_feedback_engine.cli.main.PortfolioDashboardAggregator')
def test_dashboard_multiplatform(
    mock_dashboard_class,
    mock_engine_class,
    test_config_path
):
    """Test dashboard command with multiple platforms."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    mock_dashboard = Mock()
    mock_dashboard_class.return_value = mock_dashboard
    mock_dashboard.get_aggregated_portfolio.return_value = {
        'total_value': 50000.0,
        'platforms': ['mock']
    }
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'dashboard'
    ])
    
    # Should display dashboard
    assert result.exit_code == 0


@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_dashboard_single_platform(mock_engine_class, test_config_path):
    """Test dashboard with single platform."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'dashboard'
    ])
    
    # Should work with single platform
    assert result.exit_code == 0 or 'portfolio' in result.output.lower()


# ============================================================================
# STATUS COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
def test_status_display(mock_engine_class, test_config_path):
    """Test status command displays engine status."""
    runner = CliRunner()
    
    mock_engine = Mock()
    mock_engine_class.return_value = mock_engine
    mock_engine.config = {'trading_platform': 'mock'}
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'status'
    ])
    
    # Should show status
    assert result.exit_code == 0 or 'status' in result.output.lower()


# ============================================================================
# HISTORY COMMAND TESTS
# ============================================================================

@patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
def test_history_basic(mock_store_class, test_config_path):
    """Test history command displays decision history."""
    runner = CliRunner()
    
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    mock_store.get_decision_history.return_value = [
        {'id': 'dec-1', 'asset_pair': 'BTCUSD', 'action': 'BUY'},
        {'id': 'dec-2', 'asset_pair': 'ETHUSD', 'action': 'SELL'}
    ]
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'history'
    ])
    
    # Should display history
    assert result.exit_code == 0
    assert 'BTCUSD' in result.output or 'dec-1' in result.output


@patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
def test_history_with_filters(mock_store_class, test_config_path):
    """Test history command with asset and limit filters."""
    runner = CliRunner()
    
    mock_store = Mock()
    mock_store_class.return_value = mock_store
    mock_store.get_decision_history.return_value = [
        {'id': 'dec-1', 'asset_pair': 'BTCUSD', 'action': 'BUY'}
    ]
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'history',
        '--asset', 'BTCUSD',
        '--limit', '5'
    ])
    
    # Should apply filters
    assert result.exit_code == 0


# ============================================================================
# RETRAIN-META-LEARNER COMMAND TESTS
# ============================================================================

@patch('train_meta_learner.run_training')
@patch('finance_feedback_engine.memory.portfolio_memory.PortfolioMemoryEngine')
def test_retrain_meta_learner_basic(
    mock_memory_class,
    mock_run_training,
    test_config_path
):
    """Test retrain-meta-learner command."""
    runner = CliRunner()
    
    mock_memory = Mock()
    mock_memory_class.return_value = mock_memory
    mock_run_training.return_value = None
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'retrain-meta-learner'
    ])
    
    # Should attempt retraining
    assert result.exit_code == 0 or mock_run_training.called


@patch('train_meta_learner.run_training')
def test_retrain_meta_learner_force(mock_train, test_config_path):
    """Test retrain-meta-learner with force flag."""
    runner = CliRunner()
    
    mock_train.return_value = {'accuracy': 0.90}
    
    result = runner.invoke(cli, [
        '--config', str(test_config_path),
        'retrain-meta-learner',
        '--force'
    ])
    
    # Should force retrain
    assert result.exit_code == 0
