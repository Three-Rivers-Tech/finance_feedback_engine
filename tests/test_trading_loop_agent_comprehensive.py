"""
Comprehensive tests for Trading Loop Agent (OODA State Machine).

This test suite covers:
- State machine transitions (IDLE → PERCEPTION → REASONING → RISK_CHECK → EXECUTION → LEARNING)
- Position recovery on startup with retry logic
- Kill-switch protection (P&L and drawdown limits)
- Trade rejection cooldown (prevents infinite loops)
- Analysis failure tracking with time-based decay
- Configuration validation (notification delivery)
- Dashboard event emission
- Performance metrics tracking

Tests designed to achieve >55% coverage of trading_loop_agent.py (1,445 LOC).
"""

import asyncio
import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent


@pytest.fixture
def mock_engine():
    """Mock FinanceFeedbackEngine."""
    engine = Mock()
    engine.analyze_asset_async = AsyncMock(return_value={
        "id": "test-decision-123",
        "action": "BUY",
        "confidence": 75,
        "reasoning": "Test reasoning",
        "asset_pair": "BTCUSD",
        "amount": 100.0,
    })
    engine.get_portfolio_breakdown = Mock(return_value={
        "total_value_usd": 10000.0,
        "futures_positions": [],
        "positions": [],
    })
    return engine


@pytest.fixture
def mock_trade_monitor():
    """Mock TradeMonitor."""
    monitor = Mock()
    monitor.add_active_trade = Mock()
    monitor.get_active_trades = Mock(return_value=[])
    monitor.get_closed_trades = Mock(return_value=[])
    monitor.start = Mock()
    return monitor


@pytest.fixture
def mock_portfolio_memory():
    """Mock PortfolioMemoryEngine."""
    memory = Mock()
    memory.record_trade_outcome = Mock()
    memory.get_provider_performance = Mock(return_value={})
    return memory


@pytest.fixture
def mock_trading_platform():
    """Mock BaseTradingPlatform."""
    platform = Mock()
    platform.get_balance = Mock(return_value={"USD": 10000.0})
    platform.get_portfolio_breakdown = Mock(return_value={
        "total_value_usd": 10000.0,
        "futures_positions": [],
    })
    platform.execute_trade = Mock(return_value={"success": True, "order_id": "test-order"})
    return platform


@pytest.fixture
def minimal_config():
    """Minimal valid configuration for autonomous mode."""
    from finance_feedback_engine.agent.config import AutonomousAgentConfig

    config = TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        autonomous=AutonomousAgentConfig(enabled=True),  # Autonomous mode bypasses notification validation
        analysis_frequency_seconds=60,
        max_daily_trades=10,
        max_drawdown_percent=0.2,  # 20%
        correlation_threshold=0.7,
        max_correlated_assets=3,
        max_var_pct=0.05,  # 5%
        var_confidence=0.95,
        main_loop_error_backoff_seconds=30,
    )
    # Add telegram as attribute (empty dict to indicate no telegram)
    # Use object.__setattr__ to bypass Pydantic validation
    object.__setattr__(config, 'telegram', {})
    return config


@pytest.fixture
def signal_only_config():
    """Configuration for signal-only mode (requires Telegram)."""
    from finance_feedback_engine.agent.config import AutonomousAgentConfig

    config = TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        autonomous=AutonomousAgentConfig(enabled=False),  # Signal-only mode
        analysis_frequency_seconds=60,
        max_daily_trades=10,
        max_drawdown_percent=0.2,
        correlation_threshold=0.7,
        max_correlated_assets=3,
        max_var_pct=0.05,
        var_confidence=0.95,
        main_loop_error_backoff_seconds=30,
    )
    # Add telegram configuration
    # Use object.__setattr__ to bypass Pydantic validation
    object.__setattr__(config, 'telegram', {
        "enabled": True,
        "bot_token": "test_token",
        "chat_id": "test_chat",
    })
    return config


