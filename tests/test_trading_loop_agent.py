# tests/test_trading_loop_agent.py

import datetime
import logging
from types import SimpleNamespace
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



def test_extract_order_id_accepts_top_level_success_response(trading_agent):
    assert trading_agent._extract_order_id_from_execution_result(
        {
            "success": True,
            "success_response": {"order_id": "top-level-order-1"},
        }
    ) == "top-level-order-1"


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


def test_sync_trade_outcome_recorder_annotates_active_positions_with_decision_id_from_trade_monitor(trading_agent, mock_dependencies):
    recorder = MagicMock()
    recorder.update_positions.return_value = []
    recorder.open_positions = {}
    mock_dependencies["engine"].trade_outcome_recorder = recorder
    mock_dependencies["trade_monitor"].get_decision_id_by_asset.return_value = "decision-btc-1"

    trading_agent._sync_trade_outcome_recorder([
        {
            "platform": "coinbase",
            "product_id": "BTC-USD",
            "side": "SHORT",
            "size": 1.0,
            "entry_price": 50000.0,
            "current_price": 49900.0,
            "unrealized_pnl": 100.0,
            "opened_at": "2026-03-28T09:00:00Z",
        }
    ])

    recorder.update_positions.assert_called_once()
    synced_positions = recorder.update_positions.call_args.args[0]
    assert synced_positions[0]["decision_id"] == "decision-btc-1"


def test_sync_trade_outcome_recorder_prefers_fresh_trade_monitor_decision_id_over_stale_recorder_state(trading_agent, mock_dependencies):
    recorder = MagicMock()
    recorder.update_positions.return_value = []
    recorder.open_positions = {
        "BTC-USD_SHORT": {
            "product": "BTC-USD",
            "side": "SHORT",
            "decision_id": "recovery-btc-old",
        }
    }
    mock_dependencies["engine"].trade_outcome_recorder = recorder
    mock_dependencies["trade_monitor"].get_decision_id_by_asset.return_value = "ensemble-btc-fresh"

    trading_agent._sync_trade_outcome_recorder([
        {
            "platform": "coinbase",
            "product_id": "BTC-USD",
            "side": "SHORT",
            "size": 1.0,
            "entry_price": 50000.0,
            "current_price": 49900.0,
            "unrealized_pnl": 100.0,
            "opened_at": "2026-03-28T09:00:00Z",
        }
    ])

    recorder.update_positions.assert_called_once()
    synced_positions = recorder.update_positions.call_args.args[0]
    assert synced_positions[0]["decision_id"] == "ensemble-btc-fresh"


def test_sync_trade_outcome_recorder_logs_learning_handoff_acceptance(trading_agent, mock_dependencies, caplog):
    recorder = MagicMock()
    recorder.update_positions.return_value = [
        {
            "decision_id": "decision-123",
            "product": "ETH-USD",
            "order_id": "order-123",
            "exit_price": "2100.5",
            "exit_time": "2026-03-23T20:00:00Z",
            "realized_pnl": "42.0",
        }
    ]
    mock_dependencies["engine"].trade_outcome_recorder = recorder
    mock_dependencies["engine"].record_trade_outcome.return_value = MagicMock(realized_pnl=42.0)

    with caplog.at_level(logging.INFO):
        trading_agent._sync_trade_outcome_recorder([])

    assert "Learning handoff ATTEMPT for closed position ETH-USD | order_id=order-123 | decision_id=decision-123 | lineage_source=outcome" in caplog.text
    assert "Learning handoff ACCEPTED for closed position ETH-USD | order_id=order-123 | decision_id=decision-123 | realized_pnl=42.0" in caplog.text


def test_sync_trade_outcome_recorder_logs_learning_handoff_skip(trading_agent, mock_dependencies, caplog):
    recorder = MagicMock()
    recorder.update_positions.return_value = [
        {
            "product": "ETH-USD",
            "order_id": "order-456",
            "exit_price": "2100.5",
            "exit_time": "2026-03-23T20:00:00Z",
            "realized_pnl": "42.0",
        }
    ]
    mock_dependencies["engine"].trade_outcome_recorder = recorder
    trading_agent._recover_decision_lineage_for_closed_outcome = MagicMock(return_value=(None, "no-hit", ["trade_monitor.expected_trades"]))

    with caplog.at_level(logging.WARNING):
        trading_agent._sync_trade_outcome_recorder([])

    assert "Learning handoff SKIPPED for closed position ETH-USD | order_id=order-456 | reason=missing_decision_id | attempted_sources=['trade_monitor.expected_trades']" in caplog.text


def test_recover_decision_lineage_for_closed_outcome_falls_back_to_decision_store_recovery_metadata(trading_agent, mock_dependencies):
    mock_dependencies["engine"].trade_outcome_recorder = MagicMock(open_positions={})
    mock_dependencies["trade_monitor"].expected_trades = {}
    mock_dependencies["trade_monitor"].active_trackers = {}
    mock_dependencies["trade_monitor"].closed_trades_queue = MagicMock(queue=[])
    mock_dependencies["trade_monitor"].get_decision_id_by_asset.return_value = None
    mock_dependencies["engine"].decision_store.get_recent_decisions.return_value = [
        {
            "id": "decision-recovery-btc",
            "asset_pair": "BIP20DEC30CDE",
            "action": "SELL",
            "ai_provider": "recovery",
            "recovery_metadata": {"product_id": "BIP-20DEC30-CDE", "platform": "coinbase"},
        }
    ]

    decision_id, lineage_source, attempted_sources = trading_agent._recover_decision_lineage_for_closed_outcome(
        {
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "order_id": "order-btc-close",
        }
    )

    assert decision_id == "decision-recovery-btc"
    assert lineage_source == "decision_store.recovery_metadata_product"
    assert "decision_store.recovery_metadata_product" in attempted_sources


def test_recover_decision_lineage_for_closed_outcome_reads_real_store_normalized_legacy_record(
    trading_agent, mock_dependencies, tmp_path
):
    from finance_feedback_engine.persistence.decision_store import DecisionStore

    store = DecisionStore({"storage_path": str(tmp_path / "decisions")})
    store.save_decision(
        {
            "decision_id": "decision-recovery-legacy-btc",
            "timestamp": "2026-03-30T04:00:00+00:00",
            "asset_pair": "BIP20DEC30CDE",
            "action": "SELL",
            "confidence": 70,
            "ai_provider": "recovery",
            "recovery_metadata": {
                "product_id": "BIP-20DEC30-CDE",
                "platform": "coinbase",
            },
        }
    )

    mock_dependencies["engine"].trade_outcome_recorder = MagicMock(open_positions={})
    mock_dependencies["trade_monitor"].expected_trades = {}
    mock_dependencies["trade_monitor"].active_trackers = {}
    mock_dependencies["trade_monitor"].closed_trades_queue = MagicMock(queue=[])
    mock_dependencies["trade_monitor"].get_decision_id_by_asset.return_value = None
    mock_dependencies["engine"].decision_store = store

    decision_id, lineage_source, attempted_sources = (
        trading_agent._recover_decision_lineage_for_closed_outcome(
            {
                "product": "BIP-20DEC30-CDE",
                "side": "SHORT",
                "order_id": "order-btc-close-legacy",
            }
        )
    )

    assert decision_id == "decision-recovery-legacy-btc"
    assert lineage_source == "decision_store.recovery_metadata_product"
    assert "decision_store.recovery_metadata_product" in attempted_sources


