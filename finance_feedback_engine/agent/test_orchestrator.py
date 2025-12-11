import pytest
from unittest.mock import MagicMock, patch

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator, AgentState


@pytest.fixture
def mock_engine_and_platform():
    """Fixture to provide mocked engine and platform."""
    mock_engine = MagicMock()
    mock_platform = MagicMock()
    return mock_engine, mock_platform


@pytest.fixture
def agent_config():
    """Fixture to provide a default TradingAgentConfig."""
    return TradingAgentConfig()


def test_orchestrator_initialization(mock_engine_and_platform, agent_config):
    """Test that the TradingAgentOrchestrator initializes correctly."""
    mock_engine, mock_platform = mock_engine_and_platform

    orchestrator = TradingAgentOrchestrator(
        config=agent_config,
        engine=mock_engine,
        platform=mock_platform
    )

    assert orchestrator.config == agent_config
    assert orchestrator.engine == mock_engine
    assert orchestrator.platform == mock_platform
    assert orchestrator.state == AgentState.IDLE
    assert orchestrator._stop_event.is_set() is False


def test_orchestrator_start_and_stop(mock_engine_and_platform, agent_config):
    """Test the start and stop methods of the orchestrator."""
    mock_engine, mock_platform = mock_engine_and_platform
    orchestrator = TradingAgentOrchestrator(agent_config, mock_engine, mock_platform)

    # Mock the main loop to block until stop_event is set
    orchestrator._main_loop = MagicMock(side_effect=lambda: orchestrator._stop_event.wait())

    orchestrator.start()
    assert orchestrator.thread is not None
    assert orchestrator.thread.is_alive()
    assert orchestrator._stop_event.is_set() is False

    orchestrator.stop()
    orchestrator.thread.join(timeout=1)  # Wait for the thread to terminate
    assert not orchestrator.thread.is_alive()
    assert orchestrator._stop_event.is_set() is True


def test_orchestrator_run_calls_main_loop(mock_engine_and_platform, agent_config):
    """Verify that the run method correctly calls the main loop."""
    mock_engine, mock_platform = mock_engine_and_platform
    orchestrator = TradingAgentOrchestrator(agent_config, mock_engine, mock_platform)

    with patch.object(orchestrator, '_main_loop') as mock_main_loop:
        orchestrator.run()
        mock_main_loop.assert_called_once()
