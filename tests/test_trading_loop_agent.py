# tests/test_trading_loop_agent.py

import datetime
import logging
from unittest.mock import AsyncMock, MagicMock, Mock

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



def test_sync_trade_outcome_recorder_forwards_closed_positions_into_learning(trading_agent, mock_dependencies):
    recorder = MagicMock()
    recorder.update_positions.return_value = [
        {
            "decision_id": "decision-123",
            "product": "ETH-USD",
            "exit_price": "2100.5",
            "exit_time": "2026-03-23T20:00:00Z",
            "realized_pnl": "42.0",
        }
    ]
    mock_dependencies["engine"].trade_outcome_recorder = recorder
    mock_dependencies["engine"].record_trade_outcome.return_value = MagicMock(realized_pnl=42.0)

    trading_agent._sync_trade_outcome_recorder([])

    recorder.update_positions.assert_called_once_with([])
    mock_dependencies["engine"].record_trade_outcome.assert_called_once_with(
        "decision-123",
        exit_price=2100.5,
        exit_timestamp="2026-03-23T20:00:00Z",
    )



@pytest.mark.asyncio
async def test_perception_uses_fresh_default_crypto_context_even_with_stale_pulse(trading_agent, mock_dependencies):
    stale_context = {
        "latest_market_data_timestamp": "2024-01-01T00:00:00Z",
        "asset_type": "crypto",
        "timeframe": "intraday",
        "market_status": {"is_open": True, "session": "Regular"},
    }
    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = stale_context
    trading_agent.trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = stale_context

    # mimic provider-level fresh monitoring context contract after phase A1 merge logic
    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {
        **stale_context,
        "latest_market_data_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    trading_agent.trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = {
        **stale_context,
        "latest_market_data_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    trading_agent.state = AgentState.PERCEPTION

    await trading_agent.handle_perception_state()

    assert trading_agent.state == AgentState.REASONING


@pytest.mark.asyncio
async def test_perception_prefers_fresher_market_data_timestamp_for_crypto(trading_agent, mock_dependencies):
    stale_ts = "2024-01-01T00:00:00Z"
    fresh_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    context = {
        "latest_market_data_timestamp": stale_ts,
        "market_data_timestamp": fresh_ts,
        "asset_type": "crypto",
        "timeframe": "intraday",
        "market_status": {"is_open": True, "session": "Regular"},
        "unrealized_pnl_percent": 0.0,
    }
    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = context
    trading_agent.trade_monitor.monitoring_context_provider.get_monitoring_context.return_value = context

    trading_agent.state = AgentState.PERCEPTION

    await trading_agent.handle_perception_state()

    assert trading_agent.state == AgentState.REASONING


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
    mock_dependencies["engine"].analyze_asset_async.assert_any_call(
        "BTCUSD", include_sentiment=True, include_macro=False
    )
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
async def test_filtered_decision_persists_compact_decision_artifact(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "BUY",
            "confidence": 10,
            "asset_pair": "BTCUSD",
            "reasoning": "Weak signal.",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    artifact = saved_decision["decision_artifact"]
    assert artifact["asset_pair"] == "BTCUSD"
    assert artifact["final_action"] == "BUY"
    assert artifact["actionable"] is False
    assert artifact["filtered_reason_code"] == "LOW_CONFIDENCE"
    assert artifact["execution_attempted"] is False


@pytest.mark.asyncio
async def test_filtered_low_confidence_decision_sets_observability_fields(trading_agent, mock_dependencies):
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
    assert saved_decision["actionable"] is False
    assert saved_decision["filtered_reason_code"] == "LOW_CONFIDENCE"
    assert "Low confidence" in saved_decision["filtered_reason_text"]


@pytest.mark.asyncio
async def test_no_action_decision_persists_compact_decision_artifact(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value={})
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    artifact = saved_decision["decision_artifact"]
    assert artifact["asset_pair"] == "BTCUSD"
    assert artifact["final_action"] == "HOLD"
    assert artifact["actionable"] is False
    assert artifact["filtered_reason_code"] == "NO_DECISION_PAYLOAD"
    assert artifact["execution_attempted"] is False


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
async def test_fallback_hold_decision_preserves_origin_metadata(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "HOLD",
            "policy_action": "HOLD",
            "confidence": 50,
            "reasoning": "Provider fallback due to malformed response.",
            "decision_origin": "fallback",
            "hold_origin": "provider_fallback",
            "filtered_reason_code": "MALFORMED_PROVIDER_RESPONSE",
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["execution_status"] == "filtered"
    assert saved_decision["execution_result"]["reason_code"] == "MALFORMED_PROVIDER_RESPONSE"
    assert saved_decision["decision_origin"] == "fallback"
    assert saved_decision["hold_origin"] == "provider_fallback"
    assert saved_decision["filtered_reason_code"] == "MALFORMED_PROVIDER_RESPONSE"


@pytest.mark.asyncio
async def test_position_state_forced_hold_sets_forced_hold_metadata(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "HOLD",
            "policy_action": "HOLD",
            "confidence": 0,
            "reasoning": "[FORCED HOLD - Position State Violation] Cannot BUY when already LONG BTCUSD.",
            "position_state_violation": True,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["execution_status"] == "hold"
    assert saved_decision["hold_origin"] == "position_rule"
    assert saved_decision["hold_is_genuine"] is False


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
                "bull": {"action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 72, "reasoning": "Momentum continuation.", "provider": "gemini"},
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
    assert saved_decision["hold_origin"] == "model"
    assert saved_decision["hold_is_genuine"] is True
    assert "Council summary for BTCUSD" in caplog.text
    assert "bull=gemini:OPEN_SMALL_LONG/72" in caplog.text
    assert "bear=qwen:HOLD/58" in caplog.text
    assert "judge=mistral:HOLD/64" in caplog.text



def test_log_portfolio_risk_snapshot_summarizes_positions_and_balance(trading_agent, caplog):
    snapshot = {
        "platform_breakdowns": {
            "coinbase": {
                "futures_positions": [
                    {
                        "product_id": "BIP-20DEC30-CDE",
                        "side": "SHORT",
                        "number_of_contracts": "5",
                    },
                    {
                        "product_id": "ETP-20DEC30-CDE",
                        "side": "SHORT",
                        "number_of_contracts": "5",
                    },
                ],
                "futures_summary": {
                    "total_balance_usd": 749.04,
                    "buying_power": 232.31,
                    "unrealized_pnl": -109.8,
                    "initial_margin": 437.53,
                },
            }
        }
    }

    with caplog.at_level(logging.INFO):
        trading_agent._log_portfolio_risk_snapshot("Portfolio risk snapshot (decision loop)", snapshot)

    assert "Portfolio risk snapshot (decision loop) | managed_positions=2" in caplog.text
    assert "total_balance=$749.04" in caplog.text
    assert "buying_power=$232.31" in caplog.text
    assert "margin_usage=58.41%" in caplog.text
    assert "BIP-20DEC30-CDE" in caplog.text
    assert "ETP-20DEC30-CDE" in caplog.text


@pytest.mark.asyncio
async def test_process_cycle_logs_portfolio_risk_snapshot_for_managed_positions(trading_agent, mock_dependencies, caplog):
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [
                        {
                            "product_id": "BIP-20DEC30-CDE",
                            "side": "SHORT",
                            "number_of_contracts": "5",
                        }
                    ],
                    "futures_summary": {
                        "total_balance_usd": 749.04,
                        "buying_power": 232.31,
                        "unrealized_pnl": -98.35,
                        "initial_margin": 374.52,
                    },
                }
            }
        }
    )
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "OPEN_SMALL_SHORT",
            "confidence": 85,
            "asset_pair": "BTCUSD",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 65, "provider": "gemma2:9b"},
                    "bear": {"action": "OPEN_SMALL_SHORT", "confidence": 85, "provider": "llama3.1:8b"},
                    "judge": {"action": "OPEN_SMALL_SHORT", "confidence": 85, "provider": "deepseek-r1:8b"},
                }
            },
        }
    )
    trading_agent.is_running = True

    with caplog.at_level(logging.INFO):
        await trading_agent.process_cycle()

    assert "Portfolio risk snapshot (decision loop) | managed_positions=1" in caplog.text
    assert "managed_assets=['BIP20DEC30CDE', 'BTCUSD']" in caplog.text
    assert "managed_asset_scope=['BTCUSD']" in caplog.text
    assert "margin_usage=50.00%" in caplog.text
    assert "Skipping OPEN_SMALL_SHORT for BTCUSD: SHORT position already exists (duplicate-entry guard)." in caplog.text