def test_recover_decision_lineage_for_closed_outcome_should_prefer_enriched_recovery_wrapper_over_plain_anchor(
    trading_agent, mock_dependencies
):
    mock_dependencies["engine"].trade_outcome_recorder = MagicMock(open_positions={})
    mock_dependencies["trade_monitor"].expected_trades = {}
    mock_dependencies["trade_monitor"].active_trackers = {}
    mock_dependencies["trade_monitor"].closed_trades_queue = MagicMock(queue=[])
    mock_dependencies["trade_monitor"].get_decision_id_by_asset.return_value = None
    mock_dependencies["engine"].decision_store.get_recent_decisions.return_value = [
        {
            "id": "old-plain-recovery-anchor",
            "asset_pair": "BIP20DEC30CDE",
            "action": "SELL",
            "ai_provider": "recovery",
            "recovery_metadata": {
                "product_id": "BIP-20DEC30-CDE",
            },
            "ensemble_metadata": {
                "providers_used": ["recovery"],
            },
        },
        {
            "id": "new-enriched-recovery-wrapper",
            "asset_pair": "BIP20DEC30CDE",
            "action": "SELL",
            "ai_provider": "ensemble",
            "recovery_metadata": {
                "product_id": "BIP-20DEC30-CDE",
                "shadowed_from_decision_id": "btc-ensemble-open-48539299",
                "shadowed_from_provider": "ensemble",
            },
            "ensemble_metadata": {
                "voting_strategy": "debate",
                "providers_used": ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
            },
            "policy_trace": {"decision_metadata": {"decision_id": "btc-ensemble-open-48539299"}},
        },
    ]

    decision_id, lineage_source, attempted_sources = (
        trading_agent._recover_decision_lineage_for_closed_outcome(
            {
                "product": "BIP-20DEC30-CDE",
                "side": "SHORT",
                "order_id": "order-bip-close-rich",
            }
        )
    )

    assert decision_id == "new-enriched-recovery-wrapper"
    assert lineage_source == "decision_store.recovery_metadata_product"
    assert "decision_store.recovery_metadata_product" in attempted_sources


@pytest.mark.asyncio
async def test_handle_learning_state_skips_when_decision_id_unrecoverable(trading_agent, caplog):
    """handle_learning_state logs SKIPPED and does not call record_trade_outcome when decision_id is absent and all recovery sources fail."""
    trade_outcome = {
        "trade_id": "t-missing",
        "product_id": "ETH-USD",
        "side": "LONG",
        "realized_pnl": 50.0,
        "was_profitable": True,
    }
    trading_agent.state = AgentState.LEARNING
    trading_agent._transition_to = AsyncMock()
    trading_agent.trade_monitor.get_closed_trades = Mock(return_value=[trade_outcome])
    trading_agent.trade_monitor.expected_trades = {}
    trading_agent.trade_monitor.active_trackers = {}
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value=None)
    trading_agent.trade_monitor.closed_trades_queue = MagicMock()
    trading_agent.trade_monitor.closed_trades_queue.queue = []
    trading_agent.engine.decision_store = MagicMock()
    trading_agent.engine.decision_store.get_recent_decisions = Mock(return_value=[])
    trading_agent.engine.trade_outcome_recorder = MagicMock()
    trading_agent.engine.trade_outcome_recorder.open_positions = {}

    with caplog.at_level(logging.WARNING, logger="finance_feedback_engine"):
        await trading_agent.handle_learning_state()

    trading_agent.engine.record_trade_outcome.assert_not_called()
    assert "Learning handoff SKIPPED for monitor-closed trade ETH-USD | trade_id=t-missing | reason=missing_decision_id" in caplog.text


@pytest.mark.asyncio
async def test_handle_learning_state_uses_recovered_decision_id(trading_agent, caplog):
    """handle_learning_state logs ACCEPTED and calls record_trade_outcome when decision_id is absent but recovery succeeds via get_decision_id_by_asset."""
    trade_outcome = {
        "trade_id": "t-recover",
        "product_id": "ETH-USD",
        "side": "LONG",
        "realized_pnl": 80.0,
        "was_profitable": True,
    }
    trading_agent.state = AgentState.LEARNING
    trading_agent._transition_to = AsyncMock()
    trading_agent.trade_monitor.get_closed_trades = Mock(return_value=[trade_outcome])
    trading_agent.trade_monitor.expected_trades = {}
    trading_agent.trade_monitor.active_trackers = {}
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value="dec-recovered")
    trading_agent.trade_monitor.closed_trades_queue = MagicMock()
    trading_agent.trade_monitor.closed_trades_queue.queue = []
    trading_agent.engine.trade_outcome_recorder = MagicMock()
    trading_agent.engine.trade_outcome_recorder.open_positions = {}
    trading_agent.engine.record_trade_outcome = Mock(return_value=MagicMock(realized_pnl=80.0))

    with caplog.at_level(logging.INFO, logger="finance_feedback_engine"):
        await trading_agent.handle_learning_state()

    trading_agent.engine.record_trade_outcome.assert_called_once()
    assert "Learning handoff ACCEPTED for monitor-closed trade ETH-USD | trade_id=t-recover | decision_id=dec-recovered" in caplog.text


@pytest.mark.asyncio
async def test_handle_learning_state_uses_existing_decision_id_without_recovery(trading_agent, caplog):
    """handle_learning_state does not invoke recovery when decision_id is already present."""
    trade_outcome = {
        "trade_id": "t-has-id",
        "product_id": "ETH-USD",
        "decision_id": "dec-already-set",
        "side": "LONG",
        "realized_pnl": 30.0,
        "was_profitable": True,
    }
    trading_agent.state = AgentState.LEARNING
    trading_agent._transition_to = AsyncMock()
    trading_agent.trade_monitor.get_closed_trades = Mock(return_value=[trade_outcome])
    trading_agent.engine.record_trade_outcome = Mock(return_value=MagicMock(realized_pnl=30.0))
    original_recovery = trading_agent._recover_decision_lineage_for_closed_outcome
    trading_agent._recover_decision_lineage_for_closed_outcome = Mock(side_effect=AssertionError("recovery should not be called"))

    with caplog.at_level(logging.INFO, logger="finance_feedback_engine"):
        await trading_agent.handle_learning_state()

    trading_agent.engine.record_trade_outcome.assert_called_once()
    assert "Learning handoff SKIPPED" not in caplog.text
    trading_agent._recover_decision_lineage_for_closed_outcome = original_recovery


def test_normalize_trade_outcome_product_aliases_populates_both_keys(trading_agent):
    product_only = trading_agent._normalize_trade_outcome_product_aliases(
        {"product": "ETP-20DEC30-CDE", "side": "SHORT"}
    )
    assert product_only["product"] == "ETP-20DEC30-CDE"
    assert product_only["product_id"] == "ETP-20DEC30-CDE"

    product_id_only = trading_agent._normalize_trade_outcome_product_aliases(
        {"product_id": "BIP-20DEC30-CDE", "side": "LONG"}
    )
    assert product_id_only["product"] == "BIP-20DEC30-CDE"
    assert product_id_only["product_id"] == "BIP-20DEC30-CDE"


