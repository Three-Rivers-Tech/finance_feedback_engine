# tests/test_trading_loop_agent.py

import datetime
import logging
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
    trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {
        "latest_market_data_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "asset_type": "crypto",
        "timeframe": "intraday",
        "market_status": {"is_open": True, "session": "Regular"},
        "unrealized_pnl_percent": 0.0,
    }

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
    mock_dependencies["engine"].analyze_asset_async.assert_any_call("BTCUSD")
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


@pytest.mark.asyncio
async def test_loop_metrics_collected_for_cycle(trading_agent, mock_dependencies):
    """Loop metrics should include per-phase timings for each completed cycle."""
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "HOLD",
            "confidence": 80,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    metrics = trading_agent.get_loop_metrics()
    assert metrics["cycles_completed"] == 1
    assert metrics["last_cycle_phase_durations"]["PERCEPTION"] >= 0.0
    assert metrics["last_cycle_phase_durations"]["REASONING"] >= 0.0
    assert metrics["last_cycle_phase_durations"]["RISK_CHECK"] == 0.0
    assert metrics["last_cycle_phase_durations"]["EXECUTION"] == 0.0
    assert metrics["last_cycle_phase_durations"]["LEARNING"] == 0.0
    assert metrics["last_cycle_total_duration"] >= 0.0


@pytest.mark.asyncio
async def test_loop_metrics_accumulate_across_cycles(trading_agent, mock_dependencies):
    """Cumulative phase totals should increase over multiple cycles."""
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "HOLD",
            "confidence": 80,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()
    first_metrics = trading_agent.get_loop_metrics()

    await trading_agent.process_cycle()
    second_metrics = trading_agent.get_loop_metrics()

    assert second_metrics["cycles_completed"] == 2
    assert (
        second_metrics["cumulative_phase_durations"]["PERCEPTION"]
        >= first_metrics["cumulative_phase_durations"]["PERCEPTION"]
    )
    assert (
        second_metrics["cumulative_phase_durations"]["REASONING"]
        >= first_metrics["cumulative_phase_durations"]["REASONING"]
    )


@pytest.mark.asyncio
async def test_loop_metrics_logged_at_end_of_cycle(
    trading_agent, mock_dependencies, caplog
):
    """Phase durations should be logged at INFO at cycle completion."""
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "HOLD",
            "confidence": 80,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    with caplog.at_level(logging.INFO):
        await trading_agent.process_cycle()

    assert "Cycle phase durations (s):" in caplog.text


@pytest.mark.asyncio
async def test_hold_decision_without_id_gets_persisted_with_generated_id(trading_agent, mock_dependencies):
    """HOLD decisions without upstream IDs should still be persisted for observability."""
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "HOLD",
            "confidence": 80,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["asset_pair"] == "BTCUSD"
    assert saved_decision["action"] == "HOLD"
    assert saved_decision["execution_status"] == "hold"
    assert saved_decision["executed"] is False
    assert saved_decision.get("id")
    assert saved_decision.get("timestamp")


@pytest.mark.asyncio
async def test_filtered_decision_without_id_gets_persisted_with_generated_id(trading_agent, mock_dependencies):
    """Filtered BUY/SELL decisions without upstream IDs should still be persisted."""
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "BUY",
            "confidence": 10,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["asset_pair"] == "BTCUSD"
    assert saved_decision["action"] == "BUY"
    assert saved_decision["execution_status"] == "filtered"
    assert saved_decision["executed"] is False
    assert saved_decision["execution_result"]["reason_code"] == "LOW_CONFIDENCE"
    assert saved_decision.get("id")
    assert saved_decision.get("timestamp")


@pytest.mark.asyncio
async def test_empty_decision_payload_is_persisted_as_no_action(trading_agent, mock_dependencies):
    """Falsey no-action payloads should not disappear silently."""
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value={})
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["asset_pair"] == "BTCUSD"
    assert saved_decision["action"] == "HOLD"
    assert saved_decision["execution_status"] == "no_action"
    assert saved_decision["executed"] is False
    assert saved_decision["execution_result"]["reason_code"] == "NO_DECISION_PAYLOAD"
    assert saved_decision.get("id")
    assert saved_decision.get("timestamp")


@pytest.mark.asyncio
async def test_hold_decision_preserves_ensemble_metadata_and_logs_council_summary(trading_agent, mock_dependencies, caplog):
    """Debate/council summaries should be logged and preserved in persisted HOLD artifacts."""
    decision = {
        "action": "HOLD",
        "confidence": 64,
        "asset_pair": "BTCUSD",
        "reasoning": "Judge sees conflicting signals.",
        "ensemble_metadata": {
            "debate_mode": True,
            "role_decisions": {
                "bull": {"action": "BUY", "confidence": 72, "reasoning": "Momentum continuation.", "provider": "gemini"},
                "bear": {"action": "HOLD", "confidence": 58, "reasoning": "Overextended intraday.", "provider": "qwen"},
                "judge": {"action": "HOLD", "confidence": 64, "reasoning": "Conflicting signals.", "provider": "mistral"},
            },
            "debate_seats": {"bull": "gemini", "bear": "qwen", "judge": "mistral"},
            "providers_used": ["gemini", "qwen", "mistral"],
            "voting_strategy": "debate",
        },
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value=decision)
    trading_agent.is_running = True

    with caplog.at_level(logging.INFO):
        await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["ensemble_metadata"]["role_decisions"]["bull"]["action"] == "BUY"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "HOLD"
    assert "Council summary for BTCUSD" in caplog.text
    assert "bull=gemini:BUY/72" in caplog.text
    assert "bear=qwen:HOLD/58" in caplog.text
    assert "judge=mistral:HOLD/64" in caplog.text
