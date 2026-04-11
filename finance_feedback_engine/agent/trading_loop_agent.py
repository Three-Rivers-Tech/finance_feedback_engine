# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import datetime
import logging
import queue
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, Optional

from opentelemetry import metrics, trace

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.trade_execution_safety import (
    clear_stale_reservations,
    finalize_trade_reservation,
    reserve_trade_exposure,
)
from finance_feedback_engine.decision_engine.execution_quality import (
    ExecutionQualityControls,
    evaluate_signal_quality,
)
from finance_feedback_engine.decision_engine.policy_actions import (
    build_control_outcome,
    get_legacy_action_compatibility,
    get_policy_action_family,
    is_policy_action,
    normalize_policy_action,
)
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.persistence.decision_store import normalize_decision_record

try:
    from finance_feedback_engine.monitoring.pending_linkage_store import PendingLinkageStore
except ImportError:
    PendingLinkageStore = None

try:
    from finance_feedback_engine.decision_engine.sortino_gate import SortinoGate, SortinoGateResult
except ImportError:
    SortinoGate = None  # Graceful degradation
    SortinoGateResult = None
from finance_feedback_engine.monitoring.prometheus import (
    increment_dashboard_events_dropped,
    update_agent_state,
    update_dashboard_queue_metrics,
    update_decision_confidence,
)
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.risk.exposure_reservation import get_exposure_manager
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform
from finance_feedback_engine.utils import validate_data_freshness
from finance_feedback_engine.utils.environment import is_development, is_production
from finance_feedback_engine.utils.retry import RetryConfig, exponential_backoff_retry
from finance_feedback_engine.utils.shape_normalization import (
    asset_key_candidates,
    normalize_scalar_id,
)
from finance_feedback_engine.utils.validation import standardize_asset_pair
from finance_feedback_engine.utils.product_id import product_id_to_asset_pair as _pid_to_pair

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)


def _derive_execution_intent(
    decision: Dict[str, Any]
) -> Dict[str, Optional[str] | bool]:
    """Derive execution intent from canonical policy actions or legacy actions.

    Entry-like policy actions expose an ``entry_side`` for duplicate-entry guards.
    Reduce/close actions remain actionable but skip duplicate-entry blocking because
    they unwind or reduce existing exposure rather than stack it.
    """
    raw_action = None
    if isinstance(decision, dict):
        raw_action = decision.get("policy_action") or decision.get("action")

    if raw_action is None:
        return {
            "canonical_action": None,
            "policy_action": None,
            "policy_action_family": None,
            "legacy_action": None,
            "entry_side": None,
            "position_side": None,
            "is_actionable": False,
        }

    if is_policy_action(raw_action):
        family = get_policy_action_family(raw_action)
        entry_side = None
        position_side = None
        legacy_action = None
        is_actionable = family != "hold"

        if family in {"open_long", "add_long"}:
            entry_side = "LONG"
            position_side = "LONG"
            legacy_action = "BUY"
        elif family in {"open_short", "add_short"}:
            entry_side = "SHORT"
            position_side = "SHORT"
            legacy_action = "SELL"
        elif family in {"reduce_long", "close_long"}:
            position_side = "LONG"
        elif family in {"reduce_short", "close_short"}:
            position_side = "SHORT"

        return {
            "canonical_action": str(raw_action),
            "policy_action": str(raw_action),
            "policy_action_family": family,
            "legacy_action": legacy_action,
            "entry_side": entry_side,
            "position_side": position_side,
            "is_actionable": is_actionable,
        }

    legacy_action = str(raw_action).upper()
    if legacy_action not in {"BUY", "SELL", "HOLD"}:
        return {
            "canonical_action": legacy_action,
            "policy_action": None,
            "policy_action_family": None,
            "legacy_action": None,
            "entry_side": None,
            "position_side": None,
            "is_actionable": False,
        }

    side = (
        "LONG"
        if legacy_action == "BUY"
        else "SHORT" if legacy_action == "SELL" else None
    )
    return {
        "canonical_action": legacy_action,
        "policy_action": None,
        "policy_action_family": None,
        "legacy_action": legacy_action,
        "entry_side": side,
        "position_side": side,
        "is_actionable": legacy_action in {"BUY", "SELL"},
    }


class AgentState(Enum):
    """Represents the current state of the trading agent."""

    IDLE = auto()
    RECOVERING = auto()
    PERCEPTION = auto()
    REASONING = auto()
    RISK_CHECK = auto()
    EXECUTION = auto()
    LEARNING = auto()


# Prometheus-friendly mapping for OODA states. Values align with the gauge docstring
# in finance_feedback_engine.monitoring.prometheus.agent_state.
STATE_METRIC_VALUES: dict[AgentState, int] = {
    AgentState.IDLE: 0,
    AgentState.RECOVERING: 1,
    AgentState.LEARNING: 2,
    AgentState.PERCEPTION: 3,
    AgentState.REASONING: 4,
    AgentState.RISK_CHECK: 5,
    AgentState.EXECUTION: 6,
}


@dataclass
class LoopMetrics:
    """Lightweight OODA timing metrics for cycle-level observability."""

    cycles_completed: int = 0
    cumulative_phase_durations: dict[str, float] = field(
        default_factory=lambda: {
            "PERCEPTION": 0.0,
            "REASONING": 0.0,
            "RISK_CHECK": 0.0,
            "EXECUTION": 0.0,
            "LEARNING": 0.0,
        }
    )
    last_cycle_phase_durations: dict[str, float] = field(default_factory=dict)
    last_cycle_total_duration: float = 0.0

    def record_phase(self, phase_name: str, duration_seconds: float) -> None:
        self.cumulative_phase_durations[phase_name] = (
            self.cumulative_phase_durations.get(phase_name, 0.0) + duration_seconds
        )

    def finalize_cycle(self, cycle_phase_durations: dict[str, float]) -> None:
        self.cycles_completed += 1
        self.last_cycle_phase_durations = dict(cycle_phase_durations)
        self.last_cycle_total_duration = sum(cycle_phase_durations.values())


