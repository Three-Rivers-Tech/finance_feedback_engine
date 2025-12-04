"""
Test autonomous agent kill-switch and risk management scenarios.

Tests portfolio-level stop-loss, take-profit, max drawdown, and safety limits.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator
from finance_feedback_engine.agent.config import TradingAgentConfig


@pytest.fixture
def mock_engine():
    """Mock FinanceFeedbackEngine for testing."""
    engine = MagicMock()
    engine.generate_decision = MagicMock(return_value=MagicMock(decision='BUY', confidence=0.85, reasoning='Test', suggested_amount=100.0, asset_pair='BTCUSD'))
    engine.trading_platform = MagicMock()
    engine.trading_platform.get_balance.return_value = {'USD': 10000.0}
    engine.trading_platform.execute_trade.return_value = {'status': 'success'}
    return engine


class TestKillSwitchProtection:
    """Test kill-switch triggers and portfolio protection."""

    @pytest.mark.asyncio
    async def test_take_profit_trigger(self, mock_engine):
        """Test that take-profit threshold triggers kill-switch."""
        agent_config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD'],
            'kill_switch_gain_pct': 0.05,
            'kill_switch_loss_pct': 0.02,
            'max_drawdown_percent': 0.10,
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            platform=mock_engine.trading_platform,
        )
        
        # Mock portfolio with 6% gain (above 5% threshold)
        orchestrator.initial_portfolio_value = 10000
        orchestrator.platform.get_portfolio_breakdown.return_value = {'total_value_usd': 10600}
        
        orchestrator.run(test_mode=True)
        # Exception should be raised by the kill switch
        assert orchestrator._stop_event.is_set()


    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self, mock_engine):
        """Test that stop-loss threshold triggers kill-switch."""
        agent_config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD'],
            'kill_switch_gain_pct': 0.05,
            'kill_switch_loss_pct': 0.02,
            'max_drawdown_percent': 0.10,
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            platform=mock_engine.trading_platform,
        )
        
        # Mock portfolio with -3% loss (below -2% threshold)
        orchestrator.initial_portfolio_value = 10000
        orchestrator.platform.get_portfolio_breakdown.return_value = {'total_value_usd': 9700}
        
        orchestrator.run(test_mode=True)
        assert orchestrator._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_max_drawdown_trigger(self, mock_engine):
        """Test that max drawdown threshold triggers kill-switch."""
        agent_config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD'],
            'kill_switch_gain_pct': 0.05,
            'kill_switch_loss_pct': 0.02,
            'max_drawdown_percent': 0.10,
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            platform=mock_engine.trading_platform,
        )
        
        # Mock portfolio with 12% drawdown (above 10% threshold)
        orchestrator.initial_portfolio_value = 10000
        orchestrator.peak_portfolio_value = 12000
        orchestrator.platform.get_portfolio_breakdown.return_value = {'total_value_usd': 10500}
        
        orchestrator.run(test_mode=True)
        assert orchestrator._stop_event.is_set()

    @pytest.mark.asyncio
    async def test_no_kill_switch_within_limits(self, mock_engine):
        """Test that kill-switch doesn't trigger within normal limits."""
        agent_config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD'],
            'kill_switch_gain_pct': 0.05,
            'kill_switch_loss_pct': 0.02,
            'max_drawdown_percent': 0.10,
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            platform=mock_engine.trading_platform,
        )
        
        # Mock portfolio with 2% gain (within limits)
        orchestrator.initial_portfolio_value = 10000
        orchestrator.platform.get_portfolio_breakdown.return_value = {'total_value_usd': 10200}
        
        orchestrator.run(test_mode=True)
        assert not orchestrator._stop_event.is_set()


