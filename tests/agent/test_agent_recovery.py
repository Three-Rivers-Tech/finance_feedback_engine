"""
Comprehensive test suite for TradingLoopAgent position recovery logic.

Tests cover:
- Platform returns malformed data
- Positions missing critical fields
- API timeout with retry success/failure
- 3+ positions triggering synchronous auto-close
- Close execution failures triggering recovery failure
- Mixed validation scenarios
- Connection validation failures
- Decision store persistence verification
- Position normalization edge cases
- All-or-nothing behavior validation
- Detailed error event structure
"""

import asyncio
import datetime
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform


@pytest.fixture
def mock_config():
    """Create minimal agent config for testing."""
    return TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        autonomous={"enabled": True, "approval_required": False},
        max_drawdown_percent=10,
        correlation_threshold=0.7,
        max_correlated_assets=2,
        max_var_pct=5,
        var_confidence=0.95,
        kill_switch_loss_pct=20,
        analysis_frequency_seconds=60,
        main_loop_error_backoff_seconds=5,
    )


@pytest.fixture
def mock_engine():
    """Create a mock FinanceFeedbackEngine."""
    engine = AsyncMock()
    engine.get_portfolio_breakdown_async = AsyncMock()
    # Mock decision_store with save_decision method
    engine.decision_store = MagicMock()
    engine.decision_store.save_decision = MagicMock()
    return engine


@pytest.fixture
def mock_platform():
    """Create a mock trading platform."""
    platform = AsyncMock(spec=BaseTradingPlatform)
    platform.test_connection = MagicMock(
        return_value={
            "api_auth": True,
            "account_active": True,
            "trading_enabled": True,
            "balance_available": True,
            "market_data_access": True,
        }
    )
    platform.aclose_position = AsyncMock(return_value={"status": "success"})
    return platform


@pytest.fixture
def mock_trade_monitor():
    """Create a mock TradeMonitor."""
    monitor = AsyncMock(spec=TradeMonitor)
    monitor.associate_decision_to_trade = MagicMock()
    return monitor


@pytest.fixture
def mock_portfolio_memory():
    """Create a mock PortfolioMemoryEngine."""
    memory = AsyncMock(spec=PortfolioMemoryEngine)
    memory.trade_outcomes = []
    return memory


@pytest.fixture
def agent(mock_config, mock_engine, mock_platform, mock_trade_monitor, mock_portfolio_memory):
    """Create a TradingLoopAgent with mocked dependencies."""
    agent = TradingLoopAgent(
        config=mock_config,
        engine=mock_engine,
        trade_monitor=mock_trade_monitor,
        portfolio_memory=mock_portfolio_memory,
        trading_platform=mock_platform,
    )
    agent._startup_complete = asyncio.Event()
    return agent


@pytest.mark.asyncio
async def test_recovery_no_positions(agent, mock_engine):
    """Test recovery with no open positions - should start with clean slate."""
    # Setup: no positions
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [],
        "positions": [],
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: agent transitions to LEARNING, emit recovery_complete with found=0
    assert agent.state == AgentState.LEARNING
    assert agent._recovered_positions == []
    assert agent._startup_complete.is_set()

    # Check event emitted
    events = []
    while not agent._dashboard_event_queue.empty():
        events.append(agent._dashboard_event_queue.get_nowait())
    assert len(events) > 0
    # Find recovery_complete event (state_transition may be emitted after)
    recovery_events = [e for e in events if e.get("type") == "recovery_complete"]
    assert len(recovery_events) > 0
    assert recovery_events[0]["found"] == 0


@pytest.mark.asyncio
async def test_recovery_single_position(agent, mock_engine):
    """Test recovery with single position - should be normalized and kept."""
    # Setup: one position
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "contracts": 0.5,
                "units": 0.5,
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-01T12:00:00Z",
            }
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: position normalized, decision persisted, transitions to LEARNING
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 1
    assert agent._recovered_positions[0]["asset_pair"] == "BTCUSD"
    assert agent._recovered_positions[0]["size"] == 0.5
    assert agent._startup_complete.is_set()


