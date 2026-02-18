"""Hard-gate regression tests for core profit-readiness path.

These tests are deterministic and isolate profitability-critical behavior:
1) Data freshness must block stale perception input.
2) Risk-check must only pass approved decisions to execution.
3) Execution failure must rollback exposure reservation.
"""

import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from finance_feedback_engine.agent.config import AutonomousAgentConfig, TradingAgentConfig
from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent


@pytest.fixture
def minimal_config():
    config = TradingAgentConfig(
        asset_pairs=["BTCUSD"],
        autonomous=AutonomousAgentConfig(enabled=True),
        analysis_frequency_seconds=60,
        max_daily_trades=10,
        max_drawdown_percent=0.2,
        correlation_threshold=0.7,
        max_correlated_assets=3,
        max_var_pct=0.05,
        var_confidence=0.95,
        main_loop_error_backoff_seconds=30,
    )
    object.__setattr__(config, "telegram", {})
    return config


@pytest.fixture
def mock_engine():
    engine = Mock()
    engine.validate_agent_readiness = Mock(return_value=(True, []))
    engine.config = {"safety": {"max_leverage": 5.0, "max_position_pct": 25.0}}
    engine.position_sizing_calculator = Mock()
    engine.position_sizing_calculator.calculate_position_sizing_params = Mock(
        return_value={"recommended_position_size": 0.1}
    )
    engine.execute_decision_async = AsyncMock(return_value={"success": False, "error": "insufficient_funds"})
    return engine


@pytest.fixture
def mock_trade_monitor():
    monitor = Mock()
    monitor.associate_decision_to_trade = Mock()
    monitor.monitoring_context_provider = Mock()
    monitor.monitoring_context_provider.get_monitoring_context = Mock(
        return_value={
            "latest_market_data_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "asset_type": "crypto",
            "timeframe": "intraday",
            "market_status": {"is_open": True, "session": "Regular"},
            "unrealized_pnl_percent": 0.0,
        }
    )
    return monitor


@pytest.fixture
def agent(minimal_config, mock_engine, mock_trade_monitor):
    return TradingLoopAgent(
        config=minimal_config,
        engine=mock_engine,
        trade_monitor=mock_trade_monitor,
        portfolio_memory=Mock(trade_outcomes=[]),
        trading_platform=Mock(),
    )


@pytest.mark.asyncio
async def test_perception_halts_on_stale_data(agent):
    """Perception must not advance when market data is stale."""
    agent.state = AgentState.PERCEPTION

    with patch(
        "finance_feedback_engine.agent.trading_loop_agent.validate_data_freshness",
        return_value=(False, "46m", "Data is stale"),
    ):
        await agent.handle_perception_state()

    assert agent.state == AgentState.PERCEPTION

    events = []
    while not agent._dashboard_event_queue.empty():
        events.append(agent._dashboard_event_queue.get_nowait())

    assert any(e.get("type") == "data_freshness_failed" for e in events)


@pytest.mark.asyncio
async def test_risk_check_only_advances_approved_decisions(agent):
    """Risk gate must filter rejected decisions before execution."""
    approved = {
        "id": "dec-1",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 80,
        "entry_price": 50000.0,
    }
    rejected = {
        "id": "dec-2",
        "asset_pair": "ETHUSD",
        "action": "BUY",
        "confidence": 65,
        "entry_price": 2500.0,
    }

    agent.state = AgentState.RISK_CHECK
    agent._current_decisions = [approved, rejected]
    agent.risk_gatekeeper.validate_trade = Mock(side_effect=[(True, "ok"), (False, "drawdown breach")])

    exposure_manager = Mock()
    exposure_manager.reserve_exposure = Mock()

    with patch(
        "finance_feedback_engine.agent.trading_loop_agent.get_exposure_manager",
        return_value=exposure_manager,
    ):
        await agent.handle_risk_check_state()

    assert agent.state == AgentState.EXECUTION
    assert [d["id"] for d in agent._current_decisions] == ["dec-1"]
    assert "dec-2" in agent._rejected_decisions_cache


@pytest.mark.asyncio
async def test_execution_failure_rolls_back_exposure(agent, mock_trade_monitor):
    """Failed execution must rollback reserved exposure and continue cycle safely."""
    agent.state = AgentState.EXECUTION
    agent._current_decisions = [
        {
            "id": "dec-fail-1",
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "confidence": 90,
            "recommended_position_size": 0.1,
            "entry_price": 50000.0,
        }
    ]

    exposure_manager = Mock()
    exposure_manager.rollback_reservation = Mock()
    exposure_manager.clear_stale_reservations = Mock(return_value=0)

    with patch(
        "finance_feedback_engine.agent.trading_loop_agent.get_exposure_manager",
        return_value=exposure_manager,
    ):
        await agent.handle_execution_state()

    exposure_manager.rollback_reservation.assert_called_once_with("dec-fail-1")
    assert agent.state == AgentState.LEARNING
    assert agent.daily_trade_count == 0
    mock_trade_monitor.associate_decision_to_trade.assert_not_called()
