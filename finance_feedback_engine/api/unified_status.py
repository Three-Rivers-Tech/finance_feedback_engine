from enum import Enum
from typing import Optional, TYPE_CHECKING
import logging

from ..agent.trading_loop_agent import AgentState

# Avoid circular import by using TYPE_CHECKING
if TYPE_CHECKING:
    from .bot_control import BotState

logger = logging.getLogger(__name__)


class UnifiedAgentStatus(Enum):
    """
    Unified client-facing agent status that combines lifecycle and operational states.

    This provides a clear, single status field for API consumers without requiring them
    to interpret both BotState and AgentState.
    """

    # Agent is stopped/not running
    OFFLINE = "offline"

    # Agent is starting up or shutting down
    TRANSITIONING = "transitioning"

    # Agent is running but still initializing (recovering positions, loading data, etc.)
    INITIALIZING = "initializing"

    # Agent is running and ready to trade (idle, waiting for signal)
    READY = "ready"

    # Agent is actively working (perceiving, reasoning, executing)
    ACTIVE = "active"

    # Agent encountered an error
    ERROR = "error"


class AgentStateMapper:
    """
    Maps the combination of BotState and AgentState to a unified client-facing status.

    This follows the State Machine REST API pattern where the API communicates
    the current state to consumers in a clear, unambiguous manner.
    """

    @staticmethod
    def get_unified_status(
        bot_state: "BotState",
        agent_state: Optional[AgentState]
    ) -> UnifiedAgentStatus:
        """
        Derive unified status from lifecycle and operational states.

        Args:
            bot_state (BotState): Lifecycle state (stopped, running, etc.)
            agent_state (Optional[AgentState]): OODA loop state (idle, perceiving, etc.)

        Returns:
            UnifiedAgentStatus: Clear client-facing status.
        """
        # Import at runtime to avoid circular import
        from .bot_control import BotState

        # Error state takes precedence
        if bot_state == BotState.ERROR:
            return UnifiedAgentStatus.ERROR

        # Stopped
        if bot_state == BotState.STOPPED:
            return UnifiedAgentStatus.OFFLINE

        # Transitioning (starting/stopping)
        if bot_state in (BotState.STARTING, BotState.STOPPING):
            return UnifiedAgentStatus.TRANSITIONING

        # Running - now check OODA state
        if bot_state == BotState.RUNNING:
            if agent_state is None:
                return UnifiedAgentStatus.READY

            # Initializing states
            if agent_state == AgentState.RECOVERING:
                return UnifiedAgentStatus.INITIALIZING

            # Ready state
            if agent_state == AgentState.IDLE:
                return UnifiedAgentStatus.READY

            # Active states (working on something)
            if agent_state in (
                AgentState.PERCEPTION,
                AgentState.REASONING,
                AgentState.RISK_CHECK,
                AgentState.EXECUTION,
                AgentState.LEARNING
            ):
                return UnifiedAgentStatus.ACTIVE

        # Fallback to offline if states are unrecognized
        logger.warning(
            "Unrecognized state combination: bot_state=%s, agent_state=%s", bot_state, agent_state
        )
        # Return ERROR to signal an unexpected state rather than OFFLINE which is misleading
        return UnifiedAgentStatus.ERROR

    @staticmethod
    def get_status_description(status: UnifiedAgentStatus) -> str:
        """Provide human-readable description of unified status."""
        # Exhaustive dispatch for UnifiedAgentStatus
        match status:
            case UnifiedAgentStatus.OFFLINE:
                return "Agent is offline and not running."
            case UnifiedAgentStatus.TRANSITIONING:
                return "Agent is transitioning between states."
            case UnifiedAgentStatus.INITIALIZING:
                return "Agent is initializing (recovering positions, loading data)."
            case UnifiedAgentStatus.READY:
                return "Agent is ready to start trading."
            case UnifiedAgentStatus.ACTIVE:
                return "Agent is actively trading."
            case UnifiedAgentStatus.ERROR:
                return "Agent encountered an error."
            case _:
                raise AssertionError(f"Unknown UnifiedAgentStatus: {status}")

    @staticmethod
    def is_operational(status: UnifiedAgentStatus) -> bool:
        """
        Check if the agent is operational (ready or active).
        This means the agent is able to process trades and respond to signals.
        """
        return status in (UnifiedAgentStatus.READY, UnifiedAgentStatus.ACTIVE)

    @staticmethod
    def can_accept_commands(status: UnifiedAgentStatus) -> bool:
        """
        Check if the agent can accept manual trade commands.
        This delegates to is_operational; if future logic differs, update here.
        """
        return AgentStateMapper.is_operational(status)