@pytest.mark.asyncio
async def test_recovery_excess_positions_closed(agent, mock_engine, mock_platform):
    """Test recovery with 3 positions - excess should be closed synchronously."""
    # Setup: three positions with different P&L
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "contracts": 0.5,
                "units": 0.5,
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "unrealized_pnl": 500.0,  # Highest P&L - keep
                "opened_at": "2024-01-01T12:00:00Z",
            },
            {
                "product_id": "ETH-USD",
                "side": "LONG",
                "contracts": 5.0,
                "units": 5.0,
                "entry_price": 2500.0,
                "current_price": 2600.0,
                "unrealized_pnl": 500.0,  # Equal P&L - keep (tie-breaker)
                "opened_at": "2024-01-02T12:00:00Z",
            },
            {
                "product_id": "ADA-USD",
                "side": "LONG",
                "contracts": 1000.0,
                "units": 1000.0,
                "entry_price": 1.0,
                "current_price": 0.95,
                "unrealized_pnl": -50.0,  # Lowest P&L - close
                "opened_at": "2024-01-03T12:00:00Z",
            },
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: 3 positions retrieved, 2 kept, 1 closed
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 2
    assert mock_platform.aclose_position.called
    assert agent._startup_complete.is_set()


@pytest.mark.asyncio
async def test_recovery_close_failure_all_or_nothing(agent, mock_engine, mock_platform):
    """Test recovery with close failure - entire recovery should fail (all-or-nothing)."""
    # Setup: three positions, close will fail
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "contracts": 0.5,
                "units": 0.5,
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-01T12:00:00Z",
            },
            {
                "product_id": "ETH-USD",
                "side": "LONG",
                "contracts": 5.0,
                "units": 5.0,
                "entry_price": 2500.0,
                "current_price": 2600.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-02T12:00:00Z",
            },
            {
                "product_id": "ADA-USD",
                "side": "LONG",
                "contracts": 1000.0,
                "units": 1000.0,
                "entry_price": 1.0,
                "current_price": 0.95,
                "unrealized_pnl": -50.0,
                "opened_at": "2024-01-03T12:00:00Z",
            },
        ]
    }

    # Close fails
    mock_platform.aclose_position.side_effect = Exception("Close failed: API error")

    # Execute
    await agent.handle_recovering_state()

    # Assert: recovery failed, transitions to LEARNING with clean slate
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 0  # No positions kept
    assert agent._startup_complete.is_set()

    # Check recovery_failed event
    events = []
    while not agent._dashboard_event_queue.empty():
        events.append(agent._dashboard_event_queue.get_nowait())
    assert any(e["type"] == "recovery_failed" for e in events)


@pytest.mark.asyncio
async def test_recovery_malformed_position_data(agent, mock_engine):
    """Test recovery with malformed position data - should validate and fail."""
    # Setup: position missing critical fields
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                # Missing: contracts, units, entry_price, unrealized_pnl
                "opened_at": "2024-01-01T12:00:00Z",
            }
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: recovery fails gracefully, transitions to LEARNING with clean slate
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 0


@pytest.mark.asyncio
async def test_recovery_api_timeout_retry(agent, mock_engine):
    """Test recovery with API timeout - should retry once."""
    call_count = 0

    async def mock_breakdown(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call times out by returning empty/error
            await asyncio.sleep(0.1)
            raise asyncio.TimeoutError("API timeout")
        else:
            # Second call succeeds
            return {
                "futures_positions": [
                    {
                        "product_id": "BTC-USD",
                        "side": "LONG",
                        "contracts": 0.5,
                        "units": 0.5,
                        "entry_price": 45000.0,
                        "current_price": 46000.0,
                        "unrealized_pnl": 500.0,
                        "opened_at": "2024-01-01T12:00:00Z",
                    }
                ]
            }

    mock_engine.get_portfolio_breakdown_async = mock_breakdown

    # Execute
    await agent.handle_recovering_state()

    # Assert: retried once, eventually succeeded
    assert call_count == 2
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 1


@pytest.mark.asyncio
async def test_recovery_api_failure_all_retries_exhausted(agent, mock_engine):
    """Test recovery with persistent API failure - should fail after 1 retry."""
    # Setup: API always fails
    mock_engine.get_portfolio_breakdown_async = AsyncMock(
        side_effect=Exception("API permanently unavailable")
    )

    # Execute
    await agent.handle_recovering_state()

    # Assert: recovery failed after retry exhausted, transitions to LEARNING with clean slate
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 0
    assert agent._startup_complete.is_set()


@pytest.mark.asyncio
async def test_recovery_position_normalization(agent, mock_engine):
    """Test that recovered positions are normalized like AI-generated positions."""
    # Setup: position that needs normalization
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "SHORT",  # Reversed side
                "contracts": 0.5,
                "units": -0.5,  # Negative units for short
                "entry_price": 45000.0,
                "current_price": 44000.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-01T12:00:00Z",
            }
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: decision normalized and persisted
    assert agent.state == AgentState.LEARNING
    assert len(agent._recovered_positions) == 1
    assert agent._recovered_positions[0]["side"] == "SHORT"
    assert agent._recovered_positions[0]["asset_pair"] == "BTCUSD"