def test_normalize_trade_outcome_product_aliases_backfills_asset_pair_and_recorded_via_for_futures_polling(trading_agent):
    outcome = trading_agent._normalize_trade_outcome_product_aliases(
        {"product": "BIP-20DEC30-CDE", "side": "LONG"}
    )
    assert outcome["product"] == "BIP-20DEC30-CDE"
    assert outcome["product_id"] == "BIP-20DEC30-CDE"
    assert outcome["asset_pair"] == "BTCUSD"
    assert outcome["recorded_via"] == "position_polling"


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
async def test_execution_round_trip_registers_derisk_order_and_forwards_close_into_learning(trading_agent, mock_dependencies):
    """Successful CLOSE_* execution should register outcome tracking and forward repaired close data."""
    trading_agent._current_decisions = [
        {
            "id": "decision-close-1",
            "action": "CLOSE_SHORT",
            "asset_pair": "ETHUSD",
            "confidence": 92,
            "recommended_position_size": 1.0,
            "entry_price": 2166.5,
        }
    ]
    trading_agent.daily_trade_count = 10

    mock_dependencies["engine"].execute_decision_async = AsyncMock(
        return_value={
            "success": True,
            "platform": "coinbase",
            "success_response": {"order_id": "order-123"},
        }
    )
    mock_dependencies["engine"].trade_outcome_recorder = MagicMock()
    mock_dependencies["engine"].trade_outcome_recorder.update_positions.return_value = [
        {
            "decision_id": "decision-close-1",
            "product": "ETP-20DEC30-CDE",
            "exit_price": "2156.0",
            "exit_time": "2026-03-24T13:30:00Z",
            "realized_pnl": "10.5",
            "exit_size": "1.0",
        }
    ]
    mock_dependencies["engine"].record_trade_outcome.return_value = MagicMock(realized_pnl=10.5)
    mock_dependencies["engine"].order_status_worker = MagicMock()

    await trading_agent.handle_execution_state()

    mock_dependencies["engine"].order_status_worker.add_pending_order.assert_called_once_with(
        order_id="order-123",
        decision_id="decision-close-1",
        asset_pair="ETHUSD",
        platform="coinbase",
        action="BUY",
        size=1.0,
        entry_price=2166.5,
        side="SHORT",
        policy_action_family="close_short",
    )
    assert trading_agent.daily_trade_count == 11

    trading_agent._sync_trade_outcome_recorder([])

    mock_dependencies["engine"].record_trade_outcome.assert_called_once_with(
        "decision-close-1",
        exit_price=2156.0,
        exit_timestamp="2026-03-24T13:30:00Z",
    )


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
async def test_filtered_low_confidence_decision_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "BUY",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 10,
            "asset_pair": "BTCUSD",
            "reasoning": "Weak but directional signal.",
            "decision_origin": "judge",
            "market_regime": "ranging",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 55, "reasoning": "Breakout try."},
                    "judge": {"action": "OPEN_SMALL_LONG", "confidence": 10, "reasoning": "Too weak to execute."},
                }
            },
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["filtered_reason_code"] == "LOW_CONFIDENCE"
    assert saved_decision["decision_origin"] == "judge"
    assert saved_decision["market_regime"] == "ranging"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "OPEN_SMALL_LONG"



@pytest.mark.asyncio
async def test_judged_open_below_calibrated_confidence_is_filtered(trading_agent):
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 75,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "ranging",
    }

    should_execute, reason_code, reason_message = await trading_agent._should_execute_with_reason(decision)

    assert should_execute is False
    assert reason_code == "JUDGED_OPEN_MIN_CONFIDENCE"
    assert "75% < 80%" in reason_message


@pytest.mark.asyncio
async def test_judged_derisking_action_is_not_blocked_by_open_confidence_gate(trading_agent):
    decision = {
        "action": "CLOSE_LONG",
        "policy_action": "CLOSE_LONG",
        "confidence": 75,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "ranging",
    }

    should_execute, reason_code, _reason_message = await trading_agent._should_execute_with_reason(decision)

    assert should_execute is True
    assert reason_code == "OK"


@pytest.mark.asyncio
async def test_judged_open_in_ranging_now_uses_relaxed_threshold(trading_agent):
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 85,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "ranging",
    }

    should_execute, reason_code, reason_message = await trading_agent._should_execute_with_reason(decision)

    assert should_execute is True
    assert reason_code == "OK"
    assert reason_message == "Autonomous execution enabled"


@pytest.mark.asyncio
async def test_judged_open_in_trending_up_keeps_global_confidence_gate(trading_agent):
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 85,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "trending_up",
        "volatility": 0.045,
    }

    should_execute, reason_code, _reason_message = await trading_agent._should_execute_with_reason(decision)

    assert should_execute is True
    assert reason_code == "OK"


@pytest.mark.asyncio
async def test_judged_open_long_in_trending_up_moderate_volatility_requires_stricter_confidence_gate(trading_agent):
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 85,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "trending_up",
        "volatility": 0.03,
    }

    should_execute, reason_code, reason_message = await trading_agent._should_execute_with_reason(decision)

    assert should_execute is False
    assert reason_code == "JUDGED_OPEN_CONTEXT_MIN_CONFIDENCE"
    assert "trending_up/vol=0.030" in reason_message
    assert "85% < 90%" in reason_message


def test_judged_open_rerank_adjustment_demotes_target_pocket_to_hold(trading_agent):
    trading_agent.config.judged_open_rerank_penalty_enabled = True
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 78,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "trending_up",
        "volatility": 0.03,
        "candidate_action_scores": {"HOLD": 68.0, "OPEN_SMALL_LONG": 78.0},
    }

    adjusted = trading_agent._apply_judged_open_rerank_adjustments(decision)

    assert adjusted["policy_action"] == "HOLD"
    assert adjusted["action"] == "HOLD"
    assert adjusted["candidate_action_scores"]["OPEN_SMALL_LONG"] == 60.0
    assert adjusted["candidate_action_scores"]["HOLD"] == 68.0
    assert adjusted["experiment_adjustments"][0]["kind"] == "judged_open_pocket_penalty"
    assert adjusted["experiment_adjustments"][0]["reranked_to"] == "HOLD"
    assert adjusted["experiment_adjustments"][0]["eligible"] is True
    assert adjusted["experiment_adjustments"][0]["rerank_outcome"] == "demoted_to_hold"
    assert adjusted["experiment_adjustments"][0]["pre_rerank_winner"] == "OPEN_SMALL_LONG"
    assert adjusted["experiment_adjustments"][0]["post_rerank_winner"] == "HOLD"
    assert adjusted["experiment_adjustments"][0]["net_score_delta_pct"] == -18.0
    assert len(adjusted["experiment_adjustments"][0]["components"]) == 2
    assert adjusted["experiment_adjustments"][0]["rerank_trigger"] == "confidence_bucket_and_pocket"
    assert adjusted["experiment_adjustments"][0]["applied_component_types"] == ["confidence_bucket_penalty", "pocket_penalty"]
    assert adjusted["experiment_adjustments"][0]["component_score_delta_pct"] == {"confidence_bucket_penalty": -6.0, "pocket_penalty": -12.0}
    assert adjusted["policy_trace"]["learning_metadata"]["experiment_adjustments"][0]["penalty_pct"] == 18.0


def test_judged_open_rerank_adjustment_applies_confidence_bucket_penalty_outside_target_pocket(trading_agent):
    trading_agent.config.judged_open_rerank_penalty_enabled = True
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 78,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "trending_up",
        "volatility": 0.05,
        "candidate_action_scores": {"HOLD": 68.0, "OPEN_SMALL_LONG": 78.0},
    }

    adjusted = trading_agent._apply_judged_open_rerank_adjustments(decision)

    assert adjusted["policy_action"] == "OPEN_SMALL_LONG"
    adjustment = adjusted["experiment_adjustments"][0]
    assert adjustment["net_score_delta_pct"] == -6.0
    assert adjustment["components"][0]["component"] == "confidence_bucket_penalty"
    assert adjustment["rerank_trigger"] == "confidence_bucket_only"
    assert adjustment["applied_component_types"] == ["confidence_bucket_penalty"]
    assert adjustment["component_score_delta_pct"] == {"confidence_bucket_penalty": -6.0}
    assert adjustment["rerank_outcome"] == "no_op"


def test_judged_open_rerank_adjustment_records_no_op_observability(trading_agent):
    trading_agent.config.judged_open_rerank_penalty_enabled = True
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 78,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "trending_up",
        "volatility": 0.03,
        "candidate_action_scores": {"HOLD": 55.0, "OPEN_SMALL_LONG": 78.0},
    }

    adjusted = trading_agent._apply_judged_open_rerank_adjustments(decision)

    assert adjusted["policy_action"] == "OPEN_SMALL_LONG"
    assert adjusted["action"] == "OPEN_SMALL_LONG"
    adjustment = adjusted["experiment_adjustments"][0]
    assert adjustment["eligible"] is True
    assert adjustment["rerank_outcome"] == "no_op"
    assert adjustment["pre_rerank_winner"] == "OPEN_SMALL_LONG"
    assert adjustment["post_rerank_winner"] == "OPEN_SMALL_LONG"
    assert adjustment["reranked_to"] == "OPEN_SMALL_LONG"
    assert adjustment["net_score_delta_pct"] == -18.0
    assert len(adjustment["components"]) == 2