class _TokenBucketRateLimiter:
    """Async token-bucket limiter for pacing provider calls without fixed sleeps."""

    def __init__(self, rate_per_second: float, burst: int = 1):
        self.rate_per_second = max(0.0, float(rate_per_second))
        self.capacity = max(1.0, float(burst))
        self.tokens = self.capacity
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until at least one token is available, then consume it."""
        if self.rate_per_second <= 0:
            return

        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.updated_at
                self.updated_at = now
                self.tokens = min(
                    self.capacity, self.tokens + elapsed * self.rate_per_second
                )

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                wait_time = (1.0 - self.tokens) / self.rate_per_second

            await asyncio.sleep(wait_time)


class TradingLoopAgent:
    """
    An autonomous agent that runs a continuous trading loop based on a state machine.
    """

    def __init__(
        self: Any,
        config: TradingAgentConfig,
        engine: Any,  # FinanceFeedbackEngine
        trade_monitor: TradeMonitor,
        portfolio_memory: PortfolioMemoryEngine,
        trading_platform: BaseTradingPlatform,
    ):
        self.config = config
        self.engine = engine
        self.trade_monitor = trade_monitor
        self.portfolio_memory = portfolio_memory
        self.trading_platform = trading_platform

        # Initialize RiskGatekeeper with configured risk parameters
        # Normalize percentage-like inputs: allow users to input >1 as whole percentages
        def _normalize_pct(value: float) -> float:
            try:
                return value / 100.0 if value > 1.0 else value
            except Exception:
                return value

        # Environment-aware risk configuration
        import os

        is_development = os.environ.get("ENVIRONMENT", "").lower() == "development"

        # Get risk parameters: use development defaults if in dev mode, else use config
        if is_development and hasattr(self.config, "__dict__"):
            # In development mode, use relaxed defaults from config.development_risk_limits
            # These allow portfolio building and testing without over-restrictive gates
            dev_limits = getattr(self.config, "development_risk_limits", {})
            if isinstance(dev_limits, dict):
                correlation_threshold = dev_limits.get(
                    "correlation_threshold", self.config.correlation_threshold
                )
                max_correlated_assets = dev_limits.get(
                    "max_correlated_assets", self.config.max_correlated_assets
                )
                max_var_pct = dev_limits.get("max_var_pct", self.config.max_var_pct)
                var_confidence = dev_limits.get(
                    "var_confidence", self.config.var_confidence
                )
                logger.info(
                    "RiskGatekeeper: Using development-mode relaxed constraints"
                )
            else:
                # Fallback to config defaults
                correlation_threshold = self.config.correlation_threshold
                max_correlated_assets = self.config.max_correlated_assets
                max_var_pct = self.config.max_var_pct
                var_confidence = self.config.var_confidence
        else:
            # Production mode: use strict defaults from config
            correlation_threshold = self.config.correlation_threshold
            max_correlated_assets = self.config.max_correlated_assets
            max_var_pct = self.config.max_var_pct
            var_confidence = self.config.var_confidence

        self.risk_gatekeeper = RiskGatekeeper(
            max_drawdown_pct=_normalize_pct(self.config.max_drawdown_percent),
            correlation_threshold=correlation_threshold,
            max_correlated_assets=max_correlated_assets,
            max_var_pct=_normalize_pct(max_var_pct),
            var_confidence=var_confidence,
        )
        self.is_running = False

        # Health check configuration
        self._health_check_frequency = getattr(
            self.config, "health_check_frequency_decisions", 10
        )
        self._decisions_since_health_check = 0
        self._paused = False
        self.state = AgentState.IDLE
        self._current_decisions = []  # Store multiple decisions for batch processing
        # Lock for protecting current_decisions list from concurrent modification
        self._current_decisions_lock = asyncio.Lock()
        # Lock for atomic state transitions (THR-81)
        self._state_transition_lock = asyncio.Lock()

        # Asset pairs lock removed as part of THR-172 cleanup
        # Track analysis failures and their timestamps for time-based decay
        self.analysis_failures = {}  # {failure_key: count}
        self.analysis_failure_timestamps = {}  # {failure_key: last_failure_datetime}
        self.daily_trade_count = 0
        self.last_trade_date = datetime.date.today()

        # Enhanced backtesting and risk metrics tracking
        self._performance_metrics = {
            "total_pnl": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "current_streak": 0,
            "best_streak": 0,
            "worst_streak": 0,
        }

        # Startup recovery tracking
        self._startup_complete = asyncio.Event()
        self._recovered_positions = []  # List of recovered position metadata
        self._startup_retry_count = 0
        self._max_startup_retries = 3
        self._recovery_has_run = False
        self._recovered_position_keys: set[
            tuple[str | None, str | None, str, float, float]
        ] = set()

        # For preventing infinite loops on rejected trades
        self._rejected_decisions_cache = (
            {}
        )  # {decision_id: (rejection_timestamp, asset_pair)}
        self._rejection_cooldown_seconds = 300  # 5 minutes cooldown

        # Dashboard event queue for real-time updates
        import queue

        resolved_queue_size = getattr(self.config, "dashboard_event_queue_size", 0)
        if not resolved_queue_size:
            # Environment-based defaults (fail-safe to 100 if detection fails)
            if is_production():
                resolved_queue_size = 1000
            else:
                # Treat anything not explicitly production as dev/staging-sized
                resolved_queue_size = 50

        self._dashboard_event_queue = queue.Queue(maxsize=resolved_queue_size)
        self._cycle_count = 0
        self._start_time = None  # Will be set in run()
        self._current_cycle_id: str | None = None
        self._cycle_retry_budget: dict[str, int] = {}
        self._loop_metrics = LoopMetrics()

        # Property for dashboard to track if stop was requested
        self.stop_requested = False

        # Batch review tracking (every 20 trades)
        self._batch_review_counter = 0
        self._kelly_activated = False
        self._last_batch_review_time = None

        # Track SK: Sortino-gated adaptive Kelly position sizing
        from collections import deque
        self._trade_pnl_history: deque[float] = deque(maxlen=500)
        self._sortino_gate = SortinoGate() if SortinoGate is not None else None
        self._last_sortino_gate_result: SortinoGateResult | None = None
        self._preload_trade_pnl_history()  # Phase 4: load from durable outcomes

        # Validate notification delivery path on startup
        notification_valid, notification_errors = self._validate_notification_config()
        if not notification_valid:
            error_msg = (
                "Cannot start agent in signal-only mode without valid notification delivery.\n"
                f"Configuration errors: {', '.join(notification_errors)}\n"
                "Please either:\n"
                "1. Configure Telegram notifications (telegram.enabled=true, bot_token, chat_id)\n"
                "2. Enable autonomous mode (autonomous.enabled=true)\n"
                "3. Set ENVIRONMENT=development for development without notifications\n"
                "4. Enable signal-only mode with require_notifications_for_signal_only=false\n"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("✓ Notification delivery validated")

        # Validate agent readiness (ensemble config, risk limits, Ollama connectivity)
        readiness_result = self.engine.validate_agent_readiness()
        # Support tuple, list, None, or single mock value for tests
        if isinstance(readiness_result, tuple) and len(readiness_result) == 2:
            is_ready, readiness_errors = readiness_result
        elif isinstance(readiness_result, list) and len(readiness_result) == 2:
            is_ready, readiness_errors = readiness_result
        elif hasattr(readiness_result, "__iter__") and not isinstance(
            readiness_result, str
        ):
            try:
                is_ready, readiness_errors = list(readiness_result)[:2]
            except Exception:
                is_ready, readiness_errors = True, []
        elif readiness_result is None:
            is_ready, readiness_errors = True, []
        else:
            is_ready, readiness_errors = True, []
        if not is_ready:
            error_msg = (
                "Cannot start agent - runtime validation failed.\n"
                f"Validation errors ({len(readiness_errors)}):\n"
            )
            for i, err in enumerate(readiness_errors, 1):
                error_msg += f"  {i}. {err}\n"
            error_msg += (
                "\nPlease fix the configuration issues above and try again. "
                "Check config/config.yaml or config/config.local.yaml"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("✓ Agent readiness validation passed")

        # Validate Ollama readiness for local/debate mode
        # Centralized Ollama skip logic for tests and mocks
        import os

        skip_ollama = False
        if os.environ.get("PYTEST_CURRENT_TEST"):
            skip_ollama = True
        else:
            try:
                from unittest.mock import MagicMock, Mock

                if isinstance(self.engine, (Mock, MagicMock)):
                    skip_ollama = True
            except ImportError:
                pass

        if not skip_ollama:
            # Validate Ollama readiness for local/debate mode
            engine_config = getattr(self.engine, "config", {})
            if not isinstance(engine_config, dict):
                engine_config = {}

            decision_engine_config = engine_config.get("decision_engine", {})
            ai_provider = decision_engine_config.get("ai_provider", "local")
            ensemble_config = engine_config.get("ensemble", {})
            debate_mode = ensemble_config.get("debate_mode", False)
            debate_providers = ensemble_config.get(
                "debate_providers", {"bull": "local", "bear": "local", "judge": "local"}
            )

            requires_ollama = (
                ai_provider == "local" or ai_provider == "ensemble" or debate_mode
            )

            if requires_ollama:
                try:
                    from finance_feedback_engine.utils.ollama_readiness import (
                        verify_ollama_for_agent,
                    )

                    ollama_ready, ollama_err = verify_ollama_for_agent(
                        engine_config, debate_mode, debate_providers
                    )
                    if not ollama_ready:
                        logger.error(f"Ollama readiness check failed: {ollama_err}")
                        raise ValueError(
                            f"Agent requires Ollama but service is unavailable:\n{ollama_err}\n"
                            "Please start Ollama and ensure required models are installed."
                        )
                    logger.info("✓ Ollama readiness validated")
                except ImportError:
                    logger.warning(
                        "Ollama readiness checker not available; skipping validation"
                    )
                except ValueError:
                    raise  # Re-raise readiness failures
                except Exception as e:
                    logger.warning(f"Ollama readiness check encountered error: {e}")
        else:
            pass

        # State machine handler map
        self.state_handlers = {
            AgentState.IDLE: self.handle_idle_state,
            AgentState.RECOVERING: self.handle_recovering_state,
            AgentState.PERCEPTION: self.handle_perception_state,
            AgentState.REASONING: self.handle_reasoning_state,
            AgentState.RISK_CHECK: self.handle_risk_check_state,
            AgentState.EXECUTION: self.handle_execution_state,
            AgentState.LEARNING: self.handle_learning_state,
        }

        # Initialize gauge with starting state
        self._record_state_metric()

        # Pair selection system removed as part of THR-172 cleanup

        # Pair selection initialization removed as part of THR-172 cleanup

    @property
    def start_time(self):
        """Public accessor for start time (returns datetime object)."""
        if self._start_time is None:
            return None
        return datetime.datetime.fromtimestamp(
            self._start_time, tz=datetime.timezone.utc
        )

    @property
    def is_autonomous_enabled(self) -> bool:
        """
        Check if autonomous execution mode is enabled.

        Checks both new config format (autonomous.enabled) and legacy format
        (autonomous_execution) for backward compatibility.

        Returns:
            bool: True if autonomous execution is enabled
        """
        if hasattr(self.config, "autonomous") and hasattr(
            self.config.autonomous, "enabled"
        ):
            return self.config.autonomous.enabled
        return getattr(self.config, "autonomous_execution", False)

    def supports_signal_only_mode(self) -> bool:
        """
        Check if this agent implementation supports signal-only mode.

        Signal-only mode requires:
        1. _send_signals_to_telegram() method exists
        2. Agent checks autonomous.enabled flag in execution
        3. Notification delivery mechanism is available

        Returns:
            bool: True if signal-only mode is supported
        """
        # Verify critical methods exist
        if not hasattr(self, "_send_signals_to_telegram"):
            logger.error("Agent missing _send_signals_to_telegram() method")
            return False

        # Verify execution handler checks autonomous flag
        if not hasattr(self, "handle_execution_state"):
            logger.error("Agent missing handle_execution_state() method")
            return False

        # All requirements met
        return True

    def _validate_ollama_readiness(self) -> None:
        """
        Validate Ollama is running and models are available.

        Raises:
            ValueError: If Ollama check fails
        """
        import os

        # Skip Ollama check in test environments (pytest or mock engine)
        skip_ollama = False
        if os.environ.get("PYTEST_CURRENT_TEST"):
            skip_ollama = True
        else:
            try:
                from unittest.mock import MagicMock, Mock

                if isinstance(getattr(self, "engine", None), (Mock, MagicMock)):
                    skip_ollama = True
            except ImportError:
                pass
        if skip_ollama:
            logger.info("Skipping Ollama readiness validation in test environment.")
            return
        try:
            from finance_feedback_engine.utils.ollama_readiness import (
                verify_ollama_for_agent,
            )

            # Get full config from engine (includes decision_engine and ensemble sections)
            # TradingAgentConfig only has agent-specific settings
            full_config = (
                getattr(self.engine, "config", {}) if hasattr(self, "engine") else {}
            )

            if not full_config:
                logger.debug("Engine config not available; skipping Ollama validation")
                return

            # Extract decision_engine and ensemble config safely
            decision_engine = full_config.get("decision_engine", {})
            if not isinstance(decision_engine, dict):
                decision_engine = {}

            ensemble_config = full_config.get("ensemble", {})
            if not isinstance(ensemble_config, dict):
                ensemble_config = {}

            ai_provider = decision_engine.get("ai_provider", "local")
            debate_mode = ensemble_config.get("debate_mode", False)
            debate_providers = ensemble_config.get(
                "debate_providers", {"bull": "local", "bear": "local", "judge": "local"}
            )

            requires_ollama = (
                ai_provider == "local" or ai_provider == "ensemble" or debate_mode
            )

            if requires_ollama:
                ollama_ready, ollama_err = verify_ollama_for_agent(
                    full_config, debate_mode, debate_providers
                )
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Ollama readiness check failed: {e}; proceeding anyway")

    def _validate_notification_config(self) -> tuple[bool, list[str]]:
        """
        Validate notification delivery configuration on startup.

        Returns:
            (is_valid, list_of_errors)

        Notifications are required unless:
        - Autonomous mode is enabled (autonomous.enabled=true), OR
        - Running in development environment (ENVIRONMENT=development), OR
        - Signal-only mode is explicitly allowed without notifications
        """
        import os

        errors = []

        # Check if autonomous mode is enabled (no notifications needed)
        if self.is_autonomous_enabled:
            logger.info("Autonomous mode enabled - skipping notification validation")
            return True, []  # Autonomous mode doesn't need notifications

        # Check if running in development environment (allow without notifications)
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "development":
            logger.info(
                "Development environment detected - skipping notification validation"
            )
            return True, []

        # Check if signal-only mode allows running without notifications
        require_notifications = getattr(
            self.config, "require_notifications_for_signal_only", True
        )
        if not require_notifications:
            logger.info(
                "Signal-only mode configured without notification requirement - skipping validation"
            )
            return True, []

        # Validate Telegram configuration
        telegram_config = getattr(self.config, "telegram", None)
        if not telegram_config:
            errors.append("Telegram config missing")
            return False, errors

        telegram_enabled = telegram_config.get("enabled", False)
        telegram_token = telegram_config.get("bot_token")
        telegram_chat_id = telegram_config.get("chat_id")

        if not telegram_enabled:
            errors.append("Telegram not enabled")
        if not telegram_token:
            errors.append("Telegram bot_token missing")
        if not telegram_chat_id:
            errors.append("Telegram chat_id missing")

        if errors:
            return False, errors

        return True, []

    async def run(self):
        """
        The main trading loop, implemented as a state machine.

        This method handles initialization (position recovery) and then enters
        a continuous loop that calls process_cycle() followed by a sleep interval.
        """
        with tracer.start_as_current_span("agent.ooda.run") as span:
            span.set_attribute("agent.started", True)
            logger.info("Starting autonomous trading agent...")
            self.is_running = True
            self._start_time = time.time()  # For uptime tracking

            # Transition to RECOVERING state immediately
            # (position recovery is now a proper OODA state)
            await self._transition_to(AgentState.RECOVERING)

            # Pair scheduler start logic removed as part of THR-172 cleanup

            # Main loop: process cycles with sleep intervals
            while self.is_running:
                try:
                    # Execute one complete OODA cycle
                    cycle_successful = await self.process_cycle()

                    if not cycle_successful:
                        logger.warning(
                            "Cycle execution failed, backing off before retry"
                        )
                        await asyncio.sleep(self.config.main_loop_error_backoff_seconds)
                    else:
                        # Increment cycle counter for dashboard
                        self._cycle_count += 1
                        # Normal sleep between analysis cycles
                        await asyncio.sleep(self.config.analysis_frequency_seconds)

                except asyncio.CancelledError:
                    logger.info("Trading loop cancelled.")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                    await asyncio.sleep(self.config.main_loop_error_backoff_seconds)

    # Valid state transitions — prevents illegal jumps (e.g. skipping RISK_CHECK)
    _VALID_TRANSITIONS: dict[AgentState, set[AgentState]] = {
        AgentState.IDLE: {
            AgentState.RECOVERING,
            AgentState.PERCEPTION,
            AgentState.LEARNING,
        },
        AgentState.RECOVERING: {AgentState.IDLE, AgentState.PERCEPTION},
        AgentState.PERCEPTION: {AgentState.REASONING, AgentState.IDLE},
        AgentState.REASONING: {AgentState.RISK_CHECK, AgentState.IDLE},
        AgentState.RISK_CHECK: {
            AgentState.EXECUTION,
            AgentState.IDLE,
            AgentState.REASONING,
        },
        AgentState.EXECUTION: {AgentState.LEARNING, AgentState.IDLE},
        AgentState.LEARNING: {AgentState.IDLE, AgentState.PERCEPTION},
    }

    async def _transition_to(self, new_state: AgentState):
        """Atomically transition to a new state with validation and rollback."""
        async with self._state_transition_lock:
            old_state = self.state

            # Validate transition is legal
            valid_targets = self._VALID_TRANSITIONS.get(old_state, set())
            if new_state not in valid_targets:
                logger.error(
                    f"ILLEGAL state transition blocked: {old_state.name} -> {new_state.name}. "
                    f"Valid targets: {[s.name for s in valid_targets]}"
                )
                raise ValueError(
                    f"Illegal state transition: {old_state.name} -> {new_state.name}"
                )

            try:
                self.state = new_state
                logger.info(f"Transitioning {old_state.name} -> {new_state.name}")

                # Update Prometheus gauge to reflect the new state
                self._record_state_metric()

                # Emit event for dashboard
                self._emit_dashboard_event(
                    {
                        "type": "state_transition",
                        "from": old_state.name,
                        "to": new_state.name,
                        "timestamp": time.time(),
                    }
                )
            except Exception as e:
                # Rollback on failure
                self.state = old_state
                logger.error(
                    f"State transition {old_state.name} -> {new_state.name} failed, "
                    f"rolled back: {e}",
                    exc_info=True,
                )
                raise

    def _record_state_metric(self):
        """Push the current OODA state to Prometheus gauge."""
        try:
            state_value = STATE_METRIC_VALUES.get(self.state)
            if state_value is not None:
                update_agent_state(state_value)
        except Exception:
            logger.debug("Failed to update agent state metric", exc_info=True)

    def _cleanup_rejected_cache(self):
        """
        Clean up expired entries from the rejection cache.
        """
        import datetime

        current_time = datetime.datetime.now(datetime.timezone.utc)
        expired_keys = []

        for decision_id, (
            rejection_time,
            asset_pair,
        ) in self._rejected_decisions_cache.items():
            if (
                current_time - rejection_time
            ).total_seconds() > self._rejection_cooldown_seconds:
                expired_keys.append(decision_id)

        for key in expired_keys:
            del self._rejected_decisions_cache[key]
            logger.debug(f"Removed expired rejection cache entry: {key}")

    def _emit_dashboard_event(self, event: dict):
        """
        Emit event to dashboard queue (non-blocking).

        Args:
            event: Event dictionary with type, timestamp, and event-specific fields
        """
        if hasattr(self, "_dashboard_event_queue"):
            queue_name = "dashboard"
            q = self._dashboard_event_queue
            try:
                q.put_nowait(event)
            except queue.Full:
                # Production: drop oldest to preserve most recent events; Dev: drop newest
                try:
                    if is_production():
                        # Drop oldest and attempt to enqueue new event
                        q.get_nowait()
                        increment_dashboard_events_dropped(queue_name)
                        q.put_nowait(event)
                    else:
                        increment_dashboard_events_dropped(queue_name)
                        # TODO(stage7-followup): Inspect the dashboard event consumer/drain path.
                        # The queue has remained saturated in live operation even when FFE health is otherwise healthy,
                        # so we likely need better drain behavior, backpressure, or queue sizing visibility.
                        logger.warning(
                            f"Dashboard event queue is full ({q.qsize()} events), dropping newest event."
                        )
                except Exception as inner_exc:  # noqa: BLE001
                    increment_dashboard_events_dropped(queue_name)
                    logger.warning(f"Failed to enqueue dashboard event: {inner_exc}")
            except Exception as e:  # noqa: BLE001
                # Other exception during queue operation - log it
                logger.warning(f"Failed to emit dashboard event: {e}")
            finally:
                try:
                    update_dashboard_queue_metrics(queue_name, q.qsize(), q.maxsize)
                except Exception:
                    logger.debug(
                        "Unable to update dashboard queue metrics", exc_info=True
                    )

    def _ensure_cycle_budget(self) -> None:
        """Initialize cycle id and retry budget if not already set."""

        if not self._current_cycle_id:
            self._current_cycle_id = uuid.uuid4().hex[:8]
            self._cycle_retry_budget[self._current_cycle_id] = getattr(
                self.config, "max_retries_per_cycle", 3
            )

    def _consume_cycle_retry_budget(self) -> int:
        """Decrement retry budget for current cycle and return remaining retries."""

        if not self._current_cycle_id:
            return 0

        remaining = self._cycle_retry_budget.get(
            self._current_cycle_id, getattr(self.config, "max_retries_per_cycle", 3)
        )
        if remaining > 0:
            remaining -= 1
            self._cycle_retry_budget[self._current_cycle_id] = remaining
        return remaining

    def _reset_cycle_budget(self) -> None:
        """Clear cycle id and retry budget (end of cycle)."""

        if self._current_cycle_id:
            self._cycle_retry_budget.pop(self._current_cycle_id, None)
            self._current_cycle_id = None

    def _perform_health_check(self) -> None:
        """
        Perform periodic health checks on system components.

        This method is called every N decisions (configurable) to monitor
        system health. Unlike validate_agent_readiness(), this is soft monitoring
        that logs issues but doesn't interrupt agent operation.

        Issues detected are logged as warnings; the agent continues operating
        even if issues are present. This allows graceful degradation and
        auto-recovery detection.
        """
        try:
            is_healthy, issues = self.engine.perform_health_check()

            if not is_healthy:
                logger.warning(
                    f"Health monitoring detected {len(issues)} issue(s) during cycle {self._current_cycle_id}"
                )
                for i, issue in enumerate(issues, 1):
                    logger.warning(f"  Health Issue {i}: {issue}")

                # TODO: Phase 3b - Add automatic recovery logic here
                # For example: trigger Ollama failover, switch providers, etc.
            else:
                logger.debug("Periodic health check passed")
        except Exception as e:
            logger.warning(f"Health check encountered error: {e}", exc_info=True)

    def _handle_state_exception(
        self, error: Exception, state_name: str
    ) -> Optional[str]:
        """Emit crash diagnostics and return crash dump path if available."""

        dump_path = None
        tracker = getattr(self.engine, "error_tracker", None)
        context = {
            "state": state_name,
            "cycle_id": self._current_cycle_id,
            "retry_budget": (
                self._cycle_retry_budget.get(self._current_cycle_id, 0)
                if self._current_cycle_id
                else 0
            ),
            "asset_pairs": getattr(self.config, "asset_pairs", []),
        }

        if tracker and hasattr(tracker, "capture_crash_dump"):
            try:
                dump_path = tracker.capture_crash_dump(
                    error, context=context, include_locals=True
                )
            except Exception:  # pragma: no cover - defensive
                logger.debug("Crash dump capture failed", exc_info=True)

        self._emit_dashboard_event(
            {
                "type": "agent_crashed",
                "state": state_name,
                "error": str(error),
                "cycle_id": self._current_cycle_id,
                "dump_path": dump_path,
                "timestamp": time.time(),
            }
        )
        return dump_path

    async def handle_idle_state(self) -> None:
        """
        IDLE: Marks the end of an OODA cycle.

        The sleep between cycles is now handled externally (in run() or by the backtester),
        so this state simply logs and returns, allowing the cycle to complete.
        The next cycle will start from LEARNING state after the external sleep.

        IMPORTANT: This state should NOT auto-transition. The run() method or backtester
        will explicitly transition to LEARNING after the configured sleep interval.
        """
        with tracer.start_as_current_span("agent.ooda.idle"):
            logger.info("State: IDLE - Cycle complete, waiting for next interval...")
            # Note: Sleep is handled externally in run() or by backtester
            # This state just marks the end of the cycle
            # DO NOT auto-transition here - let external controller handle timing

    async def _recover_existing_positions(self) -> None:
        """
        Recover existing positions from platform on startup.

        This method performs comprehensive position recovery with:
        1. Single API call to platform with one retry on failure
        2. Position limiting (keep top 2 by unrealized P&L, close excess)
        3. Position normalization (generate decision IDs, apply risk rules)
        4. Decision persistence (create synthetic decision records)
        5. All-or-nothing validation (fail entire recovery if any position fails)

        Emits recovery_complete or recovery_failed events with detailed metadata.
        Sets _startup_complete event and transitions to LEARNING state.
        """
        import uuid as uuid_module

        from finance_feedback_engine.memory.portfolio_memory import TradeOutcome
        from finance_feedback_engine.utils.shape_normalization import (
            asset_key_candidates,
            normalize_scalar_id,
        )
        from finance_feedback_engine.utils.validation import standardize_asset_pair

        logger.info("State: RECOVERING - Checking for existing positions...")

        if self._recovery_has_run:
            logger.warning(
                "Recovery requested after startup already completed; skipping duplicate recovery pass"
            )
            if not self._startup_complete.is_set():
                self._startup_complete.set()
            await self._transition_to(AgentState.IDLE)
            return

        max_retries = 1  # Single retry on transient failures
        max_positions = 2  # Maximum concurrent positions allowed

        for attempt in range(max_retries + 1):
            try:
                # Query platform for current portfolio state
                portfolio = await self.engine.get_portfolio_breakdown_async()
                logger.info("Portfolio breakdown retrieved: %s", portfolio)
                self._log_portfolio_risk_snapshot(
                    "Recovery portfolio snapshot", portfolio
                )

                # Extract positions from platform response
                raw_positions = []

                engine_config = getattr(self.engine, "config", None)
                enabled_platform_names = (
                    engine_config.get("enabled_platforms")
                    if isinstance(engine_config, dict)
                    else []
                )
                enabled_platforms = {
                    str(name).lower() for name in (enabled_platform_names or [])
                }

                def _platform_enabled(name: str) -> bool:
                    lname = str(name).lower()
                    return (
                        not enabled_platforms
                        or lname in enabled_platforms
                        or (
                            lname == "coinbase"
                            and "coinbase_advanced" in enabled_platforms
                        )
                    )

                # Handle UnifiedTradingPlatform (platform_breakdowns)
                if "platform_breakdowns" in portfolio:
                    for platform_name, platform_data in portfolio[
                        "platform_breakdowns"
                    ].items():
                        if not _platform_enabled(platform_name):
                            continue
                        # Coinbase futures
                        if "futures_positions" in platform_data:
                            for pos in platform_data["futures_positions"]:
                                raw_positions.append(
                                    {
                                        "platform": platform_name,
                                        "product_id": pos.get("product_id")
                                        or pos.get("instrument"),
                                        "side": pos.get("side", "LONG"),
                                        "size": abs(
                                            float(
                                                pos.get("contracts", 0)
                                                or pos.get("number_of_contracts", 0)
                                                or pos.get("units", 0)
                                            )
                                        ),
                                        "entry_price": float(pos.get("entry_price", 0)),
                                        "current_price": float(
                                            pos.get("current_price", 0)
                                        ),
                                        "unrealized_pnl": float(
                                            pos.get("unrealized_pnl", 0)
                                        ),
                                        "opened_at": pos.get("opened_at"),
                                    }
                                )
                        # Oanda positions
                        if "positions" in platform_data:
                            for pos in platform_data["positions"]:
                                raw_positions.append(
                                    {
                                        "platform": platform_name,
                                        "product_id": pos.get("instrument"),
                                        "side": (
                                            "LONG"
                                            if float(pos.get("units", 0)) > 0
                                            else "SHORT"
                                        ),
                                        "size": abs(float(pos.get("units", 0))),
                                        "entry_price": float(pos.get("entry_price", 0)),
                                        "current_price": float(
                                            pos.get("current_price", 0)
                                        ),
                                        "unrealized_pnl": float(pos.get("pnl", 0)),
                                        "opened_at": pos.get("opened_at"),
                                    }
                                )
                # Handle direct platform responses (futures_positions or positions keys)
                elif "futures_positions" in portfolio:
                    for pos in portfolio["futures_positions"]:
                        raw_positions.append(
                            {
                                "platform": "coinbase",
                                "product_id": pos.get("product_id")
                                or pos.get("instrument"),
                                "side": pos.get("side", "LONG"),
                                "size": abs(
                                    float(
                                        pos.get("contracts", 0)
                                        or pos.get("number_of_contracts", 0)
                                        or pos.get("units", 0)
                                    )
                                ),
                                "entry_price": float(pos.get("entry_price", 0)),
                                "current_price": float(pos.get("current_price", 0)),
                                "unrealized_pnl": float(pos.get("unrealized_pnl", 0)),
                                "opened_at": pos.get("opened_at"),
                            }
                        )
                elif "positions" in portfolio:
                    for pos in portfolio["positions"]:
                        raw_positions.append(
                            {
                                "platform": "oanda",
                                "product_id": pos.get("instrument"),
                                "side": (
                                    "LONG"
                                    if float(pos.get("units", 0)) > 0
                                    else "SHORT"
                                ),
                                "size": abs(float(pos.get("units", 0))),
                                "entry_price": float(pos.get("entry_price", 0)),
                                "current_price": float(pos.get("current_price", 0)),
                                "unrealized_pnl": float(pos.get("pnl", 0)),
                                "opened_at": pos.get("opened_at"),
                            }
                        )

                # Filter out positions with zero size
                active_positions = [p for p in raw_positions if p["size"] > 0]

                self._sync_trade_outcome_recorder(active_positions)

                if not active_positions:
                    logger.info("✓ No open positions found - starting with clean slate")
                    self._recovery_has_run = True
                    self._emit_dashboard_event(
                        {
                            "type": "recovery_complete",
                            "found": 0,
                            "kept": 0,
                            "closed_excess": [],
                            "timestamp": time.time(),
                        }
                    )
                    self._startup_complete.set()
                    await self._transition_to(AgentState.PERCEPTION)
                    return

                # Sort by unrealized P&L (descending) and keep top 2
                sorted_positions = sorted(
                    active_positions, key=lambda x: x["unrealized_pnl"], reverse=True
                )
                positions_to_keep = sorted_positions[:max_positions]
                positions_to_close = sorted_positions[max_positions:]

                logger.info(
                    "Found %d positions: keeping %d, closing %d",
                    len(active_positions),
                    len(positions_to_keep),
                    len(positions_to_close),
                )

                # Close excess positions synchronously (all-or-nothing)
                closed_positions = []
                if positions_to_close:
                    for pos in positions_to_close:
                        try:
                            asset_pair = standardize_asset_pair(pos["product_id"])
                            logger.info(
                                "Closing excess position: %s (P&L: $%.2f)",
                                asset_pair,
                                pos["unrealized_pnl"],
                            )

                            # Close via platform
                            close_result = await self.trading_platform.aclose_position(
                                pos["product_id"]
                            )

                            closed_positions.append(
                                {
                                    "asset_pair": asset_pair,
                                    "unrealized_pnl": pos["unrealized_pnl"],
                                    "reason": "exceeded_max_positions",
                                }
                            )
                            if close_result.get("status") == "success":
                                logger.info(
                                    "✓ Successfully closed position for %s", asset_pair
                                )
                            else:
                                raise Exception(
                                    f"Platform close failed: {close_result}"
                                )

                        except Exception as e:
                            # All-or-nothing: if any close fails, abort entire recovery
                            error_msg = f"Failed to close excess position {pos['product_id']}: {e}"
                            logger.error(error_msg)
                            self._emit_dashboard_event(
                                {
                                    "type": "recovery_failed",
                                    "reason": "position_close_failed",
                                    "failed_positions": [
                                        {
                                            "asset_pair": standardize_asset_pair(
                                                pos["product_id"]
                                            ),
                                            "error": str(e),
                                        }
                                    ],
                                    "timestamp": time.time(),
                                }
                            )
                            self._startup_complete.set()
                            await self._transition_to(AgentState.PERCEPTION)
                            return

                # Normalize and validate kept positions
                normalized_positions = []
                validation_errors = []
                recorder_positions = []

                for pos in positions_to_keep:
                    try:
                        asset_pair = standardize_asset_pair(pos["product_id"])

                        # Generate stable recovery metadata first so repeated startups
                        # can reuse the same synthetic decision instead of spamming history.
                        entry_price = float(pos.get("entry_price") or 0.0)
                        if entry_price <= 0:
                            entry_price = float(pos.get("current_price") or 0.0)
                        action = "BUY" if pos["side"] == "LONG" else "SELL"
                        recovery_metadata = {
                            "platform": pos["platform"],
                            "product_id": pos["product_id"],
                            "opened_at": pos.get("opened_at"),
                        }

                        recovery_key = (
                            str(pos["platform"] or "").lower() or None,
                            str(pos["product_id"] or "") or None,
                            action,
                            round(float(entry_price), 10),
                            round(float(pos["size"]), 10),
                        )

                        existing_recovery = self.engine.decision_store.find_equivalent_recovery_decision(
                            asset_pair=asset_pair,
                            action=action,
                            entry_price=entry_price,
                            position_size=pos["size"],
                            platform=pos["platform"],
                            product_id=pos["product_id"],
                        )
                        attribution_source = None
                        finder = getattr(
                            self.engine.decision_store,
                            "find_recent_decision_for_position",
                            None,
                        )
                        if callable(finder):
                            attribution_source = finder(
                                asset_pair=asset_pair,
                                action=action,
                                entry_price=entry_price,
                                position_size=pos["size"],
                            )

                        inherited_ai_provider = (
                            attribution_source.get("ai_provider")
                            if isinstance(attribution_source, dict)
                            else None
                        ) or "recovery"
                        inherited_ensemble_metadata = None
                        inherited_policy_trace = None
                        inherited_decision_source = None
                        shadowed_from_decision_id = None
                        if isinstance(attribution_source, dict):
                            shadowed_from_decision_id = attribution_source.get("id")
                            ensemble_metadata = attribution_source.get(
                                "ensemble_metadata"
                            )
                            if isinstance(ensemble_metadata, dict):
                                inherited_ensemble_metadata = dict(ensemble_metadata)
                            policy_trace = attribution_source.get("policy_trace")
                            if isinstance(policy_trace, dict):
                                inherited_policy_trace = dict(policy_trace)
                            inherited_decision_source = attribution_source.get(
                                "decision_source"
                            )

                        effective_recovery_metadata = dict(recovery_metadata)
                        if shadowed_from_decision_id:
                            effective_recovery_metadata[
                                "shadowed_from_decision_id"
                            ] = shadowed_from_decision_id
                            effective_recovery_metadata[
                                "shadowed_from_provider"
                            ] = inherited_ai_provider

                        if (
                            recovery_key in self._recovered_position_keys
                            and existing_recovery
                        ):
                            decision_id = existing_recovery["id"]
                            logger.info(
                                "↺ Skipping duplicate in-process recovery for %s (%s); reusing %s",
                                asset_pair,
                                pos["platform"],
                                decision_id,
                            )
                        elif existing_recovery:
                            decision_id = existing_recovery["id"]
                            upgraded = False
                            existing_recovery_metadata = dict(
                                existing_recovery.get("recovery_metadata") or {}
                            )
                            if not existing_recovery_metadata:
                                existing_recovery_metadata = dict(recovery_metadata)
                                upgraded = True

                            for key, value in effective_recovery_metadata.items():
                                if existing_recovery_metadata.get(key) != value:
                                    existing_recovery_metadata[key] = value
                                    upgraded = True

                            if (
                                inherited_ai_provider != "recovery"
                                and existing_recovery.get("ai_provider") != inherited_ai_provider
                            ):
                                existing_recovery["ai_provider"] = inherited_ai_provider
                                upgraded = True

                            if (
                                inherited_ensemble_metadata is not None
                                and existing_recovery.get("ensemble_metadata") != inherited_ensemble_metadata
                            ):
                                existing_recovery["ensemble_metadata"] = inherited_ensemble_metadata
                                upgraded = True

                            if (
                                inherited_policy_trace is not None
                                and existing_recovery.get("policy_trace") != inherited_policy_trace
                            ):
                                existing_recovery["policy_trace"] = inherited_policy_trace
                                upgraded = True

                            if (
                                inherited_decision_source is not None
                                and existing_recovery.get("decision_source") != inherited_decision_source
                            ):
                                existing_recovery["decision_source"] = inherited_decision_source
                                upgraded = True

                            existing_recovery["recovery_metadata"] = (
                                existing_recovery_metadata
                            )

                            if upgraded:
                                self.engine.decision_store.update_decision(
                                    existing_recovery
                                )
                                logger.info(
                                    "↺ Upgraded existing recovery decision %s with preserved attribution",
                                    decision_id,
                                )
                            logger.info(
                                "↺ Reusing existing recovery decision %s for %s (%s)",
                                decision_id,
                                asset_pair,
                                pos["platform"],
                            )
                        else:
                            # Generate standard UUID for decision
                            decision_id = str(uuid_module.uuid4())

                            # Create decision record (same as newly-created positions)
                            decision = {
                                "id": decision_id,
                                "asset_pair": asset_pair,
                                "timestamp": datetime.datetime.now(datetime.UTC)
                                .isoformat()
                                .replace("+00:00", "Z"),
                                "action": action,
                                "confidence": 75,  # Default confidence for recovered positions
                                "recommended_position_size": pos["size"],
                                "entry_price": entry_price,
                                "stop_loss_pct": 0.02,
                                "take_profit_pct": 0.05,
                                "reasoning": f"Recovered existing {pos['side']} position from {pos['platform']} platform",
                                "market_regime": "unknown",
                                "ai_provider": inherited_ai_provider,
                                "ensemble_metadata": inherited_ensemble_metadata or {
                                    "providers_used": ["recovery"],
                                    "providers_failed": [],
                                    "active_weights": {"recovery": 1.0},
                                    "fallback_tier": 0,
                                    "debate_summary": "Position recovered from platform at startup",
                                },
                                "risk_context": {
                                    "portfolio_drawdown_pct": 0.0,
                                    "var_limit_exceeded": False,
                                    "concentration_check": "OK",
                                    "correlation_check": "PASS",
                                },
                                "recovery_metadata": effective_recovery_metadata,
                            }
                            if inherited_policy_trace is not None:
                                decision["policy_trace"] = inherited_policy_trace
                            if inherited_decision_source is not None:
                                decision["decision_source"] = inherited_decision_source

                            # Persist decision to decision store once per live position fingerprint.
                            self._normalize_decision_for_persistence(decision)
                            self.engine.decision_store.save_decision(decision)
                            logger.info(
                                f"✓ Persisted decision {decision_id} for {asset_pair}"
                            )

                        # Add to portfolio memory
                        outcome = TradeOutcome(
                            decision_id=decision_id,
                            asset_pair=asset_pair,
                            action="BUY" if pos["side"] == "LONG" else "SELL",
                            entry_timestamp=datetime.datetime.now(datetime.UTC)
                            .isoformat()
                            .replace("+00:00", "Z"),
                            entry_price=entry_price,
                            position_size=pos["size"],
                            ai_provider="recovery",
                            market_sentiment=None,
                            volatility=None,
                            price_trend=None,
                            was_profitable=None,
                            hit_stop_loss=False,
                            hit_take_profit=False,
                        )
                        self.portfolio_memory.trade_outcomes.append(outcome)

                        # Associate with trade monitor
                        self.trade_monitor.associate_decision_to_trade(
                            decision_id, asset_pair
                        )

                        self._recovered_position_keys.add(recovery_key)

                        normalized_positions.append(
                            {
                                "decision_id": decision_id,
                                "asset_pair": asset_pair,
                                "side": pos["side"],
                                "size": pos["size"],
                                "entry_price": entry_price,
                                "unrealized_pnl": pos["unrealized_pnl"],
                                "platform": pos["platform"],
                            }
                        )
                        recorder_positions.append(
                            {
                                "product_id": pos["product_id"],
                                "side": pos["side"],
                                "size": pos["size"],
                                "entry_price": entry_price,
                                "current_price": pos.get("current_price"),
                                "opened_at": pos.get("opened_at"),
                                "decision_id": decision_id,
                            }
                        )

                    except Exception as e:
                        validation_errors.append(
                            {
                                "asset_pair": standardize_asset_pair(
                                    pos.get("product_id", "UNKNOWN")
                                ),
                                "error": str(e),
                            }
                        )
                        logger.error(
                            f"Failed to normalize position {pos.get('product_id')}: {e}",
                            exc_info=True,
                        )

                # All-or-nothing: if any position validation failed, abort recovery
                if validation_errors:
                    logger.error(
                        f"Position validation failed for {len(validation_errors)} positions"
                    )
                    self._emit_dashboard_event(
                        {
                            "type": "recovery_failed",
                            "reason": "position_validation_failed",
                            "failed_positions": validation_errors,
                            "timestamp": time.time(),
                        }
                    )
                    self._startup_complete.set()
                    await self._transition_to(AgentState.PERCEPTION)
                    return

                self._sync_trade_outcome_recorder(recorder_positions)

                # Recovery successful!
                self._recovery_has_run = True
                self._recovered_positions = normalized_positions
                total_pnl = sum(p["unrealized_pnl"] for p in normalized_positions)

                logger.info(
                    f"✓ Recovery complete: {len(normalized_positions)} positions (Total P&L: ${total_pnl:.2f})"
                )

                self._emit_dashboard_event(
                    {
                        "type": "recovery_complete",
                        "found": len(active_positions),
                        "kept": len(normalized_positions),
                        "closed_excess_positions": closed_positions,
                        "positions": normalized_positions,
                        "total_unrealized_pnl": total_pnl,
                        "timestamp": time.time(),
                    }
                )

                self._startup_complete.set()
                await self._transition_to(AgentState.PERCEPTION)
                return

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"Recovery attempt {attempt + 1} failed: {e}. Retrying..."
                    )
                    await asyncio.sleep(2.0)  # Brief delay before retry
                    continue
                else:
                    # Final failure - assume clean slate
                    logger.info(
                        f"Recovery failed after {max_retries + 1} attempts: {e}. Starting with clean slate."
                    )
                    self._emit_dashboard_event(
                        {
                            "type": "recovery_failed",
                            "reason": "platform_api_error",
                            "error": str(e),
                            "timestamp": time.time(),
                        }
                    )
                    self._startup_complete.set()
                    await self._transition_to(AgentState.PERCEPTION)
                    return

    async def handle_recovering_state(self) -> None:
        """
        RECOVERING: Recover existing positions from platform on startup.

        Delegates to _recover_existing_positions() for the actual recovery logic.
        """
        try:
            await self._recover_existing_positions()
        except Exception as e:
            logger.exception(f"Unexpected error during recovery state: {e}")
            self._emit_dashboard_event(
                {
                    "type": "recovery_failed",
                    "reason": "unexpected_exception_in_state",
                    "error": str(e),
                    "timestamp": time.time(),
                }
            )
            self._startup_complete.set()
            await self._transition_to(AgentState.PERCEPTION)

    async def handle_perception_state(self) -> None:
        """PERCEPTION: Fetching market data, portfolio state, and performing safety checks."""
        logger.info("=" * 80)
        logger.info("State: PERCEPTION - Fetching data and performing safety checks...")
        logger.info("=" * 80)

        try:
            await self._update_position_mtm()
        except Exception as e:
            logger.warning("Failed to update position MTM: %s", e, exc_info=True)
            tracker = getattr(self.engine, "error_tracker", None)
            if tracker:
                tracker.capture_error(
                    e,
                    context={
                        "phase": "position_mtm_update",
                        "cycle_id": self._current_cycle_id,
                    },
                )

        # --- Data Freshness Validation ---
        # Fetch monitoring context and cache for reuse throughout PERCEPTION state
        market_context = (
            self.trade_monitor.monitoring_context_provider.get_monitoring_context()
        )
        asset_type = market_context.get("asset_type", "crypto")
        data_timestamp = market_context.get("latest_market_data_timestamp")
        if str(asset_type).lower() == "crypto":
            market_data_timestamp = market_context.get("market_data_timestamp")
            if market_data_timestamp:
                data_timestamp = market_data_timestamp
        timeframe = market_context.get("timeframe", "intraday")
        market_status = market_context.get("market_status")

        # Defensive: Handle missing timestamp (THR-XXX: data_timestamp ValueError crash fix)
        if not data_timestamp:
            from datetime import datetime, timezone

            data_timestamp = datetime.now(timezone.utc).isoformat()
            logger.warning(
                "Missing data_timestamp in market_context, using current time: %s",
                data_timestamp,
            )

        is_fresh, age_str, warning_msg = validate_data_freshness(
            data_timestamp=data_timestamp,
            asset_type=asset_type,
            timeframe=timeframe,
            market_status=market_status,
        )
        if not is_fresh:
            expected_closed_market_stale = (
                asset_type == "forex"
                and isinstance(market_status, dict)
                and not market_status.get("is_open", True)
                and "closed-market stale" in str(warning_msg).lower()
            )
            if expected_closed_market_stale:
                logger.info(
                    "DATA FRESHNESS CHECK DEFERRED: %s (age: %s)", warning_msg, age_str
                )
                # Stay in PERCEPTION so the next loop retries with fresher data.
                return
            logger.error(
                "DATA FRESHNESS CHECK FAILED: %s (age: %s)", warning_msg, age_str
            )
            self._emit_dashboard_event(
                {
                    "type": "data_freshness_failed",
                    "reason": warning_msg,
                    "age": age_str,
                    "timestamp": time.time(),
                }
            )
            # Halt this cycle safely; outer scheduler can retry later.
            await self._transition_to(AgentState.IDLE)
            return

        # --- Cleanup rejected decisions cache (prevent memory leak) ---
        self._cleanup_rejected_cache()

        # --- Safety Check: Portfolio Kill Switch ---
        if (
            self.config.kill_switch_loss_pct is not None
            and self.config.kill_switch_loss_pct > 0
        ):
            try:
                # Reuse cached monitoring context from data freshness check
                # Assuming the context contains 'unrealized_pnl_percent'
                portfolio_pnl_pct = market_context.get("unrealized_pnl_percent", 0.0)

                if portfolio_pnl_pct < -self.config.kill_switch_loss_pct:
                    logger.critical(
                        "PORTFOLIO KILL SWITCH TRIGGERED! "
                        "Current P&L (%s%%) has breached the threshold "
                        "(-%s%%). Stopping agent.",
                        portfolio_pnl_pct,
                        self.config.kill_switch_loss_pct,
                    )
                    self.stop()
                    return  # Halt immediately
            except (TypeError, ValueError) as e:
                logger.error(
                    "Could not check portfolio kill switch due to an error: %s",
                    e,
                    exc_info=True,
                )

        # --- Additional Performance-based Kill Switches ---

        # Check for excessive consecutive losses
        current_streak = self._performance_metrics["current_streak"]
        if current_streak < -5:  # 6 or more consecutive losses
            logger.critical(
                "PERFORMANCE KILL SWITCH TRIGGERED! "
                "%d consecutive losses. Stopping agent.",
                abs(current_streak),
            )
            self.stop()
            return

        # Check for deteriorating win rate over time
        if self._performance_metrics["total_trades"] >= 20:
            win_rate = self._performance_metrics["win_rate"]
            if win_rate < 25:  # Less than 25% win rate with sufficient history
                logger.critical(
                    "PERFORMANCE KILL SWITCH TRIGGERED! "
                    "Win rate (%.1f%%) is critically low. Stopping agent.",
                    win_rate,
                )
                self.stop()
                return

        # Check for negative trend in performance
        if self._performance_metrics["total_trades"] >= 50:
            # If total P&L is significantly negative relative to risk taken
            total_pnl = self._performance_metrics["total_pnl"]
            # This is a simplified check - in practice, you might want to calculate
            # risk-adjusted returns or compare to a benchmark
            # We'll assume a default threshold if no initial balance is available
            balance_threshold = getattr(self.config, "initial_balance", 10000.0) * 0.15
            if (
                total_pnl < -balance_threshold
            ):  # Lost more than 15% of reference balance
                logger.critical(
                    "PERFORMANCE KILL SWITCH TRIGGERED! "
                    "Total loss of $%.2f exceeds 15%% of reference balance. Stopping agent.",
                    abs(total_pnl),
                )
                self.stop()
                return

        # --- Daily Counter Reset ---
        today = date.today()
        if today > self.last_trade_date:
            logger.info(
                "New day detected. Resetting daily trade count from %d to 0.",
                self.daily_trade_count,
            )
            self.daily_trade_count = 0
            self.last_trade_date = today
            # Reset all analysis failures on new day
            if self.analysis_failures:
                logger.info("Resetting analysis_failures for all assets (new day).")
                self.analysis_failures.clear()
                self.analysis_failure_timestamps.clear()

        # The trade_monitor runs in a separate process, so we don't need to switch
        # to a monitoring state here. The DecisionEngine will get the monitoring
        # context and be aware of open positions.

        # Transition to reasoning after gathering market data
        await self._transition_to(AgentState.REASONING)

    async def _update_position_mtm(self) -> None:
        """
        Mark-to-market: Update all open positions with current market prices.

        This ensures unrealized P&L reflects actual market conditions for:
        - Stop-loss/take-profit evaluation
        - Kill switch triggers
        - Risk metric calculations
        """
        from finance_feedback_engine.monitoring.error_tracking import ErrorTracker
        from finance_feedback_engine.utils.retry import async_exponential_backoff_retry

        retry_cfg = RetryConfig.get_config("API_CALL")

        @exponential_backoff_retry(**retry_cfg)
        def get_portfolio():
            return self.engine.get_portfolio_breakdown()

        try:
            portfolio = await asyncio.get_event_loop().run_in_executor(
                None, get_portfolio
            )
        except Exception as e:
            logger.error("Failed to retrieve portfolio after retries: %s", e)
            tracker = getattr(self.engine, "error_tracker", None)
            if tracker and hasattr(tracker, "capture_exception"):
                tracker.capture_exception(
                    e,
                    context={
                        "phase": "mtm_portfolio_retrieval",
                        "cycle_id": getattr(self, "_current_cycle_id", None),
                    },
                )
            return

        futures_positions = portfolio.get("futures_positions", [])
        if not futures_positions:
            return

        price_updates: Dict[str, float] = {}

        price_retry_cfg = RetryConfig.get_config("API_CALL")

        @async_exponential_backoff_retry(**price_retry_cfg)
        async def get_price_async(asset_pair):
            return await self._fetch_current_price(asset_pair)

        for pos in futures_positions:
            asset_pair = pos.get("product_id") or pos.get("instrument")
            if not asset_pair:
                continue
            try:
                normalized_pair = standardize_asset_pair(asset_pair)
            except Exception as e:
                logger.debug("Invalid asset pair %s: %s", asset_pair, e)
                continue
            try:
                current_price = await get_price_async(normalized_pair)
                if current_price and current_price > 0:
                    price_updates[normalized_pair] = current_price
            except Exception as e:
                logger.debug("Could not fetch price for %s: %s", normalized_pair, e)

        if price_updates and hasattr(self.trading_platform, "update_position_prices"):
            # Wrap update_position_prices in retry and error capture
            update_retry_cfg = RetryConfig.get_config("API_CALL")

            @exponential_backoff_retry(**update_retry_cfg)
            def update_prices():
                return self.trading_platform.update_position_prices(price_updates)

            try:
                await asyncio.get_event_loop().run_in_executor(None, update_prices)
                logger.info("Updated MTM prices for %d positions", len(price_updates))
            except Exception as e:
                logger.error("Failed to update position prices after retries: %s", e)
                tracker = getattr(self.engine, "error_tracker", None)
                if tracker and hasattr(tracker, "capture_exception"):
                    tracker.capture_exception(
                        e,
                        context={
                            "phase": "mtm_update_position_prices",
                            "cycle_id": getattr(self, "_current_cycle_id", None),
                        },
                    )

    async def _fetch_current_price(self, asset_pair: str) -> Optional[float]:
        """
        Fetch current market price for an asset pair.

        Returns:
            Current Price or None if unavailable.
        """
        from finance_feedback_engine.utils.retry import async_exponential_backoff_retry

        retry_cfg = RetryConfig.get_config("API_CALL")

        # Option 1: Use monitoring context if available, with retry
        @async_exponential_backoff_retry(**retry_cfg)
        async def get_monitoring_context():
            return (
                self.trade_monitor.monitoring_context_provider.get_monitoring_context(
                    asset_pair=asset_pair
                )
            )

        try:
            context = await get_monitoring_context()
            latest_price = context.get("latest_price") or context.get("current_price")
            if latest_price:
                return float(latest_price)
        except Exception as e:
            logger.debug("Error fetching monitoring context for %s: %s", asset_pair, e)

        # Option 2: Fetch from data provider directly, with retry
        if hasattr(self.engine, "data_provider"):

            @async_exponential_backoff_retry(**retry_cfg)
            async def get_price():
                return await self.engine.data_provider.get_latest_price(asset_pair)

            try:
                price_data = await get_price()
                return float(price_data.get("price", 0))
            except Exception as e:
                logger.debug(
                    "Error fetching price from data provider for %s: %s", asset_pair, e
                )
        return None

    async def handle_reasoning_state(self) -> None:
        """
        REASONING: Running per-asset analysis with bounded concurrency and rate limiting.
        """
        logger.info("=" * 80)
        logger.info("State: REASONING - Running DecisionEngine...")
        logger.info("=" * 80)

        # Guard against empty pair configuration only.
        # IMPORTANT: do not forcibly re-add hardcoded pairs here; API callers may
        # intentionally run focused universes (e.g., BTC/ETH long-short only).
        if not self.config.asset_pairs:
            logger.error(
                "CRITICAL: No asset pairs configured; ending cycle without reasoning"
            )
            await self._transition_to(AgentState.IDLE)
            return

        # Create a snapshot copy for iteration (prevents race conditions)
        asset_pairs_snapshot = list(self.config.asset_pairs)
        logger.info(
            "Analyzing %d pairs: %s", len(asset_pairs_snapshot), asset_pairs_snapshot
        )

        max_retries = 5  # Keep existing resilience behavior

        # If we've already hit the daily trade cap, only inspect the first pair
        limit_reached = (
            self.config.max_daily_trades > 0
            and self.daily_trade_count >= self.config.max_daily_trades
        )

        # --- Cleanup expired entries from rejection cache ---
        self._cleanup_rejected_cache()

        # --- Optional: Reset old failures at start of reasoning cycle (time-based decay) ---
        current_time = datetime.datetime.now(datetime.timezone.utc)
        for key in list(self.analysis_failures.keys()):
            last_fail = self.analysis_failure_timestamps.get(key)
            if (
                last_fail
                and (current_time - last_fail).total_seconds()
                > self.config.reasoning_failure_decay_seconds
            ):
                logger.info(
                    "Resetting analysis_failures for %s due to time-based decay.", key
                )
                self.analysis_failures.pop(key, None)
                self.analysis_failure_timestamps.pop(key, None)

        def _pair_has_active_position(asset_pair: str) -> bool:
            try:
                monitoring_context = self.trade_monitor.monitoring_context_provider.get_monitoring_context(
                    asset_pair=asset_pair
                )
            except Exception as exc:
                logger.debug(
                    "Unable to load monitoring context while checking daily-limit exemptions for %s: %s",
                    asset_pair,
                    exc,
                )
                return False

            active_positions = (
                (monitoring_context or {}).get("active_positions") or {}
            ).get("futures") or []
            target_asset = str(asset_pair or "").upper()
            for pos in active_positions:
                raw_pair = (
                    pos.get("product_id")
                    or pos.get("instrument")
                    or pos.get("asset_pair")
                )
                canonical = None
                try:
                    canonical = standardize_asset_pair(raw_pair) if raw_pair else None
                except Exception:
                    canonical = None
                raw_upper = str(raw_pair or "").upper()
                if canonical == target_asset or raw_upper == target_asset:
                    return True
                cfm_pair = _pid_to_pair(raw_upper)
                if cfm_pair == target_asset:
                    return True
            return False

        pairs_to_analyze: list[tuple[int, str]] = []
        for idx, asset_pair in enumerate(asset_pairs_snapshot):
            if limit_reached:
                if pairs_to_analyze:
                    logger.info(
                        "Daily trade limit reached; skipping analysis for remaining pairs."
                    )
                    break
                if not _pair_has_active_position(asset_pair):
                    logger.info(
                        "Daily trade limit reached with no active position in %s; skipping analysis.",
                        asset_pair,
                    )
                    continue

            failure_key = f"analysis:{asset_pair}"

            # --- Check if asset was recently rejected ---
            asset_rejected = any(
                asset_pair == cached_asset_pair
                for _, cached_asset_pair in self._rejected_decisions_cache.values()
            )
            if asset_rejected:
                logger.info(
                    "Skipping analysis for %s: recently rejected. Cooldown active.",
                    asset_pair,
                )
                continue

            if self.analysis_failures.get(failure_key, 0) >= max_retries:
                logger.warning(
                    "Skipping analysis for %s due to repeated failures (will reset after decay or daily reset).",
                    asset_pair,
                )
                continue

            pairs_to_analyze.append((idx, asset_pair))

        max_concurrent = max(
            1, int(getattr(self.config, "reasoning_max_concurrent_assets", 3))
        )
        semaphore = asyncio.Semaphore(max_concurrent)

        requests_per_minute = float(
            getattr(self.config, "reasoning_rate_limit_requests_per_minute", 4.0)
        )
        burst = int(getattr(self.config, "reasoning_rate_limit_burst", 1))
        limiter = None
        if requests_per_minute > 0:
            limiter = _TokenBucketRateLimiter(
                rate_per_second=requests_per_minute / 60.0,
                burst=burst,
            )

        async def _analyze_one(
            index: int, asset_pair: str
        ) -> tuple[int, Optional[dict]]:
            failure_key = f"analysis:{asset_pair}"
            logger.info(">>> Starting analysis for %s", asset_pair)

            async with semaphore:
                if limiter is not None:
                    await limiter.acquire()

                try:
                    logger.info(
                        "    → Calling DecisionEngine for %s (90s timeout)...",
                        asset_pair,
                    )

                    analyze_fn = getattr(self.engine, "analyze_asset", None)
                    analyze_async_fn = getattr(self.engine, "analyze_asset_async", None)
                    engine_config = getattr(self.engine, "config", None)
                    monitoring_cfg = (
                        engine_config.get("monitoring", {})
                        if isinstance(engine_config, dict)
                        else {}
                    )
                    include_sentiment = bool(
                        monitoring_cfg.get("include_sentiment", True)
                    )
                    include_macro = bool(monitoring_cfg.get("include_macro", False))

                    if callable(analyze_async_fn):
                        analysis_result = await analyze_async_fn(
                            asset_pair,
                            include_sentiment=include_sentiment,
                            include_macro=include_macro,
                        )
                    elif callable(analyze_fn):
                        analysis_result = analyze_fn(
                            asset_pair,
                            include_sentiment=include_sentiment,
                            include_macro=include_macro,
                        )
                    else:
                        raise AttributeError(
                            "Engine must implement analyze_asset() or analyze_asset_async()"
                        )

                    import inspect

                    if inspect.isawaitable(analysis_result):
                        analysis_awaitable = analysis_result
                    else:
                        analysis_awaitable = asyncio.sleep(0, result=analysis_result)

                    decision = await asyncio.wait_for(analysis_awaitable, timeout=90)

                    # Reset failure count on success
                    self.analysis_failures.pop(failure_key, None)
                    self.analysis_failure_timestamps.pop(failure_key, None)
                    return index, decision

                except asyncio.TimeoutError:
                    logger.warning(
                        "Analysis for %s timed out, skipping this cycle.", asset_pair
                    )
                    now = datetime.datetime.now(datetime.timezone.utc)
                    self.analysis_failure_timestamps[failure_key] = now
                    self.analysis_failures[failure_key] = (
                        self.analysis_failures.get(failure_key, 0) + 1
                    )
                    return index, None
                except Exception as e:
                    logger.warning("Analysis for %s failed: %s", asset_pair, e)
                    now = datetime.datetime.now(datetime.timezone.utc)
                    self.analysis_failure_timestamps[failure_key] = now
                    self.analysis_failures[failure_key] = (
                        self.analysis_failures.get(failure_key, 0) + 1
                    )
                    logger.error(
                        "Persistent failure analyzing %s. It will be skipped for a while.",
                        asset_pair,
                        exc_info=True,
                    )
                    return index, None

        analysis_results = (
            await asyncio.gather(
                *[_analyze_one(index, pair) for index, pair in pairs_to_analyze]
            )
            if pairs_to_analyze
            else []
        )

        # Preserve deterministic ordering by original asset index
        ordered_results = sorted(analysis_results, key=lambda item: item[0])
        ordered_actionable_decisions: list[dict] = []

        # Safety guard: detect currently open assets and avoid opening duplicate exposure
        # on the same standardized asset pair during decision collection.
        open_asset_pairs: set[str] = set()
        open_position_side: dict[str, str] = {}
        managed_asset_pairs: set[str] = set()
        try:
            managed_asset_pairs = {
                standardize_asset_pair(pair)
                for pair in (asset_pairs_snapshot or [])
                if pair
            }
        except Exception:
            managed_asset_pairs = {
                str(pair).upper().replace("_", "")
                for pair in (asset_pairs_snapshot or [])
                if pair
            }
        margin_usage_pct = 0.0
        margin_usage_limit_pct = 0.50
        try:
            portfolio_snapshot = await self.engine.get_portfolio_breakdown_async()
            candidate_positions = []

            if "platform_breakdowns" in portfolio_snapshot:
                for name, pdata in portfolio_snapshot["platform_breakdowns"].items():
                    candidate_positions.extend(pdata.get("futures_positions", []))
                    candidate_positions.extend(pdata.get("positions", []))
                    if str(name).lower() == "coinbase":
                        try:
                            fs = pdata.get("futures_summary", {}) or {}
                            initial_margin = float(fs.get("initial_margin", 0.0) or 0.0)
                            total_balance = float(
                                fs.get("total_balance_usd", 0.0)
                                or pdata.get("total_value_usd", 0.0)
                                or 0.0
                            )
                            if total_balance > 0:
                                margin_usage_pct = initial_margin / total_balance
                        except Exception:
                            pass
            else:
                candidate_positions.extend(
                    portfolio_snapshot.get("futures_positions", [])
                )
                candidate_positions.extend(portfolio_snapshot.get("positions", []))

            self._sync_trade_outcome_recorder(candidate_positions)

            for pos in candidate_positions:
                raw_pair = pos.get("product_id") or pos.get("instrument")
                if not raw_pair:
                    continue

                # Infer side from explicit side field or signed units/contracts.
                side = str(pos.get("side") or "").upper()
                if not side:
                    signed = 0.0
                    try:
                        signed = float(pos.get("units", 0) or 0)
                    except Exception:
                        signed = 0.0
                    if signed == 0:
                        try:
                            signed = float(
                                pos.get("number_of_contracts", 0)
                                or pos.get("contracts", 0)
                                or 0
                            )
                        except Exception:
                            signed = 0.0
                    side = "LONG" if signed >= 0 else "SHORT"

                canonical = None

                # 1) Try direct standardization (e.g., EUR_USD, BTC-USD)
                try:
                    canonical = standardize_asset_pair(raw_pair)
                    open_asset_pairs.add(canonical)
                except Exception:
                    canonical = None

                # 2) Also map Coinbase futures product IDs (e.g., BIP-20DEC30-CDE)
                #    to underlying canonical pairs (e.g., BTCUSD) for duplicate blocking.
                cfm_canonical = _pid_to_pair(raw_pair)
                if cfm_canonical:
                    canonical = cfm_canonical
                    open_asset_pairs.add(canonical)

                if (
                    canonical
                    and managed_asset_pairs
                    and canonical not in managed_asset_pairs
                ):
                    logger.info(
                        "Duplicate-entry guard ignoring position outside global managed scope: asset=%s raw_product=%s",
                        canonical,
                        raw_pair,
                    )
                    continue

                if canonical:
                    # Keep first observed side per asset for duplicate-entry logic.
                    open_position_side.setdefault(canonical, side)

            self._log_portfolio_risk_snapshot(
                "Portfolio risk snapshot (decision loop)",
                portfolio_snapshot,
                open_asset_pairs=open_asset_pairs,
                open_position_side=open_position_side,
                managed_asset_pairs=managed_asset_pairs,
                margin_usage_pct=margin_usage_pct,
            )
            if open_asset_pairs:
                logger.info(
                    "Duplicate-entry guard context | asset_scoped_pairs=%s | global_managed_pairs=%s | margin_usage=%.2f%% (limit %.2f%%)",
                    sorted(open_asset_pairs),
                    sorted(managed_asset_pairs),
                    margin_usage_pct * 100,
                    margin_usage_limit_pct * 100,
                )
        except Exception as e:
            logger.warning(
                "Unable to load open positions for duplicate-entry guard: %s", e
            )

        for index, decision in ordered_results:
            asset_pair = (
                asset_pairs_snapshot[index]
                if index < len(asset_pairs_snapshot)
                else None
            )
            if not decision:
                self._log_council_summary(decision or {}, asset_pair=asset_pair)
                self._persist_no_action_decision(
                    decision,
                    asset_pair=asset_pair or "UNKNOWN",
                    reason_code="NO_DECISION_PAYLOAD",
                    reason="Analysis completed without a materialized decision payload",
                )
                logger.info(
                    "No decision payload returned for %s; persisted explicit no-action artifact.",
                    asset_pair,
                )
                continue
            self._log_council_summary(decision, asset_pair=asset_pair)
            intent = _derive_execution_intent(decision)
            action_label = intent["canonical_action"] or (
                decision.get("policy_action") or decision.get("action")
            )

            if intent["policy_action"] and not decision.get("policy_action"):
                decision["policy_action"] = intent["policy_action"]
            if intent["policy_action_family"] and not decision.get(
                "policy_action_family"
            ):
                decision["policy_action_family"] = intent["policy_action_family"]

            if intent["is_actionable"]:
                # Block only same-direction entry stacking; allow reduce/close flows to proceed.
                try:
                    decision_pair = standardize_asset_pair(
                        decision.get("asset_pair", "")
                    )
                except Exception:
                    decision_pair = decision.get("asset_pair")

                requested_side = intent["entry_side"]
                if (
                    requested_side
                    and decision_pair
                    and decision_pair in open_asset_pairs
                ):
                    existing_side = open_position_side.get(decision_pair)

                    if existing_side == requested_side:
                        # Allow same-direction scaling on BTC/ETH futures rails until margin usage reaches 50%.
                        if (
                            decision_pair in {"BTCUSD", "ETHUSD"}
                            and margin_usage_pct < margin_usage_limit_pct
                        ):
                            logger.info(
                                "Allowing scale-in %s for %s: existing side=%s, margin usage %.2f%% < %.2f%% limit.",
                                action_label,
                                decision_pair,
                                existing_side,
                                margin_usage_pct * 100,
                                margin_usage_limit_pct * 100,
                            )
                        else:
                            reason = (
                                f"Duplicate entry blocked: existing {existing_side} for {decision_pair}; "
                                f"margin usage {margin_usage_pct*100:.2f}% (limit {margin_usage_limit_pct*100:.2f}%)"
                            )
                            self._mark_decision_not_executed(
                                decision, "DUPLICATE_ENTRY_GUARD", reason
                            )
                            logger.info(
                                "Skipping %s for %s: %s position already exists (duplicate-entry guard).",
                                action_label,
                                decision_pair,
                                existing_side,
                            )
                            continue
                    logger.info(
                        "Allowing %s for %s: existing side=%s (non-duplicate execution path).",
                        action_label,
                        decision_pair,
                        existing_side,
                    )

                should_execute, reason_code, reason_msg = (
                    await self._should_execute_with_reason(decision)
                )
                if should_execute:
                    decision["actionable"] = True
                    self._attach_decision_artifact(decision, execution_attempted=False)
                    ordered_actionable_decisions.append(decision)
                    logger.info(
                        "Actionable decision collected for %s: %s",
                        decision.get("asset_pair"),
                        action_label,
                    )
                else:
                    self._mark_decision_not_executed(decision, reason_code, reason_msg)
                    logger.info(
                        "Decision to %s %s filtered: %s (%s).",
                        action_label,
                        decision.get("asset_pair"),
                        reason_code,
                        reason_msg,
                    )
            elif decision:
                try:
                    self._ensure_decision_identity(decision)
                    decision["executed"] = False
                    fallback_reason_code = decision.get("filtered_reason_code")
                    if (
                        decision.get("decision_origin") == "fallback"
                        and fallback_reason_code
                    ):
                        decision.setdefault("hold_origin", "provider_fallback")
                        decision.setdefault("hold_is_genuine", False)
                        decision["execution_status"] = "filtered"
                        decision["execution_result"] = {
                            "success": False,
                            "reason_code": fallback_reason_code,
                            "error": decision.get("reasoning")
                            or "Provider fallback decision",
                        }
                    else:
                        if decision.get("position_state_violation"):
                            decision["hold_origin"] = "position_rule"
                            decision["hold_is_genuine"] = False
                        else:
                            decision.setdefault("hold_origin", "model")
                            decision.setdefault("hold_is_genuine", True)
                        decision["execution_status"] = "hold"
                        decision["execution_result"] = {
                            "success": True,
                            "reason_code": "HOLD",
                            "message": "Hold decision - maintain current position",
                        }
                    if getattr(self.engine, "decision_store", None):
                        if decision.get("_persisted_to_store"):
                            self._normalize_decision_for_persistence(decision)
                            self.engine.decision_store.update_decision(decision)
                        else:
                            self._normalize_decision_for_persistence(decision)
                            self.engine.decision_store.save_decision(decision)
                except Exception as e:
                    logger.warning(
                        "Failed to persist HOLD decision for %s: %s",
                        decision.get("asset_pair"),
                        e,
                    )
                logger.info(
                    "HOLD audit shape for %s: origin=%s regime=%s has_ensemble=%s has_pre_reasoning=%s filtered=%s",
                    decision.get("asset_pair"),
                    decision.get("decision_origin"),
                    decision.get("market_regime"),
                    bool(decision.get("ensemble_metadata")),
                    bool(decision.get("pre_reasoning")),
                    decision.get("filtered_reason_code"),
                )
                logger.info(
                    "Decision for %s: HOLD persisted. No action taken.",
                    decision.get("asset_pair"),
                )

        if ordered_actionable_decisions:
            async with self._current_decisions_lock:
                self._current_decisions.extend(ordered_actionable_decisions)

        # After analyzing all assets, transition based on collected decisions
        async with self._current_decisions_lock:
            has_decisions = bool(self._current_decisions)
            decisions_count = len(self._current_decisions)

        logger.info(
            "Reasoning cycle summary | analyzed_pairs=%s | actionable_pairs=%s | actionable_count=%d | non_actionable_count=%d | skipped_before_analysis=%d",
            pairs_to_analyze,
            [d.get("asset_pair") for d in ordered_actionable_decisions],
            len(ordered_actionable_decisions),
            len(
                [
                    1
                    for _, decision in ordered_results
                    if decision
                    and not _derive_execution_intent(decision)["is_actionable"]
                ]
            ),
            max(0, len(asset_pairs_snapshot) - len(pairs_to_analyze)),
        )

        if has_decisions:
            logger.info(
                "Collected %s actionable decisions. Proceeding to RISK_CHECK.",
                decisions_count,
            )
            await self._transition_to(AgentState.RISK_CHECK)
        else:
            logger.info("No actionable trades found for any asset. Going back to IDLE.")
            await self._transition_to(AgentState.IDLE)

    def _apply_derisking_execution_metadata(
        self, decision: Dict[str, Any], monitoring_context: Dict[str, Any]
    ) -> None:
        normalized_action = str(
            decision.get("policy_action") or decision.get("action") or ""
        ).upper()
        if not normalized_action.startswith(("CLOSE_", "REDUCE_")):
            return

        active_positions = (
            (monitoring_context or {}).get("active_positions") or {}
        ).get("futures") or []
        target_asset = str(decision.get("asset_pair") or "").upper()
        matched_position = None
        for pos in active_positions:
            raw_pair = (
                pos.get("product_id") or pos.get("instrument") or pos.get("asset_pair")
            )
            canonical = None
            try:
                canonical = standardize_asset_pair(raw_pair) if raw_pair else None
            except Exception:
                canonical = None
            raw_upper = str(raw_pair or "").upper()
            if canonical == target_asset or raw_upper == target_asset:
                matched_position = pos
                break
            cfm_pair = _pid_to_pair(raw_upper)
            if cfm_pair == target_asset:
                matched_position = pos
                break

        if not matched_position:
            return

        try:
            current_position_size = abs(
                float(
                    matched_position.get("number_of_contracts", 0)
                    or matched_position.get("contracts", 0)
                    or matched_position.get("units", 0)
                    or 0.0
                )
            )
        except Exception:
            current_position_size = 0.0

        try:
            current_price = float(
                matched_position.get("current_price", 0)
                or decision.get("entry_price", 0)
                or 0.0
            )
        except Exception:
            current_price = 0.0

        if current_position_size <= 0:
            return

        legacy_action = decision.get(
            "legacy_action_compatibility"
        ) or get_legacy_action_compatibility(normalized_action)
        decision["has_existing_position"] = True
        decision["current_position_size"] = current_position_size
        decision["recommended_position_size"] = current_position_size
        if legacy_action:
            decision["legacy_action_compatibility"] = legacy_action
        if current_price > 0:
            decision["suggested_amount"] = current_position_size * current_price

    async def _hydrate_derisking_monitoring_context(
        self, decision: Dict[str, Any], monitoring_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Backfill active positions for CLOSE_/REDUCE_ decisions when monitoring context is sparse."""
        normalized_action = str(
            decision.get("policy_action") or decision.get("action") or ""
        ).upper()
        if not normalized_action.startswith(("CLOSE_", "REDUCE_")):
            return monitoring_context

        active_positions = (
            (monitoring_context or {}).get("active_positions") or {}
        ).get("futures") or []
        if active_positions:
            return monitoring_context

        portfolio_snapshot = None
        get_portfolio_async = getattr(self.engine, "get_portfolio_breakdown_async", None)
        get_portfolio_sync = getattr(self.engine, "get_portfolio_breakdown", None)

        try:
            if callable(get_portfolio_async):
                portfolio_snapshot = await get_portfolio_async()
            elif callable(get_portfolio_sync):
                portfolio_snapshot = get_portfolio_sync()
        except Exception as e:
            logger.debug(
                "Failed to hydrate derisking monitoring context from portfolio snapshot for %s: %s",
                decision.get("asset_pair"),
                e,
            )
            return monitoring_context

        candidate_positions = []
        if isinstance(portfolio_snapshot, dict):
            if "platform_breakdowns" in portfolio_snapshot:
                for pdata in (portfolio_snapshot.get("platform_breakdowns") or {}).values():
                    if not isinstance(pdata, dict):
                        continue
                    candidate_positions.extend(pdata.get("futures_positions", []) or [])
                    candidate_positions.extend(pdata.get("positions", []) or [])
            else:
                candidate_positions.extend(portfolio_snapshot.get("futures_positions", []) or [])
                candidate_positions.extend(portfolio_snapshot.get("positions", []) or [])

        if not candidate_positions:
            return monitoring_context

        hydrated_context = dict(monitoring_context or {})
        active_positions_map = dict(hydrated_context.get("active_positions") or {})
        active_positions_map["futures"] = candidate_positions
        hydrated_context["active_positions"] = active_positions_map
        return hydrated_context

    async def handle_risk_check_state(self):
        """
        RISK_CHECK: Running the RiskGatekeeper for all collected decisions.
        Approved decisions are moved to execution.
        """
        logger.info("State: RISK_CHECK - Running RiskGatekeeper...")

        async with self._current_decisions_lock:
            if not self._current_decisions:
                should_return_idle = True
                decisions_to_check = []
            else:
                should_return_idle = False
                decisions_to_check = self._current_decisions.copy()

        if should_return_idle:
            logger.info("No decisions to risk check. Returning to IDLE.")
            await self._transition_to(AgentState.IDLE)
            return

        # Process without lock
        approved_decisions = []
        for decision in decisions_to_check:
            decision_id = decision.get("id")
            asset_pair = decision.get("asset_pair")

            # Retrieve monitoring context for risk validation
            try:
                monitoring_context = self.trade_monitor.monitoring_context_provider.get_monitoring_context(
                    asset_pair=asset_pair
                )
                monitoring_context = await self._hydrate_derisking_monitoring_context(
                    decision, monitoring_context
                )
                safety_config = self.engine.config.get("safety", {})
                monitoring_context["max_leverage"] = safety_config.get(
                    "max_leverage", 5.0
                )
                monitoring_context["max_concentration"] = safety_config.get(
                    "max_position_pct", 25.0
                )
                self._apply_derisking_execution_metadata(decision, monitoring_context)
            except Exception as e:
                logger.warning(
                    "Failed to get monitoring context for risk validation: %s", e
                )
                monitoring_context = {"max_leverage": 5.0, "max_concentration": 25.0}

            # First run the standard RiskGatekeeper validation
            approved, reason = self.risk_gatekeeper.validate_trade(
                decision, monitoring_context
            )

            if not approved:
                decision.setdefault("gatekeeper_message", reason)

            # If standard validation passes, run additional performance-based risk checks
            if approved:
                (
                    performance_approved,
                    performance_reason,
                ) = self._check_performance_based_risks(decision)
                if not performance_approved:
                    approved = False
                    reason = performance_reason
                    decision.setdefault("gatekeeper_message", performance_reason)

            should_execute, outcome_kind, outcome_code, outcome_message = (
                self._classify_action_execution_outcome(
                    decision,
                    risk_reason=None if approved else reason,
                )
            )

            if should_execute:
                # --- Track SK: Inject sortino gate + performance metrics ---
                # Single defensive boundary: gate computation + metrics injection.
                # If anything fails, decision proceeds without gate/metrics (fixed risk).
                try:
                    if self._sortino_gate is not None:
                        self._last_sortino_gate_result = self._sortino_gate.compute(
                            list(self._trade_pnl_history)
                        )
                        decision["sortino_gate_result"] = self._last_sortino_gate_result

                    # Inject performance_metrics for Kelly parameter extraction
                    raw_wr = float(self._performance_metrics.get("win_rate", 0) or 0)
                    normalized_wr = raw_wr / 100.0 if raw_wr > 1.0 else raw_wr
                    normalized_wr = max(0.0, min(1.0, normalized_wr))  # clamp [0, 1]

                    avg_win = abs(float(self._performance_metrics.get("avg_win", 0) or 0))
                    avg_loss = abs(float(self._performance_metrics.get("avg_loss", 0) or 0))
                    payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

                    decision["performance_metrics"] = {
                        "win_rate": normalized_wr,
                        "avg_win": avg_win,
                        "avg_loss": avg_loss,
                        "payoff_ratio": payoff_ratio,
                    }
                except Exception as e:
                    logger.warning(
                        "Sortino gate / metrics injection failed: %s (sizing will use fixed risk)",
                        e,
                    )

                # --- INJECT POSITION SIZING HERE ---
                try:
                    # Use the engine's position_sizing_calculator
                    sizing = self.engine.position_sizing_calculator.calculate_position_sizing_params(
                        context=decision,
                        current_price=decision.get("entry_price", 0),
                        action=decision.get("action", "UNKNOWN"),
                        has_existing_position=decision.get(
                            "has_existing_position", False
                        ),
                        relevant_balance=decision.get("relevant_balance", {}),
                        balance_source=decision.get("balance_source", "unknown"),
                    )
                    if sizing:
                        recommended_size = sizing.get("recommended_position_size")
                        decision["recommended_position_size"] = recommended_size
                    # De-risking actions must carry executable close size metadata.
                    # Re-apply live position metadata after generic sizing because the
                    # sizing path intentionally zeroes CLOSE_/REDUCE_ recommendations.
                    self._apply_derisking_execution_metadata(
                        decision, monitoring_context
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to calculate position size for %s: %s", decision_id, e
                    )

                decision["control_outcome"] = build_control_outcome(
                    action=decision.get("action"),
                    structural_action_validity=decision.get(
                        "structural_action_validity"
                    ),
                    invalid_action_reason_text=decision.get("invalid_action_reason"),
                    risk_vetoed=bool(decision.get("risk_vetoed", False)),
                    risk_veto_reason=decision.get("risk_veto_reason"),
                )
                policy_package = decision.get("policy_package")
                if isinstance(policy_package, dict):
                    policy_package["control_outcome"] = decision[
                        "control_outcome"
                    ].copy()
                if isinstance(decision.get("policy_trace"), dict) and isinstance(
                    decision["policy_trace"].get("policy_package"), dict
                ):
                    decision["policy_trace"]["policy_package"]["control_outcome"] = (
                        decision["control_outcome"].copy()
                    )
                logger.info(
                    "Trade for %s approved by RiskGatekeeper. Adding to execution queue.",
                    asset_pair,
                )
                approved_decisions.append(decision)
                try:
                    exposure_manager = get_exposure_manager()
                    reserve_trade_exposure(
                        exposure_manager=exposure_manager, decision=decision
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to reserve exposure for %s: %s", decision_id, e
                    )
                    tracker = getattr(self.engine, "error_tracker", None)
                    if tracker:
                        tracker.capture_error(
                            e,
                            context={
                                "decision_id": decision_id,
                                "phase": "reserve_exposure",
                            },
                        )

                # Record decision confidence for metrics dashboards
                try:
                    update_decision_confidence(
                        asset_pair,
                        decision.get("action", "UNKNOWN"),
                        float(decision.get("confidence", 0)),
                    )
                except Exception:
                    logger.debug(
                        "Failed to record decision confidence metric", exc_info=True
                    )

                # Emit approval event for dashboard
                self._emit_dashboard_event(
                    {
                        "type": "decision_approved",
                        "asset": asset_pair,
                        "action": decision.get("action", "UNKNOWN"),
                        "confidence": decision.get("confidence", 0),
                        "reasoning": decision.get("reasoning", "")[:200],
                        "timestamp": time.time(),
                    }
                )
            else:
                logger.info(
                    "Trade for %s is %s: %s.", asset_pair, outcome_kind, outcome_message
                )
                self._mark_decision_not_executed(
                    decision,
                    outcome_code or "REJECTED",
                    outcome_message or reason or "Rejected",
                )
                if outcome_kind in {"vetoed", "rejected"}:
                    self._rejected_decisions_cache[decision_id] = (
                        datetime.datetime.now(datetime.timezone.utc),
                        asset_pair,
                    )  # Add to cache

                self._emit_dashboard_event(
                    {
                        "type": (
                            "decision_rejected"
                            if outcome_kind in {"vetoed", "rejected", "invalid"}
                            else "decision_filtered"
                        ),
                        "asset": asset_pair,
                        "action": decision.get("action", "UNKNOWN"),
                        "reason": outcome_message or reason,
                        "outcome_kind": outcome_kind,
                        "timestamp": time.time(),
                    }
                )

        async with self._current_decisions_lock:
            self._current_decisions = approved_decisions  # Keep only approved decisions
            has_approved = bool(self._current_decisions)
            approved_count = len(self._current_decisions)

        if has_approved:
            logger.info(
                "Proceeding to EXECUTION with %s approved decisions.", approved_count
            )
            await self._transition_to(AgentState.EXECUTION)
        else:
            logger.info("No decisions approved by RiskGatekeeper. Going back to IDLE.")
            await self._transition_to(AgentState.IDLE)

    def _check_performance_based_risks(
        self, decision: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Check additional performance-based risk conditions.

        Args:
            decision: The trading decision to evaluate

        Returns:
            Tuple of (is_approved, reason) where is_approved indicates if the decision should proceed
        """
        normalized_action = str(
            decision.get("policy_action") or decision.get("action") or ""
        ).upper()
        if normalized_action.startswith(("CLOSE_", "REDUCE_")):
            return (
                True,
                f"Performance-based risk checks bypassed for derisking action: {normalized_action}",
            )

        # Check for excessive consecutive losses
        current_streak = self._performance_metrics["current_streak"]

        if current_streak < -3:  # 4 or more consecutive losses
            return (
                False,
                f"Rejected due to poor performance streak: {abs(current_streak)} consecutive losses",
            )

        # Check win rate if we have sufficient history
        if self._performance_metrics["total_trades"] >= 10:
            win_rate = self._performance_metrics["win_rate"]
            if win_rate < 30:  # Less than 30% win rate
                # Only block if confidence is also low
                decision_confidence = decision.get("confidence", 0)
                if decision_confidence < 70:
                    return (
                        False,
                        f"Rejected due to low win rate ({win_rate:.1f}%) and low confidence ({decision_confidence}%)",
                    )

        # Check loss magnitude vs win magnitude ratio
        avg_loss = abs(self._performance_metrics["avg_loss"])
        avg_win = self._performance_metrics["avg_win"]

        if avg_loss > 0 and avg_win > 0:
            loss_win_ratio = avg_loss / avg_win
            if loss_win_ratio > 2.0:  # Average losses are more than 2x average wins
                decision_confidence = decision.get("confidence", 0)
                if decision_confidence < 75:
                    return (
                        False,
                        f"Rejected due to high loss/win ratio ({loss_win_ratio:.2f}) and low confidence ({decision_confidence}%)",
                    )

        # If position sizing is used, check if the position would risk too much of recent profits
        if decision.get("recommended_position_size"):
            # Calculate risk as percentage of recent P&L
            recent_pnl = self._performance_metrics["total_pnl"]
            if recent_pnl > 0:  # Only apply if we have positive P&L to protect
                # Calculate potential loss from this position (roughly)
                entry_price = decision.get("entry_price", 0)
                position_size = decision.get("recommended_position_size", 0)
                if entry_price > 0 and position_size > 0:
                    # Rough calculation for max potential loss (stop loss distance)
                    stop_loss_price = decision.get("stop_loss_price")
                    if stop_loss_price and entry_price > stop_loss_price:
                        potential_loss = (
                            abs(entry_price - stop_loss_price) * position_size
                        )
                        risk_to_pnl_ratio = potential_loss / recent_pnl

                        if (
                            risk_to_pnl_ratio > 0.5
                        ):  # Risking more than 50% of recent profits
                            return (
                                False,
                                f"Rejected due to high risk ({risk_to_pnl_ratio:.2%}) relative to recent profits",
                            )

        # All checks passed
        return True, "Performance-based risk checks passed"

    async def handle_execution_state(self):
        """
        EXECUTION: Sending orders to BaseTradingPlatform for all approved decisions.

        If autonomous mode is disabled, sends signals to Telegram for approval instead.
        """
        logger.info("State: EXECUTION - Processing decisions...")

        async with self._current_decisions_lock:
            if not self._current_decisions:
                await self._transition_to(AgentState.IDLE)
                logger.warning(
                    "EXECUTION state reached without decisions. Returning to IDLE."
                )
                return
            decisions_to_execute = self._current_decisions.copy()
            self._current_decisions.clear()

        # Use property for cleaner autonomous mode check
        autonomous_enabled = self.is_autonomous_enabled
        logger.info("Autonomous execution mode: %s", autonomous_enabled)

        if autonomous_enabled:
            # Full autonomous mode: execute trades directly
            logger.info("Autonomous execution enabled - executing trades directly")
            for decision in decisions_to_execute:
                decision_id = decision.get("id")
                asset_pair = decision.get("asset_pair")

                try:
                    execution_result = await self.engine.execute_decision_async(
                        decision_id
                    )
                    action = (
                        decision.get("policy_action")
                        or decision.get("action")
                        or "UNKNOWN"
                    )
                    normalized_action = self._normalize_execution_action(decision)
                    extracted_order_id = self._extract_order_id_from_execution_result(
                        execution_result
                    )
                    if extracted_order_id and not execution_result.get("order_id"):
                        execution_result["order_id"] = extracted_order_id
                    if execution_result.get("success"):
                        decision["execution_status"] = "executed"
                        decision["executed"] = True
                        decision["execution_result"] = execution_result
                        decision["control_outcome"] = build_control_outcome(
                            action=decision.get("action"),
                            structural_action_validity=decision.get(
                                "structural_action_validity"
                            ),
                            invalid_action_reason_text=decision.get(
                                "invalid_action_reason"
                            ),
                            risk_vetoed=bool(decision.get("risk_vetoed", False)),
                            risk_veto_reason=decision.get("risk_veto_reason"),
                            execution_status=decision.get("execution_status"),
                            execution_result=decision.get("execution_result"),
                        )
                        if isinstance(decision.get("policy_package"), dict):
                            decision["policy_package"]["control_outcome"] = decision[
                                "control_outcome"
                            ].copy()
                        if isinstance(
                            decision.get("policy_trace"), dict
                        ) and isinstance(
                            decision["policy_trace"].get("policy_package"), dict
                        ):
                            decision["policy_trace"]["policy_package"][
                                "control_outcome"
                            ] = decision["control_outcome"].copy()

                        # Update Stage 62 execution confirmation contract
                        self._update_execution_confirmation_contract(decision)

                        logger.info(
                            "Trade execution succeeded for %s %s. Associating decision with monitor.",
                            action,
                            asset_pair,
                        )

                        # FIX-LINEAGE: For exit/close actions, immediately record the
                        # trade outcome with the correct decision_id instead of relying
                        # on the async detection pipeline which loses lineage.
                        _is_close_action = str(action or "").upper().startswith(("CLOSE_", "REDUCE_"))
                        if _is_close_action and decision_id:
                            try:
                                exit_price = float(
                                    execution_result.get("execution_price")
                                    or execution_result.get("fill_price")
                                    or decision.get("entry_price")
                                    or 0
                                )
                                if exit_price > 0:
                                    self.engine.record_trade_outcome(
                                        decision_id,
                                        exit_price=exit_price,
                                        exit_timestamp=decision.get("executed_at"),
                                    )
                                    logger.info(
                                        "Direct learning handoff for %s %s | decision_id=%s | exit_price=%.2f",
                                        action, asset_pair, decision_id, exit_price,
                                    )
                                else:
                                    logger.warning(
                                        "Direct learning handoff skipped for %s %s: no exit price available",
                                        action, asset_pair,
                                    )
                            except Exception as e:
                                logger.warning(
                                    "Direct learning handoff failed for %s %s: %s",
                                    action, asset_pair, e,
                                )

                        if self._counts_toward_daily_trade_limit(
                            decision, execution_result
                        ):
                            self.daily_trade_count += 1
                            logger.info(
                                "Daily trade count incremented to %d for %s",
                                self.daily_trade_count,
                                asset_pair,
                            )
                        else:
                            logger.info(
                                "Execution for %s did not count toward daily limit "
                                "(insufficient funds/logistics/rejection/no order id).",
                                asset_pair,
                            )

                        self.trade_monitor.associate_decision_to_trade(
                            decision_id, asset_pair
                        )

                        order_status_worker = getattr(
                            self.engine, "order_status_worker", None
                        )
                        if (
                            order_status_worker
                            and extracted_order_id
                            and normalized_action
                        ):
                            try:
                                execution_intent = _derive_execution_intent(decision)
                                order_status_worker.add_pending_order(
                                    order_id=extracted_order_id,
                                    decision_id=decision_id,
                                    asset_pair=asset_pair,
                                    platform=execution_result.get("platform")
                                    or "unknown",
                                    action=normalized_action,
                                    size=float(
                                        decision.get("recommended_position_size")
                                        or decision.get("translated_size")
                                        or decision.get("suggested_amount")
                                        or 0
                                    ),
                                    entry_price=decision.get("entry_price"),
                                    side=execution_intent.get("position_side"),
                                    policy_action_family=execution_intent.get("policy_action_family"),
                                )
                                logger.info(
                                    "Registered executed order %s for outcome tracking on %s",
                                    extracted_order_id,
                                    asset_pair,
                                )
                            except Exception as e:
                                logger.warning(
                                    "Failed to register order %s for outcome tracking: %s",
                                    extracted_order_id,
                                    e,
                                )
                        elif execution_result.get("success") and not extracted_order_id:
                            logger.warning(
                                "Execution succeeded for %s but no concrete order_id was extracted; outcome tracking skipped.",
                                asset_pair,
                            )

                        # THR-134: Commit reservation - actual position now exists
                        try:
                            exposure_manager = get_exposure_manager()
                            finalize_trade_reservation(
                                exposure_manager=exposure_manager,
                                decision_id=decision_id,
                                execution_succeeded=True,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to finalize reservation for {decision_id}: {e}"
                            )
                    else:
                        decision["execution_status"] = "execution_failed"
                        decision["executed"] = False
                        decision["execution_result"] = execution_result
                        decision["control_outcome"] = build_control_outcome(
                            action=decision.get("action"),
                            structural_action_validity=decision.get(
                                "structural_action_validity"
                            ),
                            invalid_action_reason_text=decision.get(
                                "invalid_action_reason"
                            ),
                            risk_vetoed=bool(decision.get("risk_vetoed", False)),
                            risk_veto_reason=decision.get("risk_veto_reason"),
                            execution_status=decision.get("execution_status"),
                            execution_result=decision.get("execution_result"),
                        )
                        if isinstance(decision.get("policy_package"), dict):
                            decision["policy_package"]["control_outcome"] = decision[
                                "control_outcome"
                            ].copy()
                        if isinstance(
                            decision.get("policy_trace"), dict
                        ) and isinstance(
                            decision["policy_trace"].get("policy_package"), dict
                        ):
                            decision["policy_trace"]["policy_package"][
                                "control_outcome"
                            ] = decision["control_outcome"].copy()

                        # Update Stage 62 execution confirmation contract
                        self._update_execution_confirmation_contract(decision)

                        error_msg = execution_result.get(
                            "message"
                        ) or execution_result.get("error", "Unknown error")
                        logger.error(
                            f"Trade execution failed for {asset_pair}: {error_msg}. Full result: {execution_result}"
                        )
                        # THR-134: Rollback reservation - trade didn't execute
                        try:
                            exposure_manager = get_exposure_manager()
                            finalize_trade_reservation(
                                exposure_manager=exposure_manager,
                                decision_id=decision_id,
                                execution_succeeded=False,
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to finalize reservation for {decision_id}: {e}"
                            )
                except asyncio.CancelledError:
                    logger.warning(
                        f"Trade execution cancelled for decision {decision_id} (agent shutdown?)"
                    )
                    # THR-134: Rollback reservation on cancellation
                    try:
                        exposure_manager = get_exposure_manager()
                        finalize_trade_reservation(
                            exposure_manager=exposure_manager,
                            decision_id=decision_id,
                            execution_succeeded=False,
                        )
                    except Exception:
                        pass
                    raise  # Re-raise to allow proper cleanup
                except Exception as e:
                    logger.error(
                        "Exception during trade execution for decision %s: %s",
                        decision_id,
                        e,
                        exc_info=True,
                    )
                    # THR-134: Rollback reservation on exception
                    try:
                        exposure_manager = get_exposure_manager()
                        finalize_trade_reservation(
                            exposure_manager=exposure_manager,
                            decision_id=decision_id,
                            execution_succeeded=False,
                        )
                    except Exception:
                        pass
        else:
            # Signal-only mode: send to Telegram for approval
            logger.info(
                "Autonomous execution disabled - sending signals to Telegram for approval"
            )
            await self._send_signals_to_telegram()

        # THR-134: Safety cleanup - clear any stale reservations
        # This handles edge cases where reservations weren't properly committed/rolled back
        try:
            exposure_manager = get_exposure_manager()
            clear_stale_reservations(exposure_manager)
        except Exception as e:
            logger.warning(f"Failed to clear stale reservations: {e}")

        # After processing, transition to LEARNING
        await self._transition_to(AgentState.LEARNING)

    async def _send_signals_to_telegram(self):
        """
        Send trading signals to Telegram for human approval.

        This method formats decisions as Telegram messages with approval buttons.

        SAFETY: If notification delivery fails, signals are logged and marked as failed
        rather than silently continuing. This prevents execution without approval.
        """
        import logging

        logger = logging.getLogger(__name__)

        # Track signal delivery status
        signals_sent = 0
        signals_failed = 0
        failure_reasons = []

        for decision in self._current_decisions:
            decision_id = decision.get("id")
            asset_pair = decision.get("asset_pair")
            confidence = decision.get("confidence", 0)
            reasoning = decision.get("reasoning", "No reasoning provided")
            recommended_position_size = decision.get("recommended_position_size")

            # Format message
            message = (
                f"🤖 *Trading Signal Generated*\n\n"
                f"Asset: {asset_pair}\n"
                f"Action: {action.upper()}\n"
                f"Confidence: {confidence}%\n"
                f"Position Size: {recommended_position_size if recommended_position_size else 'Signal-only'}\n\n"
                f"Reasoning:\n{reasoning}\n\n"
                f"Decision ID: `{decision_id}`\n\n"
                f"Reply with:\n"
                f"✅ `/approve {decision_id}` to execute\n"
                f"❌ `/reject {decision_id}` to skip\n"
                f"📊 `/details {decision_id}` for more info"
            )

            signal_delivered = False

            # Try to send via Telegram if configured
            try:
                telegram_config = (
                    self.config.telegram if hasattr(self.config, "telegram") else {}
                )
                telegram_enabled = telegram_config.get("enabled", False)
                telegram_token = telegram_config.get("bot_token")
                telegram_chat_id = telegram_config.get("chat_id")

                if telegram_enabled and telegram_token and telegram_chat_id:
                    try:
                        from finance_feedback_engine.integrations.telegram_bot import (
                            TelegramBot,
                        )

                        bot = TelegramBot(token=telegram_token)
                        bot.send_message(telegram_chat_id, message)
                        logger.info(
                            f"✅ Signal sent to Telegram for decision {decision_id}"
                        )
                        signal_delivered = True
                        signals_sent += 1
                    except ImportError:
                        error_msg = (
                            "Telegram integration module not available (ImportError)"
                        )
                        logger.warning(error_msg)
                        failure_reasons.append(f"{decision_id}: {error_msg}")
                    except Exception as e:
                        error_msg = f"Telegram send failed: {e}"
                        logger.error(error_msg)
                        failure_reasons.append(f"{decision_id}: {error_msg}")
                else:
                    missing_fields = []
                    if not telegram_enabled:
                        missing_fields.append("enabled=false")
                    if not telegram_token:
                        missing_fields.append("bot_token")
                    if not telegram_chat_id:
                        missing_fields.append("chat_id")
                    error_msg = f"Telegram not configured: {', '.join(missing_fields)}"
                    logger.warning(error_msg)
                    failure_reasons.append(f"{decision_id}: {error_msg}")
            except Exception as e:
                error_msg = f"Telegram config check failed: {e}"
                logger.error(error_msg, exc_info=True)
                failure_reasons.append(f"{decision_id}: {error_msg}")

            # Try webhook delivery if Telegram failed
            if not signal_delivered:
                try:
                    webhook_config = (
                        self.config.webhook if hasattr(self.config, "webhook") else {}
                    )
                    webhook_enabled = webhook_config.get("enabled", False)
                    webhook_url = webhook_config.get("url")

                    if webhook_enabled and webhook_url:
                        # Prepare webhook payload
                        webhook_payload = {
                            "event_type": "trading_decision",
                            "decision_id": decision_id,
                            "timestamp": datetime.datetime.now(
                                datetime.timezone.utc
                            ).isoformat(),
                            "asset_pair": asset_pair,
                            "action": action,
                            "confidence": confidence,
                            "reasoning": reasoning,
                            "recommended_position_size": recommended_position_size,
                        }

                        # Deliver webhook with retry logic
                        webhook_success = await self._deliver_webhook(
                            webhook_url=webhook_url,
                            payload=webhook_payload,
                            max_retries=webhook_config.get("retry_attempts", 3),
                        )

                        if webhook_success:
                            signal_delivered = True
                            signals_sent += 1
                            logger.info(
                                f"✅ Signal sent to webhook for decision {decision_id}"
                            )
                        else:
                            failure_reasons.append(
                                f"{decision_id}: Webhook delivery failed after retries"
                            )
                    else:
                        logger.debug("Webhook not configured, skipping")
                except Exception as e:
                    error_msg = f"Webhook config check failed: {e}"
                    logger.error(error_msg, exc_info=True)
                    failure_reasons.append(f"{decision_id}: {error_msg}")

            # Log signal status
            if not signal_delivered:
                signals_failed += 1
                logger.warning(
                    f"⚠️ Signal delivery FAILED for {asset_pair} (decision {decision_id}). "
                    f"No notification channels available or all failed."
                )
                # Log to console for visibility
                logger.info(
                    f"UNDELIVERED SIGNAL for {asset_pair}: {action.upper()} (confidence: {confidence}%)"
                )

        # Summary reporting
        logger.info(
            f"Signal delivery summary: {signals_sent} sent, {signals_failed} failed "
            f"(out of {len(self._current_decisions)} total decisions)"
        )

        # CRITICAL SAFETY CHECK: If ALL signals failed to deliver, log error and prevent silent failure
        if signals_failed > 0 and signals_sent == 0:
            logger.error(
                f"❌ CRITICAL: All {signals_failed} signal(s) failed to deliver! "
                f"No approval mechanism available. Decisions will NOT be executed."
            )
            logger.error(f"Failure details: {'; '.join(failure_reasons)}")
            # Emit dashboard event
            self._emit_dashboard_event(
                {
                    "type": "signal_delivery_failure",
                    "failed_count": signals_failed,
                    "reasons": failure_reasons,
                    "timestamp": time.time(),
                }
            )
        elif signals_failed > 0:
            logger.warning(
                f"⚠️ Partial signal delivery failure: {signals_failed}/{len(self._current_decisions)} failed"
            )
            logger.warning(f"Failed signals: {'; '.join(failure_reasons)}")

    def _decision_has_recorded_outcome(self, decision_id: Optional[str]) -> bool:
        """Return True when durable memory already contains an outcome for this decision."""
        normalized = normalize_scalar_id(decision_id)
        if not normalized:
            return False

        memory_engine = getattr(self.engine, "memory_engine", None)
        legacy_engine = getattr(memory_engine, "_legacy_engine", None)
        storage_path = getattr(legacy_engine, "storage_path", None)
        if storage_path is None:
            return False

        try:
            outcome_path = Path(storage_path) / f"outcome_{normalized}.json"
            return outcome_path.exists()
        except Exception:
            logger.debug(
                "Failed to check existing outcome artifact for decision %s",
                normalized,
                exc_info=True,
            )
            return False

    def _recover_decision_lineage_for_closed_outcome(
        self, outcome: Dict[str, Any]
    ) -> tuple[Optional[str], str, list[str]]:
        """Best-effort recovery of decision lineage for recorder close events."""
        product = outcome.get("product")
        side = outcome.get("side")
        attempted_sources: list[str] = []
        if not product:
            return None, "no-product", attempted_sources

        recorder = getattr(self.engine, "trade_outcome_recorder", None)
        if recorder and side:
            attempted_sources.append("recorder.open_positions")
            try:
                pos_key = f"{product}_{side}"
                open_positions = getattr(recorder, "open_positions", None)
                if isinstance(open_positions, dict):
                    existing = open_positions.get(pos_key) or {}
                    decision_id = existing.get("decision_id")
                    if decision_id:
                        return decision_id, "recorder.open_positions", attempted_sources
            except Exception:
                logger.debug(
                    "Failed recorder-state decision recovery for closed outcome %s",
                    product,
                    exc_info=True,
                )

        try:
            asset_pair = standardize_asset_pair(product)
        except Exception:
            asset_pair = None

        candidate_asset_pairs = asset_key_candidates(product)

        trade_monitor = getattr(self, "trade_monitor", None)
        if trade_monitor and candidate_asset_pairs:
            try:
                expected = getattr(trade_monitor, "expected_trades", None)
                attempted_sources.append("trade_monitor.expected_trades")
                if isinstance(expected, dict):
                    for candidate_asset_pair in candidate_asset_pairs:
                        association = expected.get(candidate_asset_pair)
                        decision_id = normalize_scalar_id(association)
                        if decision_id:
                            return (
                                decision_id,
                                "trade_monitor.expected_trades",
                                attempted_sources,
                            )

                active_trackers = getattr(trade_monitor, "active_trackers", None)
                attempted_sources.append("trade_monitor.active_trackers")
                if isinstance(active_trackers, dict):
                    for tracker in active_trackers.values():
                        raw_product = getattr(tracker, "product_id", None)
                        if not raw_product:
                            continue
                        tracker_candidates = asset_key_candidates(raw_product)
                        if any(
                            candidate in tracker_candidates
                            for candidate in candidate_asset_pairs
                        ):
                            decision_id = normalize_scalar_id(
                                getattr(tracker, "decision_id", None)
                            )
                            if decision_id:
                                return (
                                    decision_id,
                                    "trade_monitor.active_trackers",
                                    attempted_sources,
                                )

                getter = getattr(trade_monitor, "get_decision_id_by_asset", None)
                attempted_sources.append("trade_monitor.get_decision_id_by_asset")
                if callable(getter):
                    for candidate_asset_pair in candidate_asset_pairs:
                        decision_id = normalize_scalar_id(getter(candidate_asset_pair))
                        if decision_id:
                            return (
                                decision_id,
                                "trade_monitor.get_decision_id_by_asset",
                                attempted_sources,
                            )

                attempted_sources.append("trade_monitor.closed_trades_queue")
                closed_queue = getattr(trade_monitor, "closed_trades_queue", None)
                if closed_queue is not None:
                    queue_items = list(getattr(closed_queue, "queue", []))
                    for closed_trade in reversed(queue_items):
                        closed_product = closed_trade.get(
                            "product_id"
                        ) or closed_trade.get("product")
                        closed_side = closed_trade.get("side")
                        closed_decision_id = closed_trade.get("decision_id")
                        if not closed_product or not closed_decision_id:
                            continue
                        if (
                            closed_side
                            and side
                            and str(closed_side).upper() != str(side).upper()
                        ):
                            continue
                        try:
                            closed_asset_pair = standardize_asset_pair(closed_product)
                        except Exception:
                            closed_asset_pair = None
                        closed_candidates = (
                            [closed_asset_pair] if closed_asset_pair else []
                        )
                        closed_cfm = _pid_to_pair(closed_product)
                        if closed_cfm and closed_cfm not in closed_candidates:
                            closed_candidates.append(closed_cfm)
                        if any(
                            candidate in closed_candidates
                            for candidate in candidate_asset_pairs
                        ):
                            return (
                                closed_decision_id,
                                "trade_monitor.closed_trades_queue",
                                attempted_sources,
                            )
            except Exception:
                logger.debug(
                    "Failed trade-monitor decision recovery for closed outcome %s",
                    product,
                    exc_info=True,
                )

        decision_store = getattr(self.engine, "decision_store", None)
        if decision_store:
            expected_action = None
            normalized_side = str(side or "").upper()
            if normalized_side == "SHORT":
                expected_action = "SELL"
            elif normalized_side == "LONG":
                expected_action = "BUY"

            attempted_sources.append("decision_store.recovery_metadata_product")
            try:
                recent_decisions = decision_store.get_recent_decisions(limit=250)
                matching_recovery_candidates: list[dict[str, Any]] = []
                for decision in recent_decisions:
                    recovery_metadata = decision.get("recovery_metadata") or {}
                    recovery_product = recovery_metadata.get("product_id")
                    decision_id = normalize_scalar_id(decision.get("id"))
                    decision_action = str(decision.get("action") or "").upper()
                    if not recovery_product or not decision_id:
                        continue
                    if str(recovery_product).upper() != str(product).upper():
                        continue
                    if (
                        expected_action
                        and decision_action
                        and decision_action != expected_action
                    ):
                        continue

                    if self._decision_has_recorded_outcome(decision_id):
                        continue

                    matching_recovery_candidates.append(decision)

                if matching_recovery_candidates:
                    def _candidate_priority(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
                        recovery_metadata = candidate.get("recovery_metadata") or {}
                        ensemble_metadata = candidate.get("ensemble_metadata") or {}
                        has_shadowed_from = bool(recovery_metadata.get("shadowed_from_decision_id"))
                        preserved_provider = str(candidate.get("ai_provider") or "").lower() != "recovery"
                        has_rich_metadata = bool(candidate.get("policy_trace")) or bool(
                            ensemble_metadata.get("provider_decisions")
                            or ensemble_metadata.get("role_decisions")
                            or ensemble_metadata.get("voting_strategy")
                        )
                        timestamp = str(candidate.get("timestamp") or "")
                        return (
                            1 if has_shadowed_from else 0,
                            1 if preserved_provider else 0,
                            1 if has_rich_metadata else 0,
                            timestamp,
                        )

                    selected = max(matching_recovery_candidates, key=_candidate_priority)
                    return (
                        normalize_scalar_id(selected.get("id")),
                        "decision_store.recovery_metadata_product",
                        attempted_sources,
                    )
            except Exception:
                logger.debug(
                    "Failed decision-store recovery by product metadata for closed outcome %s",
                    product,
                    exc_info=True,
                )

        return None, "no-hit", attempted_sources

    def _recover_decision_id_for_closed_outcome(
        self, outcome: Dict[str, Any]
    ) -> Optional[str]:
        decision_id, _lineage_source, _attempted_sources = (
            self._recover_decision_lineage_for_closed_outcome(outcome)
        )
        return decision_id

    def _annotate_positions_with_decision_ids(
        self, current_positions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Best-effort enrichment so recorder state preserves decision lineage while positions remain open."""
        if not current_positions:
            return []

        def _normalize_lineage_candidate(value: Any) -> Optional[str]:
            return normalize_scalar_id(value)

        recorder = getattr(self.engine, "trade_outcome_recorder", None)
        trade_monitor = getattr(self, "trade_monitor", None)
        enriched_positions: list[dict[str, Any]] = []

        for raw_position in current_positions:
            position = dict(raw_position)
            existing_decision_id = _normalize_lineage_candidate(
                position.get("decision_id")
            )
            if existing_decision_id:
                position["decision_id"] = existing_decision_id
                enriched_positions.append(position)
                continue

            product_id = (
                position.get("product_id")
                or position.get("product")
                or position.get("instrument")
            )
            side = position.get("side")
            decision_id = None

            trade_monitor_decision_id = None
            if trade_monitor and product_id:
                getter = getattr(trade_monitor, "get_decision_id_by_asset", None)
                if callable(getter):
                    try:
                        trade_monitor_decision_id = _normalize_lineage_candidate(
                            getter(product_id)
                        )
                    except Exception:
                        logger.debug(
                            "Failed trade-monitor lookup while annotating active position %s",
                            product_id,
                            exc_info=True,
                        )

            if recorder and product_id and side:
                try:
                    pos_key = f"{product_id}_{side}"
                    open_positions = getattr(recorder, "open_positions", None)
                    if isinstance(open_positions, dict):
                        existing = open_positions.get(pos_key) or {}
                        decision_id = _normalize_lineage_candidate(
                            existing.get("decision_id")
                        )
                except Exception:
                    logger.debug(
                        "Failed recorder-state lookup while annotating active position %s",
                        product_id,
                        exc_info=True,
                    )

            if trade_monitor_decision_id:
                decision_id = trade_monitor_decision_id

            if decision_id:
                position["decision_id"] = decision_id

            enriched_positions.append(position)

        return enriched_positions

    @staticmethod
    def _normalize_trade_outcome_product_aliases(
        trade_outcome: dict[str, Any]
    ) -> dict[str, Any]:
        """Populate both `product` and `product_id` aliases for close outcomes."""
        if not isinstance(trade_outcome, dict):
            return trade_outcome

        product = trade_outcome.get("product")
        product_id = trade_outcome.get("product_id")
        if product and not product_id:
            trade_outcome = {**trade_outcome, "product_id": product}
        elif product_id and not product:
            trade_outcome = {**trade_outcome, "product": product_id}
        return trade_outcome

    def _sync_trade_outcome_recorder(
        self, current_positions: list[dict[str, Any]]
    ) -> None:
        """Sync the outcome recorder with live positions and forward closes into learning."""
        recorder = getattr(self.engine, "trade_outcome_recorder", None)
        if recorder is None:
            return

        current_positions = self._annotate_positions_with_decision_ids(
            current_positions or []
        )

        try:
            outcomes = recorder.update_positions(current_positions or [])
        except Exception as e:
            logger.warning("Trade outcome recorder sync failed: %s", e, exc_info=True)
            return

        if not outcomes:
            return

        logger.info(
            "Trade outcome recorder detected %d closed position(s)",
            len(outcomes),
        )

        for outcome in outcomes:
            outcome = self._normalize_trade_outcome_product_aliases(outcome)
            decision_id = normalize_scalar_id(outcome.get("decision_id"))
            product = outcome.get("product") or outcome.get("product_id") or "UNKNOWN"
            order_id = outcome.get("order_id") or outcome.get("trade_id") or "UNKNOWN"
            lineage_source = "outcome"
            attempted_sources: list[str] = []
            if not decision_id:
                decision_id, lineage_source, attempted_sources = (
                    self._recover_decision_lineage_for_closed_outcome(outcome)
                )
                if decision_id:
                    outcome["decision_id"] = decision_id
                    logger.info(
                        "Recovered decision_id %s for closed position %s | lineage_source=%s | attempted_sources=%s",
                        decision_id,
                        product,
                        lineage_source,
                        attempted_sources,
                    )
                else:
                    logger.warning(
                        "Learning handoff SKIPPED for closed position %s | order_id=%s | reason=missing_decision_id | attempted_sources=%s",
                        product,
                        order_id,
                        attempted_sources,
                    )
                    logger.warning(
                        "Closed position %s missing decision_id; durable artifact recorded but learning update skipped | attempted_sources=%s",
                        product,
                        attempted_sources,
                    )
                    continue

            logger.info(
                "Learning handoff ATTEMPT for closed position %s | order_id=%s | decision_id=%s | lineage_source=%s",
                product,
                order_id,
                decision_id,
                lineage_source,
            )

            try:
                memory_outcome = self.engine.record_trade_outcome(
                    decision_id,
                    exit_price=float(outcome["exit_price"]),
                    exit_timestamp=outcome.get("exit_time"),
                )
                realized_pnl = getattr(memory_outcome, "realized_pnl", None)
                if realized_pnl is None:
                    realized_pnl = outcome.get("realized_pnl", 0)
                pnl_value = float(realized_pnl or 0.0)
                self._update_performance_metrics(
                    {
                        "realized_pnl": pnl_value,
                        "was_profitable": pnl_value > 0,
                    }
                )
                logger.info(
                    "Learning handoff ACCEPTED for closed position %s | order_id=%s | decision_id=%s | realized_pnl=%s",
                    product,
                    order_id,
                    decision_id,
                    pnl_value,
                )
                logger.info(
                    "Recorded learning outcome for decision %s from closed position %s",
                    decision_id,
                    product,
                )
            except Exception as e:
                logger.error(
                    "Learning handoff FAILED for closed position %s | order_id=%s | decision_id=%s | error=%s",
                    product,
                    order_id,
                    decision_id,
                    e,
                    exc_info=True,
                )
                logger.error(
                    "Failed to forward closed position %s into learning for decision %s: %s",
                    product,
                    decision_id,
                    e,
                    exc_info=True,
                )

    async def handle_learning_state(self):
        """
        LEARNING: Processing outcomes of closed trades to update the model.
        """
        logger.info("=" * 80)
        logger.info("State: LEARNING - Processing closed trades for feedback...")
        logger.info("=" * 80)

        # --- Cleanup rejected decisions cache (prevent memory leak) ---
        self._cleanup_rejected_cache()

        closed_trades = self.trade_monitor.get_closed_trades()
        if not closed_trades:
            logger.info("No closed trades to process.")
        else:
            logger.info(f"Processing {len(closed_trades)} closed trades...")
            for trade_outcome in closed_trades:
                trade_outcome = self._normalize_trade_outcome_product_aliases(
                    trade_outcome
                )

                decision_id = normalize_scalar_id(trade_outcome.get("decision_id"))
                product = (
                    trade_outcome.get("product")
                    or trade_outcome.get("product_id")
                    or "UNKNOWN"
                )
                trade_id = (
                    trade_outcome.get("trade_id")
                    or trade_outcome.get("id")
                    or "UNKNOWN"
                )
                lineage_source = "outcome"
                attempted_sources: list[str] = []

                if not decision_id:
                    decision_id, lineage_source, attempted_sources = (
                        self._recover_decision_lineage_for_closed_outcome(trade_outcome)
                    )
                    if decision_id:
                        trade_outcome = {**trade_outcome, "decision_id": decision_id}
                        logger.info(
                            "Recovered decision_id %s for monitor-closed trade %s | lineage_source=%s | attempted_sources=%s",
                            decision_id,
                            product,
                            lineage_source,
                            attempted_sources,
                        )
                    else:
                        logger.warning(
                            "Learning handoff SKIPPED for monitor-closed trade %s | trade_id=%s | reason=missing_decision_id | attempted_sources=%s",
                            product,
                            trade_id,
                            attempted_sources,
                        )
                        continue

                logger.info(
                    "Learning handoff ATTEMPT for monitor-closed trade %s | trade_id=%s | decision_id=%s | lineage_source=%s",
                    product,
                    trade_id,
                    decision_id,
                    lineage_source,
                )

                try:
                    self.engine.record_trade_outcome(trade_outcome)
                    self._update_performance_metrics(trade_outcome)
                    logger.info(
                        "Learning handoff ACCEPTED for monitor-closed trade %s | trade_id=%s | decision_id=%s",
                        product,
                        trade_id,
                        decision_id,
                    )
                except Exception as e:
                    logger.error(
                        "Learning handoff FAILED for monitor-closed trade %s | trade_id=%s | decision_id=%s | error=%s",
                        product,
                        trade_id,
                        decision_id,
                        e,
                        exc_info=True,
                    )

        # After processing, end this cycle cleanly; the next process_cycle() call will start PERCEPTION
        await self._transition_to(AgentState.IDLE)

    def _preload_trade_pnl_history(self) -> None:
        """Phase 4: Pre-load P&L history from durable trade outcome files on startup.

        Reads data/trade_outcomes/*.jsonl to populate _trade_pnl_history so the
        sortino gate can evaluate immediately instead of cold-starting after
        every restart. Only non-zero realized_pnl values are loaded, ordered
        chronologically (oldest first).
        """
        import glob
        import json
        import os

        outcomes_dir = os.path.join("data", "trade_outcomes")
        if not os.path.isdir(outcomes_dir):
            logger.info("Track SK: No trade outcomes directory found, starting with empty P&L history")
            return

        pnls = []
        try:
            files = sorted(glob.glob(os.path.join(outcomes_dir, "*.jsonl")))
            for fpath in files:
                try:
                    with open(fpath) as f:
                        for line in f:
                            try:
                                rec = json.loads(line)
                                p = float(rec.get("realized_pnl", 0))
                                if p != 0:
                                    pnls.append(p)
                            except (json.JSONDecodeError, TypeError, ValueError):
                                continue
                except OSError:
                    continue

            # deque(maxlen=500) auto-caps, but only load last 500
            for p in pnls[-500:]:
                self._trade_pnl_history.append(p)

            logger.info(
                "Track SK: Pre-loaded %d P&L samples from %d outcome files "
                "(deque has %d, gate can evaluate immediately)",
                len(pnls),
                len(files),
                len(self._trade_pnl_history),
            )
        except Exception as e:
            logger.warning("Track SK: Failed to pre-load P&L history: %s", e)

    def _update_performance_metrics(self, trade_outcome: Dict[str, Any]) -> None:
        """
        Update performance metrics based on a completed trade.

        Args:
            trade_outcome: Dictionary containing trade results
        """
        try:
            # Extract trade details
            realized_pnl = trade_outcome.get("realized_pnl", 0)
            is_profitable = trade_outcome.get("was_profitable", realized_pnl > 0)

            # Track SK: append to P&L history for sortino gate (deque auto-caps)
            if realized_pnl != 0:
                self._trade_pnl_history.append(float(realized_pnl))

            # Update basic metrics
            self._performance_metrics["total_trades"] += 1
            self._performance_metrics["total_pnl"] += realized_pnl

            if is_profitable:
                self._performance_metrics["winning_trades"] += 1
                self._performance_metrics["avg_win"] = (
                    self._performance_metrics["avg_win"]
                    * (self._performance_metrics["winning_trades"] - 1)
                    + realized_pnl
                ) / self._performance_metrics["winning_trades"]

                # Update streaks
                self._performance_metrics["current_streak"] = max(
                    1, self._performance_metrics["current_streak"] + 1
                )
                self._performance_metrics["best_streak"] = max(
                    self._performance_metrics["best_streak"],
                    self._performance_metrics["current_streak"],
                )
            else:
                self._performance_metrics["losing_trades"] += 1
                self._performance_metrics["avg_loss"] = (
                    self._performance_metrics["avg_loss"]
                    * (self._performance_metrics["losing_trades"] - 1)
                    + abs(realized_pnl)
                ) / self._performance_metrics["losing_trades"]

                # Update streaks
                self._performance_metrics["current_streak"] = min(
                    -1, self._performance_metrics["current_streak"] - 1
                )
                self._performance_metrics["worst_streak"] = min(
                    self._performance_metrics["worst_streak"],
                    self._performance_metrics["current_streak"],
                )

            # Update win rate
            if self._performance_metrics["total_trades"] > 0:
                self._performance_metrics["win_rate"] = (
                    self._performance_metrics["winning_trades"]
                    / self._performance_metrics["total_trades"]
                ) * 100

            logger.debug(
                f"Updated performance metrics: P&L=${realized_pnl:.2f}, Total=${self._performance_metrics['total_pnl']:.2f}"
            )

            # Check if batch review should be triggered (every 20 trades)
            self._batch_review_counter += 1
            if self._batch_review_counter % 20 == 0:
                self._perform_batch_review()

        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}", exc_info=True)

    def _perform_batch_review(self) -> None:
        """
        Perform batch review every 20 trades:
        1. Recalculate rolling cost averages
        2. Check Kelly activation criteria
        3. Log performance trends and recommendations
        """
        import datetime

        batch_number = self._batch_review_counter // 20
        logger.info(f"\n{'='*60}")
        logger.info(
            f"BATCH REVIEW #{batch_number} (After {self._batch_review_counter} trades)"
        )
        logger.info(f"{'='*60}")

        try:
            # 1. Recalculate rolling cost averages
            cost_stats = self.portfolio_memory.calculate_rolling_cost_averages(
                window=20, exclude_outlier_pct=0.10
            )

            if cost_stats.get("has_data"):
                logger.info(
                    f"Transaction Costs (20-trade avg): {cost_stats.get('avg_total_cost_pct', 0):.3f}% per position"
                )
                logger.info(
                    f"  - Slippage: {cost_stats.get('avg_slippage_pct', 0):.3f}%"
                )
                logger.info(f"  - Fees: {cost_stats.get('avg_fee_pct', 0):.3f}%")
                logger.info(f"  - Spread: {cost_stats.get('avg_spread_pct', 0):.3f}%")
                logger.info(
                    f"  - Sample size: {cost_stats.get('sample_size', 0)} trades ({cost_stats.get('outliers_filtered', 0)} outliers filtered)"
                )
            else:
                logger.info(
                    "Transaction Costs: Insufficient data (<20 trades with cost info)"
                )

            # 2. Check Kelly activation criteria (requires 50+ trades)
            # --- Track SK: Sortino-gated Kelly status (replaces legacy _kelly_activated) ---
            if self._sortino_gate is not None and self._last_sortino_gate_result is not None:
                sgr = self._last_sortino_gate_result
                logger.info(
                    f"\nSortino-Kelly Status: {sgr.sizing_mode.upper()} "
                    f"(sortino={sgr.weighted_sortino:.3f}, multiplier={sgr.kelly_multiplier:.2f}, "
                    f"trades={sgr.trade_count}, windows={sgr.windows_used})"
                )
                if sgr.short_window_veto:
                    logger.warning("  ⚠️ Short-window veto active — recent performance deteriorating")
                if sgr.sizing_mode != "fixed_risk":
                    logger.info(f"  🎯 Kelly active: {sgr.reason}")
                else:
                    logger.info(f"  ℹ️ Fixed risk: {sgr.reason}")
            elif self._sortino_gate is not None:
                logger.info(
                    f"\nSortino-Kelly Status: BOOTSTRAP ({len(self._trade_pnl_history)} P&L samples collected)"
                )

            # Legacy Kelly check (INFORMATIONAL ONLY — does NOT drive sizing decisions.
            # Sortino gate above is the authoritative sizing controller.)
            if self._performance_metrics["total_trades"] >= 50:
                kelly_check = self.portfolio_memory.check_kelly_activation_criteria(
                    window=50
                )
                previous_status = self._kelly_activated
                should_activate = kelly_check.get("should_activate_kelly", False)
                self._kelly_activated = should_activate
                logger.info(
                    f"  [INFO ONLY] Legacy Kelly: {'ACTIVATED' if should_activate else 'NOT ACTIVATED'} "
                    f"(PF={kelly_check.get('avg_pf', 0):.3f}, PF_std={kelly_check.get('pf_std', 0):.3f}) "
                    f"— not used for sizing"
                )
            else:
                remaining_trades = 50 - self._performance_metrics["total_trades"]
                logger.info(
                    f"  [INFO ONLY] Legacy Kelly: BOOTSTRAP ({remaining_trades} trades to eligibility) — not used for sizing"
                )
                logger.info(
                    "  Using platform-specific fixed sizing until 50-trade threshold."
                )

            # 3. Performance trend analysis
            win_rate = self._performance_metrics.get("win_rate", 0)
            avg_win = self._performance_metrics.get("avg_win", 0)
            avg_loss = self._performance_metrics.get("avg_loss", 0)
            profit_factor = (
                (avg_win * win_rate / 100) / (avg_loss * (1 - win_rate / 100))
                if avg_loss > 0 and win_rate < 100
                else float("inf")
            )

            logger.info("\nPerformance Summary:")
            logger.info(
                f"  - Total Trades: {self._performance_metrics['total_trades']}"
            )
            logger.info(f"  - Win Rate: {win_rate:.1f}%")
            logger.info(
                f"  - Profit Factor: {profit_factor:.2f}"
                if profit_factor != float("inf")
                else "  - Profit Factor: ∞ (no losses)"
            )
            logger.info(f"  - Total P&L: ${self._performance_metrics['total_pnl']:.2f}")
            logger.info(
                f"  - Current Streak: {self._performance_metrics['current_streak']}"
            )

            # Store batch review timestamp
            self._last_batch_review_time = datetime.datetime.now(datetime.timezone.utc)
            logger.info(f"\n{'='*60}\n")

        except Exception as e:
            logger.error(f"Error during batch review: {e}", exc_info=True)

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the agent's performance.

        Returns:
            Dictionary with performance metrics
        """
        return {
            "total_pnl": self._performance_metrics["total_pnl"],
            "total_trades": self._performance_metrics["total_trades"],
            "winning_trades": self._performance_metrics["winning_trades"],
            "losing_trades": self._performance_metrics["losing_trades"],
            "win_rate": self._performance_metrics["win_rate"],
            "avg_win": self._performance_metrics["avg_win"],
            "avg_loss": self._performance_metrics["avg_loss"],
            "current_streak": self._performance_metrics["current_streak"],
            "best_streak": self._performance_metrics["best_streak"],
            "worst_streak": self._performance_metrics["worst_streak"],
            "pnl_ratio": (
                abs(
                    self._performance_metrics["avg_win"]
                    / self._performance_metrics["avg_loss"]
                )
                if self._performance_metrics["avg_loss"] != 0
                else float("inf")
            ),
        }

    def get_loop_metrics(self) -> Dict[str, Any]:
        """Return cycle timing metrics for API consumption."""
        return asdict(self._loop_metrics)

    async def _deliver_webhook(
        self, webhook_url: str, payload: dict, max_retries: int = 3
    ) -> bool:
        """
        Deliver webhook payload to configured URL with retry logic.

        Args:
            webhook_url: Target webhook URL
            payload: JSON payload to deliver
            max_retries: Maximum retry attempts

        Returns:
            bool: True if delivered successfully
        """
        import httpx
        from tenacity import (
            retry,
            retry_if_exception,
            stop_after_attempt,
            wait_exponential,
        )

        def is_retryable_error(exception):
            """
            Determine if an error should be retried.

            Retry on:
            - Network errors (RequestError, TimeoutException)
            - 5xx server errors (transient failures)

            Don't retry on:
            - 4xx client errors (permanent failures)
            """
            if isinstance(exception, httpx.HTTPStatusError):
                # Only retry on 5xx server errors
                return 500 <= exception.response.status_code < 600
            # Always retry network/timeout errors
            return isinstance(exception, (httpx.RequestError, httpx.TimeoutException))

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception(is_retryable_error),
        )
        async def _send_webhook():
            webhook_config = getattr(self, "webhook_config", {}) or {}
            timeout_seconds = webhook_config.get("timeout_seconds", 10.0)
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "FinanceFeedbackEngine/0.9.9",
                        "X-FFE-Event": payload.get("event_type", "decision"),
                    },
                )
                response.raise_for_status()
                return response

        try:
            response = await _send_webhook()
            # Handle case where response might be None (shouldn't happen but defensive)
            if response is None:
                logger.error("Webhook delivery returned None response")
                return False

            # Sanitize URL to prevent credential exposure in logs
            from urllib.parse import urlparse

            parsed_url = urlparse(webhook_url)
            safe_url = f"{parsed_url.scheme}://{parsed_url.netloc}/***"
            logger.info(
                f"✅ Webhook delivered successfully to {safe_url} "
                f"(status: {response.status_code})"
            )
            return True
        except (httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            # Log error without exposing webhook URL
            error_type = type(e).__name__
            status_code = (
                getattr(e.response, "status_code", "N/A")
                if hasattr(e, "response")
                else "N/A"
            )
            logger.error(
                f"❌ Webhook delivery failed after {max_retries} attempts: "
                f"{error_type} (status: {status_code})",
                exc_info=True,
            )
            return False

    def _extract_order_id_from_execution_result(
        self, execution_result: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Extract a concrete platform order id from normalized or nested execution payloads."""
        if not isinstance(execution_result, dict):
            return None

        response = execution_result.get("response") or {}
        top_level_success_response = execution_result.get("success_response") or {}
        success_response = response.get("success_response") or {}
        candidates = [
            execution_result.get("order_id"),
            (
                top_level_success_response.get("order_id")
                if isinstance(top_level_success_response, dict)
                else None
            ),
            response.get("order_id") if isinstance(response, dict) else None,
            (
                success_response.get("order_id")
                if isinstance(success_response, dict)
                else None
            ),
        ]
        for candidate in candidates:
            if candidate:
                return str(candidate)
        return None

    def _normalize_execution_action(self, decision: Dict[str, Any]) -> Optional[str]:
        """Normalize canonical policy actions to adapter-edge BUY/SELL semantics."""
        raw_action = decision.get("policy_action") or decision.get("action", "")
        if is_policy_action(raw_action):
            legacy = get_legacy_action_compatibility(raw_action)
            if legacy:
                return legacy
            family = get_policy_action_family(raw_action)
            if family in {"reduce_long", "close_long", "open_short", "add_short"}:
                return "SELL"
            if family in {"reduce_short", "close_short", "open_long", "add_long"}:
                return "BUY"
            return None
        normalized = str(raw_action).upper()
        return normalized if normalized in {"BUY", "SELL"} else None

    def _counts_toward_daily_trade_limit(
        self, decision: Dict[str, Any], execution_result: Dict[str, Any]
    ) -> bool:
        """
        Determine whether an attempted execution should consume one daily trade slot.

        Rules:
        - Must be a successful actionable execution (normalized to BUY/SELL at the adapter edge)
        - Must have an order identifier
        - Must NOT be rejected/cancelled/failed due to logistics (insufficient funds,
          connectivity, stale data, platform rejection)
        """
        if not execution_result or not execution_result.get("success"):
            return False

        action = self._normalize_execution_action(decision)
        if action not in {"BUY", "SELL"}:
            return False

        response = execution_result.get("response") or {}
        order_id = self._extract_order_id_from_execution_result(execution_result)
        if not order_id:
            # No concrete order => do not burn daily quota
            return False

        order_status = str(
            execution_result.get("order_status") or response.get("status") or ""
        ).upper()
        non_count_statuses = {
            "FAILED",
            "FAILURE",
            "REJECTED",
            "CANCELED",
            "CANCELLED",
            "EXPIRED",
            "PENDING_REJECT",
        }
        if order_status in non_count_statuses:
            return False

        error_blob = " ".join(
            str(v)
            for v in [
                execution_result.get("error", ""),
                execution_result.get("error_details", ""),
                (response.get("error_response", {}) or {}).get("error", ""),
                (response.get("error_response", {}) or {}).get("message", ""),
                (response.get("error_response", {}) or {}).get(
                    "preview_failure_reason", ""
                ),
            ]
            if v
        ).lower()

        logistical_failure_markers = [
            "insufficient_fund",
            "insufficient fund",
            "preview_insufficient_fund",
            "connection",
            "timeout",
            "name resolution",
            "stale",
            "rejected",
            "order creation failed",
            "no valid coinbase balance",
            "rate limit",
        ]
        if any(marker in error_blob for marker in logistical_failure_markers):
            return False

        return True

    def _ensure_decision_identity(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure decisions have stable identity/timestamp before persistence."""
        if not decision.get("id"):
            decision["id"] = str(uuid.uuid4())
        if not decision.get("timestamp"):
            decision["timestamp"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        return decision

    def _normalize_decision_for_persistence(
        self, decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Backfill canonical learning metadata before save/update operations."""
        normalized = normalize_decision_record(dict(decision or {}))
        decision.clear()
        decision.update(normalized)
        return decision

    def _attach_decision_artifact(
        self, decision: Dict[str, Any], *, execution_attempted: bool
    ) -> Dict[str, Any]:
        """Attach a compact per-decision artifact for later sweep/debug inspection."""
        self._ensure_decision_identity(decision)
        decision["decision_artifact"] = {
            "decision_id": decision.get("id"),
            "cycle_timestamp": decision.get("timestamp"),
            "asset_pair": decision.get("asset_pair"),
            "final_action": decision.get("policy_action") or decision.get("action"),
            "confidence": decision.get("confidence"),
            "actionable": decision.get("actionable", False),
            "filtered_reason_code": decision.get("filtered_reason_code"),
            "filtered_reason_text": decision.get("filtered_reason_text"),
            "hold_origin": decision.get("hold_origin"),
            "hold_is_genuine": decision.get("hold_is_genuine"),
            "execution_attempted": execution_attempted,
            "provider_decisions": (
                (decision.get("ensemble_metadata") or {}).get("provider_decisions")
            ),
        }
        return self._normalize_decision_for_persistence(decision)

    def _log_portfolio_risk_snapshot(
        self,
        label: str,
        portfolio_snapshot: Optional[Dict[str, Any]],
        *,
        open_asset_pairs: Optional[set[str]] = None,
        open_position_side: Optional[Dict[str, str]] = None,
        managed_asset_pairs: Optional[set[str]] = None,
        margin_usage_pct: Optional[float] = None,
    ) -> None:
        """Log a compact portfolio/position awareness snapshot for operator visibility."""
        try:
            portfolio_snapshot = portfolio_snapshot or {}
            candidate_positions = []
            total_balance = 0.0
            buying_power = 0.0
            initial_margin = 0.0
            unrealized_pnl = 0.0

            if "platform_breakdowns" in portfolio_snapshot:
                for platform_name, platform_data in (
                    portfolio_snapshot.get("platform_breakdowns") or {}
                ).items():
                    candidate_positions.extend(
                        (platform_data.get("futures_positions") or [])
                    )
                    candidate_positions.extend((platform_data.get("positions") or []))
                    if str(platform_name).lower() == "coinbase":
                        futures_summary = platform_data.get("futures_summary") or {}
                        total_balance = float(
                            futures_summary.get("total_balance_usd", 0.0)
                            or platform_data.get("total_value_usd", 0.0)
                            or total_balance
                            or 0.0
                        )
                        buying_power = float(
                            futures_summary.get("buying_power", 0.0)
                            or buying_power
                            or 0.0
                        )
                        initial_margin = float(
                            futures_summary.get("initial_margin", 0.0)
                            or initial_margin
                            or 0.0
                        )
                        unrealized_pnl = float(
                            futures_summary.get("unrealized_pnl", 0.0)
                            or unrealized_pnl
                            or 0.0
                        )
            else:
                candidate_positions.extend(
                    (portfolio_snapshot.get("futures_positions") or [])
                )
                candidate_positions.extend((portfolio_snapshot.get("positions") or []))
                total_balance = float(
                    portfolio_snapshot.get("total_value_usd", 0.0) or 0.0
                )
                buying_power = float(portfolio_snapshot.get("buying_power", 0.0) or 0.0)
                initial_margin = float(
                    portfolio_snapshot.get("initial_margin", 0.0) or 0.0
                )
                unrealized_pnl = float(
                    portfolio_snapshot.get("unrealized_pnl", 0.0) or 0.0
                )

            raw_products = []
            derived_assets = set(open_asset_pairs or [])
            side_summary = dict(open_position_side or {})

            for pos in candidate_positions:
                raw_pair = pos.get("product_id") or pos.get("instrument")
                if raw_pair:
                    raw_products.append(str(raw_pair))
                canonical = _pid_to_pair(raw_pair)
                if canonical is None:
                    try:
                        canonical = (
                            standardize_asset_pair(raw_pair) if raw_pair else None
                        )
                    except Exception:
                        canonical = None
                if canonical:
                    derived_assets.add(canonical)
                    if canonical not in side_summary:
                        side_summary[canonical] = str(
                            pos.get("side") or "UNKNOWN"
                        ).upper()

            positions_count = len(candidate_positions)
            margin_usage_effective = margin_usage_pct
            if (
                margin_usage_effective is None
                and total_balance > 0
                and initial_margin > 0
            ):
                margin_usage_effective = initial_margin / total_balance

            logger.info(
                "%s | asset_scoped_open_positions=%d | asset_scoped_pairs=%s | sides=%s | total_balance=$%.2f | buying_power=$%.2f | unrealized_pnl=$%.2f | initial_margin=$%.2f | margin_usage=%s | global_managed_pairs=%s | platform_products=%s",
                label,
                positions_count,
                sorted(derived_assets),
                {k: side_summary[k] for k in sorted(side_summary)},
                total_balance,
                buying_power,
                unrealized_pnl,
                initial_margin,
                (
                    f"{margin_usage_effective * 100:.2f}%"
                    if margin_usage_effective is not None
                    else "n/a"
                ),
                sorted(managed_asset_pairs) if managed_asset_pairs else [],
                sorted(raw_products),
            )
        except Exception:
            logger.debug("Failed to log portfolio risk snapshot", exc_info=True)

    def _log_council_summary(
        self, decision: Dict[str, Any], asset_pair: Optional[str] = None
    ) -> None:
        """Log concise bull/bear/judge council summaries with canonical policy-action labels."""
        try:
            ensemble_metadata = decision.get("ensemble_metadata") or {}
            role_decisions = ensemble_metadata.get("role_decisions") or {}
            if not role_decisions:
                return
            asset_label = asset_pair or decision.get("asset_pair") or "UNKNOWN"
            parts = []
            for role in ("bull", "bear", "judge"):
                role_decision = role_decisions.get(role) or {}
                if not role_decision:
                    continue
                provider = (
                    role_decision.get("provider")
                    or (ensemble_metadata.get("debate_seats") or {}).get(role)
                    or "unknown"
                )
                raw_action = (
                    role_decision.get("policy_action")
                    or role_decision.get("action")
                    or "UNKNOWN"
                )
                try:
                    action = (
                        normalize_policy_action(raw_action).value
                        if is_policy_action(raw_action)
                        else str(raw_action).upper()
                    )
                except Exception:
                    action = str(raw_action)
                confidence = role_decision.get("confidence")
                confidence_text = str(confidence) if confidence is not None else "?"
                reasoning = str(role_decision.get("reasoning") or "")
                reasoning_snippet = reasoning[:80] + (
                    "..." if len(reasoning) > 80 else ""
                )
                if reasoning_snippet:
                    parts.append(
                        f"{role}={provider}:{action}/{confidence_text} ({reasoning_snippet})"
                    )
                else:
                    parts.append(f"{role}={provider}:{action}/{confidence_text}")
            if parts:
                logger.info(
                    "Council summary for %s | %s", asset_label, " | ".join(parts)
                )
        except Exception:
            logger.debug("Failed to log council summary", exc_info=True)

    def _update_execution_confirmation_contract(self, decision: Dict[str, Any]) -> None:
        """Update execution confirmation contract after trade execution."""
        try:
            policy_trace = decision.get("policy_trace")
            if not isinstance(policy_trace, dict):
                return

            chain = policy_trace.get("stage_49_62_contract_chain", {})
            orch = chain.get("orchestration_summary", {})
            exec_ex = orch.get("exchange_execution", {})

            if "execution_confirmation_contract" not in exec_ex:
                return

            exec_result = decision.get("execution_result", {})
            exec_conf = exec_ex["execution_confirmation_contract"]

            # Map execution result to contract
            exec_conf["execution_status"] = decision.get("execution_status", "unknown")
            exec_conf["execution_success"] = exec_result.get("success", False)
            exec_conf["execution_timestamp"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()

            if exec_result.get("order_id"):
                exec_conf["order_id"] = exec_result["order_id"]
            if exec_result.get("platform"):
                exec_conf["platform"] = exec_result["platform"]
            if exec_result.get("message"):
                exec_conf["execution_message"] = exec_result["message"]

        except Exception as e:
            logger.warning(f"Failed to update execution confirmation contract: {e}")

    def _persist_no_action_decision(
        self,
        decision: Dict[str, Any],
        *,
        asset_pair: str,
        reason_code: str,
        reason: str,
    ) -> None:
        """Persist explicit no-action artifacts when analysis returns no materialized decision payload."""
        try:
            normalized = dict(decision or {})
            normalized.setdefault("asset_pair", asset_pair)
            normalized.setdefault("action", "HOLD")
            self._ensure_decision_identity(normalized)
            normalized["executed"] = False
            normalized["actionable"] = False
            normalized["filtered_reason_code"] = reason_code
            normalized["filtered_reason_text"] = reason
            normalized["execution_status"] = "no_action"
            normalized["execution_result"] = {
                "success": True,
                "reason_code": reason_code,
                "message": reason,
            }
            self._attach_decision_artifact(normalized, execution_attempted=False)
            if getattr(self.engine, "decision_store", None):
                self.engine.decision_store.save_decision(normalized)
        except Exception as e:
            logger.warning(
                "Failed to persist no-action decision for %s: %s", asset_pair, e
            )

    def _mark_decision_not_executed(
        self, decision: Dict[str, Any], reason_code: str, reason: str
    ) -> None:
        """Persist explicit non-execution reason on a decision for observability."""
        try:
            had_id = bool(decision.get("id"))
            self._ensure_decision_identity(decision)
            decision["executed"] = False
            decision["actionable"] = False
            decision["filtered_reason_code"] = reason_code
            decision["filtered_reason_text"] = reason
            decision["execution_status"] = "filtered"
            decision["execution_result"] = {
                "success": False,
                "reason_code": reason_code,
                "error": reason,
            }
            self._attach_decision_artifact(decision, execution_attempted=False)
            decision["control_outcome"] = build_control_outcome(
                action=decision.get("action"),
                structural_action_validity=decision.get("structural_action_validity"),
                invalid_action_reason_text=decision.get("invalid_action_reason"),
                risk_vetoed=bool(decision.get("risk_vetoed", False)),
                risk_veto_reason=decision.get("risk_veto_reason"),
                execution_status=decision.get("execution_status"),
                execution_result=decision.get("execution_result"),
            )
            policy_package = decision.get("policy_package")
            if isinstance(policy_package, dict):
                policy_package["control_outcome"] = decision["control_outcome"].copy()
            policy_trace = decision.get("policy_trace")
            if isinstance(policy_trace, dict):
                trace_package = policy_trace.get("policy_package")
                if isinstance(trace_package, dict):
                    trace_package["control_outcome"] = decision[
                        "control_outcome"
                    ].copy()
            if getattr(self.engine, "decision_store", None):
                if had_id:
                    self._normalize_decision_for_persistence(decision)
                    self.engine.decision_store.update_decision(decision)
                else:
                    self._normalize_decision_for_persistence(decision)
                    self.engine.decision_store.save_decision(decision)
        except Exception as e:
            logger.warning(
                "Failed to persist non-execution reason for %s: %s",
                decision.get("id"),
                e,
            )

    def _classify_action_execution_outcome(
        self, decision: Dict[str, Any], risk_reason: str | None = None
    ) -> tuple[bool, str | None, str | None, str | None]:
        """Classify whether a policy-aware decision is executable vs invalid/vetoed/rejected."""
        structural_validity = decision.get("structural_action_validity")
        invalid_reason = decision.get("invalid_action_reason")
        risk_vetoed = bool(decision.get("risk_vetoed", False))
        risk_veto_reason = decision.get("risk_veto_reason")

        if structural_validity == "invalid":
            return (
                False,
                "invalid",
                "INVALID_POLICY_ACTION",
                invalid_reason or f"Invalid policy action: {action}",
            )

        if risk_vetoed:
            return (
                False,
                "vetoed",
                "RISK_VETO",
                risk_veto_reason or risk_reason or f"Risk vetoed action: {action}",
            )

        if risk_reason:
            return False, "rejected", "RISK_REJECTED", risk_reason

        return True, "executable", None, None

    async def _should_execute_with_reason(self, decision):
        """Return (should_execute, reason_code, reason_message)."""
        confidence = decision.get("confidence", 0)
        confidence_normalized = confidence / 100.0
        if confidence_normalized < self.config.min_confidence_threshold:
            msg = f"Low confidence ({confidence}% < {self.config.min_confidence_threshold*100:.0f}%)"
            logger.info("Skipping trade due to %s", msg)
            return False, "LOW_CONFIDENCE", msg

        controls = ExecutionQualityControls(
            enabled=bool(getattr(self.config, "quality_gate_enabled", True)),
            min_risk_reward_ratio=float(
                getattr(self.config, "min_risk_reward_ratio", 1.25)
            ),
            high_volatility_threshold=float(
                getattr(self.config, "high_volatility_threshold", 0.04)
            ),
            high_volatility_min_confidence=float(
                getattr(self.config, "high_volatility_min_confidence", 80.0)
            ),
            full_size_confidence=float(
                getattr(self.config, "position_size_full_confidence", 90.0)
            ),
            min_size_multiplier=float(
                getattr(self.config, "position_size_min_multiplier", 0.50)
            ),
            high_volatility_size_scale=float(
                getattr(self.config, "position_size_high_volatility_scale", 0.75)
            ),
            extreme_volatility_threshold=float(
                getattr(self.config, "position_size_extreme_volatility_threshold", 0.07)
            ),
            extreme_volatility_size_scale=float(
                getattr(self.config, "position_size_extreme_volatility_scale", 0.50)
            ),
        )

        quality_ok, quality_reasons, quality_metrics = evaluate_signal_quality(
            confidence_pct=float(confidence),
            min_conf_threshold_pct=self.config.min_confidence_threshold * 100.0,
            volatility=float(decision.get("volatility", 0.0) or 0.0),
            stop_loss_fraction=decision.get("stop_loss_fraction"),
            take_profit_fraction=(
                decision.get("take_profit_percentage")
                or decision.get("portfolio_take_profit_percentage")
            ),
            controls=controls,
        )
        if not quality_ok:
            msg = f"Quality gate: {','.join(quality_reasons)}"
            logger.info(
                "Skipping trade due to quality gate (%s) for %s | metrics=%s",
                ",".join(quality_reasons),
                decision.get("asset_pair"),
                quality_metrics,
            )
            return False, "QUALITY_GATE_BLOCK", msg

        normalized_action = str(
            decision.get("policy_action") or decision.get("action") or ""
        ).upper()
        is_derisking_action = normalized_action.startswith(("CLOSE_", "REDUCE_"))

        judged_open_min_confidence = float(
            getattr(self.config, "judged_open_min_confidence_pct", 80.0)
        )
        market_regime = str(decision.get("market_regime") or "unknown").strip().lower()
        volatility = float(decision.get("volatility", 0.0) or 0.0)
        judged_open_regime_min_confidence = judged_open_min_confidence
        if market_regime == "ranging":
            judged_open_regime_min_confidence = max(
                judged_open_regime_min_confidence,
                float(getattr(self.config, "judged_open_min_confidence_pct_ranging", judged_open_min_confidence)),
            )
        elif market_regime == "unknown":
            judged_open_regime_min_confidence = max(
                judged_open_regime_min_confidence,
                float(getattr(self.config, "judged_open_min_confidence_pct_unknown", judged_open_min_confidence)),
            )

        judged_open_context_min_confidence = judged_open_regime_min_confidence
        if (
            normalized_action.endswith("_LONG")
            and market_regime == "trending_up"
            and 0.02 <= volatility < 0.04
        ):
            judged_open_context_min_confidence = max(
                judged_open_context_min_confidence,
                float(
                    getattr(
                        self.config,
                        "judged_open_long_min_confidence_pct_trending_up_moderate_volatility",
                        judged_open_regime_min_confidence,
                    )
                ),
            )

        if (
            decision.get("decision_origin") == "judge"
            and normalized_action.startswith("OPEN_")
            and float(confidence) < judged_open_min_confidence
        ):
            msg = (
                "Judged open confidence too low "
                f"({confidence}% < {judged_open_min_confidence:.0f}%)"
            )
            logger.info("Skipping trade due to %s", msg)
            return False, "JUDGED_OPEN_MIN_CONFIDENCE", msg

        if (
            decision.get("decision_origin") == "judge"
            and normalized_action.startswith("OPEN_")
            and float(confidence) < judged_open_regime_min_confidence
        ):
            msg = (
                "Judged open confidence too low for regime "
                f"{market_regime} ({confidence}% < {judged_open_regime_min_confidence:.0f}%)"
            )
            logger.info("Skipping trade due to %s", msg)
            return False, "JUDGED_OPEN_REGIME_MIN_CONFIDENCE", msg

        if (
            decision.get("decision_origin") == "judge"
            and normalized_action.startswith("OPEN_")
            and float(confidence) < judged_open_context_min_confidence
        ):
            msg = (
                "Judged open confidence too low for context "
                f"{market_regime}/vol={volatility:.3f} ({confidence}% < {judged_open_context_min_confidence:.0f}%)"
            )
            logger.info("Skipping trade due to %s", msg)
            return False, "JUDGED_OPEN_CONTEXT_MIN_CONFIDENCE", msg

        if (
            self.config.max_daily_trades > 0
            and self.daily_trade_count >= self.config.max_daily_trades
        ):
            if is_derisking_action:
                logger.info(
                    "Allowing de-risking action despite daily trade limit: action=%s asset=%s count=%s max=%s",
                    normalized_action,
                    decision.get("asset_pair"),
                    self.daily_trade_count,
                    self.config.max_daily_trades,
                )
                return True, "OK", "De-risking action bypassed daily trade limit"
            msg = f"Max daily trade limit reached ({self.daily_trade_count}/{self.config.max_daily_trades})"
            logger.warning("%s. Skipping %s", msg, decision.get("asset_pair"))
            return False, "DAILY_TRADE_LIMIT", msg

        autonomous_enabled = self.is_autonomous_enabled
        if autonomous_enabled:
            return True, "OK", "Autonomous execution enabled"

        notification_valid, errors = self._validate_notification_config()
        if not notification_valid:
            msg = f"Notification unavailable: {', '.join(errors)}"
            logger.error("%s", msg)
            return False, "NOTIFICATION_UNAVAILABLE", msg

        telegram_config = (
            self.config.telegram if hasattr(self.config, "telegram") else {}
        )
        telegram_enabled = telegram_config.get("enabled", False)

        if telegram_enabled:
            logger.info(
                "Decision will be sent to Telegram for approval (signal-only mode)"
            )
            return True, "OK", "Signal mode with Telegram enabled"

        if self.config.approval_policy == "never":
            return False, "APPROVAL_DISABLED", "Approval policy forbids execution"

        msg = "Decision requires approval but Telegram is not configured"
        logger.warning(
            "%s. Enable Telegram or autonomous mode.",
            msg,
        )
        return False, "APPROVAL_PATH_UNAVAILABLE", msg

    async def _should_execute(self, decision) -> bool:
        should_execute, _, _ = await self._should_execute_with_reason(decision)
        return should_execute

    async def process_cycle(self):
        """
        Process a single OODA cycle without the infinite loop.

        This method exposes the inner logic of the run() method for controlled
        execution in backtesting scenarios. It processes one complete cycle:
        RECOVERING -> LEARNING -> PERCEPTION -> REASONING -> RISK_CHECK -> EXECUTION -> (back to IDLE)

        The sleep between cycles is handled externally by the caller (e.g., run() method
        or backtester), allowing for flexible timing control.

        Returns:
            bool: True if cycle completed successfully, False if agent should stop
        """
        if not self.is_running:
            return False

        try:
            # Start from current state (RECOVERING on first cycle, PERCEPTION thereafter)
            # If state is IDLE (from previous cycle), transition to PERCEPTION to start new cycle
            if self.state == AgentState.IDLE:
                self._reset_cycle_budget()
                self._ensure_cycle_budget()
                await self._transition_to(AgentState.PERCEPTION)
            else:
                # Ensure budget exists for mid-cycle recoveries (e.g., after errors)
                self._ensure_cycle_budget()

            # Execute state machine until we return to IDLE or encounter error
            max_iterations = 10  # Prevent infinite loops in one cycle
            iterations = 0

            with tracer.start_as_current_span("agent.ooda.cycle") as cycle_span:
                cycle_phase_durations: dict[str, float] = {
                    "PERCEPTION": 0.0,
                    "REASONING": 0.0,
                    "RISK_CHECK": 0.0,
                    "EXECUTION": 0.0,
                    "LEARNING": 0.0,
                }

                while (
                    self.state != AgentState.IDLE
                    and iterations < max_iterations
                    and self.is_running
                ):
                    handler = self.state_handlers.get(self.state)
                    if handler:
                        phase_name = self.state.name
                        cycle_span.add_event(
                            "state_handler_start", {"state": phase_name}
                        )
                        phase_start = time.perf_counter()
                        try:
                            await handler()
                        except Exception as handler_err:
                            dump_path = self._handle_state_exception(
                                handler_err, self.state.name
                            )
                            if is_development():
                                # Hard crash in dev to surface issues
                                raise

                            remaining = self._consume_cycle_retry_budget()
                            if remaining > 0:
                                logger.warning(
                                    "State %s failed; retrying within cycle (remaining=%s)",
                                    self.state.name,
                                    remaining,
                                )
                                continue

                            logger.error(
                                "State handler failed; retry budget exhausted; aborting cycle",
                                exc_info=True,
                            )
                            if dump_path:
                                logger.error("Crash dump captured at %s", dump_path)
                            self._reset_cycle_budget()
                            return False
                        finally:
                            if phase_name in cycle_phase_durations:
                                phase_duration = time.perf_counter() - phase_start
                                cycle_phase_durations[phase_name] += phase_duration
                                self._loop_metrics.record_phase(
                                    phase_name, phase_duration
                                )

                        cycle_span.add_event(
                            "state_handler_end", {"state": self.state.name}
                        )
                    else:
                        logger.error(f"No handler found for state {self.state}")
                        return False
                    iterations += 1

                self._loop_metrics.finalize_cycle(cycle_phase_durations)
                logger.info(
                    "Cycle phase durations (s): PERCEPTION=%.4f REASONING=%.4f "
                    "RISK_CHECK=%.4f EXECUTION=%.4f LEARNING=%.4f TOTAL=%.4f",
                    cycle_phase_durations["PERCEPTION"],
                    cycle_phase_durations["REASONING"],
                    cycle_phase_durations["RISK_CHECK"],
                    cycle_phase_durations["EXECUTION"],
                    cycle_phase_durations["LEARNING"],
                    self._loop_metrics.last_cycle_total_duration,
                )

                cycle_span.set_attribute("iterations", iterations)
                if iterations >= max_iterations:
                    logger.warning(
                        "process_cycle exceeded max iterations, possible infinite loop"
                    )
                    self._reset_cycle_budget()
                    return False

            # Clear cycle budget when returning to IDLE
            if self.state == AgentState.IDLE:
                self._reset_cycle_budget()

                # Perform periodic health checks (every N decisions)
                self._decisions_since_health_check += 1
                if self._decisions_since_health_check >= self._health_check_frequency:
                    self._perform_health_check()
                    self._decisions_since_health_check = 0

            return True

        except asyncio.CancelledError:
            logger.info("Cycle cancelled.")
            return False
        except Exception as e:
            logger.error(f"Error in process_cycle: {e}", exc_info=True)
            self._reset_cycle_budget()
            return False

    def stop(self):
        """Stops the trading loop."""
        logger.info("Stopping autonomous trading agent...")
        self.is_running = False
        self.stop_requested = True

        # Mark state as IDLE for metrics when stop is requested
        self.state = AgentState.IDLE
        self._record_state_metric()

        # Pair scheduler stop logic removed as part of THR-172 cleanup

    def pause(self) -> bool:
        """
        Pause the trading agent.

        Temporarily halts the trading loop without closing positions. The agent can be
        resumed later with the resume() method.

        Returns:
            bool: True if pause was successful, False if agent was not running or already paused.
        """
        if not self.is_running:
            logger.warning("Cannot pause: agent is not running")
            return False

        if self._paused:
            logger.warning("Cannot pause: agent is already paused")
            return False

        logger.info("Pausing trading agent via public method")
        self.is_running = False
        self._paused = True
        return True

    def resume(self) -> bool:
        """
        Resume the trading agent.

        Resumes a paused agent to continue trading. Only works if the agent was previously
        paused (not stopped or crashed).

        Returns:
            bool: True if resume was successful, False if agent was not paused.
        """
        if not self._paused:
            logger.warning("Cannot resume: agent is not paused")
            return False

        logger.info("Resuming trading agent via public method")
        self.is_running = True
        self._paused = False
        return True
