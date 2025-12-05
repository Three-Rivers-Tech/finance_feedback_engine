# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import datetime
import logging
from enum import Enum, auto
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)

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
        # Track analysis failures and their timestamps for time-based decay
        self.analysis_failures = {}  # {failure_key: count}
        self.analysis_failure_timestamps = {}  # {failure_key: last_failure_datetime}
        self.daily_trade_count = 0
        self.last_trade_date = datetime.date.today()

        # Startup recovery tracking
        self._startup_complete = asyncio.Event()
        self._recovered_positions = []  # List of recovered position metadata
        self._startup_retry_count = 0
        self._max_startup_retries = 3

        # State machine handler map
        self.state_handlers = {
            AgentState.IDLE: self.handle_idle_state,
            AgentState.PERCEPTION: self.handle_perception_state,
            AgentState.REASONING: self.handle_reasoning_state,
            AgentState.RISK_CHECK: self.handle_risk_check_state,
            AgentState.EXECUTION: self.handle_execution_state,
            AgentState.LEARNING: self.handle_learning_state,
        }

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
        from finance_feedback_engine.utils.validation import standardize_asset_pair
        from finance_feedback_engine.memory.portfolio_memory import TradeOutcome

        logger.info("Starting position recovery from trading platform...")

        # Exponential backoff retry loop
        base_delay = 2.0
        for attempt in range(self._max_startup_retries):
            try:
                # Query platform for current portfolio state
                portfolio = self.trading_platform.get_portfolio_breakdown()

                # Extract positions based on platform type
                positions = []

                # Check if this is UnifiedTradingPlatform (has platform_breakdowns)
                if 'platform_breakdowns' in portfolio:
                    for platform_name, platform_data in portfolio['platform_breakdowns'].items():

                        # Coinbase futures positions
                        if 'futures_positions' in platform_data:
                            for pos in platform_data['futures_positions']:
                                contracts = pos.get('contracts', 0)
                                if contracts and float(contracts) != 0:
                                    positions.append({
                                        'platform': f'{platform_name}_futures',
                                        'product_id': pos.get('product_id', 'UNKNOWN'),
                                        'side': pos.get('side', 'UNKNOWN'),
                                        'size': float(contracts),
                                        'entry_price': pos.get('entry_price', 0),
                                        'current_price': pos.get('current_price', 0),
                                        'unrealized_pnl': pos.get('unrealized_pnl', 0),
                                        'leverage': pos.get('leverage', 1)
                                    })

                        # Oanda forex positions
                        if 'positions' in platform_data:
                            for pos in platform_data['positions']:
                                units = pos.get('units', 0)
                                if units and float(units) != 0:
                                    positions.append({
                                        'platform': f'{platform_name}_forex',
                                        'product_id': pos.get('instrument', 'UNKNOWN'),
                                        'side': pos.get('position_type', 'UNKNOWN'),
                                        'size': abs(float(units)),
                                        'entry_price': 0,  # Oanda doesn't provide avg entry in summary
                                        'current_price': 0,
                                        'unrealized_pnl': pos.get('unrealized_pl', 0),
                                        'leverage': 1
                                    })

                # Direct platform access (non-unified)
                else:
                    # Coinbase Advanced: futures_positions
                    if 'futures_positions' in portfolio:
                        for pos in portfolio['futures_positions']:
                            contracts = pos.get('contracts', 0)
                            if contracts and float(contracts) != 0:
                                positions.append({
                                    'platform': 'coinbase',
                                    'product_id': pos.get('product_id', 'UNKNOWN'),
                                    'side': pos.get('side', 'UNKNOWN'),
                                    'size': float(contracts),
                                    'entry_price': pos.get('entry_price', 0),
                                    'current_price': pos.get('current_price', 0),
                                    'unrealized_pnl': pos.get('unrealized_pnl', 0),
                                    'leverage': pos.get('leverage', 1)
                                })

                    # Oanda: positions
                    if 'positions' in portfolio:
                        for pos in portfolio['positions']:
                            units = pos.get('units', 0)
                            if units and float(units) != 0:
                                positions.append({
                                    'platform': 'oanda',
                                    'product_id': pos.get('instrument', 'UNKNOWN'),
                                    'side': pos.get('position_type', 'UNKNOWN'),
                                    'size': abs(float(units)),
                                    'entry_price': 0,
                                    'current_price': 0,
                                    'unrealized_pnl': pos.get('unrealized_pl', 0),
                                    'leverage': 1
                                })

                logger.info(f"Found {len(positions)} open position(s) on platform")

                # Process each position
                for pos in positions:
                    try:
                        # Standardize asset pair
                        product_id = pos['product_id']
                        asset_pair = standardize_asset_pair(product_id)

                        # Generate synthetic decision ID
                        timestamp = datetime.datetime.utcnow().isoformat()
                        hash_input = f"{product_id}_{timestamp}_{pos['platform']}_{pos['size']}"
                        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]
                        decision_id = f"RECOVERED_{asset_pair}_{int(time.time())}_{hash_suffix}"

                        # Get entry price (fallback to current price if unavailable)
                        entry_price = pos['entry_price']
                        if entry_price == 0:
                            entry_price = pos['current_price']
                            if entry_price == 0:
                                logger.warning(
                                    f"No entry price available for {asset_pair}, "
                                    "will track unrealized P&L only"
                                )
                                entry_price = "UNKNOWN"

                        # Build synthetic decision record
                        synthetic_decision = {
                            'id': decision_id,
                            'asset_pair': asset_pair,
                            'action': 'HOLD',
                            'confidence': 50,
                            'timestamp': timestamp,
                            'entry_price': entry_price if entry_price != "UNKNOWN" else None,
                            'recommended_position_size': pos['size'],
                            'position_size': pos['size'],
                            'signal_only': True,
                            'ai_provider': 'recovery',
                            'reasoning': f"Position recovered from {pos['platform']} platform on startup",
                            'metadata': {
                                'recovery_source': 'platform_startup',
                                'platform': pos['platform'],
                                'original_product_id': product_id,
                                'side': pos['side'],
                                'original_unrealized_pnl': pos['unrealized_pnl'],
                                'leverage': pos['leverage'],
                                'entry_price_status': 'known' if entry_price != "UNKNOWN" else 'unknown'
                            }
                        }

                        # Save decision to store
                        if hasattr(self.engine, 'decision_store'):
                            self.engine.decision_store.save_decision(synthetic_decision)
                            logger.info(f"Saved synthetic decision {decision_id} for {asset_pair}")

                        # Create partial TradeOutcome for portfolio memory
                        outcome = TradeOutcome(
                            decision_id=decision_id,
                            asset_pair=asset_pair,
                            action='HOLD',
                            entry_timestamp=timestamp,
                            exit_timestamp=None,
                            entry_price=float(entry_price) if entry_price != "UNKNOWN" else 0.0,
                            exit_price=None,
                            position_size=pos['size'],
                            realized_pnl=None,
                            pnl_percentage=None,
                            holding_period_hours=None,
                            ai_provider='recovery',
                            ensemble_providers=None,
                            decision_confidence=50,
                            market_sentiment=None,
                            volatility=None,
                            price_trend=None,
                            was_profitable=None,
                            hit_stop_loss=False,
                            hit_take_profit=False
                        )

                        # Append to portfolio memory (rebuild from platform truth)
                        self.portfolio_memory.trade_outcomes.append(outcome)
                        logger.info(f"Added {asset_pair} to portfolio memory")

                        # Associate with trade monitor for tracking
                        self.trade_monitor.associate_decision_to_trade(decision_id, asset_pair)
                        logger.info(f"Associated {asset_pair} with trade monitor")

                        # Store position metadata for later reference
                        self._recovered_positions.append({
                            'decision_id': decision_id,
                            'asset_pair': asset_pair,
                            'side': pos['side'],
                            'size': pos['size'],
                            'unrealized_pnl': pos['unrealized_pnl'],
                            'platform': pos['platform']
                        })

                    except Exception as e:
                        logger.error(
                            f"Error processing position {pos.get('product_id', 'UNKNOWN')}: {e}",
                            exc_info=True
                        )
                        continue

                # Log recovery summary
                if self._recovered_positions:
                    total_pnl = sum(p['unrealized_pnl'] for p in self._recovered_positions)
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
                        exc_info=True
                    )
                    # Continue anyway with empty recovery
                    self._startup_complete.set()
                    return
                else:
                    # Exponential backoff
                    delay = base_delay * (2 ** attempt)
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
        """
        logger.info("Starting autonomous trading agent...")
        self.is_running = True
        logger.info("Starting autonomous trading agent...")
        self.is_running = True

        # Block until position recovery completes
        try:
            await asyncio.wait_for(
                self._recover_existing_positions(),
                timeout=60.0  # 60 second timeout
            )
        except asyncio.TimeoutError:
            logger.error(
                "Position recovery timed out after 60 seconds. "
                "Starting agent with empty position state."
            )
            self._startup_complete.set()

        self.state = AgentState.IDLE  # Start in IDLE state

        while self.is_running:
            try:
                handler = self.state_handlers.get(self.state)
                if handler:
                    await handler()
                else:
                    logger.error(f"No handler found for state {self.state}. Stopping agent.")
                    self.stop()
            except asyncio.CancelledError:
                logger.info("Trading loop cancelled.")
                break
            except Exception as e:
                logger.error(f"An error occurred in the trading loop: {e}", exc_info=True)
                self.state = AgentState.IDLE  # Go to idle on error and wait before retrying
                await asyncio.sleep(self.config.main_loop_error_backoff_seconds)

    async def _transition_to(self, new_state: AgentState):
        """Helper method to handle state transitions with logging."""
        old_state = self.state
        self.state = new_state
        logger.info(f"Transitioning {old_state.name} -> {new_state.name}")

    async def handle_idle_state(self):
        """
        IDLE: Waiting for the next analysis interval before transitioning to learning.
        """
        # Skip initial wait if positions were recovered on startup
        if self._recovered_positions and self.daily_trade_count == 0:
            logger.info(
                "State: IDLE - Positions recovered on startup, "
                "skipping initial wait and transitioning immediately to LEARNING"
            )
            await self._transition_to(AgentState.LEARNING)
            return

        logger.info("State: IDLE - Waiting for next analysis interval...")
        await asyncio.sleep(self.config.analysis_frequency_seconds)
        # Periodically check for closed trades to learn from
        await self._transition_to(AgentState.LEARNING)

    async def handle_perception_state(self):
        """
        PERCEPTION: Fetching market data, portfolio state, and performing safety checks.
        """
        logger.info("State: PERCEPTION - Fetching data and performing safety checks...")

        # --- Safety Check: Portfolio Kill Switch ---
        if self.config.kill_switch_loss_pct is not None and self.config.kill_switch_loss_pct > 0:
            try:
                # Assuming get_monitoring_context() without args gives portfolio overview
                portfolio_context = self.trade_monitor.monitoring_context_provider.get_monitoring_context()
                # Assuming the context contains 'unrealized_pnl_percent'
                portfolio_pnl_pct = portfolio_context.get('unrealized_pnl_percent', 0.0)

                if portfolio_pnl_pct < -self.config.kill_switch_loss_pct:
                    logger.critical(
                        f"PORTFOLIO KILL SWITCH TRIGGERED! "
                        f"Current P&L ({portfolio_pnl_pct:.2f}%) has breached the threshold "
                        f"(-{self.config.kill_switch_loss_pct:.2f}%). Stopping agent."
                    )
                    self.stop()
                    return  # Halt immediately
            except Exception as e:
                logger.error(f"Could not check portfolio kill switch due to an error: {e}", exc_info=True)

        # --- Daily Counter Reset ---
        today = datetime.date.today()
        if today > self.last_trade_date:
            logger.info(f"New day detected. Resetting daily trade count from {self.daily_trade_count} to 0.")
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

        # --- Optional: Reset old failures at start of reasoning cycle (time-based decay) ---
        current_time = datetime.datetime.now()
        for key in list(self.analysis_failures.keys()):
            last_fail = self.analysis_failure_timestamps.get(key)
            if last_fail and (current_time - last_fail).total_seconds() > self.config.reasoning_failure_decay_seconds:
                logger.info(f"Resetting analysis_failures for {key} due to time-based decay.")
                self.analysis_failures.pop(key, None)
                self.analysis_failure_timestamps.pop(key, None)

        for asset_pair in self.config.asset_pairs:
            failure_key = f"analysis:{asset_pair}"

            if self.analysis_failures.get(failure_key, 0) >= MAX_RETRIES:
                logger.warning(f"Skipping analysis for {asset_pair} due to repeated failures (will reset after decay or daily reset).")
                continue

            for attempt in range(MAX_RETRIES):
                try:
                    logger.debug(f"Analyzing {asset_pair} (Attempt {attempt + 1}/{MAX_RETRIES})...")
                    decision = self.engine.analyze_asset(asset_pair)

                    # Reset failure count and timestamp on success
                    self.analysis_failures[failure_key] = 0
                    self.analysis_failure_timestamps[failure_key] = current_time

                    if decision and decision.get('action') in ["BUY", "SELL"]:
                        if await self._should_execute(decision):
                            self._current_decision = decision
                            await self._transition_to(AgentState.RISK_CHECK)
                            return
                        else:
                            logger.info(f"Decision to {decision['action']} {asset_pair} not executed due to policy or low confidence.")
                    else:
                        logger.info(f"Decision for {asset_pair}: HOLD. No action taken.")

                    break  # Analysis successful, break retry loop

                except Exception as e:
                    logger.warning(f"Analysis attempt {attempt + 1} for {asset_pair} failed: {e}")
                    self.analysis_failure_timestamps[failure_key] = current_time
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(self.config.reasoning_retry_delay_seconds * (attempt + 1))
                    else:
                        self.analysis_failures[failure_key] = self.analysis_failures.get(failure_key, 0) + 1
                        logger.error(
                            f"Persistent failure analyzing {asset_pair} after {MAX_RETRIES} attempts. "
                            f"It will be skipped for a while.",
                            exc_info=True
                        )

        logger.info("Analysis complete. No actionable trades found. Going back to IDLE.")
        await self._transition_to(AgentState.IDLE)
    async def handle_risk_check_state(self):
        """
        RISK_CHECK: Running the RiskGatekeeper.
        """
        logger.info("State: RISK_CHECK - Running RiskGatekeeper...")

        if not self._current_decision:
            logger.warning("RISK_CHECK state reached without a decision. Returning to IDLE.")
            await self._transition_to(AgentState.IDLE)
            return

        decision_id = self._current_decision.get('id')
        asset_pair = self._current_decision.get('asset_pair')

        # Retrieve monitoring context for risk validation
        try:
            # Use the monitoring context provider to get context
            monitoring_context = self.trade_monitor.monitoring_context_provider.get_monitoring_context(asset_pair=asset_pair)
        except Exception as e:
            logger.warning(f"Failed to get monitoring context for risk validation: {e}")
            monitoring_context = {}

        # Validate trade with RiskGatekeeper
        approved, reason = self.risk_gatekeeper.validate_trade(self._current_decision, monitoring_context)
        if not approved:
            logger.info(f"Trade rejected by RiskGatekeeper: {reason}. Skipping execution.")
            # Reset decision and return to perception for next cycle
            self._current_decision = None
            await self._transition_to(AgentState.PERCEPTION)
            return

        logger.info(f"Trade approved by RiskGatekeeper for {asset_pair}. Proceeding to EXECUTION.")
        await self._transition_to(AgentState.EXECUTION)

    async def handle_execution_state(self):
        """
        EXECUTION: Sending orders to BaseTradingPlatform.
        """
        logger.info("State: EXECUTION - Sending orders to BaseTradingPlatform...")

        if not self._current_decision:
            logger.warning("EXECUTION state reached without a decision. Returning to PERCEPTION.")
            await self._transition_to(AgentState.PERCEPTION)
            return

        decision_id = self._current_decision.get('id')
        action = self._current_decision.get('action')
        asset_pair = self._current_decision.get('asset_pair')

        try:
            execution_result = self.engine.execute_decision(decision_id)
            if execution_result.get('success'):
                logger.info(f"Trade executed successfully for {action} {asset_pair}. Associating decision with monitor.")
                self.daily_trade_count += 1
                # Link this decision to the next trade detected for this asset
                self.trade_monitor.associate_decision_to_trade(decision_id, asset_pair)
                await self._transition_to(AgentState.LEARNING)
            else:
                logger.error(f"Trade execution failed: {execution_result.get('message')}. Returning to PERCEPTION.")
                await self._transition_to(AgentState.PERCEPTION)
        except Exception as e:
            logger.error(f"Exception during trade execution for decision {decision_id}: {e}")
            await self._transition_to(AgentState.PERCEPTION) # Go back to perception on failure

        # Clear decision after execution attempt
        self._current_decision = None

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
                    logger.info(f"Recorded outcome for trade {trade_outcome.get('id')}")
                except Exception as e:
                    logger.error(f"Error recording trade outcome: {e}", exc_info=True)

        # After processing, transition to perception to gather fresh market data
        await self._transition_to(AgentState.PERCEPTION)

    async def _should_execute(self, decision) -> bool:
        """Determine if a trade should be executed based on confidence and policy."""
        confidence = decision.get('confidence', 0)  # 0-100 scale from decision validation
        # Normalize confidence to 0-1 for comparison with config threshold (which is auto-normalized)
        confidence_normalized = confidence / 100.0
        if confidence_normalized < self.config.min_confidence_threshold:
            logger.info(f"Skipping trade due to low confidence ({confidence}% < {self.config.min_confidence_threshold*100:.0f}%)")
            return False

        # Check daily trade limit
        if self.config.max_daily_trades > 0 and self.daily_trade_count >= self.config.max_daily_trades:
            logger.warning(
                f"Max daily trade limit ({self.config.max_daily_trades}) reached. "
                f"Skipping trade for {decision.get('asset_pair')}."
            )
            return False

        if self.config.autonomous_execution:
            return True

        if self.config.approval_policy == "never":
            return False

        logger.warning("Manual approval is required but not implemented in async loop. Skipping trade.")
        return False

    def stop(self):
        """Stops the trading loop."""
        logger.info("Stopping autonomous trading agent...")
        self.is_running = False