def test_derisking_execution_metadata_uses_active_position_size(trading_agent):
    decision = {
        "asset_pair": "ETHUSD",
        "action": "CLOSE_SHORT",
        "policy_action": "CLOSE_SHORT",
        "entry_price": 2127.0,
    }
    monitoring_context = {
        "active_positions": {
            "futures": [
                {
                    "product_id": "ETP-20DEC30-CDE",
                    "side": "SHORT",
                    "number_of_contracts": "5",
                    "current_price": "2127.0",
                }
            ]
        }
    }

    trading_agent._apply_derisking_execution_metadata(decision, monitoring_context)

    assert decision["has_existing_position"] is True
    assert decision["current_position_size"] == 5.0
    assert decision["legacy_action_compatibility"] == "BUY"
    assert decision["recommended_position_size"] == 5.0
    assert decision["suggested_amount"] == 10635.0




@pytest.mark.asyncio
async def test_process_cycle_passes_monitoring_macro_flags_to_engine_analysis(trading_agent, mock_dependencies):
    mock_dependencies["engine"].config = {
        "monitoring": {
            "include_sentiment": True,
            "include_macro": True,
        }
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "HOLD",
            "policy_action": "HOLD",
            "confidence": 55,
            "asset_pair": "BTCUSD",
        }
    )
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={"platform_breakdowns": {}}
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    mock_dependencies["engine"].analyze_asset_async.assert_any_call(
        "BTCUSD", include_sentiment=True, include_macro=True
    )