def test_judged_open_rerank_adjustment_keeps_only_bucket_penalty_when_ranging_pocket_disabled(trading_agent):
    trading_agent.config.judged_open_rerank_penalty_enabled = True
    trading_agent.config.judged_open_rerank_penalty_ranging_enabled = False
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 78,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "ranging",
        "volatility": 0.03,
        "candidate_action_scores": {"HOLD": 68.0, "OPEN_SMALL_LONG": 78.0},
    }

    adjusted = trading_agent._apply_judged_open_rerank_adjustments(decision)

    assert adjusted["policy_action"] == "OPEN_SMALL_LONG"
    adjustment = adjusted["experiment_adjustments"][0]
    assert adjustment["net_score_delta_pct"] == -6.0
    assert len(adjustment["components"]) == 1
    assert adjustment["components"][0]["component"] == "confidence_bucket_penalty"



def test_judged_open_rerank_adjustment_demotes_ranging_pocket_when_enabled(trading_agent):
    trading_agent.config.judged_open_rerank_penalty_enabled = True
    trading_agent.config.judged_open_rerank_penalty_ranging_enabled = True
    decision = {
        "action": "OPEN_SMALL_LONG",
        "policy_action": "OPEN_SMALL_LONG",
        "confidence": 78,
        "asset_pair": "BTCUSD",
        "decision_origin": "judge",
        "market_regime": "ranging",
        "volatility": 0.03,
        "candidate_action_scores": {"HOLD": 69.0, "OPEN_SMALL_LONG": 78.0},
    }

    adjusted = trading_agent._apply_judged_open_rerank_adjustments(decision)

    assert adjusted["policy_action"] == "HOLD"
    adjustment = adjusted["experiment_adjustments"][0]
    assert adjustment["pocket"]["market_regime"] == "ranging"
    assert adjustment["rerank_outcome"] == "demoted_to_hold"
    assert adjustment["post_rerank_winner"] == "HOLD"
    assert adjustment["net_score_delta_pct"] == -18.0
    assert adjustment["rerank_trigger"] == "confidence_bucket_and_pocket"
    assert adjustment["component_score_delta_pct"] == {"confidence_bucket_penalty": -6.0, "pocket_penalty": -12.0}
    assert len(adjustment["components"]) == 2


@pytest.mark.asyncio
async def test_reranked_judged_open_persists_experiment_adjustment_metadata(trading_agent, mock_dependencies):
    trading_agent.config.judged_open_rerank_penalty_enabled = True
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 78,
            "asset_pair": "BTCUSD",
            "reasoning": "Judge sees a borderline trend continuation.",
            "decision_origin": "judge",
            "market_regime": "trending_up",
            "volatility": 0.03,
            "candidate_actions": ["HOLD", "OPEN_SMALL_LONG"],
            "candidate_action_scores": {"HOLD": 68.0, "OPEN_SMALL_LONG": 78.0},
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["policy_action"] == "HOLD"
    assert saved_decision["action"] == "HOLD"
    assert saved_decision["experiment_adjustments"][0]["reranked_to"] == "HOLD"
    assert saved_decision["experiment_adjustments"][0]["pre_rerank_winner"] == "OPEN_SMALL_LONG"
    assert saved_decision["experiment_adjustments"][0]["post_rerank_winner"] == "HOLD"
    assert saved_decision["experiment_adjustments"][0]["rerank_outcome"] == "demoted_to_hold"
    assert saved_decision["experiment_adjustments"][0]["net_score_delta_pct"] == -18.0
    assert saved_decision["experiment_adjustments"][0]["rerank_trigger"] == "confidence_bucket_and_pocket"
    assert saved_decision["experiment_adjustments"][0]["applied_component_types"] == ["confidence_bucket_penalty", "pocket_penalty"]
    assert len(saved_decision["experiment_adjustments"][0]["components"]) == 2
    assert saved_decision["policy_trace"]["learning_metadata"]["experiment_adjustments"][0]["kind"] == "judged_open_pocket_penalty"


@pytest.mark.asyncio
async def test_filtered_context_specific_judged_open_gate_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 85,
            "asset_pair": "BTCUSD",
            "reasoning": "Judge sees a moderate-vol trend continuation.",
            "decision_origin": "judge",
            "market_regime": "trending_up",
            "volatility": 0.03,
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 88, "reasoning": "Trend continuation"},
                    "judge": {"action": "OPEN_SMALL_LONG", "confidence": 85, "reasoning": "Still too weak for this context"},
                }
            },
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["filtered_reason_code"] == "JUDGED_OPEN_CONTEXT_MIN_CONFIDENCE"
    assert saved_decision["decision_origin"] == "judge"
    assert saved_decision["market_regime"] == "trending_up"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "OPEN_SMALL_LONG"


@pytest.mark.asyncio
async def test_filtered_unknown_regime_specific_judged_open_gate_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 85,
            "asset_pair": "BTCUSD",
            "reasoning": "Judge sees a decent setup but regime is unresolved.",
            "decision_origin": "judge",
            "market_regime": "unknown",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 88, "reasoning": "Bounce"},
                    "judge": {"action": "OPEN_SMALL_LONG", "confidence": 85, "reasoning": "Still too weak for unknown regime"},
                }
            },
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["filtered_reason_code"] == "JUDGED_OPEN_REGIME_MIN_CONFIDENCE"
    assert saved_decision["decision_origin"] == "judge"
    assert saved_decision["market_regime"] == "unknown"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "OPEN_SMALL_LONG"


@pytest.mark.asyncio
async def test_filtered_judged_open_confidence_gate_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 75,
            "asset_pair": "BTCUSD",
            "reasoning": "Judge sees a weak breakout try.",
            "decision_origin": "judge",
            "market_regime": "ranging",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 85, "reasoning": "Breakout"},
                    "judge": {"action": "OPEN_SMALL_LONG", "confidence": 75, "reasoning": "Weak edge"},
                }
            },
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["filtered_reason_code"] == "JUDGED_OPEN_MIN_CONFIDENCE"
    assert saved_decision["decision_origin"] == "judge"
    assert saved_decision["market_regime"] == "ranging"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "OPEN_SMALL_LONG"



@pytest.mark.asyncio
async def test_filtered_decision_preserves_learning_scaffold_fields(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "BUY",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 10,
            "asset_pair": "BTCUSD",
            "reasoning": "Weak exploratory signal.",
            "decision_origin": "judge",
            "market_regime": "ranging",
            "policy_family": "baseline_ffe",
            "decision_mode": "shadow",
            "coverage_bucket": "ranging:lt70",
            "exploration_metadata": {"experiment_id": "shadow-low-conf"},
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["filtered_reason_code"] == "LOW_CONFIDENCE"
    assert saved_decision["policy_family"] == "baseline_ffe"
    assert saved_decision["decision_mode"] == "shadow"
    assert saved_decision["coverage_bucket"] == "ranging:lt70"
    assert saved_decision["exploration_metadata"]["experiment_id"] == "shadow-low-conf"


@pytest.mark.asyncio
async def test_filtered_decision_backfills_learning_metadata_defaults_before_save(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "BUY",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 10,
            "asset_pair": "BTCUSD",
            "reasoning": "Weak exploratory signal.",
            "decision_origin": "judge",
            "market_regime": "ranging",
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["filtered_reason_code"] == "LOW_CONFIDENCE"
    assert saved_decision["policy_family"] == "baseline_ffe"
    assert saved_decision["decision_mode"] == "exploitation"
    assert saved_decision["coverage_bucket"] == "ranging:lt50"
    assert saved_decision["candidate_actions"] == ["OPEN_SMALL_LONG"]
    assert saved_decision["candidate_action_scores"] == {"OPEN_SMALL_LONG": 10.0}
    assert saved_decision["policy_trace"]["learning_metadata"]["decision_mode"] == "exploitation"


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
async def test_position_state_forced_hold_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "action": "HOLD",
            "policy_action": "HOLD",
            "confidence": 0,
            "reasoning": "[FORCED HOLD - Position State Violation] Cannot BUY when already LONG BTCUSD.",
            "position_state_violation": True,
            "decision_origin": "judge",
            "market_regime": "trending",
            "asset_pair": "BTCUSD",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "OPEN_SMALL_LONG", "confidence": 88, "reasoning": "double down"},
                    "judge": {"action": "OPEN_SMALL_LONG", "confidence": 88, "reasoning": "trend continuation"},
                }
            },
        }
    )
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision["hold_origin"] == "position_rule"
    assert saved_decision["decision_origin"] == "judge"
    assert saved_decision["market_regime"] == "trending"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "OPEN_SMALL_LONG"


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