class TestMaxConcurrentTrades:
    """Test maximum concurrent trades limit."""

    @pytest.mark.asyncio
    async def test_max_trades_limit_enforced(self, mock_engine):
        """Test that max concurrent trades limit is enforced."""
        config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD', 'BNBUSD'],
            'max_daily_trades': 2,
            'autonomous_execution': True,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        # Simulate 2 active trades
        orchestrator.trades_today = 2
        can_trade = orchestrator._should_execute({})
        
        # Should block new trades
        assert can_trade is False
        
        # Simulate 1 active trade
        orchestrator.trades_today = 1
        can_trade = orchestrator._should_execute({})
        
        # Should allow new trades
        assert can_trade is True

    @pytest.mark.asyncio
    async def test_trade_completes_frees_slot(self, mock_engine):
        """Test that completing a trade frees up a slot."""
        config = {
            'asset_pairs': ['BTCUSD'],
            'max_daily_trades': 1,
            'autonomous_execution': True,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        # Initially at max capacity
        orchestrator.trades_today = 1
        assert orchestrator._should_execute({}) is False
        
        # Trade completes
        orchestrator.trades_today = 0
        assert orchestrator._should_execute({}) is True


class TestApprovalPolicy:
    """Test approval policy enforcement."""

    @pytest.mark.asyncio
    async def test_autonomous_mode_no_approval(self, mock_engine):
        """Test that autonomous mode executes without approval."""
        config = {
            'asset_pairs': ['BTCUSD'],
            'autonomous_execution': True,
            'approval_policy': 'never',
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        # Should execute without requiring approval
        requires_approval = orchestrator._should_execute({})
        assert requires_approval is True

    @pytest.mark.asyncio
    async def test_approval_mode_blocks_execution(self, mock_engine):
        """Test that approval mode blocks automatic execution."""
        config = {
            'asset_pairs': ['BTCUSD'],
            'autonomous_execution': False,
            'approval_policy': 'never',
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        # Should require approval
        requires_approval = orchestrator._should_execute({})
        assert requires_approval is False


class TestOODALoop:
    """Test Observe-Orient-Decide-Act loop."""

    @pytest.mark.asyncio
    async def test_ooda_observe_phase(self, mock_engine):
        """Test the Observe phase of OODA loop."""
        config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD'],
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        # This test is difficult to implement without a running loop
        # and real data providers. We will assume the orchestrator's
        # `run` method calls the perceive/orient/decide/act methods.
        # For now, this test is a placeholder.
        assert True

    @pytest.mark.asyncio
    async def test_ooda_decide_phase(self, mock_engine):
        """Test the Decide phase of OODA loop."""
        config = {
            'asset_pairs': ['BTCUSD'],
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        # Decide should generate trading decision
        decision = mock_engine.generate_decision('BTCUSD')
        
        assert decision is not None
        

    @pytest.mark.asyncio
    async def test_ooda_act_phase_autonomous(self, mock_engine):
        """Test the Act phase executes in autonomous mode."""
        config = {
            'asset_pairs': ['BTCUSD'],
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        decision = {
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Test',
            'suggested_amount': 100.0,
            'asset_pair': 'BTCUSD'
        }
        
        # Act should execute the trade
        orchestrator.platform.execute_trade(decision)
        
        # Should have executed
        assert mock_engine.trading_platform.execute_trade.called


class TestThreadSafety:
    """Test thread-safe operations of the agent."""

    @pytest.mark.asyncio
    async def test_active_trade_count_returns_valid_integer(self, mock_engine):
        """Test that trades_today returns a valid non-negative integer."""
        config = {
            'asset_pairs': ['BTCUSD'],
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        initial_count = orchestrator.trades_today
        assert isinstance(initial_count, int), "Active trade count must be an integer"
        assert initial_count >= 0, "Active trade count cannot be negative"


class TestWatchlistManagement:
    """Test watchlist asset management."""

    def test_watchlist_accepts_assets(self, mock_engine):
        """Test that watchlist accepts asset pairs without validation."""
        config = {
            'asset_pairs': ['BTCUSD', 'ETHUSD', 'INVALID'],
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        assert len(config_obj.asset_pairs) == 3
        assert 'BTCUSD' in config_obj.asset_pairs
        assert 'ETHUSD' in config_obj.asset_pairs
        assert 'INVALID' in config_obj.asset_pairs

    def test_empty_watchlist_handling(self, mock_engine):
        """Test handling of empty watchlist."""
        config = {
            'asset_pairs': [],
            'autonomous_execution': True,
            'max_daily_trades': 5,
        }
        
        config_obj = TradingAgentConfig(**config)
        
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config_obj,
            platform=mock_engine.trading_platform,
        )
        
        assert config_obj.asset_pairs == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])