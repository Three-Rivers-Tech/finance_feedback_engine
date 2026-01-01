# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import datetime
import logging
import queue
import time
from enum import Enum, auto
from typing import Any, Dict

from opentelemetry import metrics, trace

from finance_feedback_engine.monitoring.prometheus import (
    update_agent_state,
    update_decision_confidence,
)

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)


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


class TradingLoopAgent:
    """
    An autonomous agent that runs a continuous trading loop based on a state machine.
    """

    def __init__(
        self,
        config: TradingAgentConfig,
        engine,  # FinanceFeedbackEngine
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

        self.risk_gatekeeper = RiskGatekeeper(
            max_drawdown_pct=_normalize_pct(self.config.max_drawdown_percent),
            correlation_threshold=self.config.correlation_threshold,
            max_correlated_assets=self.config.max_correlated_assets,
            max_var_pct=_normalize_pct(self.config.max_var_pct),
            var_confidence=self.config.var_confidence,
        )
        self.is_running = False
        self._paused = False
        self.state = AgentState.IDLE
        self._current_decisions = []  # Store multiple decisions for batch processing
        
        # Lock for protecting asset_pairs list from concurrent modification
        self._asset_pairs_lock = asyncio.Lock()
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

        # For preventing infinite loops on rejected trades
        self._rejected_decisions_cache = (
            {}
        )  # {decision_id: (rejection_timestamp, asset_pair)}
        self._rejection_cooldown_seconds = 300  # 5 minutes cooldown

        # Dashboard event queue for real-time updates
        import queue

        self._dashboard_event_queue = queue.Queue(
            maxsize=100
        )  # Dashboard event queue with reasonable limit
        self._cycle_count = 0
        self._start_time = None  # Will be set in run()

        # Property for dashboard to track if stop was requested
        self.stop_requested = False

        # Batch review tracking (every 20 trades)
        self._batch_review_counter = 0
        self._kelly_activated = False
        self._last_batch_review_time = None

        # Validate notification delivery path on startup
        notification_valid, notification_errors = self._validate_notification_config()
        if not notification_valid:
            error_msg = (
                "Cannot start agent in signal-only mode without valid notification delivery.\n"
                f"Configuration errors: {', '.join(notification_errors)}\n"
                "Please either:\n"
                "1. Configure Telegram notifications (telegram.enabled=true, bot_token, chat_id)\n"
                "2. Enable autonomous mode (autonomous.enabled=true)\n"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("✓ Notification delivery validated: Telegram configured")

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

        # Pair selection system (optional)
        self.pair_selector = None
        self.pair_scheduler = None

        # Initialize pair selection if configured
        if hasattr(config, "pair_selection") and config.pair_selection.get(
            "enabled", False
        ):
            try:
                from finance_feedback_engine.pair_selection import (
                    PairSelectionConfig,
                    PairSelector,
                )
                from finance_feedback_engine.pair_selection.core.discovery_filters import (
                    DiscoveryFilterConfig,
                    WhitelistConfig,
                )
                from finance_feedback_engine.pair_selection.core.selection_scheduler import (
                    PairSelectionScheduler,
                )

                # Build PairSelectionConfig from dict config
                ps_config = config.pair_selection

                # Load discovery filter configuration from YAML
                discovery_filters_cfg = ps_config.get("universe", {}).get(
                    "discovery_filters", {}
                )
                discovery_filter_config = DiscoveryFilterConfig(
                    enabled=discovery_filters_cfg.get("enabled", True),
                    volume_threshold_usd=discovery_filters_cfg.get(
                        "volume_threshold_usd", 50_000_000
                    ),
                    min_listing_age_days=discovery_filters_cfg.get(
                        "min_listing_age_days", 365
                    ),
                    max_spread_pct=discovery_filters_cfg.get("max_spread_pct", 0.001),
                    min_depth_usd=discovery_filters_cfg.get(
                        "min_depth_usd", 10_000_000
                    ),
                    exclude_suspicious_patterns=discovery_filters_cfg.get(
                        "exclude_suspicious_patterns", True
                    ),
                    min_venue_count=discovery_filters_cfg.get("min_venue_count", 2),
                    auto_add_to_whitelist=discovery_filters_cfg.get(
                        "auto_add_to_whitelist", False
                    ),
                )

                # Load whitelist configuration from YAML
                whitelist_cfg = ps_config.get("universe", {})
                whitelist_config = WhitelistConfig(
                    enabled=whitelist_cfg.get("whitelist_enabled", True),
                    whitelist_entries=whitelist_cfg.get(
                        "whitelist_entries",
                        ["BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY"],
                    ),
                )

                pair_selection_config = PairSelectionConfig(
                    target_pair_count=ps_config.get("target_pair_count", 5),
                    candidate_oversampling=ps_config.get("llm", {}).get(
                        "candidate_oversampling", 3
                    ),
                    sortino_weight=ps_config.get("statistical", {})
                    .get("aggregation_weights", {})
                    .get("sortino", 0.4),
                    diversification_weight=ps_config.get("statistical", {})
                    .get("aggregation_weights", {})
                    .get("diversification", 0.35),
                    volatility_weight=ps_config.get("statistical", {})
                    .get("aggregation_weights", {})
                    .get("volatility", 0.25),
                    sortino_windows_days=ps_config.get("statistical", {})
                    .get("sortino", {})
                    .get("windows_days", [7, 30, 90]),
                    sortino_window_weights=ps_config.get("statistical", {})
                    .get("sortino", {})
                    .get("weights", [0.5, 0.3, 0.2]),
                    correlation_lookback_days=ps_config.get("statistical", {})
                    .get("correlation", {})
                    .get("lookback_days", 30),
                    garch_p=ps_config.get("statistical", {})
                    .get("garch", {})
                    .get("p", 1),
                    garch_q=ps_config.get("statistical", {})
                    .get("garch", {})
                    .get("q", 1),
                    garch_forecast_horizon_days=ps_config.get("statistical", {})
                    .get("garch", {})
                    .get("forecast_horizon_days", 7),
                    garch_fitting_window_days=ps_config.get("statistical", {})
                    .get("garch", {})
                    .get("fitting_window_days", 90),
                    thompson_enabled=ps_config.get("thompson_sampling", {}).get(
                        "enabled", True
                    ),
                    thompson_success_threshold=ps_config.get(
                        "thompson_sampling", {}
                    ).get("success_threshold", 0.55),
                    thompson_failure_threshold=ps_config.get(
                        "thompson_sampling", {}
                    ).get("failure_threshold", 0.45),
                    thompson_min_trades=ps_config.get("thompson_sampling", {}).get(
                        "min_trades_for_update", 3
                    ),
                    universe_cache_ttl_hours=ps_config.get("universe", {}).get(
                        "cache_ttl_hours", 24
                    ),
                    pair_blacklist=ps_config.get("universe", {}).get("blacklist", []),
                    auto_discover=ps_config.get("universe", {}).get(
                        "auto_discover", False
                    ),
                    discovery_filter_config=discovery_filter_config,
                    whitelist_config=whitelist_config,
                    llm_enabled=ps_config.get("llm", {}).get("enabled", True),
                    llm_enabled_providers=None,  # Will use all enabled
                )

                # Initialize pair selector
                self.pair_selector = PairSelector(
                    data_provider=engine.data_provider,
                    config=pair_selection_config,
                    ai_decision_manager=getattr(engine, "ai_decision_manager", None),
                )

                # Initialize scheduler
                def on_selection_callback(result):
                    """Update agent's asset_pairs when selection completes."""
                    # Always preserve core pairs (BTCUSD, ETHUSD, EURUSD)
                    core_pairs = getattr(self.config, 'core_pairs', ["BTCUSD", "ETHUSD", "EURUSD"])
                    
                    # Merge selected pairs with core pairs (union, preserving order)
                    # Core pairs come first, then any additional selected pairs
                    final_pairs = list(core_pairs)  # Start with core pairs
                    for pair in result.selected_pairs:
                        if pair not in final_pairs:
                            final_pairs.append(pair)
                    
                    # Thread-safe update using asyncio.create_task with lock
                    async def update_pairs():
                        async with self._asset_pairs_lock:
                            self.config.asset_pairs = final_pairs
                            logger.info(
                                f"✓ Updated active pairs: {final_pairs} "
                                f"(core: {core_pairs}, additional: {[p for p in final_pairs if p not in core_pairs]})"
                            )
                    
                    # Schedule the update in the event loop
                    try:
                        asyncio.create_task(update_pairs())
                    except RuntimeError:
                        # If no event loop, update synchronously (shouldn't happen in async context)
                        self.config.asset_pairs = final_pairs
                        logger.info(
                            f"✓ Updated active pairs: {final_pairs} "
                            f"(core: {core_pairs}, additional: {[p for p in final_pairs if p not in core_pairs]})"
                        )

                self.pair_scheduler = PairSelectionScheduler(
                    pair_selector=self.pair_selector,
                    trade_monitor=trade_monitor,
                    portfolio_memory=portfolio_memory,
                    interval_hours=ps_config.get("rotation_interval_hours", 1.0),
                    on_selection_callback=on_selection_callback,
                )

                logger.info("✓ Pair selection system initialized")

            except ImportError as e:
                logger.warning(f"Pair selection disabled: Import error - {e}")
                self.pair_selector = None
                self.pair_scheduler = None
            except Exception as e:
                logger.error(f"Failed to initialize pair selection: {e}", exc_info=True)
                self.pair_selector = None
                self.pair_scheduler = None

    @property
    def start_time(self):
        """Public accessor for start time (returns datetime object)."""
        if self._start_time is None:
            return None
        return datetime.datetime.fromtimestamp(self._start_time)

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

    def _validate_notification_config(self) -> tuple[bool, list[str]]:
        """
        Validate notification delivery configuration on startup.

        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Check if autonomous mode is enabled (no notifications needed)
        if self.is_autonomous_enabled:
            return True, []  # Autonomous mode doesn't need notifications

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

            # Start pair selection scheduler if configured
            if self.pair_scheduler:
                try:
                    await self.pair_scheduler.start()
                    logger.info("✓ Pair selection scheduler started")
                except Exception as e:
                    logger.error(f"Failed to start pair scheduler: {e}", exc_info=True)

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

    async def _transition_to(self, new_state: AgentState):
        """Helper method to handle state transitions with logging."""
        old_state = self.state
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

        current_time = datetime.datetime.now()
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
            try:
                self._dashboard_event_queue.put_nowait(event)
            except queue.Full:
                # Queue is full - log with size info and drop event
                queue_size = self._dashboard_event_queue.qsize()
                logger.warning(
                    f"Dashboard event queue is full ({queue_size} events), dropping event. Consider increasing maxsize or processing events faster."
                )
            except Exception as e:
                # Other exception during queue operation - log it
                logger.warning(f"Failed to emit dashboard event: {e}")

    async def handle_idle_state(self):
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

    async def handle_recovering_state(self):
        """
        RECOVERING: Recover existing positions from platform on startup.

        This method performs comprehensive position recovery with:
        1. Single API call to platform with one retry on failure
        2. Position limiting (keep top 2 by unrealized P&L, close excess)
        3. Position normalization (generate decision IDs, apply risk rules)
        4. Decision persistence (create synthetic decision records)
        5. All-or-nothing validation (fail entire recovery if any position fails)

        Emits recovery_complete or recovery_failed events with detailed metadata.
        Transitions to LEARNING state on success or assumes clean slate on failure.
        """
        import hashlib
        import uuid as uuid_module

        from finance_feedback_engine.memory.portfolio_memory import TradeOutcome
        from finance_feedback_engine.utils.validation import standardize_asset_pair

        logger.info("State: RECOVERING - Checking for existing positions...")

        max_retries = 1  # Single retry on transient failures
        max_positions = 2  # Maximum concurrent positions allowed

        for attempt in range(max_retries + 1):
            try:
                # Query platform for current portfolio state
                portfolio = await self.engine.get_portfolio_breakdown_async()
                logger.info(f"Portfolio breakdown retrieved: {list(portfolio.keys())}")

                # Extract positions from platform response
                raw_positions = []

                # Handle UnifiedTradingPlatform (platform_breakdowns)
                if "platform_breakdowns" in portfolio:
                    for platform_name, platform_data in portfolio["platform_breakdowns"].items():
                        # Coinbase futures
                        if "futures_positions" in platform_data:
                            for pos in platform_data["futures_positions"]:
                                raw_positions.append({
                                    "platform": platform_name,
                                    "product_id": pos.get("product_id") or pos.get("instrument"),
                                    "side": pos.get("side", "LONG"),
                                    "size": abs(float(pos.get("contracts", 0) or pos.get("units", 0))),
                                    "entry_price": float(pos.get("entry_price", 0)),
                                    "current_price": float(pos.get("current_price", 0)),
                                    "unrealized_pnl": float(pos.get("unrealized_pnl", 0)),
                                    "opened_at": pos.get("opened_at"),
                                })
                        # Oanda positions
                        if "positions" in platform_data:
                            for pos in platform_data["positions"]:
                                raw_positions.append({
                                    "platform": platform_name,
                                    "product_id": pos.get("instrument"),
                                    "side": "LONG" if float(pos.get("units", 0)) > 0 else "SHORT",
                                    "size": abs(float(pos.get("units", 0))),
                                    "entry_price": float(pos.get("entry_price", 0)),
                                    "current_price": float(pos.get("current_price", 0)),
                                    "unrealized_pnl": float(pos.get("pnl", 0)),
                                    "opened_at": pos.get("opened_at"),
                                })
                # Handle direct platform responses (futures_positions or positions keys)
                elif "futures_positions" in portfolio:
                    for pos in portfolio["futures_positions"]:
                        raw_positions.append({
                            "platform": "coinbase",
                            "product_id": pos.get("product_id") or pos.get("instrument"),
                            "side": pos.get("side", "LONG"),
                            "size": abs(float(pos.get("contracts", 0) or pos.get("units", 0))),
                            "entry_price": float(pos.get("entry_price", 0)),
                            "current_price": float(pos.get("current_price", 0)),
                            "unrealized_pnl": float(pos.get("unrealized_pnl", 0)),
                            "opened_at": pos.get("opened_at"),
                        })
                elif "positions" in portfolio:
                    for pos in portfolio["positions"]:
                        raw_positions.append({
                            "platform": "oanda",
                            "product_id": pos.get("instrument"),
                            "side": "LONG" if float(pos.get("units", 0)) > 0 else "SHORT",
                            "size": abs(float(pos.get("units", 0))),
                            "entry_price": float(pos.get("entry_price", 0)),
                            "current_price": float(pos.get("current_price", 0)),
                            "unrealized_pnl": float(pos.get("pnl", 0)),
                            "opened_at": pos.get("opened_at"),
                        })

                # Filter out positions with zero size
                active_positions = [p for p in raw_positions if p["size"] > 0]

                if not active_positions:
                    logger.info("✓ No open positions found - starting with clean slate")
                    self._emit_dashboard_event({
                        "type": "recovery_complete",
                        "found": 0,
                        "kept": 0,
                        "closed_excess": [],
                        "timestamp": time.time(),
                    })
                    self._startup_complete.set()
                    await self._transition_to(AgentState.LEARNING)
                    return

                # Sort by unrealized P&L (descending) and keep top 2
                sorted_positions = sorted(active_positions, key=lambda x: x["unrealized_pnl"], reverse=True)
                positions_to_keep = sorted_positions[:max_positions]
                positions_to_close = sorted_positions[max_positions:]

                logger.info(f"Found {len(active_positions)} positions: keeping {len(positions_to_keep)}, closing {len(positions_to_close)}")

                # Close excess positions synchronously (all-or-nothing)
                closed_positions = []
                if positions_to_close:
                    for pos in positions_to_close:
                        try:
                            asset_pair = standardize_asset_pair(pos["product_id"])
                            logger.info(f"Closing excess position: {asset_pair} (P&L: ${pos['unrealized_pnl']:.2f})")

                            # Close via platform
                            close_result = await self.trading_platform.aclose_position(pos["product_id"])

                            closed_positions.append({
                                "asset_pair": asset_pair,
                                "unrealized_pnl": pos["unrealized_pnl"],
                                "reason": "exceeded_max_positions",
                            })
                            logger.info(f"✓ Closed {asset_pair}")

                        except Exception as e:
                            # All-or-nothing: if any close fails, abort entire recovery
                            error_msg = f"Failed to close excess position {pos['product_id']}: {e}"
                            logger.error(error_msg)
                            self._emit_dashboard_event({
                                "type": "recovery_failed",
                                "reason": "position_close_failed",
                                "failed_positions": [{
                                    "asset_pair": standardize_asset_pair(pos["product_id"]),
                                    "error": str(e),
                                }],
                                "timestamp": time.time(),
                            })
                            self._startup_complete.set()
                            await self._transition_to(AgentState.LEARNING)
                            return

                # Normalize and validate kept positions
                normalized_positions = []
                validation_errors = []

                for pos in positions_to_keep:
                    try:
                        asset_pair = standardize_asset_pair(pos["product_id"])

                        # Generate standard UUID for decision
                        decision_id = str(uuid_module.uuid4())

                        # Calculate stop-loss/take-profit using risk rules (2% stop, 5% target)
                        entry_price = pos["entry_price"]
                        stop_loss_price = entry_price * (1 - 0.02) if pos["side"] == "LONG" else entry_price * (1 + 0.02)
                        take_profit_price = entry_price * (1 + 0.05) if pos["side"] == "LONG" else entry_price * (1 - 0.05)

                        # Create decision record (same as newly-created positions)
                        decision = {
                            "id": decision_id,
                            "asset_pair": asset_pair,
                            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                            "action": "BUY" if pos["side"] == "LONG" else "SELL",
                            "confidence": 75,  # Default confidence for recovered positions
                            "recommended_position_size": pos["size"],
                            "entry_price": entry_price,
                            "stop_loss_pct": 0.02,
                            "take_profit_pct": 0.05,
                            "reasoning": f"Recovered existing {pos['side']} position from {pos['platform']} platform",
                            "market_regime": "unknown",
                            "ai_provider": "recovery",
                            "ensemble_metadata": {
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
                            }
                        }

                        # Persist decision to decision store
                        self.engine.decision_store.save_decision(decision)
                        logger.info(f"✓ Persisted decision {decision_id} for {asset_pair}")

                        # Add to portfolio memory
                        outcome = TradeOutcome(
                            decision_id=decision_id,
                            asset_pair=asset_pair,
                            action="BUY" if pos["side"] == "LONG" else "SELL",
                            entry_timestamp=datetime.datetime.utcnow().isoformat() + "Z",
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
                        self.trade_monitor.associate_decision_to_trade(decision_id, asset_pair)

                        normalized_positions.append({
                            "decision_id": decision_id,
                            "asset_pair": asset_pair,
                            "side": pos["side"],
                            "size": pos["size"],
                            "entry_price": entry_price,
                            "unrealized_pnl": pos["unrealized_pnl"],
                            "platform": pos["platform"],
                        })

                    except Exception as e:
                        validation_errors.append({
                            "asset_pair": standardize_asset_pair(pos.get("product_id", "UNKNOWN")),
                            "error": str(e),
                        })
                        logger.error(f"Failed to normalize position {pos.get('product_id')}: {e}", exc_info=True)

                # All-or-nothing: if any position validation failed, abort recovery
                if validation_errors:
                    logger.error(f"Position validation failed for {len(validation_errors)} positions")
                    self._emit_dashboard_event({
                        "type": "recovery_failed",
                        "reason": "position_validation_failed",
                        "failed_positions": validation_errors,
                        "timestamp": time.time(),
                    })
                    self._startup_complete.set()
                    await self._transition_to(AgentState.LEARNING)
                    return

                # Recovery successful!
                self._recovered_positions = normalized_positions
                total_pnl = sum(p["unrealized_pnl"] for p in normalized_positions)

                logger.info(f"✓ Recovery complete: {len(normalized_positions)} positions (Total P&L: ${total_pnl:.2f})")

                self._emit_dashboard_event({
                    "type": "recovery_complete",
                    "found": len(active_positions),
                    "kept": len(normalized_positions),
                    "closed_excess_positions": closed_positions,
                    "positions": normalized_positions,
                    "total_unrealized_pnl": total_pnl,
                    "timestamp": time.time(),
                })

                self._startup_complete.set()
                await self._transition_to(AgentState.LEARNING)
                return

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Recovery attempt {attempt + 1} failed: {e}. Retrying...")
                    await asyncio.sleep(2.0)  # Brief delay before retry
                    continue
                else:
                    # Final failure - assume clean slate
                    logger.info(f"Recovery failed after {max_retries + 1} attempts: {e}. Starting with clean slate.")
                    self._emit_dashboard_event({
                        "type": "recovery_failed",
                        "reason": "platform_api_error",
                        "error": str(e),
                        "timestamp": time.time(),
                    })
                    self._startup_complete.set()
                    await self._transition_to(AgentState.LEARNING)
                    return

    async def handle_perception_state(self):
        """
        PERCEPTION: Fetching market data, portfolio state, and performing safety checks.
        """
        logger.info("=" * 80)
        logger.info("State: PERCEPTION - Fetching data and performing safety checks...")
        logger.info("=" * 80)

        # --- Cleanup rejected decisions cache (prevent memory leak) ---
        self._cleanup_rejected_cache()

        # --- Safety Check: Portfolio Kill Switch ---
        if (
            self.config.kill_switch_loss_pct is not None
            and self.config.kill_switch_loss_pct > 0
        ):
            try:
                # Assuming get_monitoring_context() without args gives portfolio overview
                portfolio_context = (
                    self.trade_monitor.monitoring_context_provider.get_monitoring_context()
                )
                # Assuming the context contains 'unrealized_pnl_percent'
                portfolio_pnl_pct = portfolio_context.get("unrealized_pnl_percent", 0.0)

                if portfolio_pnl_pct < -self.config.kill_switch_loss_pct:
                    logger.critical(
                        f"PORTFOLIO KILL SWITCH TRIGGERED! "
                        f"Current P&L ({portfolio_pnl_pct:.2f}%) has breached the threshold "
                        f"(-{self.config.kill_switch_loss_pct:.2f}%). Stopping agent."
                    )
                    self.stop()
                    return  # Halt immediately
            except Exception as e:
                logger.error(
                    f"Could not check portfolio kill switch due to an error: {e}",
                    exc_info=True,
                )

        # --- Additional Performance-based Kill Switches ---

        # Check for excessive consecutive losses
        current_streak = self._performance_metrics["current_streak"]
        if current_streak < -5:  # 6 or more consecutive losses
            logger.critical(
                f"PERFORMANCE KILL SWITCH TRIGGERED! "
                f"{abs(current_streak)} consecutive losses. Stopping agent."
            )
            self.stop()
            return

        # Check for deteriorating win rate over time
        if self._performance_metrics["total_trades"] >= 20:
            win_rate = self._performance_metrics["win_rate"]
            if win_rate < 25:  # Less than 25% win rate with sufficient history
                logger.critical(
                    f"PERFORMANCE KILL SWITCH TRIGGERED! "
                    f"Win rate ({win_rate:.1f}%) is critically low. Stopping agent."
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
                    f"PERFORMANCE KILL SWITCH TRIGGERED! "
                    f"Total loss of ${abs(total_pnl):.2f} exceeds 15% of reference balance. Stopping agent."
                )
                self.stop()
                return

        # --- Daily Counter Reset ---
        today = datetime.date.today()
        if today > self.last_trade_date:
            logger.info(
                f"New day detected. Resetting daily trade count from {self.daily_trade_count} to 0."
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

    async def handle_reasoning_state(self):
        """
        REASONING: Running the DecisionEngine with retry logic for robustness.
        """
        logger.info("=" * 80)
        logger.info("State: REASONING - Running DecisionEngine...")
        logger.info("=" * 80)

        # Guard against empty or missing core pairs (with lock protection)
        async with self._asset_pairs_lock:
            core_pairs = getattr(self.config, 'core_pairs', ["BTCUSD", "ETHUSD", "EURUSD"])
            if not self.config.asset_pairs:
                logger.error(
                    "CRITICAL: No asset pairs configured! Restoring core pairs."
                )
                self.config.asset_pairs = core_pairs
            
            # Validate core pairs are present
            missing_core_pairs = [p for p in core_pairs if p not in self.config.asset_pairs]
            if missing_core_pairs:
                logger.warning(
                    f"Core pairs missing from asset_pairs: {missing_core_pairs}. Restoring them."
                )
                self.config.asset_pairs.extend(missing_core_pairs)

            # Create a snapshot copy for iteration (prevents race conditions)
            asset_pairs_snapshot = list(self.config.asset_pairs)
        
        logger.info(f"Analyzing {len(asset_pairs_snapshot)} pairs: {asset_pairs_snapshot}")

        MAX_RETRIES = 5  # Increased from 3 to handle intermittent API failures

        # --- Cleanup expired entries from rejection cache ---
        self._cleanup_rejected_cache()

        # --- Optional: Reset old failures at start of reasoning cycle (time-based decay) ---
        current_time = datetime.datetime.now()
        for key in list(self.analysis_failures.keys()):
            last_fail = self.analysis_failure_timestamps.get(key)
            if (
                last_fail
                and (current_time - last_fail).total_seconds()
                > self.config.reasoning_failure_decay_seconds
            ):
                logger.info(
                    f"Resetting analysis_failures for {key} due to time-based decay."
                )
                self.analysis_failures.pop(key, None)
                self.analysis_failure_timestamps.pop(key, None)

        for asset_pair in asset_pairs_snapshot:  # Iterate over snapshot, not live list
            logger.info(f">>> Starting analysis for {asset_pair}")
            failure_key = f"analysis:{asset_pair}"

            # --- Check if asset was recently rejected ---
            asset_rejected = False
            for timestamp, cached_asset_pair in self._rejected_decisions_cache.values():
                if asset_pair == cached_asset_pair:
                    logger.info(
                        f"Skipping analysis for {asset_pair}: recently rejected. Cooldown active."
                    )
                    asset_rejected = True
                    break
            if asset_rejected:
                continue

            if self.analysis_failures.get(failure_key, 0) >= MAX_RETRIES:
                logger.warning(
                    f"Skipping analysis for {asset_pair} due to repeated failures (will reset after decay or daily reset)."
                )
                continue

            # Use asyncio.wait_for to prevent long-running operations from blocking the loop
            try:
                logger.info(f"    → Calling DecisionEngine for {asset_pair} (90s timeout)...")

                analyze_fn = getattr(self.engine, "analyze_asset", None)
                analyze_async_fn = getattr(self.engine, "analyze_asset_async", None)

                if callable(analyze_async_fn):
                    analysis_result = await analyze_async_fn(asset_pair)
                elif callable(analyze_fn):
                    analysis_result = analyze_fn(asset_pair)
                else:
                    raise AttributeError(
                        "Engine must implement analyze_asset() or analyze_asset_async()"
                    )

                # Wrap with a timeout to prevent blocking
                import inspect

                if inspect.isawaitable(analysis_result):
                    analysis_awaitable = analysis_result
                else:
                    analysis_awaitable = asyncio.sleep(0, result=analysis_result)

                decision = await asyncio.wait_for(
                    analysis_awaitable,
                    timeout=90,  # Timeout after 90 seconds
                )

                # Reset failure count on success - remove from dict to prevent unbounded growth
                if failure_key in self.analysis_failures:
                    del self.analysis_failures[failure_key]
                if failure_key in self.analysis_failure_timestamps:
                    del self.analysis_failure_timestamps[failure_key]

                if decision and decision.get("action") in ["BUY", "SELL"]:
                    if await self._should_execute(decision):
                        self._current_decisions.append(decision)  # Collect decision
                        logger.info(
                            f"Actionable decision collected for {asset_pair}: {decision['action']}"
                        )
                    else:
                        logger.info(
                            f"Decision to {decision['action']} {asset_pair} not executed due to policy or low confidence."
                        )
                else:
                    logger.info(f"Decision for {asset_pair}: HOLD. No action taken.")

            except asyncio.TimeoutError:
                logger.warning(
                    f"Analysis for {asset_pair} timed out, skipping this cycle."
                )
                self.analysis_failure_timestamps[failure_key] = current_time
                self.analysis_failures[failure_key] = (
                    self.analysis_failures.get(failure_key, 0) + 1
                )
            except Exception as e:
                logger.warning(f"Analysis for {asset_pair} failed: {e}")
                self.analysis_failure_timestamps[failure_key] = current_time
                self.analysis_failures[failure_key] = (
                    self.analysis_failures.get(failure_key, 0) + 1
                )
                logger.error(
                    f"Persistent failure analyzing {asset_pair}. "
                    f"It will be skipped for a while.",
                    exc_info=True,
                )

            # Add delay between pairs to avoid Alpha Vantage rate limits
            # Only delay if there are more pairs to analyze
            if asset_pair != asset_pairs_snapshot[-1]:
                logger.info(f"    → Waiting 15s before analyzing next pair (rate limit protection)...")
                await asyncio.sleep(15)

        # After analyzing all assets, transition based on collected decisions
        if self._current_decisions:
            logger.info(
                f"Collected {len(self._current_decisions)} actionable decisions. Proceeding to RISK_CHECK."
            )
            await self._transition_to(AgentState.RISK_CHECK)
        else:
            logger.info("No actionable trades found for any asset. Going back to IDLE.")
            await self._transition_to(AgentState.IDLE)

    async def handle_risk_check_state(self):
        """
        RISK_CHECK: Running the RiskGatekeeper for all collected decisions.
        Approved decisions are moved to execution.
        """
        logger.info("State: RISK_CHECK - Running RiskGatekeeper...")

        if not self._current_decisions:
            logger.info("No decisions to risk check. Returning to IDLE.")
            await self._transition_to(AgentState.IDLE)
            return

        approved_decisions = []
        for decision in self._current_decisions:
            decision_id = decision.get("id")
            asset_pair = decision.get("asset_pair")

            # Retrieve monitoring context for risk validation
            try:
                monitoring_context = self.trade_monitor.monitoring_context_provider.get_monitoring_context(
                    asset_pair=asset_pair
                )

                # Enrich context with safety thresholds from config
                # These are used by RiskGatekeeper._validate_leverage_and_concentration()
                safety_config = self.config.get("safety", {})
                monitoring_context["max_leverage"] = safety_config.get(
                    "max_leverage", 5.0
                )
                monitoring_context["max_concentration"] = safety_config.get(
                    "max_position_pct", 25.0
                )

            except Exception as e:
                logger.warning(
                    f"Failed to get monitoring context for risk validation: {e}"
                )
                monitoring_context = {"max_leverage": 5.0, "max_concentration": 25.0}

            # First run the standard RiskGatekeeper validation
            approved, reason = self.risk_gatekeeper.validate_trade(
                decision, monitoring_context
            )

            # If standard validation passes, run additional performance-based risk checks
            if approved:
                (
                    performance_approved,
                    performance_reason,
                ) = self._check_performance_based_risks(decision)
                if not performance_approved:
                    approved = False
                    reason = performance_reason

            if approved:
                logger.info(
                    f"Trade for {asset_pair} approved by RiskGatekeeper. Adding to execution queue."
                )
                approved_decisions.append(decision)

                # Record decision confidence for metrics dashboards
                try:
                    update_decision_confidence(
                        asset_pair,
                        decision.get("action", "UNKNOWN"),
                        float(decision.get("confidence", 0)),
                    )
                except Exception:
                    logger.debug("Failed to record decision confidence metric", exc_info=True)

                # Emit approval event for dashboard
                self._emit_dashboard_event(
                    {
                        "type": "decision_approved",
                        "asset": asset_pair,
                        "action": decision.get("action", "UNKNOWN"),
                        "confidence": decision.get("confidence", 0),
                        "reasoning": decision.get("reasoning", "")[
                            :200
                        ],  # First 200 chars
                        "timestamp": time.time(),
                    }
                )
            else:
                logger.info(
                    f"Trade for {asset_pair} rejected by RiskGatekeeper: {reason}."
                )
                self._rejected_decisions_cache[decision_id] = (
                    datetime.datetime.now(),
                    asset_pair,
                )  # Add to cache

                # Emit rejection event for dashboard
                self._emit_dashboard_event(
                    {
                        "type": "decision_rejected",
                        "asset": asset_pair,
                        "action": decision.get("action", "UNKNOWN"),
                        "reason": reason,
                        "timestamp": time.time(),
                    }
                )

        self._current_decisions = approved_decisions  # Keep only approved decisions

        if self._current_decisions:
            logger.info(
                f"Proceeding to EXECUTION with {len(self._current_decisions)} approved decisions."
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

        if not self._current_decisions:
            logger.warning(
                "EXECUTION state reached without decisions. Returning to IDLE."
            )
            await self._transition_to(AgentState.IDLE)
            return

        # Use property for cleaner autonomous mode check
        autonomous_enabled = self.is_autonomous_enabled
        logger.info(f"Autonomous execution mode: {autonomous_enabled}")

        if autonomous_enabled:
            # Full autonomous mode: execute trades directly
            logger.info("Autonomous execution enabled - executing trades directly")
            for decision in self._current_decisions:
                decision_id = decision.get("id")
                action = decision.get("action")
                asset_pair = decision.get("asset_pair")

                try:
                    execution_result = await self.engine.execute_decision_async(
                        decision_id
                    )
                    if execution_result.get("success"):
                        logger.info(
                            f"Trade executed successfully for {action} {asset_pair}. Associating decision with monitor."
                        )
                        self.daily_trade_count += 1
                        self.trade_monitor.associate_decision_to_trade(
                            decision_id, asset_pair
                        )
                    else:
                        logger.error(
                            f"Trade execution failed for {asset_pair}: {execution_result.get('message')}."
                        )
                except Exception as e:
                    logger.error(
                        f"Exception during trade execution for decision {decision_id}: {e}"
                    )
        else:
            # Signal-only mode: send to Telegram for approval
            logger.info(
                "Autonomous execution disabled - sending signals to Telegram for approval"
            )
            await self._send_signals_to_telegram()

        # Clear all decisions after processing
        self._current_decisions.clear()

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
            action = decision.get("action")
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
                try:
                    self.engine.record_trade_outcome(trade_outcome)
                    # Update performance metrics based on trade outcome
                    self._update_performance_metrics(trade_outcome)
                    logger.info(f"Recorded outcome for trade {trade_outcome.get('id')}")
                except Exception as e:
                    logger.error(f"Error recording trade outcome: {e}", exc_info=True)

        # After processing, transition to perception to gather fresh market data
        await self._transition_to(AgentState.PERCEPTION)

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
            if self._performance_metrics["total_trades"] >= 50:
                kelly_check = self.portfolio_memory.check_kelly_activation_criteria(
                    window=50
                )

                previous_status = self._kelly_activated
                should_activate = kelly_check.get("should_activate_kelly", False)
                self._kelly_activated = should_activate

                logger.info(
                    f"\nKelly Criterion Status: {'ACTIVATED' if should_activate else 'NOT ACTIVATED'}"
                )
                logger.info(
                    f"  - Profit Factor: {kelly_check.get('avg_pf', 0):.3f} (threshold: 1.20)"
                )
                logger.info(
                    f"  - PF Stability (std): {kelly_check.get('pf_std', 0):.3f} (threshold: 0.15)"
                )
                logger.info(f"  - Window: {kelly_check.get('actual_window', 0)} trades")

                if should_activate and not previous_status:
                    logger.info(
                        "\n🎯 Kelly Criterion NEWLY ACTIVATED! Position sizing will use Quarter Kelly (0.25) with adaptive scaling to Half Kelly (0.5)."
                    )
                elif not should_activate and previous_status:
                    logger.warning(
                        "\n⚠️  Kelly Criterion DEACTIVATED due to instability. Reverting to 2% fixed risk."
                    )

                # Recommendation based on stability
                if kelly_check.get("avg_pf", 0) >= 1.20:
                    if kelly_check.get("pf_std", 1.0) < 0.10:
                        logger.info(
                            "Recommendation: Excellent stability. Consider scaling to Half Kelly (0.50)."
                        )
                    elif kelly_check.get("pf_std", 1.0) < 0.15:
                        logger.info(
                            "Recommendation: Good stability. Maintain Quarter Kelly (0.25)."
                        )
                    else:
                        logger.info(
                            "Recommendation: Borderline stability. Keep Quarter Kelly and monitor."
                        )
            else:
                remaining_trades = 50 - self._performance_metrics["total_trades"]
                logger.info(
                    f"\nKelly Criterion Status: BOOTSTRAP PERIOD ({remaining_trades} trades until eligibility)"
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
            self._last_batch_review_time = datetime.datetime.now()
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
        from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

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

    async def _should_execute(self, decision) -> bool:
        """
        Determine if a decision should be collected for processing.

        Returns True if the decision should proceed to execution state, where it will
        be either executed (autonomous mode) or sent to Telegram (signal-only mode).
        """
        confidence = decision.get(
            "confidence", 0
        )  # 0-100 scale from decision validation
        # Normalize confidence to 0-1 for comparison with config threshold (which is auto-normalized)
        confidence_normalized = confidence / 100.0
        if confidence_normalized < self.config.min_confidence_threshold:
            logger.info(
                f"Skipping trade due to low confidence ({confidence}% < {self.config.min_confidence_threshold*100:.0f}%)"
            )
            return False

        # Check daily trade limit
        if (
            self.config.max_daily_trades > 0
            and self.daily_trade_count >= self.config.max_daily_trades
        ):
            logger.warning(
                f"Max daily trade limit ({self.config.max_daily_trades}) reached. "
                f"Skipping trade for {decision.get('asset_pair')}."
            )
            return False

        # Use property for cleaner autonomous mode check
        autonomous_enabled = self.is_autonomous_enabled

        # If autonomous execution is enabled, always proceed
        if autonomous_enabled:
            return True

        # Re-validate notification config before proceeding to execution
        notification_valid, errors = self._validate_notification_config()
        if not notification_valid:
            logger.error(
                f"Notification delivery unavailable: {', '.join(errors)}. "
                f"Cannot proceed with signal-only decision for {decision.get('asset_pair')}"
            )
            return False

        # If autonomous is disabled, check if we have Telegram configured for signal-only mode
        telegram_config = (
            self.config.telegram if hasattr(self.config, "telegram") else {}
        )
        telegram_enabled = telegram_config.get("enabled", False)

        if telegram_enabled:
            # Telegram is enabled - allow decision to proceed to execution state
            # where it will be sent as a signal for approval
            logger.info(
                "Decision will be sent to Telegram for approval (signal-only mode)"
            )
            return True

        # No execution path available (neither autonomous nor Telegram)
        if self.config.approval_policy == "never":
            return False

        logger.warning(
            "Decision requires approval but Telegram is not configured. "
            "Enable Telegram in config or set autonomous.enabled=true to proceed."
        )
        return False

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
            # Start from current state (RECOVERING on first cycle, LEARNING thereafter)
            # If state is IDLE (from previous cycle), transition to LEARNING to start new cycle
            if self.state == AgentState.IDLE:
                await self._transition_to(AgentState.LEARNING)

            # Execute state machine until we return to IDLE or encounter error
            max_iterations = 10  # Prevent infinite loops in one cycle
            iterations = 0

            with tracer.start_as_current_span("agent.ooda.cycle") as cycle_span:
                while (
                    self.state != AgentState.IDLE
                    and iterations < max_iterations
                    and self.is_running
                ):
                    handler = self.state_handlers.get(self.state)
                    if handler:
                        cycle_span.add_event(
                            "state_handler_start", {"state": self.state.name}
                        )
                        await handler()
                        cycle_span.add_event(
                            "state_handler_end", {"state": self.state.name}
                        )
                    else:
                        logger.error(f"No handler found for state {self.state}")
                        return False
                    iterations += 1

                cycle_span.set_attribute("iterations", iterations)
                if iterations >= max_iterations:
                    logger.warning(
                        "process_cycle exceeded max iterations, possible infinite loop"
                    )
                    return False

            return True

        except asyncio.CancelledError:
            logger.info("Cycle cancelled.")
            return False
        except Exception as e:
            logger.error(f"Error in process_cycle: {e}", exc_info=True)
            return False

    def stop(self):
        """Stops the trading loop."""
        logger.info("Stopping autonomous trading agent...")
        self.is_running = False
        self.stop_requested = True

        # Mark state as IDLE for metrics when stop is requested
        self.state = AgentState.IDLE
        self._record_state_metric()

        # Stop pair selection scheduler if running
        if self.pair_scheduler and self.pair_scheduler.is_running:
            try:
                # Check if there's a running event loop
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule the coroutine in the running loop and wait for completion
                    if loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(
                            self.pair_scheduler.stop(), loop
                        )
                        # Wait up to 5 seconds for graceful shutdown
                        try:
                            future.result(timeout=5.0)
                            logger.info("✓ Pair selection scheduler stopped successfully")
                        except TimeoutError:
                            logger.warning(
                                "Pair scheduler stop timed out after 5s; may still be running"
                            )
                    else:
                        logger.warning(
                            "Event loop exists but is not running; cannot stop pair scheduler gracefully"
                        )
                except RuntimeError:
                    # No running event loop - log warning
                    logger.warning(
                        "No running event loop available to stop pair scheduler; "
                        "scheduler may not stop gracefully"
                    )
            except Exception as e:
                logger.error(f"Error stopping pair scheduler: {e}", exc_info=True)

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
