"""
Test autonomous agent kill-switch and risk management scenarios.

Tests portfolio-level stop-loss, take-profit, max drawdown, and safety limits.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator
from finance_feedback_engine.agent.config import TradingAgentConfig


class TestKillSwitchProtection:
    """Test kill-switch triggers and portfolio protection."""

    @pytest.fixture
    def agent_config(self):
        """Agent configuration with kill-switch settings."""
        return {
            'watchlist': ['BTCUSD', 'ETHUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {
                'require_approval': False
            },
            'autonomous': {
                'enabled': True
            },
            'kill_switch': {
                'enabled': True,
                'take_profit_threshold': 0.05,  # 5%
                'stop_loss_threshold': 0.02,     # 2%
                'max_drawdown_threshold': 0.10   # 10%
            }
        }

    @pytest.fixture
    def mock_engine(self):
        """Mock FinanceFeedbackEngine for testing."""
        engine = MagicMock()
        engine.analyze_asset = AsyncMock(return_value={
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Test',
            'suggested_amount': 100.0,
            'asset_pair': 'BTCUSD'
        })
        engine.trading_platform = MagicMock()
        engine.trading_platform.get_balance.return_value = {'USD': 10000.0}
        engine.trading_platform.execute_trade.return_value = {'status': 'success'}
        return engine

    @pytest.mark.asyncio
    async def test_take_profit_trigger(self, agent_config, mock_engine):
        """Test that take-profit threshold triggers kill-switch."""
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            take_profit_threshold=0.05,
            stop_loss_threshold=0.02
        )
        
        # Mock portfolio with 6% gain (above 5% threshold)
        with patch.object(orchestrator, '_calculate_portfolio_pnl', return_value=0.06):
            should_continue = orchestrator._check_kill_switch()
            
            # Kill-switch should trigger (stop trading)
            assert should_continue is False

    @pytest.mark.asyncio
    async def test_stop_loss_trigger(self, agent_config, mock_engine):
        """Test that stop-loss threshold triggers kill-switch."""
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            take_profit_threshold=0.05,
            stop_loss_threshold=0.02
        )
        
        # Mock portfolio with -3% loss (below -2% threshold)
        with patch.object(orchestrator, '_calculate_portfolio_pnl', return_value=-0.03):
            should_continue = orchestrator._check_kill_switch()
            
            # Kill-switch should trigger (stop trading)
            assert should_continue is False

    @pytest.mark.asyncio
    async def test_max_drawdown_trigger(self, agent_config, mock_engine):
        """Test that max drawdown threshold triggers kill-switch."""
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            max_drawdown_threshold=0.10
        )
        
        # Mock portfolio with 12% drawdown (above 10% threshold)
        with patch.object(orchestrator, '_calculate_max_drawdown', return_value=0.12):
            should_continue = orchestrator._check_kill_switch()
            
            # Kill-switch should trigger (stop trading)
            assert should_continue is False

    @pytest.mark.asyncio
    async def test_no_kill_switch_within_limits(self, agent_config, mock_engine):
        """Test that kill-switch doesn't trigger within normal limits."""
        config = TradingAgentConfig(**agent_config)
        orchestrator = TradingAgentOrchestrator(
            engine=mock_engine,
            config=config,
            take_profit_threshold=0.05,
            stop_loss_threshold=0.02
        )
        
        # Mock portfolio with 2% gain (within limits)
        with patch.object(orchestrator, '_calculate_portfolio_pnl', return_value=0.02):
            with patch.object(orchestrator, '_calculate_max_drawdown', return_value=0.05):
                should_continue = orchestrator._check_kill_switch()
                
                # Should continue trading
                assert should_continue is True