@pytest.mark.asyncio
async def test_risk_check_persists_invalid_policy_action_distinctly(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-invalid",
        "action": "ADD_SMALL_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "structural_action_validity": "invalid",
        "invalid_action_reason": "action ADD_SMALL_LONG is structurally invalid for position_state=flat",
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(True, "approved"))
    trading_agent._check_performance_based_risks = Mock(return_value=(True, "ok"))

    await trading_agent.handle_risk_check_state()

    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert saved_decision["execution_status"] == "filtered"
    assert saved_decision["execution_result"]["reason_code"] == "INVALID_POLICY_ACTION"
    assert saved_decision["execution_result"]["error"] == "action ADD_SMALL_LONG is structurally invalid for position_state=flat"


@pytest.mark.asyncio
async def test_risk_check_persists_vetoed_policy_action_distinctly(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-vetoed",
        "action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "structural_action_validity": "valid",
        "risk_vetoed": True,
        "risk_veto_reason": "Trade rejected: drawdown exceeds threshold",
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(False, "Trade rejected: drawdown exceeds threshold"))

    await trading_agent.handle_risk_check_state()

    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert saved_decision["execution_status"] == "filtered"
    assert saved_decision["execution_result"]["reason_code"] == "RISK_VETO"
    assert saved_decision["execution_result"]["error"] == "Trade rejected: drawdown exceeds threshold"


@pytest.mark.asyncio
async def test_risk_check_keeps_executable_policy_action_flowing_normally(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-valid",
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "entry_price": 100.0,
        "relevant_balance": {"USD": 1000.0},
        "balance_source": "test",
        "structural_action_validity": "valid",
        "risk_vetoed": False,
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(True, "approved"))
    trading_agent._check_performance_based_risks = Mock(return_value=(True, "ok"))
    mock_dependencies["engine"].position_sizing_calculator.calculate_position_sizing_params.return_value = {
        "recommended_position_size": 1.25
    }

    await trading_agent.handle_risk_check_state()

    async with trading_agent._current_decisions_lock:
        assert len(trading_agent._current_decisions) == 1
        assert trading_agent._current_decisions[0]["recommended_position_size"] == 1.25
    assert mock_dependencies["engine"].decision_store.update_decision.call_count == 0



@pytest.mark.asyncio
async def test_risk_check_rejected_policy_action_stays_distinct_from_veto(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-rejected",
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "structural_action_validity": "valid",
        "risk_vetoed": False,
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(False, "Trade rejected: temporal constraints"))

    await trading_agent.handle_risk_check_state()

    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert saved_decision["execution_result"]["reason_code"] == "RISK_REJECTED"
    assert saved_decision.get("risk_vetoed") is False
    assert saved_decision.get("risk_veto_reason") is None
    assert saved_decision.get("gatekeeper_message") == "Trade rejected: temporal constraints"


