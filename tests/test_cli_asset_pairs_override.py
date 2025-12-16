"""Test --asset-pairs CLI override for run-agent command."""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
import yaml


@pytest.fixture
def test_config():
    """Create a minimal test configuration."""
    return {
        "agent": {
            "autonomous_execution": False,
            "asset_pairs": ["BTCUSD", "ETHUSD"],
            "watchlist": ["BTCUSD", "ETHUSD", "EURUSD"],
            "analysis_frequency_seconds": 300,
            "autonomous": {"enabled": False},
        },
        "trading_platform": {"type": "mock"},
        "decision_engine": {"ai_provider": "copilot"},
    }


@pytest.fixture
def temp_config_file(test_config):
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(test_config, f)
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.remove(config_path)


def test_asset_pairs_override_parsing():
    """Test that asset pairs are correctly parsed from CLI argument."""
    from finance_feedback_engine.utils.validation import standardize_asset_pair

    # Simulate the parsing logic
    asset_pairs_input = "BTCUSD,ETHUSD,EURUSD"
    parsed_asset_pairs = [
        standardize_asset_pair(pair.strip())
        for pair in asset_pairs_input.split(",")
        if pair.strip()
    ]

    assert parsed_asset_pairs == ["BTCUSD", "ETHUSD", "EURUSD"]


def test_asset_pairs_override_various_formats():
    """Test that various asset pair formats are standardized correctly."""
    from finance_feedback_engine.utils.validation import standardize_asset_pair

    # Test various input formats
    asset_pairs_input = "btc-usd, eth-usd, EURUSD, gbp_usd"
    parsed_asset_pairs = [
        standardize_asset_pair(pair.strip())
        for pair in asset_pairs_input.split(",")
        if pair.strip()
    ]

    assert parsed_asset_pairs == ["BTCUSD", "ETHUSD", "EURUSD", "GBPUSD"]


def test_asset_pairs_override_with_spaces():
    """Test that spaces are handled correctly."""
    from finance_feedback_engine.utils.validation import standardize_asset_pair

    asset_pairs_input = " BTCUSD , ETHUSD , EURUSD "
    parsed_asset_pairs = [
        standardize_asset_pair(pair.strip())
        for pair in asset_pairs_input.split(",")
        if pair.strip()
    ]

    assert parsed_asset_pairs == ["BTCUSD", "ETHUSD", "EURUSD"]


def test_asset_pairs_override_empty_entries():
    """Test that empty entries are filtered out."""
    from finance_feedback_engine.utils.validation import standardize_asset_pair

    asset_pairs_input = "BTCUSD,,ETHUSD,,,EURUSD"
    parsed_asset_pairs = [
        standardize_asset_pair(pair.strip())
        for pair in asset_pairs_input.split(",")
        if pair.strip()
    ]

    assert parsed_asset_pairs == ["BTCUSD", "ETHUSD", "EURUSD"]


@patch("finance_feedback_engine.cli.commands.agent.TradingLoopAgent")
@patch("finance_feedback_engine.cli.commands.agent.TradeMonitor")
def test_initialize_agent_with_override(mock_monitor, mock_agent_class):
    """Test that _initialize_agent correctly applies asset pairs override."""
    from finance_feedback_engine.cli.commands.agent import _initialize_agent

    # Mock config
    config = {
        "agent": {
            "autonomous_execution": False,
            "asset_pairs": ["BTCUSD", "ETHUSD"],
            "watchlist": ["BTCUSD", "ETHUSD", "EURUSD"],
            "autonomous": {"enabled": True},
        }
    }

    # Mock engine
    mock_engine = Mock()
    mock_platform = Mock()
    mock_engine.trading_platform = mock_platform
    mock_engine.memory_engine = Mock()
    mock_engine.trade_monitor = Mock()

    # Mock TradeMonitor
    mock_monitor_instance = Mock()
    mock_monitor.return_value = mock_monitor_instance
    mock_engine.enable_monitoring_integration = Mock()

    # Mock TradingLoopAgent
    mock_agent_instance = Mock()
    mock_agent_class.return_value = mock_agent_instance

    # Test with asset pairs override
    override = ["BTCUSD", "EURUSD", "GBPUSD"]
    agent = _initialize_agent(
        config=config,
        engine=mock_engine,
        take_profit=0.05,
        stop_loss=0.02,
        autonomous=False,
        asset_pairs_override=override,
    )

    # Verify the agent was created
    assert agent is not None

    # Verify TradingLoopAgent was called with overridden config
    assert mock_agent_class.called
    call_kwargs = mock_agent_class.call_args[1]
    agent_config = call_kwargs["config"]

    # Check that asset_pairs and watchlist were overridden
    assert agent_config.asset_pairs == override
    assert agent_config.watchlist == override


@patch("finance_feedback_engine.cli.commands.agent.TradingLoopAgent")
@patch("finance_feedback_engine.cli.commands.agent.TradeMonitor")
def test_initialize_agent_without_override(mock_monitor, mock_agent_class):
    """Test that _initialize_agent uses config values when no override is provided."""
    from finance_feedback_engine.cli.commands.agent import _initialize_agent

    # Mock config
    config = {
        "agent": {
            "autonomous_execution": False,
            "asset_pairs": ["BTCUSD", "ETHUSD"],
            "watchlist": ["BTCUSD", "ETHUSD", "EURUSD"],
            "autonomous": {"enabled": True},
        }
    }

    # Mock engine
    mock_engine = Mock()
    mock_platform = Mock()
    mock_engine.trading_platform = mock_platform
    mock_engine.memory_engine = Mock()
    mock_engine.trade_monitor = Mock()

    # Mock TradeMonitor
    mock_monitor_instance = Mock()
    mock_monitor.return_value = mock_monitor_instance
    mock_engine.enable_monitoring_integration = Mock()

    # Mock TradingLoopAgent
    mock_agent_instance = Mock()
    mock_agent_class.return_value = mock_agent_instance

    # Test without override
    agent = _initialize_agent(
        config=config,
        engine=mock_engine,
        take_profit=0.05,
        stop_loss=0.02,
        autonomous=False,
        asset_pairs_override=None,
    )

    # Verify the agent was created
    assert agent is not None

    # Verify TradingLoopAgent was called with original config
    assert mock_agent_class.called
    call_kwargs = mock_agent_class.call_args[1]
    agent_config = call_kwargs["config"]

    # Check that asset_pairs and watchlist match config
    assert agent_config.asset_pairs == ["BTCUSD", "ETHUSD"]
    assert agent_config.watchlist == ["BTCUSD", "ETHUSD", "EURUSD"]