@pytest.mark.asyncio
async def test_hold_decision_preserves_spine_fields_for_judged_hold(trading_agent, mock_dependencies):
    decision = {
        "action": "HOLD",
        "confidence": 30,
        "asset_pair": "BTCUSD",
        "reasoning": "Judge sees no edge after debate.",
        "decision_origin": "judge",
        "market_regime": "ranging",
        "ensemble_metadata": {
            "debate_mode": True,
            "role_decisions": {
                "bull": {"role": "bull", "action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 40, "reasoning": "Momentum up.", "provider": "gemini"},
                "bear": {"role": "bear", "action": "HOLD", "confidence": 40, "reasoning": "Range-bound.", "provider": "qwen"},
                "judge": {"role": "judge", "action": "HOLD", "confidence": 30, "reasoning": "No strong edge.", "provider": "mistral"},
            },
            "debate_seats": {"bull": "gemini", "bear": "qwen", "judge": "mistral"},
        },
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value=decision)
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved_decision = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved_decision.get("filtered_reason_code") != "NO_DECISION_PAYLOAD"
    assert saved_decision.get("confidence") == 30
    assert saved_decision.get("decision_origin") == "judge"
    assert saved_decision.get("reasoning") == "Judge sees no edge after debate."
    assert saved_decision.get("market_regime") == "ranging"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["judge"]["action"] == "HOLD"
    assert saved_decision["ensemble_metadata"]["role_decisions"]["bull"]["policy_action"] == "OPEN_SMALL_LONG"


@pytest.mark.asyncio
async def test_judged_hold_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    decision = {
        "action": "HOLD",
        "policy_action": "HOLD",
        "confidence": 60,
        "asset_pair": "BTCUSD",
        "reasoning": "Judge rationale preserved.",
        "decision_origin": "judge",
        "market_regime": "ranging",
        "ensemble_metadata": {
            "debate_mode": True,
            "debate_seats": {"bull": "gemini", "bear": "qwen", "judge": "mistral"},
            "role_decisions": {
                "bull": {"role": "bull", "action": "BUY", "policy_action": "OPEN_SMALL_LONG", "confidence": 40, "reasoning": "Momentum up."},
                "bear": {"role": "bear", "action": "HOLD", "policy_action": "HOLD", "confidence": 40, "reasoning": "Range-bound."},
                "judge": {"role": "judge", "action": "HOLD", "policy_action": "HOLD", "confidence": 60, "reasoning": "No edge."},
            },
        },
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value=decision)
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved["decision_origin"] == "judge"
    assert saved["market_regime"] == "ranging"
    assert saved["ensemble_metadata"]["debate_seats"]["judge"] == "mistral"
    assert saved["ensemble_metadata"]["role_decisions"]["bull"]["policy_action"] == "OPEN_SMALL_LONG"


@pytest.mark.asyncio
async def test_pre_reason_skip_hold_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    decision = {
        "action": "HOLD",
        "policy_action": "HOLD",
        "confidence": 75,
        "asset_pair": "BTCUSD",
        "reasoning": "[PRE-REASON SKIP] Price is ranging with no catalyst.",
        "decision_origin": "pre_reasoner",
        "market_regime": "ranging",
        "pre_reasoning": {
            "skip_debate": True,
            "regime": "ranging",
            "reason": "No clear catalyst",
            "key_question": "Wait for breakout?",
        },
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value=decision)
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved["decision_origin"] == "pre_reasoner"
    assert saved["market_regime"] == "ranging"
    assert saved["pre_reasoning"]["skip_debate"] is True
    assert saved["pre_reasoning"]["reason"] == "No clear catalyst"


@pytest.mark.asyncio
async def test_filtered_pre_reason_hold_preserves_audit_spine_fields(trading_agent, mock_dependencies):
    decision = {
        "action": "HOLD",
        "policy_action": "HOLD",
        "confidence": 50,
        "asset_pair": "BTCUSD",
        "reasoning": "[PRE-REASON SKIP] No clear directional signal. Regime: ranging.",
        "decision_origin": "pre_reasoner",
        "market_regime": "ranging",
        "pre_reasoning": {
            "skip_debate": True,
            "regime": "ranging",
            "reason": "No clear directional signal",
        },
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value=decision)
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    saved = mock_dependencies["engine"].decision_store.save_decision.call_args[0][0]
    assert saved["execution_status"] == "hold"
    assert saved["decision_origin"] == "pre_reasoner"
    assert saved["market_regime"] == "ranging"
    assert saved["pre_reasoning"]["skip_debate"] is True


@pytest.mark.asyncio
async def test_hold_decision_already_persisted_upstream_updates_instead_of_saving_again(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-hold-already-persisted",
        "action": "HOLD",
        "confidence": 64,
        "asset_pair": "BTCUSD",
        "reasoning": "Judge sees conflicting signals.",
        "_persisted_to_store": True,
    }
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(return_value=decision)
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    mock_dependencies["engine"].decision_store.update_decision.assert_called_once()
    mock_dependencies["engine"].decision_store.save_decision.assert_not_called()
    updated_decision = mock_dependencies["engine"].decision_store.update_decision.call_args[0][0]
    assert updated_decision["id"] == "decision-hold-already-persisted"
    assert updated_decision["execution_status"] == "hold"
    assert updated_decision["executed"] is False



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

    assert "Portfolio risk snapshot (decision loop) | asset_scoped_open_positions=2" in caplog.text
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

    assert "Portfolio risk snapshot (decision loop) | asset_scoped_open_positions=1" in caplog.text
    assert "asset_scoped_pairs=['BIP20DEC30CDE', 'BTCUSD']" in caplog.text
    assert "global_managed_pairs=['BTCUSD']" in caplog.text
    assert "margin_usage=50.00%" in caplog.text
    assert "Skipping OPEN_SMALL_SHORT for BTCUSD: SHORT position already exists (duplicate-entry guard)." in caplog.text



@pytest.mark.asyncio
async def test_process_cycle_blocks_scale_in_above_configured_concentration_limit(trading_agent, mock_dependencies, caplog):
    mock_dependencies["engine"].config = {"safety": {"max_position_pct": 25.0}}
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [
                        {
                            "product_id": "BIP-20DEC30-CDE",
                            "side": "LONG",
                            "number_of_contracts": "1",
                        }
                    ],
                    "futures_summary": {
                        "total_balance_usd": 231.43,
                        "buying_power": 146.23,
                        "unrealized_pnl": -1.15,
                        "initial_margin": 78.94,
                    },
                }
            }
        }
    )
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-1",
            "action": "ADD_SMALL_LONG",
            "confidence": 85,
            "asset_pair": "BTCUSD",
            "ensemble_metadata": {
                "role_decisions": {
                    "bull": {"action": "ADD_SMALL_LONG", "confidence": 85, "provider": "gemma4:e2b"},
                    "bear": {"action": "HOLD", "confidence": 65, "provider": "llama3.1:8b"},
                    "judge": {"action": "ADD_SMALL_LONG", "confidence": 85, "provider": "deepseek-r1:8b"},
                }
            },
        }
    )
    trading_agent.is_running = True

    with caplog.at_level(logging.INFO):
        await trading_agent.process_cycle()

    assert "margin_usage=34.11% (limit 25.00%)" in caplog.text
    assert "Skipping ADD_SMALL_LONG for BTCUSD: LONG position already exists (duplicate-entry guard)." in caplog.text
    assert "Actionable decision collected for BTCUSD: ADD_SMALL_LONG" not in caplog.text



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