@pytest.mark.asyncio
async def test_classify_action_execution_outcome_rejects_hold_with_risk_reason(trading_agent):
    should_execute, outcome_kind, outcome_code, outcome_message = trading_agent._classify_action_execution_outcome(
        {"action": "HOLD"},
        risk_reason="Trade rejected: temporal constraints",
    )

    assert should_execute is False
    assert outcome_kind == "rejected"
    assert outcome_code == "RISK_REJECTED"
    assert outcome_message == "Trade rejected: temporal constraints"



def test_classify_action_execution_outcome_prefers_invalid_over_veto(trading_agent):
    should_execute, outcome_kind, outcome_code, outcome_message = trading_agent._classify_action_execution_outcome(
        {
            "action": "ADD_SMALL_LONG",
            "structural_action_validity": "invalid",
            "invalid_action_reason": "action ADD_SMALL_LONG is structurally invalid for position_state=flat",
            "risk_vetoed": True,
            "risk_veto_reason": "Trade rejected: drawdown exceeds threshold",
        }
    )

    assert should_execute is False
    assert outcome_kind == "invalid"
    assert outcome_code == "INVALID_POLICY_ACTION"
    assert outcome_message == "action ADD_SMALL_LONG is structurally invalid for position_state=flat"



@pytest.mark.asyncio
async def test_risk_check_updates_canonical_control_outcome_for_vetoed_decision(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-vetoed-package",
        "action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "structural_action_validity": "valid",
        "risk_vetoed": True,
        "risk_veto_reason": "Trade rejected: drawdown exceeds threshold",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(False, "Trade rejected: drawdown exceeds threshold"))

    await trading_agent.handle_risk_check_state()

    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert saved_decision["control_outcome"]["status"] == "vetoed"
    assert saved_decision["control_outcome"]["reason_code"] == "RISK_VETO"
    assert saved_decision["policy_package"]["control_outcome"] == saved_decision["control_outcome"]


@pytest.mark.asyncio
async def test_risk_check_updates_canonical_control_outcome_for_executable_decision(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-executable-package",
        "action": "OPEN_SMALL_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "entry_price": 100.0,
        "relevant_balance": {"USD": 1000.0},
        "balance_source": "test",
        "structural_action_validity": "valid",
        "risk_vetoed": False,
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(True, "approved"))
    trading_agent._check_performance_based_risks = Mock(return_value=(True, "ok"))
    mock_dependencies["engine"].position_sizing_calculator.calculate_position_sizing_params.return_value = {
        "recommended_position_size": 1.25
    }

    await trading_agent.handle_risk_check_state()

    async with trading_agent._current_decisions_lock:
        kept = trading_agent._current_decisions[0]
        assert kept["control_outcome"]["status"] == "proposed"
        assert kept["policy_package"]["control_outcome"] == kept["control_outcome"]



@pytest.mark.asyncio
async def test_execution_state_requires_engine_async_entrypoint(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-missing-async-entrypoint",
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION

    assert hasattr(trading_agent.engine, "execute_decision_async")
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={
        "success": True,
        "message": "order placed",
        "order_id": "abc123",
    })

    await trading_agent.handle_execution_state()

    trading_agent.engine.execute_decision_async.assert_awaited_once_with("decision-missing-async-entrypoint")
    assert decision["execution_status"] == "executed"


@pytest.mark.asyncio
async def test_execution_state_registers_pending_order_from_nested_success_response(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-order-tracking",
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "entry_price": 50000.0,
        "recommended_position_size": 0.25,
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION
    trading_agent.engine.order_status_worker = MagicMock()
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={
        "success": True,
        "platform": "coinbase_advanced",
        "response": {"success": True, "success_response": {"order_id": "nested-abc123"}},
    })

    await trading_agent.handle_execution_state()

    trading_agent.engine.order_status_worker.add_pending_order.assert_called_once_with(
        order_id="nested-abc123",
        decision_id="decision-order-tracking",
        asset_pair="BTCUSD",
        platform="coinbase_advanced",
        action="BUY",
        size=0.25,
        entry_price=50000.0,
    )
    assert decision["execution_result"]["order_id"] == "nested-abc123"
    assert decision["execution_status"] == "executed"
    assert decision["executed"] is True
    assert trading_agent.daily_trade_count == 1


@pytest.mark.asyncio
async def test_execution_state_updates_canonical_control_outcome_on_success(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-exec-success",
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={"success": True, "message": "order placed", "order_id": "abc123"})

    await trading_agent.handle_execution_state()

    assert decision["execution_status"] == "executed"
    assert decision["control_outcome"]["status"] == "executed"
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_package"]["control_outcome"] is not decision["control_outcome"]


