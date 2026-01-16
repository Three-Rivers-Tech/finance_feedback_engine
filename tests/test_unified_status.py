import pytest
from finance_feedback_engine.api.unified_status import (
    UnifiedAgentStatus,
    AgentStateMapper,
)
from finance_feedback_engine.api.bot_control import BotState
from finance_feedback_engine.agent.trading_loop_agent import AgentState


def test_offline_status():
    """Test OFFLINE status mapping."""
    status = AgentStateMapper.get_unified_status(BotState.STOPPED, None)
    assert status == UnifiedAgentStatus.OFFLINE
    assert not AgentStateMapper.is_operational(status)


def test_transitioning_status():
    """Test TRANSITIONING status mapping."""
    status = AgentStateMapper.get_unified_status(BotState.STARTING, None)
    assert status == UnifiedAgentStatus.TRANSITIONING
    assert not AgentStateMapper.is_operational(status)
    assert not AgentStateMapper.can_accept_commands(status)

    status = AgentStateMapper.get_unified_status(BotState.STOPPING, None)
    assert status == UnifiedAgentStatus.TRANSITIONING
    assert not AgentStateMapper.is_operational(status)
    assert not AgentStateMapper.can_accept_commands(status)


def test_initializing_status():
    """
    INITIALIZING status scenario:
    When BotState.RUNNING and AgentState.RECOVERING are combined, AgentStateMapper.get_unified_status is expected to return UnifiedAgentStatus.INITIALIZING. This reflects that the agent is running but still in a recovery phase, so it is not yet fully operational. Therefore, AgentStateMapper.is_operational(status) should return False for this status.
    """
    status = AgentStateMapper.get_unified_status(
        BotState.RUNNING, AgentState.RECOVERING
    )
    assert status == UnifiedAgentStatus.INITIALIZING
    assert not AgentStateMapper.is_operational(status)


def test_ready_status():
    """Test READY status."""
    status = AgentStateMapper.get_unified_status(
        BotState.RUNNING, AgentState.IDLE
    )
    assert status == UnifiedAgentStatus.READY
    assert AgentStateMapper.is_operational(status)
    assert AgentStateMapper.can_accept_commands(status)


@pytest.mark.parametrize(
    "agent_state",
    [
        AgentState.PERCEPTION,
        AgentState.REASONING,
        AgentState.RISK_CHECK,
        AgentState.EXECUTION,
        AgentState.LEARNING,
    ]
)
def test_active_status(agent_state):
    """Test ACTIVE status for all working states."""
    status = AgentStateMapper.get_unified_status(
        BotState.RUNNING, agent_state
    )
    assert status == UnifiedAgentStatus.ACTIVE
    assert AgentStateMapper.is_operational(status)


def test_error_status():
    """Test ERROR status takes precedence for all AgentState values."""
    for agent_state in [
        None,
        AgentState.IDLE,
        AgentState.EXECUTION,
        AgentState.PERCEPTION,
    ]:
        status = AgentStateMapper.get_unified_status(
            BotState.ERROR, agent_state
        )
        assert status == UnifiedAgentStatus.ERROR
        assert not AgentStateMapper.is_operational(status)


def test_status_descriptions():
    """Test human-readable descriptions for all UnifiedAgentStatus values."""
    desc = AgentStateMapper.get_status_description(UnifiedAgentStatus.INITIALIZING)
    assert "initializing" in desc.lower()
    assert "positions" in desc.lower()

    desc = AgentStateMapper.get_status_description(UnifiedAgentStatus.OFFLINE)
    assert any(kw in desc.lower() for kw in ["offline", "disconnected"])

    desc = AgentStateMapper.get_status_description(UnifiedAgentStatus.READY)
    assert any(kw in desc.lower() for kw in ["ready", "idle"])

    desc = AgentStateMapper.get_status_description(UnifiedAgentStatus.ACTIVE)
    assert any(kw in desc.lower() for kw in ["active", "running"])

    desc = AgentStateMapper.get_status_description(UnifiedAgentStatus.ERROR)
    assert any(kw in desc.lower() for kw in ["error", "failed", "failure"])