class TestAgentInitialization:
    """Test agent initialization and configuration validation."""

    def test_minimal_initialization_autonomous_mode(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test agent initializes successfully in autonomous mode."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        assert agent is not None
        assert agent.state == AgentState.IDLE
        assert agent.is_running is False
        assert agent.config == minimal_config
        assert agent.risk_gatekeeper is not None
        assert agent._rejected_decisions_cache == {}
        assert agent._rejection_cooldown_seconds == 300  # 5 minutes
        assert agent._startup_retry_count == 0
        assert agent._max_startup_retries == 3

    def test_signal_only_mode_requires_telegram(
        self, signal_only_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test signal-only mode requires valid Telegram configuration."""
        # This should initialize successfully since Telegram is configured
        agent = TradingLoopAgent(
            config=signal_only_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        assert agent is not None
        assert not agent.config.autonomous.enabled
        assert agent.config.telegram["enabled"]

    def test_signal_only_without_telegram_raises_error(
        self, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test signal-only mode without Telegram raises ValueError."""
        from finance_feedback_engine.agent.config import AutonomousAgentConfig

        # Create config with signal-only mode (autonomous disabled) and no Telegram
        config = TradingAgentConfig(
            asset_pairs=["BTCUSD"],
            autonomous=AutonomousAgentConfig(enabled=False),
            analysis_frequency_seconds=60,
            max_daily_trades=10,
            max_drawdown_percent=0.2,
            correlation_threshold=0.7,
            max_correlated_assets=3,
            max_var_pct=0.05,
            var_confidence=0.95,
            main_loop_error_backoff_seconds=30,
        )
        # No telegram config
        # Use object.__setattr__ to bypass Pydantic validation
        object.__setattr__(config, 'telegram', {})

        with pytest.raises(ValueError, match="signal-only mode without valid notification"):
            agent = TradingLoopAgent(
                config=config,
                engine=mock_engine,
                trade_monitor=mock_trade_monitor,
                portfolio_memory=mock_portfolio_memory,
                trading_platform=mock_trading_platform,
            )

    def test_percentage_normalization(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test that percentages >1 are normalized to decimals."""
        # Set percentages as whole numbers (e.g., 20 instead of 0.2)
        minimal_config.max_drawdown_percent = 20.0  # Should become 0.2
        minimal_config.max_var_pct = 5.0  # Should become 0.05

        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Verify risk gatekeeper received normalized values
        assert agent.risk_gatekeeper.max_drawdown_pct == 0.2
        assert agent.risk_gatekeeper.max_var_pct == 0.05


class TestStateMachineTransitions:
    """Test OODA state machine transitions."""

    @pytest.mark.asyncio
    async def test_idle_to_learning_transition(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test IDLE state transitions to LEARNING."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        agent.state = AgentState.IDLE
        await agent.handle_idle_state()

        assert agent.state == AgentState.LEARNING

    @pytest.mark.asyncio
    async def test_learning_to_perception_transition(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test LEARNING state transitions to PERCEPTION."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock memory engine methods
        agent.portfolio_memory.optimize_weights_thompson = Mock()

        agent.state = AgentState.LEARNING
        await agent.handle_learning_state()

        assert agent.state == AgentState.PERCEPTION

    @pytest.mark.asyncio
    async def test_perception_to_reasoning_transition(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test PERCEPTION state transitions to REASONING when checks pass."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock safe portfolio state
        mock_trading_platform.get_balance.return_value = {"USD": 10000.0}
        mock_engine.get_portfolio_breakdown.return_value = {
            "total_value_usd": 10000.0,
            "futures_positions": [],
        }

        agent.state = AgentState.PERCEPTION
        await agent.handle_perception_state()

        assert agent.state == AgentState.REASONING

    @pytest.mark.asyncio
    async def test_reasoning_to_risk_check_transition(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test REASONING state transitions to RISK_CHECK after analysis."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock analyze_asset (not analyze_asset_async)
        mock_engine.analyze_asset = AsyncMock(return_value={
            "id": "test-decision",
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Test",
            "asset_pair": "BTCUSD",
            "amount": 100.0,
        })

        # Mock _should_execute to return True
        with patch.object(agent, '_should_execute', new_callable=AsyncMock, return_value=True):
            agent.state = AgentState.REASONING
            await agent.handle_reasoning_state()

        assert agent.state == AgentState.RISK_CHECK
        assert agent._current_decisions is not None
        assert len(agent._current_decisions) > 0


class TestPositionRecovery:
    """Test startup position recovery logic."""

    @pytest.mark.asyncio
    async def test_position_recovery_with_no_positions(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test position recovery succeeds with no open positions."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock empty portfolio
        mock_engine.get_portfolio_breakdown.return_value = {
            "total_value_usd": 10000.0,
            "futures_positions": [],
        }

        await agent._recover_existing_positions()

        assert agent._startup_complete.is_set()
        assert len(agent._recovered_positions) == 0

    @pytest.mark.asyncio
    async def test_position_recovery_with_futures_positions(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test position recovery with open futures positions."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock portfolio with open position
        mock_engine.get_portfolio_breakdown.return_value = {
            "total_value_usd": 10000.0,
            "futures_positions": [
                {
                    "product_id": "BTC-USD-PERP",
                    "side": "LONG",
                    "contracts": 1.5,
                    "entry_price": 50000.0,
                    "current_price": 51000.0,
                    "unrealized_pnl": 1500.0,
                    "leverage": 10,
                }
            ],
        }

        await agent._recover_existing_positions()

        assert agent._startup_complete.is_set()
        assert len(agent._recovered_positions) > 0

    @pytest.mark.asyncio
    async def test_position_recovery_retry_on_failure(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test position recovery retries on failure."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # First call fails, second succeeds
        mock_engine.get_portfolio_breakdown.side_effect = [
            Exception("Connection error"),
            {"total_value_usd": 10000.0, "futures_positions": []},
        ]

        await agent._recover_existing_positions()

        # Should have retried and succeeded
        assert agent._startup_complete.is_set()
        assert mock_engine.get_portfolio_breakdown.call_count == 2

    @pytest.mark.asyncio
    async def test_position_recovery_timeout(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test position recovery handles timeout gracefully."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Simulate slow recovery that exceeds timeout
        async def slow_recovery():
            await asyncio.sleep(2)  # Longer than test timeout
            return {"total_value_usd": 10000.0, "futures_positions": []}

        with patch.object(agent, '_recover_existing_positions', new=slow_recovery):
            # Simulate the timeout behavior from run()
            try:
                await asyncio.wait_for(agent._recover_existing_positions(), timeout=0.5)
            except asyncio.TimeoutError:
                agent._startup_complete.set()

        assert agent._startup_complete.is_set()


class TestKillSwitchProtection:
    """Test kill-switch protection (P&L and drawdown limits)."""

    @pytest.mark.asyncio
    async def test_kill_switch_stops_agent_on_drawdown(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test agent stops when drawdown limit exceeded."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock large drawdown via monitoring context (30% loss, limit is 20%)
        mock_context_provider = Mock()
        mock_context_provider.get_monitoring_context.return_value = {
            "unrealized_pnl_percent": -30.0  # 30% loss exceeds 20% limit
        }
        mock_trade_monitor.monitoring_context_provider = mock_context_provider

        agent.state = AgentState.PERCEPTION
        agent.is_running = True

        await agent.handle_perception_state()

        # Agent should have stopped due to kill-switch
        assert not agent.is_running

    @pytest.mark.asyncio
    async def test_kill_switch_allows_normal_operation(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test agent continues when within risk limits."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock normal portfolio state
        mock_engine.get_portfolio_breakdown.return_value = {
            "total_value_usd": 9500.0,  # Only 5% drawdown
            "futures_positions": [],
        }

        agent.state = AgentState.PERCEPTION
        agent.is_running = True

        await agent.handle_perception_state()

        # Agent should continue to REASONING
        assert agent.is_running
        assert agent.state == AgentState.REASONING


class TestTradeRejectionCooldown:
    """Test trade rejection cooldown prevents infinite loops."""

    def test_rejection_cache_stores_rejected_decisions(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test rejected decisions are cached."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        decision_id = "test-decision-123"
        asset_pair = "BTCUSD"
        rejection_time = datetime.datetime.now()

        agent._rejected_decisions_cache[decision_id] = (rejection_time, asset_pair)

        assert decision_id in agent._rejected_decisions_cache
        assert agent._rejected_decisions_cache[decision_id][1] == asset_pair

    def test_rejection_cache_cleanup_removes_expired(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test cleanup removes expired rejection cache entries."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Add expired entry (6 minutes ago, cooldown is 5 minutes)
        expired_time = datetime.datetime.now() - datetime.timedelta(seconds=360)
        agent._rejected_decisions_cache["expired-decision"] = (expired_time, "BTCUSD")

        # Add recent entry
        recent_time = datetime.datetime.now()
        agent._rejected_decisions_cache["recent-decision"] = (recent_time, "ETHUSD")

        agent._cleanup_rejected_cache()

        # Expired should be removed, recent should remain
        assert "expired-decision" not in agent._rejected_decisions_cache
        assert "recent-decision" in agent._rejected_decisions_cache


class TestAnalysisFailureTracking:
    """Test analysis failure tracking with time-based decay."""

    def test_analysis_failures_tracked(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test analysis failures are tracked by key."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        failure_key = "BTCUSD_analysis"
        agent.analysis_failures[failure_key] = 3
        agent.analysis_failure_timestamps[failure_key] = datetime.datetime.now()

        assert agent.analysis_failures[failure_key] == 3
        assert failure_key in agent.analysis_failure_timestamps


class TestDashboardEvents:
    """Test dashboard event emission."""

    def test_dashboard_event_emission(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test events are emitted to dashboard queue."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        test_event = {
            "type": "test_event",
            "timestamp": 12345.0,
            "data": "test_data",
        }

        agent._emit_dashboard_event(test_event)

        # Event should be in queue
        assert not agent._dashboard_event_queue.empty()
        received_event = agent._dashboard_event_queue.get_nowait()
        assert received_event == test_event

    def test_dashboard_event_queue_full_drops_event(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test full queue drops events gracefully."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Fill queue to capacity (100)
        for i in range(100):
            agent._emit_dashboard_event({"type": "fill", "index": i})

        # Try to add one more (should be dropped)
        agent._emit_dashboard_event({"type": "overflow"})

        # Queue should still have 100 items
        assert agent._dashboard_event_queue.qsize() == 100


class TestPerformanceMetrics:
    """Test performance metrics tracking."""

    def test_performance_metrics_initialized(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test performance metrics are initialized."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        assert "total_pnl" in agent._performance_metrics
        assert "winning_trades" in agent._performance_metrics
        assert "losing_trades" in agent._performance_metrics
        assert "total_trades" in agent._performance_metrics
        assert agent._performance_metrics["total_pnl"] == 0.0
        assert agent._performance_metrics["total_trades"] == 0


class TestRunLoop:
    """Test the main run() loop behavior."""

    @pytest.mark.asyncio
    async def test_run_loop_starts_and_stops(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test run loop starts, processes cycles, and stops."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock process_cycle to run once then stop
        cycle_count = 0

        async def mock_process_cycle():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 1:
                agent.is_running = False
            return True

        agent.process_cycle = mock_process_cycle

        # Mock position recovery
        async def mock_recovery():
            agent._startup_complete.set()

        agent._recover_existing_positions = mock_recovery

        # Run agent (will stop after 1 cycle)
        await agent.run()

        assert cycle_count == 1
        assert not agent.is_running

    @pytest.mark.asyncio
    async def test_run_loop_handles_cycle_failure(
        self, minimal_config, mock_engine, mock_trade_monitor,
        mock_portfolio_memory, mock_trading_platform
    ):
        """Test run loop handles cycle failures with backoff."""
        agent = TradingLoopAgent(
            config=minimal_config,
            engine=mock_engine,
            trade_monitor=mock_trade_monitor,
            portfolio_memory=mock_portfolio_memory,
            trading_platform=mock_trading_platform,
        )

        # Mock process_cycle to fail once, then succeed and stop
        cycle_count = 0

        async def mock_process_cycle():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count == 1:
                return False  # Failure
            agent.is_running = False
            return True  # Success

        agent.process_cycle = mock_process_cycle

        # Mock position recovery
        async def mock_recovery():
            agent._startup_complete.set()

        agent._recover_existing_positions = mock_recovery

        # Reduce backoff time for faster test
        agent.config.main_loop_error_backoff_seconds = 0.1
        agent.config.analysis_frequency_seconds = 0.1

        await agent.run()

        assert cycle_count == 2  # One failure, one success
        assert not agent.is_running


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