def test_derisking_execution_metadata_preserves_existing_exit_notional(trading_agent):
    decision = {
        "asset_pair": "BTCUSD",
        "action": "REDUCE_LONG",
        "policy_action": "REDUCE_LONG",
        "entry_price": 77556.22,
        "suggested_amount": 1250.1535893290443,
        "current_position_size": 0.1611932078857175,
        "recommended_position_size": 0.1611932078857175,
    }
    monitoring_context = {
        "active_positions": {
            "futures": [
                {
                    "product_id": "BTC-FUT",
                    "side": "LONG",
                    "number_of_contracts": "0.1611932078857175",
                    "current_price": "78323.7",
                    "contract_size": "0.1",
                }
            ]
        }
    }

    trading_agent._apply_derisking_execution_metadata(decision, monitoring_context)

    assert decision["current_position_size"] == 0.1611932078857175
    assert decision["recommended_position_size"] == 0.1611932078857175
    assert decision["suggested_amount"] == 1250.1535893290443



def test_derisking_execution_metadata_uses_contract_effective_notional_when_available(trading_agent):
    decision = {
        "asset_pair": "ETHUSD",
        "action": "REDUCE_LONG",
        "policy_action": "REDUCE_LONG",
        "entry_price": 2127.0,
    }
    monitoring_context = {
        "active_positions": {
            "futures": [
                {
                    "product_id": "ETP-20DEC30-CDE",
                    "side": "LONG",
                    "number_of_contracts": "5",
                    "current_price": "2127.0",
                    "contract_size": "0.1",
                }
            ]
        }
    }

    trading_agent._apply_derisking_execution_metadata(decision, monitoring_context)

    assert decision["current_position_size"] == 5.0
    assert decision["recommended_position_size"] == 5.0
    assert decision["suggested_amount"] == 1063.5



def test_performance_risk_checks_allow_derisking_actions(trading_agent):
    trading_agent._performance_metrics.update(
        {
            "current_streak": 0,
            "total_trades": 12,
            "win_rate": 80,
            "avg_loss": -10,
            "avg_win": 40,
            "total_pnl": 100.0,
        }
    )
    decision = {
        "asset_pair": "BTCUSD",
        "action": "CLOSE_SHORT",
        "policy_action": "CLOSE_SHORT",
        "confidence": 95,
        "entry_price": 70535.0,
        "stop_loss_price": 0.0,
        "recommended_position_size": 0.293,
    }

    approved, reason = trading_agent._check_performance_based_risks(decision)

    assert approved is True
    assert "derisking" in reason.lower()



def test_performance_risk_checks_reject_live_entry_after_four_losses(trading_agent):
    trading_agent.engine.config = {"platforms": ["coinbase"]}
    trading_agent._performance_metrics.update(
        {
            "current_streak": -4,
            "total_trades": 12,
            "win_rate": 55,
            "avg_loss": -10,
            "avg_win": 40,
            "total_pnl": 100.0,
        }
    )
    decision = {
        "asset_pair": "BTCUSD",
        "action": "OPEN_MEDIUM_LONG",
        "policy_action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "entry_price": 70535.0,
    }

    approved, reason = trading_agent._check_performance_based_risks(decision)

    assert approved is False
    assert "poor performance streak" in reason.lower()



def test_performance_risk_checks_allow_paper_only_entry_at_four_losses(trading_agent):
    trading_agent.engine.config = {"platforms": ["paper"]}
    trading_agent._performance_metrics.update(
        {
            "current_streak": -4,
            "total_trades": 12,
            "win_rate": 55,
            "avg_loss": -10,
            "avg_win": 40,
            "total_pnl": 100.0,
        }
    )
    decision = {
        "asset_pair": "BTCUSD",
        "action": "OPEN_MEDIUM_LONG",
        "policy_action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "entry_price": 70535.0,
    }

    approved, reason = trading_agent._check_performance_based_risks(decision)

    assert approved is True
    assert "passed" in reason.lower()



def test_performance_risk_checks_reject_paper_only_entry_after_six_losses(trading_agent):
    trading_agent.engine.config = {"platforms": ["paper"]}
    trading_agent._performance_metrics.update(
        {
            "current_streak": -6,
            "total_trades": 12,
            "win_rate": 55,
            "avg_loss": -10,
            "avg_win": 40,
            "total_pnl": 100.0,
        }
    )
    decision = {
        "asset_pair": "BTCUSD",
        "action": "OPEN_MEDIUM_LONG",
        "policy_action": "OPEN_MEDIUM_LONG",
        "confidence": 80,
        "entry_price": 70535.0,
    }

    approved, reason = trading_agent._check_performance_based_risks(decision)

    assert approved is False
    assert "6 consecutive losses" in reason.lower()



def test_performance_risk_checks_do_not_block_derisking_high_risk_to_recent_pnl(trading_agent):
    trading_agent._performance_metrics.update(
        {
            "current_streak": 0,
            "total_trades": 12,
            "win_rate": 80,
            "avg_loss": -10,
            "avg_win": 40,
            "total_pnl": 100.0,
        }
    )
    decision = {
        "asset_pair": "BTCUSD",
        "action": "CLOSE_SHORT",
        "policy_action": "CLOSE_SHORT",
        "confidence": 95,
        "entry_price": 70535.0,
        "stop_loss_price": 69000.0,
        "recommended_position_size": 0.293,
    }

    approved, reason = trading_agent._check_performance_based_risks(decision)

    assert approved is True
    assert "derisking" in reason.lower()





def test_sync_trade_outcome_recorder_uses_recorder_backfilled_decision_id_from_open_state(trading_agent, mock_dependencies):
    recorder = mock_dependencies["engine"].trade_outcome_recorder
    recorder.open_positions = {
        "ETP-20DEC30-CDE_SHORT": {
            "product": "ETP-20DEC30-CDE",
            "side": "SHORT",
            "entry_price": 2080.0,
            "entry_size": 1.0,
            "decision_id": "decision-eth-close",
        }
    }
    recorder.update_positions.return_value = [
        {
            "product": "ETP-20DEC30-CDE",
            "side": "SHORT",
            "exit_price": "2073.0",
            "exit_time": "2026-03-27T01:03:32+00:00",
            "realized_pnl": "-6.5",
            "decision_id": None,
        }
    ]
    mock_dependencies["engine"].record_trade_outcome.return_value = SimpleNamespace(realized_pnl=-6.5)
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value=None)

    trading_agent._sync_trade_outcome_recorder([])

    mock_dependencies["engine"].record_trade_outcome.assert_called_once_with(
        "decision-eth-close",
        exit_price=2073.0,
        exit_timestamp="2026-03-27T01:03:32+00:00",
    )