@pytest.mark.asyncio
async def test_execution_state_updates_canonical_control_outcome_on_failure(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-exec-fail",
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={"success": False, "reason_code": "EXECUTION_FAILED", "error": "broker reject"})

    await trading_agent.handle_execution_state()

    assert decision["execution_status"] == "execution_failed"
    assert decision["control_outcome"]["status"] == "rejected"
    assert decision["control_outcome"]["reason_code"] == "EXECUTION_FAILED"
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_package"]["control_outcome"] is not decision["control_outcome"]





@pytest.mark.asyncio
async def test_execution_state_updates_policy_trace_control_outcome_on_success(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-exec-trace-success",
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
        "policy_trace": {
            "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
            "decision_envelope": {"action": "OPEN_SMALL_LONG", "version": 1},
            "decision_metadata": {"decision_id": "decision-exec-trace-success"},
            "trace_version": 1,
        },
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={"success": True, "message": "order placed", "order_id": "abc123"})

    await trading_agent.handle_execution_state()

    assert decision["execution_status"] == "executed"
    assert decision["control_outcome"]["status"] == "executed"
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_trace"]["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_trace"]["policy_package"]["control_outcome"] is not decision["control_outcome"]


@pytest.mark.asyncio
async def test_execution_state_updates_policy_trace_control_outcome_on_failure(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-exec-trace-fail",
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
        "policy_trace": {
            "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
            "decision_envelope": {"action": "OPEN_SMALL_LONG", "version": 1},
            "decision_metadata": {"decision_id": "decision-exec-trace-fail"},
            "trace_version": 1,
        },
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={"success": False, "reason_code": "EXECUTION_FAILED", "error": "broker reject"})

    await trading_agent.handle_execution_state()

    assert decision["execution_status"] == "execution_failed"
    assert decision["control_outcome"]["status"] == "rejected"
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_trace"]["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_trace"]["policy_package"]["control_outcome"] is not decision["control_outcome"]


@pytest.mark.asyncio
async def test_execution_state_policy_package_control_outcome_copy_stays_isolated(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-copy-isolated",
        "action": "OPEN_SMALL_LONG",
        "asset_pair": "BTCUSD",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={"success": True, "message": "order placed", "order_id": "abc123"})

    await trading_agent.handle_execution_state()

    decision["control_outcome"]["message"] = "mutated later"
    assert decision["policy_package"]["control_outcome"]["message"] == "order placed"


@pytest.mark.asyncio
async def test_risk_check_policy_package_control_outcome_copy_stays_isolated(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-risk-copy-isolated",
        "action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "asset_pair": "BTCUSD",
        "structural_action_validity": "valid",
        "risk_vetoed": True,
        "risk_veto_reason": "Trade rejected: drawdown exceeds threshold",
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(False, "Trade rejected: drawdown exceeds threshold"))

    await trading_agent.handle_risk_check_state()

    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    saved_decision["control_outcome"]["message"] = "mutated later"
    assert saved_decision["policy_package"]["control_outcome"]["message"] == "Trade rejected: drawdown exceeds threshold"



def test_mark_decision_not_executed_updates_policy_trace_control_outcome(trading_agent):
    decision = {
        "id": "decision-123",
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "structural_action_validity": "valid",
        "risk_vetoed": False,
        "policy_package": {
            "policy_state": {"position_state": "flat", "version": 1},
            "action_context": {"structural_action_validity": "valid", "version": 1},
            "policy_sizing_intent": None,
            "provider_translation_result": None,
            "control_outcome": {"status": "proposed", "version": 1},
            "version": 1,
        },
        "policy_trace": {
            "policy_package": {
                "policy_state": {"position_state": "flat", "version": 1},
                "action_context": {"structural_action_validity": "valid", "version": 1},
                "policy_sizing_intent": None,
                "provider_translation_result": None,
                "control_outcome": {"status": "proposed", "version": 1},
                "version": 1,
            },
            "decision_envelope": {"action": "OPEN_SMALL_LONG", "version": 1},
            "decision_metadata": {"decision_id": "decision-123"},
            "trace_version": 1,
        },
    }

    trading_agent._mark_decision_not_executed(decision, "RISK_REJECTED", "risk rejected")

    assert decision["control_outcome"]["status"] == "rejected"
    assert decision["policy_package"]["control_outcome"] == decision["control_outcome"]
    assert decision["policy_trace"]["policy_package"]["control_outcome"] == decision["control_outcome"]