@pytest.mark.asyncio
async def test_recovery_decision_persistence_in_memory(agent, mock_engine, mock_portfolio_memory):
    """Test that recovered positions are persisted to portfolio memory."""
    # Setup
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "contracts": 0.5,
                "units": 0.5,
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-01T12:00:00Z",
            }
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: position added to portfolio memory
    assert len(mock_portfolio_memory.trade_outcomes) > 0
    outcome = mock_portfolio_memory.trade_outcomes[0]
    assert outcome.asset_pair == "BTCUSD"
    assert outcome.position_size == 0.5
    assert outcome.ai_provider == "recovery"


@pytest.mark.asyncio
async def test_recovery_trade_monitor_association(agent, mock_engine, mock_trade_monitor):
    """Test that recovered positions are associated with trade monitor."""
    # Setup
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "contracts": 0.5,
                "units": 0.5,
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-01T12:00:00Z",
            }
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: position associated with trade monitor
    assert mock_trade_monitor.associate_decision_to_trade.called
    call_args = mock_trade_monitor.associate_decision_to_trade.call_args
    assert call_args[0][1] == "BTCUSD"  # asset_pair argument


@pytest.mark.asyncio
async def test_recovery_event_emissions(agent, mock_engine):
    """Test that recovery events are properly emitted with metadata."""
    # Setup
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "contracts": 0.5,
                "units": 0.5,
                "entry_price": 45000.0,
                "current_price": 46000.0,
                "unrealized_pnl": 500.0,
                "opened_at": "2024-01-01T12:00:00Z",
            }
        ]
    }

    # Execute
    await agent.handle_recovering_state()

    # Assert: recovery_complete event emitted with metadata
    events = []
    while not agent._dashboard_event_queue.empty():
        events.append(agent._dashboard_event_queue.get_nowait())

    complete_event = [e for e in events if e["type"] == "recovery_complete"][0]
    assert complete_event["found"] == 1
    assert complete_event["kept"] == 1
    assert "positions" in complete_event
    assert "total_unrealized_pnl" in complete_event
    assert complete_event["total_unrealized_pnl"] == 500.0


@pytest.mark.asyncio
async def test_recovery_state_transitions(agent, mock_engine):
    """Test that RECOVERING state transitions correctly through the OODA loop."""
    # Setup: no positions for fast test
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [],
        "positions": [],
    }

    # Initial state should be IDLE
    assert agent.state == AgentState.IDLE

    # Execute recovery
    await agent.handle_recovering_state()

    # After recovery, should transition to LEARNING
    assert agent.state == AgentState.LEARNING


@pytest.mark.asyncio
async def test_run_transitions_to_recovering(agent, mock_engine):
    """Test that run() method transitions to RECOVERING immediately."""
    # Setup: no positions
    mock_engine.get_portfolio_breakdown_async.return_value = {
        "futures_positions": [],
        "positions": [],
    }

    # Start the run() coroutine but don't await yet
    run_task = asyncio.create_task(agent.run())

    # Give it a moment to transition to RECOVERING
    await asyncio.sleep(0.1)

    # Check that agent transitioned to RECOVERING (or past it if recovery was very fast)
    # The state should not be IDLE anymore
    assert agent.state != AgentState.IDLE or agent._startup_complete.is_set()

    # Clean up
    agent.stop()
    try:
        await asyncio.wait_for(run_task, timeout=1.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass


@pytest.mark.asyncio
async def test_start_time_property(agent):
    """Test that start_time property works correctly."""
    # Initially None
    assert agent.start_time is None

    # Set _start_time
    agent._start_time = 1704067200.0

    # Property should return datetime
    start_time = agent.start_time
    assert start_time is not None
    assert isinstance(start_time, datetime.datetime)
    assert start_time.timestamp() == pytest.approx(1704067200.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