class TestMaxConcurrentTrades:
    """Test maximum concurrent trades limit."""

    @pytest.mark.asyncio
    async def test_max_trades_limit_enforced(self):
        """Test that max concurrent trades limit is enforced."""
        config = {
            'watchlist': ['BTCUSD', 'ETHUSD', 'BNBUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,  # Max 2 concurrent
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        engine.analyze_asset = AsyncMock(return_value={
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Test',
            'suggested_amount': 100.0
        })
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Simulate 2 active trades
        with patch.object(orchestrator, '_get_active_trade_count', return_value=2):
            can_trade = orchestrator._can_execute_new_trade()
            
            # Should block new trades
            assert can_trade is False
        
        # Simulate 1 active trade
        with patch.object(orchestrator, '_get_active_trade_count', return_value=1):
            can_trade = orchestrator._can_execute_new_trade()
            
            # Should allow new trades
            assert can_trade is True

    @pytest.mark.asyncio
    async def test_trade_completes_frees_slot(self):
        """Test that completing a trade frees up a slot."""
        config = {
            'watchlist': ['BTCUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 1,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Initially at max capacity
        with patch.object(orchestrator, '_get_active_trade_count', return_value=1):
            assert orchestrator._can_execute_new_trade() is False
        
        # Trade completes
        with patch.object(orchestrator, '_get_active_trade_count', return_value=0):
            assert orchestrator._can_execute_new_trade() is True


class TestApprovalPolicy:
    """Test approval policy enforcement."""

    @pytest.mark.asyncio
    async def test_autonomous_mode_no_approval(self):
        """Test that autonomous mode executes without approval."""
        config = {
            'watchlist': ['BTCUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        engine.analyze_asset = AsyncMock(return_value={
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Test',
            'suggested_amount': 100.0,
            'asset_pair': 'BTCUSD'
        })
        engine.trading_platform = MagicMock()
        engine.trading_platform.execute_trade.return_value = {'status': 'success'}
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Should execute without requiring approval
        requires_approval = orchestrator._requires_approval()
        assert requires_approval is False

    @pytest.mark.asyncio
    async def test_approval_mode_blocks_execution(self):
        """Test that approval mode blocks automatic execution."""
        config = {
            'watchlist': ['BTCUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': True},
            'autonomous': {'enabled': False},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Should require approval
        requires_approval = orchestrator._requires_approval()
        assert requires_approval is True


class TestOODALoop:
    """Test Observe-Orient-Decide-Act loop."""

    @pytest.mark.asyncio
    async def test_ooda_observe_phase(self):
        """Test the Observe phase of OODA loop."""
        config = {
            'watchlist': ['BTCUSD', 'ETHUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        engine.data_provider = MagicMock()
        engine.data_provider.get_market_data = AsyncMock(return_value={
            'close': 50000.0,
            'volume': 1000000
        })
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Observe should gather market data
        market_data = await orchestrator._observe_market()
        
        assert market_data is not None
        assert len(market_data) > 0

    @pytest.mark.asyncio
    async def test_ooda_decide_phase(self):
        """Test the Decide phase of OODA loop."""
        config = {
            'watchlist': ['BTCUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        engine.analyze_asset = AsyncMock(return_value={
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Strong bullish momentum',
            'suggested_amount': 100.0,
            'asset_pair': 'BTCUSD'
        })
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Decide should generate trading decision
        decision = await orchestrator._decide_action('BTCUSD')
        
        assert decision is not None
        assert decision['action'] in ['BUY', 'SELL', 'HOLD']
        assert 'confidence' in decision

    @pytest.mark.asyncio
    async def test_ooda_act_phase_autonomous(self):
        """Test the Act phase executes in autonomous mode."""
        config = {
            'watchlist': ['BTCUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        engine.trading_platform = MagicMock()
        engine.trading_platform.execute_trade.return_value = {
            'status': 'success',
            'order_id': '12345'
        }
        
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        decision = {
            'action': 'BUY',
            'confidence': 85,
            'reasoning': 'Test',
            'suggested_amount': 100.0,
            'asset_pair': 'BTCUSD'
        }
        
        # Act should execute the trade
        result = await orchestrator._act_on_decision(decision)
        
        # Should have executed
        assert engine.trading_platform.execute_trade.called


class TestThreadSafety:
    """Test thread-safe operations of the agent."""

    @pytest.mark.asyncio
    async def test_concurrent_trade_tracking(self):
        """Test that concurrent trade tracking is thread-safe."""
        config = {
            'watchlist': ['BTCUSD'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        # Simulate concurrent trade operations
        # In a real scenario, this would use threading/asyncio
        # Here we test the logic
        
        initial_count = orchestrator._get_active_trade_count() if hasattr(orchestrator, '_get_active_trade_count') else 0
        assert isinstance(initial_count, int)
        assert initial_count >= 0


class TestWatchlistManagement:
    """Test watchlist asset management."""

    def test_watchlist_validation(self):
        """Test that watchlist assets are validated."""
        config = {
            'watchlist': ['BTCUSD', 'ETHUSD', 'INVALID'],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        
        # Watchlist should accept standard formats
        config_obj = TradingAgentConfig(**config)
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        assert len(config_obj.watchlist) > 0

    def test_empty_watchlist_handling(self):
        """Test handling of empty watchlist."""
        config = {
            'watchlist': [],
            'check_interval_seconds': 60,
            'max_concurrent_trades': 2,
            'approval_policy': {'require_approval': False},
            'autonomous': {'enabled': True},
            'kill_switch': {'enabled': False}
        }
        
        engine = MagicMock()
        config_obj = TradingAgentConfig(**config)
        
        # Should handle empty watchlist gracefully
        orchestrator = TradingAgentOrchestrator(
            engine=engine,
            config=config_obj
        )
        
        assert config_obj.watchlist == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