@pytest.mark.asyncio
async def test_actionable_decision_carries_compact_decision_artifact_into_queue(trading_agent, mock_dependencies):
    trading_agent.config.asset_pairs = ["BTCUSD"]
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-actionable-artifact",
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 82,
            "asset_pair": "BTCUSD",
            "reasoning": "Momentum breakout.",
        }
    )
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(return_value={"platform_breakdowns": {}})
    trading_agent._should_execute_with_reason = AsyncMock(return_value=(True, "OK", "Autonomous execution enabled"))
    trading_agent.state = AgentState.REASONING

    await trading_agent.handle_reasoning_state()

    async with trading_agent._current_decisions_lock:
        queued = trading_agent._current_decisions[0]
    artifact = queued["decision_artifact"]
    assert artifact["asset_pair"] == "BTCUSD"
    assert artifact["final_action"] == "OPEN_SMALL_LONG"
    assert artifact["actionable"] is True
    assert artifact["filtered_reason_code"] is None
    assert artifact["execution_attempted"] is False


@pytest.mark.asyncio
async def test_reasoning_state_keeps_close_long_policy_action_actionable(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-close-long",
            "action": "CLOSE_LONG",
            "policy_action": "CLOSE_LONG",
            "confidence": 82,
            "asset_pair": "BTCUSD",
        }
    )
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [
                        {"product_id": "SOL-USD-PERP", "side": "LONG", "contracts": 1.0}
                    ]
                }
            }
        }
    )
    trading_agent._should_execute_with_reason = AsyncMock(return_value=(True, "OK", "Autonomous execution enabled"))
    trading_agent.state = AgentState.REASONING

    await trading_agent.handle_reasoning_state()

    async with trading_agent._current_decisions_lock:
        assert len(trading_agent._current_decisions) == 1
        assert trading_agent._current_decisions[0]["policy_action"] == "CLOSE_LONG"
    assert trading_agent.state == AgentState.RISK_CHECK


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_duplicate_entry_block_sets_observability_fields(trading_agent, mock_dependencies):
    trading_agent.config.asset_pairs = ["BTCUSD"]
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-open-long-observability",
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 82,
            "asset_pair": "BTCUSD",
        }
    )
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [
                        {"product_id": "BIP-20DEC30-CDE", "side": "LONG", "contracts": 1.0}
                    ],
                    "futures_summary": {"initial_margin": 6000.0, "total_balance_usd": 10000.0},
                }
            }
        }
    )
    trading_agent._should_execute_with_reason = AsyncMock(return_value=(True, "OK", "Autonomous execution enabled"))
    trading_agent.state = AgentState.REASONING

    await trading_agent.handle_reasoning_state()

    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert saved_decision["actionable"] is False
    assert saved_decision["filtered_reason_code"] == "DUPLICATE_ENTRY_GUARD"
    assert "Duplicate entry blocked" in saved_decision["filtered_reason_text"]


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_reasoning_state_blocks_duplicate_same_direction_policy_entry(trading_agent, mock_dependencies):
    trading_agent.config.asset_pairs = ["BTCUSD"]
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-open-long",
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 82,
            "asset_pair": "BTCUSD",
        }
    )
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [
                        {"product_id": "BIP-20DEC30-CDE", "side": "LONG", "contracts": 1.0}
                    ],
                    "futures_summary": {"initial_margin": 6000.0, "total_balance_usd": 10000.0},
                }
            }
        }
    )
    trading_agent._should_execute_with_reason = AsyncMock(return_value=(True, "OK", "Autonomous execution enabled"))
    trading_agent.state = AgentState.REASONING

    await trading_agent.handle_reasoning_state()

    async with trading_agent._current_decisions_lock:
        assert trading_agent._current_decisions == []
    saved_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert saved_decision["asset_pair"] == "BTCUSD"
    assert saved_decision["execution_result"]["reason_code"] == "DUPLICATE_ENTRY_GUARD"
    assert trading_agent.state == AgentState.IDLE



def test_counts_toward_daily_trade_limit_accepts_policy_open_action():
    from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
    agent = TradingLoopAgent.__new__(TradingLoopAgent)
    decision = {"policy_action": "OPEN_SMALL_LONG"}
    execution_result = {"success": True, "order_id": "abc123", "order_status": "FILLED", "response": {}}
    assert agent._counts_toward_daily_trade_limit(decision, execution_result) is True
