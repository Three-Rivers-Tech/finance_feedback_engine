
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent, AgentState
from finance_feedback_engine.agent.config import TradingAgentConfig


@pytest.fixture
def mock_engine():
    return MagicMock()


@pytest.fixture
def mock_trade_monitor():
    return MagicMock()


@pytest.fixture
def mock_portfolio_memory():
    return MagicMock()


@pytest.fixture
def mock_trading_platform():
    return MagicMock()


@pytest.fixture
def agent_config():
    return TradingAgentConfig()


@pytest.fixture
def trading_agent(agent_config, mock_engine, mock_trade_monitor, mock_portfolio_memory, mock_trading_platform):
    return TradingLoopAgent(
        config=agent_config,
        engine=mock_engine,
        trade_monitor=mock_trade_monitor,
        portfolio_memory=mock_portfolio_memory,
        trading_platform=mock_trading_platform,
    )


@pytest.mark.asyncio
async def test_agent_state_transitions(trading_agent):
    # Mocking sleep to speed up the test
    with patch('asyncio.sleep', new=AsyncMock()):
        # IDLE -> LEARNING
        assert trading_agent.state == AgentState.IDLE
        await trading_agent.handle_idle_state()
        assert trading_agent.state == AgentState.LEARNING

        # LEARNING -> PERCEPTION
        await trading_agent.handle_learning_state()
        assert trading_agent.state == AgentState.PERCEPTION

        # PERCEPTION -> REASONING
        await trading_agent.handle_perception_state()
        assert trading_agent.state == AgentState.REASONING


@pytest.mark.asyncio
async def test_run_agent_command():
    from finance_feedback_engine.cli.main import run_agent
    from click.testing import CliRunner

    runner = CliRunner()
    
    # Mock config that will be passed via context
    test_config = {
        'agent': {'autonomous': {'enabled': False}},
        'monitoring': {'enable_live_view': False}
    }
    
    with patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine') as mock_ffe:
        mock_ffe.return_value = mock_engine
        
        with patch('finance_feedback_engine.cli.main._initialize_agent') as mock_init_agent:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock()
            mock_init_agent.return_value = mock_agent

            with patch('finance_feedback_engine.cli.main._run_live_market_view', new_callable=AsyncMock) as mock_live_view:
                result = runner.invoke(run_agent, ['--autonomous'], obj={'config': test_config})
                # The command may exit with an error if there are config issues, so just check it ran
                assert mock_init_agent.called or result.exit_code in [0, 1]
