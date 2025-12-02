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
        self.analysis_failures = {}
        self.daily_trade_count = 0
        self.last_trade_date = datetime.date.today()

    async def run(self):
        """
        The main trading loop, implemented as a state machine.
        """
        logger.info("Starting autonomous trading agent...")
        self.is_running = True
        self.state = AgentState.IDLE  # Start in IDLE state

        while self.is_running:
            try:
                if self.state == AgentState.IDLE:
                    await self.handle_idle_state()
                elif self.state == AgentState.PERCEPTION:
                    await self.handle_perception_state()
                elif self.state == AgentState.REASONING:
                    await self.handle_reasoning_state()
                elif self.state == AgentState.RISK_CHECK:
                    await self.handle_risk_check_state()
                elif self.state == AgentState.EXECUTION:
                    await self.handle_execution_state()
                elif self.state == AgentState.LEARNING:
                    await self.handle_learning_state()

            except asyncio.CancelledError:
                logger.info("Trading loop cancelled.")
                break
            except Exception as e:
                logger.error(f"An error occurred in the trading loop: {e}", exc_info=True)
                self.state = AgentState.IDLE  # Go to idle on error and wait before retrying
                await asyncio.sleep(300)  # Backoff on error

    async def _transition_to(self, new_state: AgentState):
        """Helper method to handle state transitions with logging."""
        old_state = self.state
        self.state = new_state
        logger.info(f"Transitioning {old_state.name} -> {new_state.name}")

    async def handle_idle_state(self):
        """
        IDLE: Waiting for the next analysis interval before transitioning to learning.
        """
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
        RETRY_DELAY_SECONDS = 60

        for asset_pair in self.config.asset_pairs:
            failure_key = f"analysis:{asset_pair}"
            
            if self.analysis_failures.get(failure_key, 0) >= MAX_RETRIES:
                logger.warning(f"Skipping analysis for {asset_pair} due to repeated failures.")
                continue

            for attempt in range(MAX_RETRIES):
                try:
                    logger.debug(f"Analyzing {asset_pair} (Attempt {attempt + 1}/{MAX_RETRIES})...")
                    decision = self.engine.analyze_asset(asset_pair)

                    # Reset failure count on success
                    self.analysis_failures[failure_key] = 0
                    
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
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
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
        confidence = decision.get('confidence', 0)
        if confidence < self.config.min_confidence_threshold:
            logger.info(f"Skipping trade due to low confidence ({confidence}% < {self.config.min_confidence_threshold}%)")
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