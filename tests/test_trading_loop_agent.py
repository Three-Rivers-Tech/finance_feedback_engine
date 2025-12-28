# tests/test_trading_loop_agent.py

from unittest.mock import AsyncMock, MagicMock

import pytest

from finance_feedback_engine.agent.config import (
    AutonomousAgentConfig,
    TradingAgentConfig,
)
from finance_feedback_engine.agent.trading_loop_agent import (
    AgentState,
    TradingLoopAgent,
)


@pytest.fixture
def mock_dependencies():
    """Provides mock objects for TradingLoopAgent dependencies."""
    engine = MagicMock()
    engine.analyze_asset = AsyncMock()
    engine.execute_decision = MagicMock()

    trade_monitor = MagicMock()
    trade_monitor.monitoring_context_provider = MagicMock()
    trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {}

    portfolio_memory = MagicMock()
    trading_platform = MagicMock()
    trading_platform.get_portfolio_breakdown.return_value = {}

    return {
        "engine": engine,
        "trade_monitor": trade_monitor,
        "portfolio_memory": portfolio_memory,
        "trading_platform": trading_platform,
    }


@pytest.fixture
def agent_config():
    """Provides a default TradingAgentConfig."""
    return TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        analysis_frequency_seconds=1,  # Changed from 0.1 to 1 (integer)
        main_loop_error_backoff_seconds=1,  # Changed from 0.1 to 1 (integer)
        autonomous_execution=True,
        autonomous=AutonomousAgentConfig(enabled=True),  # Enable autonomous mode
        min_confidence_threshold=0.6,
    )


@pytest.fixture
def trading_agent(agent_config, mock_dependencies):
    """Provides a TradingLoopAgent instance with mocked dependencies."""
    agent = TradingLoopAgent(
        config=agent_config,
        engine=mock_dependencies["engine"],
        trade_monitor=mock_dependencies["trade_monitor"],
        portfolio_memory=mock_dependencies["portfolio_memory"],
        trading_platform=mock_dependencies["trading_platform"],
    )
    # Mark recovery as complete to not block tests
    agent._startup_complete.set()
    return agent


@pytest.mark.asyncio
async def test_agent_initial_state(trading_agent):
    """Test that the agent initializes in the IDLE state."""
    assert trading_agent.state == AgentState.IDLE
    assert trading_agent.is_running is False


@pytest.mark.asyncio
async def test_agent_process_cycle_no_action(trading_agent, mock_dependencies):
    """Test a full agent cycle where the AI decides to HOLD."""
    # Arrange
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "HOLD",
            "confidence": 80,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    # Act
    await trading_agent.process_cycle()

    # Assert
    # The cycle should go through all states and end at IDLE
    assert trading_agent.state == AgentState.IDLE
    # analyze_asset_async should be called in the REASONING state
    mock_dependencies["engine"].analyze_asset_async.assert_called_once_with("BTCUSD")
    # execute_decision should NOT be called for a HOLD action
    mock_dependencies["engine"].execute_decision.assert_not_called()
    # No decisions should be left in the current_decisions list
    assert not trading_agent._current_decisions


@pytest.mark.asyncio
async def test_agent_stop_method(trading_agent):
    """Test that the stop() method correctly stops the agent."""
    # Arrange
    trading_agent.is_running = True

    # Act
    trading_agent.stop()

    # Assert
    assert trading_agent.is_running is False