def test_sync_trade_outcome_recorder_recovers_missing_decision_id_from_trade_monitor(trading_agent, mock_dependencies):
    recorder = mock_dependencies["engine"].trade_outcome_recorder
    recorder.update_positions.return_value = [
        {
            "product": "ETP-20DEC30-CDE",
            "side": "SHORT",
            "exit_price": "2073.0",
            "exit_time": "2026-03-26T14:15:43+00:00",
            "realized_pnl": "-7.5",
            "decision_id": None,
        }
    ]
    mock_dependencies["engine"].record_trade_outcome.return_value = SimpleNamespace(realized_pnl=-7.5)
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value="decision-eth-close")

    trading_agent._sync_trade_outcome_recorder([])

    mock_dependencies["engine"].record_trade_outcome.assert_called_once_with(
        "decision-eth-close",
        exit_price=2073.0,
        exit_timestamp="2026-03-26T14:15:43+00:00",
    )


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
async def test_risk_check_reapplies_derisking_execution_metadata_after_generic_sizing(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-derisk-size",
        "action": "CLOSE_SHORT",
        "policy_action": "CLOSE_SHORT",
        "confidence": 95,
        "asset_pair": "ETHUSD",
        "entry_price": 2127.0,
        "structural_action_validity": "valid",
        "risk_vetoed": False,
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {
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
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(True, "approved"))
    trading_agent._check_performance_based_risks = Mock(return_value=(True, "ok"))
    mock_dependencies["engine"].position_sizing_calculator.calculate_position_sizing_params.return_value = {
        "recommended_position_size": 0
    }

    await trading_agent.handle_risk_check_state()

    async with trading_agent._current_decisions_lock:
        kept = trading_agent._current_decisions[0]
        assert kept["current_position_size"] == 5.0
        assert kept["recommended_position_size"] == 5.0
        assert kept["suggested_amount"] == 10635.0


@pytest.mark.asyncio
async def test_risk_check_hydrates_derisking_positions_from_portfolio_when_monitoring_context_is_empty(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-derisk-fallback",
        "action": "CLOSE_SHORT",
        "policy_action": "CLOSE_SHORT",
        "confidence": 90,
        "asset_pair": "ETHUSD",
        "entry_price": 2096.31,
        "structural_action_validity": "valid",
        "risk_vetoed": False,
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.RISK_CHECK

    mock_dependencies["trade_monitor"].monitoring_context_provider.get_monitoring_context.return_value = {}
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(
        return_value={
            "platform_breakdowns": {
                "coinbase": {
                    "futures_positions": [
                        {
                            "product_id": "ETP-20DEC30-CDE",
                            "side": "SHORT",
                            "number_of_contracts": "1",
                            "current_price": "2096.31",
                        }
                    ]
                }
            }
        }
    )
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(True, "approved"))
    trading_agent._check_performance_based_risks = Mock(return_value=(True, "ok"))
    mock_dependencies["engine"].position_sizing_calculator.calculate_position_sizing_params.return_value = {
        "recommended_position_size": 0
    }

    await trading_agent.handle_risk_check_state()

    async with trading_agent._current_decisions_lock:
        kept = trading_agent._current_decisions[0]
        assert kept["current_position_size"] == 1.0
        assert kept["recommended_position_size"] == 1.0
        assert kept["suggested_amount"] == 2096.31



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
        side="LONG",
        policy_action_family="open_long",
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



def test_sync_trade_outcome_recorder_recovers_missing_decision_id_from_trade_monitor_active_tracker(trading_agent, mock_dependencies):
    from types import SimpleNamespace
    recorder = mock_dependencies["engine"].trade_outcome_recorder
    recorder.update_positions.return_value = [
        {
            "product": "ETP-20DEC30-CDE",
            "side": "SHORT",
            "exit_price": "1974.0",
            "exit_time": "2026-03-27T17:57:20+00:00",
            "realized_pnl": "1.5",
            "decision_id": None,
        }
    ]
    mock_dependencies["engine"].record_trade_outcome.return_value = SimpleNamespace(realized_pnl=1.5)
    trading_agent.trade_monitor.active_trackers = {
        "tracker-1": SimpleNamespace(product_id="ETP-20DEC30-CDE", decision_id="decision-eth-close")
    }
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value=None)

    trading_agent._sync_trade_outcome_recorder([])

    mock_dependencies["engine"].record_trade_outcome.assert_called_once_with(
        "decision-eth-close",
        exit_price=1974.0,
        exit_timestamp="2026-03-27T17:57:20+00:00",
    )


def test_trade_monitor_detect_new_trades_unwraps_expected_trade_tuple(tmp_path):
    from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
    platform = MagicMock()
    platform.get_portfolio_breakdown.return_value = {
        "futures_positions": [
            {
                "product_id": "ETP-20DEC30-CDE",
                "side": "SHORT",
                "entry_price": 2080.0,
                "contracts": 1,
            }
        ]
    }
    monitor = TradeMonitor(platform=platform, detection_interval=30, poll_interval=30)
    monitor.expected_trades = {"ETP20DEC30CDE": ("decision-eth-open", 0.0)}

    monitor._detect_new_trades()

    queued = monitor.pending_queue.get_nowait()
    assert queued["decision_id"] == "decision-eth-open"



def test_sync_trade_outcome_recorder_logs_lineage_source_for_recovered_close(trading_agent, mock_dependencies, caplog):
    from types import SimpleNamespace
    recorder = mock_dependencies["engine"].trade_outcome_recorder
    recorder.update_positions.return_value = [
        {
            "product": "BIP-20DEC30-CDE",
            "side": "LONG",
            "exit_price": "88450.0",
            "exit_time": "2026-03-27T21:35:43+00:00",
            "realized_pnl": "15.0",
            "decision_id": None,
        }
    ]
    mock_dependencies["engine"].record_trade_outcome.return_value = SimpleNamespace(realized_pnl=15.0)
    trading_agent.trade_monitor.expected_trades = {}
    trading_agent.trade_monitor.active_trackers = {
        "trade-1": SimpleNamespace(product_id="BIP-20DEC30-CDE", decision_id="decision-btc-open")
    }

    with caplog.at_level(logging.INFO):
        trading_agent._sync_trade_outcome_recorder([])

    assert "lineage_source=trade_monitor.active_trackers" in caplog.text
    assert "attempted_sources=[" in caplog.text


@pytest.mark.asyncio
async def test_process_cycle_logs_reasoning_cycle_summary(trading_agent, mock_dependencies, caplog):
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(return_value={})
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-hold-1",
            "action": "HOLD",
            "confidence": 55,
            "asset_pair": "BTCUSD",
        }
    )
    trading_agent.is_running = True

    with caplog.at_level(logging.INFO):
        await trading_agent.process_cycle()

    assert "Reasoning cycle summary | analyzed_pairs=[(0, 'BTCUSD')]" in caplog.text
    assert "actionable_count=0" in caplog.text
    assert "non_actionable_count=1" in caplog.text


@pytest.mark.asyncio
async def test_process_cycle_logs_filtered_judged_open_as_non_actionable(trading_agent, mock_dependencies, caplog):
    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(return_value={})
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-filtered-open-1",
            "action": "OPEN_SMALL_LONG",
            "policy_action": "OPEN_SMALL_LONG",
            "confidence": 75,
            "asset_pair": "BTCUSD",
            "decision_origin": "judge",
            "market_regime": "ranging",
            "reasoning": "Weak judged open should be filtered.",
        }
    )
    trading_agent.is_running = True

    with caplog.at_level(logging.INFO):
        await trading_agent.process_cycle()

    assert "Reasoning cycle summary | analyzed_pairs=[(0, 'BTCUSD')]" in caplog.text
    assert "actionable_count=0" in caplog.text
    assert "non_actionable_count=1" in caplog.text


@pytest.mark.asyncio
async def test_process_cycle_stops_at_idle_after_execution_path(trading_agent, mock_dependencies):
    from finance_feedback_engine.agent.trading_loop_agent import AgentState

    mock_dependencies["engine"].get_portfolio_breakdown_async = AsyncMock(return_value={})
    mock_dependencies["engine"].analyze_asset_async = AsyncMock(
        return_value={
            "id": "decision-open-1",
            "action": "OPEN_SMALL_SHORT",
            "confidence": 80,
            "asset_pair": "BTCUSD",
            "legacy_action_compatibility": "OPEN_SHORT",
        }
    )
    mock_dependencies["engine"].validate_decision = Mock(return_value=True)
    trading_agent.risk_gatekeeper.validate_trade = Mock(return_value=(True, None))
    trading_agent.engine.execute_decision_async = AsyncMock(return_value={"success": True, "order_id": "abc123", "order_status": "FILLED", "response": {}})
    trading_agent.autonomous_execution = False
    trading_agent.is_running = True

    await trading_agent.process_cycle()

    assert trading_agent.state == AgentState.IDLE


