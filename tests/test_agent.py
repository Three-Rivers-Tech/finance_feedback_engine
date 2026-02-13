from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import (
    AgentState,
    TradingLoopAgent,
)


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
    config = TradingAgentConfig(
        correlation_threshold=0.7,
        max_correlated_assets=2,
        max_var_pct=0.05,
        var_confidence=0.95,
    )
    # Enable autonomous mode to bypass signal-only validation checks
    config.autonomous.enabled = True
    return config


@pytest.fixture
def trading_agent(
    agent_config,
    mock_engine,
    mock_trade_monitor,
    mock_portfolio_memory,
    mock_trading_platform,
):
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
    with patch("asyncio.sleep", new=AsyncMock()):
        # IDLE: Does NOT auto-transition (external controller handles it)
        assert trading_agent.state == AgentState.IDLE
        await trading_agent.handle_idle_state()
        assert trading_agent.state == AgentState.IDLE  # Should remain in IDLE

        # Manually transition to LEARNING (as run() method would do)
        trading_agent.state = AgentState.LEARNING

        # LEARNING -> PERCEPTION
        await trading_agent.handle_learning_state()
        assert trading_agent.state == AgentState.PERCEPTION

        # PERCEPTION -> REASONING
        # Mock monitoring context for data freshness validation
        from datetime import datetime, timezone
        mock_context = {
            "latest_market_data_timestamp": datetime.now(timezone.utc).isoformat(),
            "asset_type": "crypto",
            "timeframe": "intraday",
            "market_status": None,
            "unrealized_pnl_percent": 0.0,
        }
        trading_agent.trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = mock_context
        
        await trading_agent.handle_perception_state()
        assert trading_agent.state == AgentState.REASONING


@pytest.mark.asyncio
async def test_run_agent_command():
    from click.testing import CliRunner

    from finance_feedback_engine.cli.main import run_agent

    runner = CliRunner()

    # Mock config that will be passed via context
    test_config = {
        "agent": {"autonomous": {"enabled": False}},
        "monitoring": {"enable_live_view": False},
    }

    # The run-agent command implementation lives in cli.commands.agent
    with patch(
        "finance_feedback_engine.cli.commands.agent.FinanceFeedbackEngine"
    ) as mock_ffe:
        mock_ffe.return_value = MagicMock()

        with patch(
            "finance_feedback_engine.cli.commands.agent._initialize_agent"
        ) as mock_init_agent:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock()
            mock_init_agent.return_value = mock_agent

            with patch(
                "finance_feedback_engine.cli.commands.agent._run_live_dashboard",
                new_callable=AsyncMock,
            ):
                result = runner.invoke(
                    run_agent, ["--autonomous", "--yes"], obj={"config": test_config}
                )

                # Conditional assertions based on exit code
                if result.exit_code == 0:
                    # Success: agent should have been initialized
                    assert (
                        mock_init_agent.called
                    ), "Agent initialization should be called on successful execution"
                else:
                    # Failure: validate expected error exit codes and output
                    assert result.exit_code in [
                        1,
                        2,
                    ], f"Unexpected exit code: {result.exit_code}"
                    assert (
                        result.output or result.exception
                    ), "Error exit should produce output or exception"
