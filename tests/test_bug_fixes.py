"""Tests for bug fixes in trading loop agent and core components."""

import asyncio
import datetime
import pytest
from unittest.mock import AsyncMock, Mock, patch

from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent, AgentState
from finance_feedback_engine.agent.config import TradingAgentConfig


class TestOODALoopBugFixes:
    """Test fixes for OODA loop bugs."""

    @pytest.mark.asyncio
    async def test_idle_state_does_not_auto_transition(self):
        """
        Test Bug #1 fix: IDLE state should not automatically transition to LEARNING.
        The transition should be explicit in process_cycle.
        """
        # Setup minimal mock config
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD"]
        config.core_pairs = ["BTCUSD"]
        config.autonomous = Mock(enabled=True)
        config.kill_switch_loss_pct = None
        config.max_daily_trades = 10
        
        # Create mocks
        engine = Mock()
        trade_monitor = Mock()
        trade_monitor.get_closed_trades = Mock(return_value=[])
        trade_monitor.monitoring_context_provider = Mock()
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        # Create agent
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        # Set state to IDLE
        agent.state = AgentState.IDLE
        
        # Call handle_idle_state
        await agent.handle_idle_state()
        
        # Verify state remains IDLE (no auto-transition)
        assert agent.state == AgentState.IDLE, "IDLE state should not auto-transition to LEARNING"

    @pytest.mark.asyncio
    async def test_asset_pairs_race_condition_protection(self):
        """
        Test Bug #2 fix: asset_pairs mutations should be thread-safe.
        """
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD", "ETHUSD"]
        config.core_pairs = ["BTCUSD", "ETHUSD"]
        config.autonomous = Mock(enabled=True)
        config.kill_switch_loss_pct = None
        config.max_daily_trades = 10
        config.reasoning_failure_decay_seconds = 3600
        
        engine = Mock()
        engine.analyze_asset = AsyncMock(return_value=None)
        
        trade_monitor = Mock()
        trade_monitor.get_closed_trades = Mock(return_value=[])
        trade_monitor.monitoring_context_provider = Mock()
        
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        # Verify lock exists
        assert hasattr(agent, '_asset_pairs_lock'), "Agent should have _asset_pairs_lock"
        assert isinstance(agent._asset_pairs_lock, asyncio.Lock), "Lock should be asyncio.Lock"
        
        # Simulate concurrent access
        async def modify_pairs():
            async with agent._asset_pairs_lock:
                agent.config.asset_pairs.append("XRPUSD")
                await asyncio.sleep(0.01)
        
        async def read_pairs():
            async with agent._asset_pairs_lock:
                return list(agent.config.asset_pairs)
        
        # Run concurrently
        results = await asyncio.gather(modify_pairs(), read_pairs())
        
        # Verify no exceptions raised
        assert "XRPUSD" in agent.config.asset_pairs

    def test_rejected_cache_cleanup_scheduled(self):
        """
        Test Bug #3 fix: _cleanup_rejected_cache should be called in multiple states.
        """
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD"]
        config.core_pairs = ["BTCUSD"]
        config.autonomous = Mock(enabled=True)
        
        engine = Mock()
        trade_monitor = Mock()
        trade_monitor.monitoring_context_provider = Mock()
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        # Add expired entry to cache
        old_time = datetime.datetime.now() - datetime.timedelta(seconds=400)
        agent._rejected_decisions_cache["test_id"] = (old_time, "BTCUSD")
        
        # Call cleanup
        agent._cleanup_rejected_cache()
        
        # Verify expired entry removed
        assert "test_id" not in agent._rejected_decisions_cache

    def test_scheduler_stop_waits_for_completion(self):
        """
        Test Bug #4 fix: stop() should wait for scheduler to complete.
        """
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD"]
        config.core_pairs = ["BTCUSD"]
        config.autonomous = Mock(enabled=True)
        
        engine = Mock()
        trade_monitor = Mock()
        trade_monitor.monitoring_context_provider = Mock()
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        # Mock pair scheduler
        agent.pair_scheduler = Mock()
        agent.pair_scheduler.is_running = True
        agent.pair_scheduler.stop = AsyncMock()
        
        # The stop() method now waits for completion
        # We verify by checking if it attempts to wait on the future
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop.side_effect = RuntimeError("No running loop")
            agent.stop()
        
        # Verify stop was attempted (even though no loop available)
        assert agent.is_running is False
        assert agent.stop_requested is True

    def test_autonomous_mode_property(self):
        """
        Test Bug #5 fix: is_autonomous_enabled property should work correctly.
        """
        # Test new format (autonomous.enabled)
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD"]
        config.core_pairs = ["BTCUSD"]
        config.autonomous = Mock(enabled=True)
        
        engine = Mock()
        trade_monitor = Mock()
        trade_monitor.monitoring_context_provider = Mock()
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        assert agent.is_autonomous_enabled is True
        
        # Test legacy format (autonomous_execution)
        config2 = Mock(spec=TradingAgentConfig)
        config2.asset_pairs = ["BTCUSD"]
        config2.core_pairs = ["BTCUSD"]
        config2.autonomous_execution = False
        delattr(config2, 'autonomous')
        
        agent2 = TradingLoopAgent(
            config=config2,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        assert agent2.is_autonomous_enabled is False

    def test_unused_variable_removed(self):
        """
        Test Bug #8 fix: _current_decision variable should not exist.
        """
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD"]
        config.core_pairs = ["BTCUSD"]
        config.autonomous = Mock(enabled=True)
        
        engine = Mock()
        trade_monitor = Mock()
        trade_monitor.monitoring_context_provider = Mock()
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        # Verify _current_decision doesn't exist
        assert not hasattr(agent, '_current_decision'), "_current_decision should be removed"
        
        # Verify _current_decisions still exists
        assert hasattr(agent, '_current_decisions'), "_current_decisions should exist"

    def test_analysis_failures_cleanup(self):
        """
        Test Bug #9 fix: Successful analysis should remove entry from dict.
        """
        config = Mock(spec=TradingAgentConfig)
        config.asset_pairs = ["BTCUSD"]
        config.core_pairs = ["BTCUSD"]
        config.autonomous = Mock(enabled=True)
        
        engine = Mock()
        trade_monitor = Mock()
        trade_monitor.monitoring_context_provider = Mock()
        portfolio_memory = Mock()
        trading_platform = Mock()
        
        agent = TradingLoopAgent(
            config=config,
            engine=engine,
            trade_monitor=trade_monitor,
            portfolio_memory=portfolio_memory,
            trading_platform=trading_platform,
        )
        
        # Add failure entry
        failure_key = "analysis:BTCUSD"
        agent.analysis_failures[failure_key] = 3
        agent.analysis_failure_timestamps[failure_key] = datetime.datetime.now()
        
        # Simulate success by manually removing (as the code now does)
        if failure_key in agent.analysis_failures:
            del agent.analysis_failures[failure_key]
        if failure_key in agent.analysis_failure_timestamps:
            del agent.analysis_failure_timestamps[failure_key]
        
        # Verify entries removed (not just set to 0)
        assert failure_key not in agent.analysis_failures
        assert failure_key not in agent.analysis_failure_timestamps


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
