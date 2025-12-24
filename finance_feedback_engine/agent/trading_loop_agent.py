# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import datetime
import logging
import queue
import time
from enum import Enum, auto

from opentelemetry import trace, metrics

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform
from finance_feedback_engine.observability.context import with_span

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)


class AgentState(Enum):
    """Represents the current state of the trading agent."""

    IDLE = auto()
    PERCEPTION = auto()
    REASONING = auto()
    RISK_CHECK = auto()
    EXECUTION = auto()
    LEARNING = auto()


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
        self.state = AgentState.IDLE
        self._current_decision = None
        self._current_decisions = []  # New: to store multiple decisions
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

        self._dashboard_event_queue = queue.Queue(maxsize=100)
        self._cycle_count = 0
        self._start_time = None  # Will be set in run()

        # Property for dashboard to track if stop was requested
        self.stop_requested = False

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
            AgentState.PERCEPTION: self.handle_perception_state,
            AgentState.REASONING: self.handle_reasoning_state,
            AgentState.RISK_CHECK: self.handle_risk_check_state,
            AgentState.EXECUTION: self.handle_execution_state,
            AgentState.LEARNING: self.handle_learning_state,
        }

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

        # Check if signal-only mode is enabled
        autonomous_enabled = getattr(self.config, "autonomous", None)
        if autonomous_enabled and hasattr(autonomous_enabled, "enabled"):
            autonomous_enabled = autonomous_enabled.enabled
        else:
            autonomous_enabled = getattr(self.config, "autonomous_execution", False)

        if autonomous_enabled:
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

    async def _recover_existing_positions(self):
        """
        Recover existing open positions from the trading platform on startup.

        This method:
        1. Queries platform.get_portfolio_breakdown() with exponential backoff retry
        2. Extracts open positions (futures_positions or positions lists)
        3. Creates synthetic decision IDs and records
        4. Rebuilds portfolio memory from platform truth
        5. Associates positions with trade monitor

        Sets _startup_complete event when finished.
        """
        import hashlib
        import time

        from finance_feedback_engine.memory.portfolio_memory import TradeOutcome
        from finance_feedback_engine.utils.validation import standardize_asset_pair

        logger.info("Starting position recovery from trading platform...")

        # Exponential backoff retry loop
        base_delay = 2.0
        for attempt in range(self._max_startup_retries):
            try:
                # Query platform for current portfolio state (use cached method from engine)
                portfolio = self.engine.get_portfolio_breakdown()

                logger.info(f"Portfolio breakdown keys: {list(portfolio.keys())}")

                # Extract positions based on platform type
                positions = []

                # Check if this is UnifiedTradingPlatform (has platform_breakdowns)
                if "platform_breakdowns" in portfolio:
                    logger.info(f"Using unified platform breakdown with {len(portfolio['platform_breakdowns'])} platforms")
                    for platform_name, platform_data in portfolio[
                        "platform_breakdowns"
                    ].items():
                        logger.info(f"Processing platform: {platform_name}, keys: {list(platform_data.keys())}")
                        # Coinbase futures positions
                        if "futures_positions" in platform_data:
                            fps = platform_data['futures_positions']
                            logger.info(f"{platform_name} has {len(fps)} futures_positions: {fps}")
                            logger.debug(f"Processing {len(fps)} futures positions from {platform_name}")
                            for idx, pos in enumerate(platform_data["futures_positions"]):
                                # Handle both dict and PositionInfo objects
                                contracts = pos.get("contracts", 0) if isinstance(pos, dict) else getattr(pos, "contracts", 0)
                                units = pos.get("units", 0) if isinstance(pos, dict) else getattr(pos, "units", 0)

                                # Use units if contracts is zero (units can be negative for SHORT)
                                if contracts and float(contracts) != 0:
                                    size = abs(float(contracts))
                                else:
                                    size = abs(float(units))

                                logger.debug(f"{platform_name} position {idx}: contracts={contracts}, units={units}, size={size}")

                                # Position is active if it has non-zero size OR has unrealized P&L
                                unrealized_pnl = pos.get("unrealized_pnl", 0) if isinstance(pos, dict) else getattr(pos, "unrealized_pnl", 0)
                                has_pnl = unrealized_pnl and float(unrealized_pnl) != 0

                                # If size is reported as 0 but has P&L, infer size from P&L and price
                                if size == 0 and has_pnl:
                                    entry_price_val = pos.get("entry_price", 0) if isinstance(pos, dict) else getattr(pos, "entry_price", 0)
                                    current_price_val = pos.get("current_price", 0) if isinstance(pos, dict) else getattr(pos, "current_price", 0)
                                    if entry_price_val and current_price_val:
                                        # Estimate size from P&L: size = PnL / (current - entry)
                                        price_diff = float(current_price_val) - float(entry_price_val)
                                        if abs(price_diff) > 0.01:
                                            size = abs(float(unrealized_pnl) / price_diff)
                                            logger.info(f"Inferred size {size} from P&L for {platform_name} position")

                                if size != 0 or has_pnl:
                                    product_id = pos.get("product_id", "UNKNOWN") if isinstance(pos, dict) else getattr(pos, "product_id", "UNKNOWN")
                                    side = pos.get("side", "UNKNOWN") if isinstance(pos, dict) else getattr(pos, "side", "UNKNOWN")
                                    entry_price = pos.get("entry_price", 0) if isinstance(pos, dict) else getattr(pos, "entry_price", 0)
                                    current_price = pos.get("current_price", 0) if isinstance(pos, dict) else getattr(pos, "current_price", 0)
                                    leverage = pos.get("leverage", 1) if isinstance(pos, dict) else getattr(pos, "leverage", 1)

                                    logger.info(f"Recovered {platform_name} futures position: {product_id} {side} size={size}")

                                    positions.append(
                                        {
                                            "platform": f"{platform_name}_futures",
                                            "product_id": product_id,
                                            "side": side,
                                            "size": size,
                                            "entry_price": entry_price,
                                            "current_price": current_price,
                                            "unrealized_pnl": unrealized_pnl,
                                            "leverage": leverage,
                                        }
                                    )
                                else:
                                    logger.debug(f"Skipping {platform_name} position {idx} with zero size")

                        # Oanda forex positions
                        if "positions" in platform_data:
                            for pos in platform_data["positions"]:
                                units = pos.get("units", 0)
                                if units and float(units) != 0:
                                    # Extract entry_price from Oanda position data
                                    entry_price = pos.get("entry_price", 0)
                                    if not entry_price:
                                        # Fallback to current_price if available
                                        entry_price = pos.get("current_price", 0)

                                    positions.append(
                                        {
                                            "platform": f"{platform_name}_forex",
                                            "product_id": pos.get(
                                                "instrument", "UNKNOWN"
                                            ),
                                            "side": pos.get("position_type", "UNKNOWN"),
                                            "size": abs(float(units)),
                                            "entry_price": entry_price,
                                            "current_price": pos.get(
                                                "current_price", 0
                                            ),
                                            "unrealized_pnl": pos.get(
                                                "unrealized_pl", 0
                                            ),
                                            "leverage": 1,
                                        }
                                    )

                logger.info(f"Found {len(positions)} open position(s) on platform")

                # Process each position
                for pos in positions:
                    try:
                        # Standardize asset pair
                        product_id = pos["product_id"]
                        asset_pair = standardize_asset_pair(product_id)

                        # Generate synthetic decision ID
                        timestamp = datetime.datetime.utcnow().isoformat()
                        hash_input = (
                            f"{product_id}_{timestamp}_{pos['platform']}_{pos['size']}"
                        )
                        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[
                            :8
                        ]
                        decision_id = (
                            f"RECOVERED_{asset_pair}_{int(time.time())}_{hash_suffix}"
                        )

                        # Get entry price (fallback to current price if unavailable)
                        entry_price = pos["entry_price"]
                        if entry_price == 0:
                            entry_price = pos["current_price"]
                            if entry_price == 0:
                                logger.warning(
                                    f"No entry price available for {asset_pair}, "
                                    "will track unrealized P&L only"
                                )
                                entry_price = "UNKNOWN"

                        # Build synthetic decision record (with new fields)
                        synthetic_decision = {
                            "id": decision_id,
                            "asset_pair": asset_pair,
                            "action": "HOLD",
                            "confidence": 50,
                            "timestamp": timestamp,
                            "entry_price": (
                                entry_price if entry_price != "UNKNOWN" else None
                            ),
                            "recommended_position_size": pos["size"],
                            "position_size": pos["size"],
                            "signal_only": True,
                            "ai_provider": "recovery",
                            "reasoning": f"Position recovered from {pos['platform']} platform on startup",
                            "metadata": {
                                "recovery_source": "platform_startup",
                                "platform": pos["platform"],
                                "original_product_id": product_id,
                                "side": pos["side"],
                                "original_unrealized_pnl": pos["unrealized_pnl"],
                                "leverage": pos["leverage"],
                                "entry_price_status": (
                                    "known" if entry_price != "UNKNOWN" else "unknown"
                                ),
                                "current_price": pos.get("current_price"),  # New
                                "avg_entry_price": pos.get("avg_entry_price"),  # New
                                "averagePrice": pos.get("averagePrice"),  # New (Oanda)
                            },
                        }

                        # Save decision to store
                        if hasattr(self.engine, "decision_store"):
                            self.engine.decision_store.save_decision(synthetic_decision)
                            logger.info(
                                f"Saved synthetic decision {decision_id} for {asset_pair}"
                            )

                        # Create partial TradeOutcome for portfolio memory
                        outcome = TradeOutcome(
                            decision_id=decision_id,
                            asset_pair=asset_pair,
                            action="HOLD",
                            entry_timestamp=timestamp,
                            exit_timestamp=None,
                            entry_price=(
                                float(entry_price) if entry_price != "UNKNOWN" else 0.0
                            ),
                            exit_price=None,
                            position_size=pos["size"],
                            realized_pnl=None,
                            pnl_percentage=None,
                            holding_period_hours=None,
                            ai_provider="recovery",
                            ensemble_providers=None,
                            decision_confidence=50,
                            market_sentiment=None,
                            volatility=None,
                            price_trend=None,
                            was_profitable=None,
                            hit_stop_loss=False,
                            hit_take_profit=False,
                        )

                        # Append to portfolio memory (rebuild from platform truth)
                        self.portfolio_memory.trade_outcomes.append(outcome)
                        logger.info(f"Added {asset_pair} to portfolio memory")

                        # Associate with trade monitor for tracking
                        self.trade_monitor.associate_decision_to_trade(
                            decision_id, asset_pair
                        )
                        logger.info(f"Associated {asset_pair} with trade monitor")

                        # Store position metadata for later reference
                        self._recovered_positions.append(
                            {
                                "decision_id": decision_id,
                                "asset_pair": asset_pair,
                                "side": pos["side"],
                                "size": pos["size"],
                                "unrealized_pnl": pos["unrealized_pnl"],
                                "platform": pos["platform"],
                            }
                        )

                    except Exception as e:
                        logger.error(
                            f"Error processing position {pos.get('product_id', 'UNKNOWN')}: {e}",
                            exc_info=True,
                        )
                        continue

                # Log recovery summary
                if self._recovered_positions:
                    total_pnl = sum(
                        p["unrealized_pnl"] for p in self._recovered_positions
                    )
                    logger.info(
                        f"✓ Position recovery complete: {len(self._recovered_positions)} position(s), "
                        f"Total unrealized P&L: ${total_pnl:.2f}"
                    )
                else:
                    logger.info("✓ Position recovery complete: No open positions found")

                # Mark startup as complete
                self._startup_complete.set()
                return

            except Exception as e:
                self._startup_retry_count += 1
                if self._startup_retry_count >= self._max_startup_retries:
                    logger.error(
                        f"Failed to recover positions after {self._max_startup_retries} attempts: {e}",
                        exc_info=True,
                    )
                    # Continue anyway with empty recovery
                    self._startup_complete.set()
                    return
                else:
                    # Exponential backoff
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        f"Position recovery attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

        # If we exit the loop without success, mark complete anyway
        self._startup_complete.set()

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

            # Block until position recovery completes
            try:
                await asyncio.wait_for(
                    self._recover_existing_positions(), timeout=60.0  # 60 second timeout
                )
            except asyncio.TimeoutError:
                logger.error(
                    "Position recovery timed out after 60 seconds. "
                    "Starting agent with empty position state."
                )
                self._startup_complete.set()

            # Main loop: process cycles with sleep intervals
            while self.is_running:
                try:
                    # Execute one complete OODA cycle
                    cycle_successful = await self.process_cycle()

                    if not cycle_successful:
                        logger.warning("Cycle execution failed, backing off before retry")
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

        # Emit event for dashboard
        self._emit_dashboard_event(
            {
                "type": "state_transition",
                "from": old_state.name,
                "to": new_state.name,
                "timestamp": time.time(),
            }
        )

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
                # Queue is full - log and drop event
                logger.warning("Dashboard event queue is full, dropping event")
            except Exception as e:
                # Other exception during queue operation - log it
                logger.warning(f"Failed to emit dashboard event: {e}")

    async def handle_idle_state(self):
        """
        IDLE: Marks the end of an OODA cycle.

        The sleep between cycles is now handled externally (in run() or by the backtester),
        so this state simply logs and returns, allowing the cycle to complete.
        The next cycle will start from LEARNING state after the external sleep.
        """
        with tracer.start_as_current_span("agent.ooda.idle"):
            logger.info("State: IDLE - Cycle complete, waiting for next interval...")
            # Note: Sleep is handled externally in run() or by backtester
            # This state just marks the end of the cycle
            await self._transition_to(AgentState.LEARNING)

    async def handle_perception_state(self):
        """
        PERCEPTION: Fetching market data, portfolio state, and performing safety checks.
        """
        logger.info("State: PERCEPTION - Fetching data and performing safety checks...")

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
        logger.info("State: REASONING - Running DecisionEngine...")

        MAX_RETRIES = 3

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

        for asset_pair in self.config.asset_pairs:
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
                logger.debug(f"Analyzing {asset_pair} (with timeout)...")

                # Wrap the analysis with a timeout to prevent blocking
                decision = await asyncio.wait_for(
                    self.engine.analyze_asset_async(asset_pair),
                    timeout=60,  # Timeout after 60 seconds
                )

                # Reset failure count and timestamp on success
                self.analysis_failures[failure_key] = 0
                self.analysis_failure_timestamps[failure_key] = current_time

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
            except Exception as e:
                logger.warning(
                    f"Failed to get monitoring context for risk validation: {e}"
                )
                monitoring_context = {}

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
        self, decision: dict[str, any]
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

        # Check if autonomous execution is enabled (prioritize autonomous.enabled over legacy autonomous_execution)
        if hasattr(self.config, "autonomous") and hasattr(
            self.config.autonomous, "enabled"
        ):
            autonomous_enabled = self.config.autonomous.enabled
        else:
            autonomous_enabled = getattr(self.config, "autonomous_execution", False)

        logger.info(f"Autonomous execution mode: {autonomous_enabled}")

        if autonomous_enabled:
            # Full autonomous mode: execute trades directly
            logger.info("Autonomous execution enabled - executing trades directly")
            for decision in self._current_decisions:
                decision_id = decision.get("id")
                action = decision.get("action")
                asset_pair = decision.get("asset_pair")

                try:
                    execution_result = self.engine.execute_decision(decision_id)
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
            self._send_signals_to_telegram()

        # Clear all decisions after processing
        self._current_decisions.clear()

        # After processing, transition to LEARNING
        await self._transition_to(AgentState.LEARNING)

    def _send_signals_to_telegram(self):
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

            # Try webhook delivery if Telegram failed (future implementation)
            if not signal_delivered:
                try:
                    webhook_config = (
                        self.config.webhook if hasattr(self.config, "webhook") else {}
                    )
                    webhook_enabled = webhook_config.get("enabled", False)
                    webhook_url = webhook_config.get("url")

                    if webhook_enabled and webhook_url:
                        # TODO: Implement webhook delivery
                        logger.info(
                            f"Webhook delivery not yet implemented for {decision_id}"
                        )
                        failure_reasons.append(
                            f"{decision_id}: Webhook delivery not implemented"
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
        logger.info("State: LEARNING - Processing closed trades for feedback...")

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

    def _update_performance_metrics(self, trade_outcome: dict[str, any]) -> None:
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

        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}", exc_info=True)

    def get_performance_summary(self) -> dict[str, any]:
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

        # Check autonomous execution setting
        if hasattr(self.config, "autonomous") and hasattr(
            self.config.autonomous, "enabled"
        ):
            autonomous_enabled = self.config.autonomous.enabled
        else:
            autonomous_enabled = getattr(self.config, "autonomous_execution", False)

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
        LEARNING -> PERCEPTION -> REASONING -> RISK_CHECK -> EXECUTION -> (back to IDLE)

        The sleep between cycles is handled externally by the caller (e.g., run() method
        or backtester), allowing for flexible timing control.

        Returns:
            bool: True if cycle completed successfully, False if agent should stop
        """
        if not self.is_running:
            return False

        try:
            # Start from LEARNING state (check for completed trades)
            # This matches the flow: sleep -> LEARNING -> PERCEPTION -> ... -> IDLE
            self.state = AgentState.LEARNING

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
                        cycle_span.add_event("state_handler_start", {"state": self.state.name})
                        await handler()
                        cycle_span.add_event("state_handler_end", {"state": self.state.name})
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
