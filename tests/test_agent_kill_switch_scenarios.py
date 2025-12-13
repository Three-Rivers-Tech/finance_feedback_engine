"""
Test autonomous agent kill-switch and risk management scenarios.

Tests portfolio-level stop-loss, take-profit, max drawdown, and safety limits.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
from finance_feedback_engine.agent.config import TradingAgentConfig


@pytest.fixture
def mock_dependencies():
    """Provides mock objects for TradingLoopAgent dependencies."""
    engine = MagicMock()
    trade_monitor = MagicMock()
    trade_monitor.monitoring_context_provider = MagicMock()
    portfolio_memory = MagicMock()
    trading_platform = MagicMock()
    return {
        "engine": engine,
        "trade_monitor": trade_monitor,
        "portfolio_memory": portfolio_memory,
        "trading_platform": trading_platform,
    }

@pytest.fixture
def agent_config():
    """Provides a default TradingAgentConfig for kill switch tests."""
    return TradingAgentConfig(
        asset_pairs=['BTCUSD'],
        kill_switch_loss_pct=2.0, # 2%
        autonomous_execution=True,
        max_daily_trades=5,
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
    agent._startup_complete.set()
    return agent


class TestKillSwitchProtection:
    """Test kill-switch triggers and portfolio protection."""

    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self, trading_agent, mock_dependencies):
        """Test that stop-loss threshold triggers kill-switch."""
        # Arrange: Mock portfolio with -3% loss (breaching the -2% threshold)
        mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {
            'unrealized_pnl_percent': -3.0
        }
        trading_agent.is_running = True
        original_stop_method = trading_agent.stop
        trading_agent.stop = MagicMock()

        # Act
        await trading_agent.handle_perception_state()

        # Assert
        trading_agent.stop.assert_called_once()
        trading_agent.stop = original_stop_method

    @pytest.mark.asyncio
    async def test_no_kill_switch_within_limits(self, trading_agent, mock_dependencies):
        """Test that kill-switch doesn't trigger within normal limits."""
        # Arrange: Mock portfolio with -1% loss (within the -2% threshold)
        mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {
            'unrealized_pnl_percent': -1.0
        }
        trading_agent.is_running = True
        original_stop_method = trading_agent.stop
        trading_agent.stop = MagicMock()

        # Act
        await trading_agent.handle_perception_state()

        # Assert
        trading_agent.stop.assert_not_called()
        trading_agent.stop = original_stop_method


class TestDailyTradeLimit:
    """Test maximum daily trades limit."""

    @pytest.mark.asyncio
    async def test_max_trades_limit_enforced(self, trading_agent):
        """Test that max daily trades limit is enforced."""
        # Arrange
        trading_agent.config.max_daily_trades = 2
        trading_agent.daily_trade_count = 2
        decision = {'confidence': 90, 'asset_pair': 'BTCUSD'}

        # Act
        can_trade = await trading_agent._should_execute(decision)

        # Assert
        assert can_trade is False

    @pytest.mark.asyncio
    async def test_trade_allowed_below_limit(self, trading_agent):
        """Test that a trade is allowed when below the daily limit."""
        # Arrange
        trading_agent.config.max_daily_trades = 2
        trading_agent.daily_trade_count = 1
        decision = {'confidence': 90}

        # Act
        can_trade = await trading_agent._should_execute(decision)

        # Assert
        assert can_trade is True

    @pytest.mark.asyncio
    async def test_reasoning_state_skips_trade_when_limit_reached(self, trading_agent, mock_dependencies):
        """
        Test that handle_reasoning_state does not collect decisions
        when the daily trade limit is reached.
        """
        # Arrange
        trading_agent.config.max_daily_trades = 2
        trading_agent.daily_trade_count = 2

        # Mock the engine to return an actionable decision
        mock_decision = {'action': 'BUY', 'confidence': 95, 'asset_pair': 'BTCUSD'}
        mock_dependencies["engine"].analyze_asset = AsyncMock(return_value=mock_decision)

        # Ensure the agent's decision list is empty
        trading_agent._current_decisions = []

        # Act: Run the reasoning state handler
        await trading_agent.handle_reasoning_state()

        # Assert: No decisions should have been collected for execution
        assert len(trading_agent._current_decisions) == 0
        mock_dependencies["engine"].analyze_asset.assert_called_once_with('BTCUSD')