def test_sync_trade_outcome_recorder_recovers_missing_decision_id_from_trade_monitor_expected_trade_alias(trading_agent, mock_dependencies):
    from types import SimpleNamespace
    recorder = mock_dependencies["engine"].trade_outcome_recorder
    recorder.update_positions.return_value = [
        {
            "product": "ETP-20DEC30-CDE",
            "side": "SHORT",
            "exit_price": "1986.0",
            "exit_time": "2026-03-27T22:25:38+00:00",
            "realized_pnl": "0.85",
            "decision_id": None,
        }
    ]
    mock_dependencies["engine"].record_trade_outcome.return_value = SimpleNamespace(realized_pnl=0.85)
    trading_agent.trade_monitor.expected_trades = {"ETHUSD": ("decision-eth-open", 0.0)}
    trading_agent.trade_monitor.active_trackers = {}
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value=None)

    trading_agent._sync_trade_outcome_recorder([])

    mock_dependencies["engine"].record_trade_outcome.assert_called_once_with(
        "decision-eth-open",
        exit_price=1986.0,
        exit_timestamp="2026-03-27T22:25:38+00:00",
    )



@pytest.mark.asyncio
async def test_process_cycle_stale_data_ends_cycle_without_looping(trading_agent, mock_dependencies, monkeypatch):
    from finance_feedback_engine.agent.trading_loop_agent import AgentState
    monkeypatch.setattr('finance_feedback_engine.agent.trading_loop_agent.validate_data_freshness', lambda **kwargs: (False, '10m', 'stale market data'))
    trading_agent.trade_monitor.monitoring_context_provider.get_monitoring_context = Mock(return_value={
        'asset_type': 'crypto',
        'latest_market_data_timestamp': '2026-03-27T00:00:00+00:00',
        'timeframe': 'intraday',
        'market_status': {'is_open': True},
        'current_timestamp': '2026-03-27T00:10:00+00:00',
    })
    trading_agent.state = AgentState.PERCEPTION
    trading_agent.is_running = True
    await trading_agent.process_cycle()
    assert trading_agent.state == AgentState.IDLE


@pytest.mark.asyncio
async def test_process_cycle_closed_market_staleness_ends_cycle_without_looping(trading_agent, mock_dependencies, monkeypatch):
    from finance_feedback_engine.agent.trading_loop_agent import AgentState
    monkeypatch.setattr('finance_feedback_engine.agent.trading_loop_agent.validate_data_freshness', lambda **kwargs: (False, '2d', 'closed-market stale weekend'))
    trading_agent.trade_monitor.monitoring_context_provider.get_monitoring_context = Mock(return_value={
        'asset_type': 'forex',
        'latest_market_data_timestamp': '2026-03-27T00:00:00+00:00',
        'timeframe': 'intraday',
        'market_status': {'is_open': False},
        'current_timestamp': '2026-03-29T00:10:00+00:00',
    })
    trading_agent.state = AgentState.PERCEPTION
    trading_agent.is_running = True
    await trading_agent.process_cycle()
    assert trading_agent.state == AgentState.IDLE


@pytest.mark.asyncio
async def test_process_cycle_empty_pairs_reasoning_ends_cycle_without_looping(trading_agent, mock_dependencies):
    from finance_feedback_engine.agent.trading_loop_agent import AgentState
    trading_agent.config.asset_pairs = []
    trading_agent.state = AgentState.REASONING
    trading_agent.is_running = True
    await trading_agent.process_cycle()
    assert trading_agent.state == AgentState.IDLE


def test_sync_trade_outcome_recorder_recovers_missing_decision_id_from_closed_trade_queue_after_tracker_cleanup(trading_agent, mock_dependencies):
    from queue import Queue
    from types import SimpleNamespace
    recorder = mock_dependencies['engine'].trade_outcome_recorder
    recorder.update_positions.return_value = [{
        'product': 'ETP-20DEC30-CDE',
        'side': 'SHORT',
        'exit_price': '1986.0',
        'exit_time': '2026-03-27T22:25:38+00:00',
        'realized_pnl': '0.85',
        'decision_id': None,
    }]
    mock_dependencies['engine'].record_trade_outcome.return_value = SimpleNamespace(realized_pnl=0.85)
    trading_agent.trade_monitor.expected_trades = {}
    trading_agent.trade_monitor.active_trackers = {}
    q = Queue()
    q.put({'product_id': 'ETP-20DEC30-CDE', 'side': 'SHORT', 'decision_id': 'decision-eth-open'})
    trading_agent.trade_monitor.closed_trades_queue = q
    trading_agent.trade_monitor.get_decision_id_by_asset = Mock(return_value=None)

    trading_agent._sync_trade_outcome_recorder([])

    mock_dependencies['engine'].record_trade_outcome.assert_called_once_with(
        'decision-eth-open',
        exit_price=1986.0,
        exit_timestamp='2026-03-27T22:25:38+00:00',
    )


def test_recover_decision_lineage_for_closed_outcome_skips_candidates_with_existing_outcome(
    trading_agent, mock_dependencies, tmp_path
):
    class _LegacyMemory:
        def __init__(self, storage_path):
            self.storage_path = storage_path

    class _MemoryEngine:
        def __init__(self, storage_path):
            self._legacy_engine = _LegacyMemory(storage_path)

    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "outcome_decision-recovery-btc.json").write_text("{}")
    mock_dependencies["engine"].memory_engine = _MemoryEngine(memory_dir)
    mock_dependencies["engine"].trade_outcome_recorder = MagicMock(open_positions={})
    mock_dependencies["trade_monitor"].expected_trades = {}
    mock_dependencies["trade_monitor"].active_trackers = {}
    mock_dependencies["trade_monitor"].closed_trades_queue = MagicMock(queue=[])
    mock_dependencies["trade_monitor"].get_decision_id_by_asset.return_value = None
    mock_dependencies["engine"].decision_store.get_recent_decisions.return_value = [
        {
            "id": "decision-recovery-btc",
            "asset_pair": "BIP20DEC30CDE",
            "action": "SELL",
            "ai_provider": "recovery",
            "recovery_metadata": {"product_id": "BIP-20DEC30-CDE", "platform": "coinbase"},
        }
    ]

    decision_id, lineage_source, attempted_sources = trading_agent._recover_decision_lineage_for_closed_outcome(
        {
            "product": "BIP-20DEC30-CDE",
            "side": "SHORT",
            "order_id": "order-btc-close",
        }
    )

    assert decision_id is None
    assert lineage_source == "no-hit"
    assert "decision_store.recovery_metadata_product" in attempted_sources


@pytest.mark.asyncio
async def test_execution_state_passes_modified_decision_for_derisking_metadata(trading_agent, mock_dependencies):
    decision = {
        "id": "decision-derisking-metadata",
        "action": "REDUCE_LONG",
        "policy_action": "REDUCE_LONG",
        "asset_pair": "BTCUSD",
        "entry_price": 6352.10,
        "recommended_position_size": 1.0,
        "suggested_amount": 6352.10,
        "execution_metadata": {"execution_amount_usd": 6352.10},
        "control_outcome": {"status": "proposed", "version": 1},
        "policy_package": {"control_outcome": {"status": "proposed", "version": 1}, "version": 1},
    }
    async with trading_agent._current_decisions_lock:
        trading_agent._current_decisions = [decision]
    trading_agent.state = AgentState.EXECUTION

    trading_agent.engine.execute_decision_async = AsyncMock(return_value={
        "success": True,
        "message": "order placed",
        "order_id": "abc123",
    })

    await trading_agent.handle_execution_state()

    trading_agent.engine.execute_decision_async.assert_awaited_once_with(
        "decision-derisking-metadata",
        modified_decision=decision,
    )
    assert decision["execution_status"] == "executed"
