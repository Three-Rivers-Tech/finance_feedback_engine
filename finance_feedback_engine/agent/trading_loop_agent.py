# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
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
    EXECUTING = auto()  # For backward compatibility with existing functionality
    ANALYZING = auto()  # For backward compatibility with existing functionality
    MONITORING = auto()  # For backward compatibility with existing functionality

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
        # Initialize RiskGatekeeper for trade validation
        self.risk_gatekeeper = RiskGatekeeper()
        self.is_running = False
        self.state = AgentState.IDLE
        self._current_decision = None

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
                # Backward compatibility states
                elif self.state == AgentState.ANALYZING:
                    await self.handle_analyzing_state()
                elif self.state == AgentState.EXECUTING:
                    await self.handle_executing_state()
                elif self.state == AgentState.MONITORING:
                    await self.handle_monitoring_state()

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
        IDLE: Waiting for the next analysis interval.
        """
        logger.info("State: IDLE - Waiting for next analysis interval...")
        await asyncio.sleep(self.config.analysis_frequency_seconds)
        await self._transition_to(AgentState.PERCEPTION)

    async def handle_perception_state(self):
        """
        PERCEPTION: Fetching market data and portfolio state.
        """
        logger.info("State: PERCEPTION - Fetching market data and portfolio state...")
        # Check for open positions first. If trades are open, we should be monitoring.
        if self.trade_monitor.is_trade_open():
            logger.info("Open trades detected. Switching to MONITORING state.")
            await self._transition_to(AgentState.MONITORING)
            return

        # Process each asset pair to gather market data
        for asset_pair in self.config.asset_pairs:
            try:
                logger.debug(f"Analyzing {asset_pair}...")
                # In perception state, we gather data but don't make decisions yet
                # We'll transition to reasoning to make decisions based on the data
                break  # Just move to reasoning state after checking if there are open trades
            except Exception as e:
                logger.error(f"Error analyzing {asset_pair}: {e}")
                continue

        # Transition to reasoning after gathering market data
        await self._transition_to(AgentState.REASONING)

    async def handle_reasoning_state(self):
        """
        REASONING: Running the DecisionEngine (Ensemble voting).
        """
        logger.info("State: REASONING - Running DecisionEngine...")

        for asset_pair in self.config.asset_pairs:
            try:
                logger.debug(f"Generating decision for {asset_pair}...")
                decision = self.engine.analyze_asset(asset_pair)
                
                # If a valid trade decision is found, move to risk check
                if decision and decision.get('action') in ["BUY", "SELL"]:
                    if await self._should_execute(decision):
                        self._current_decision = decision
                        await self._transition_to(AgentState.RISK_CHECK)
                        return # Exit reasoning to handle the risk check
                    else:
                        logger.info(f"Decision to {decision['action']} {asset_pair} not executed due to policy or low confidence.")
                else:
                    logger.info(f"Decision for {asset_pair}: HOLD. No action taken.")

            except Exception as e:
                logger.error(f"Error analyzing {asset_pair}: {e}")
                continue  # Try next asset

        # If no opportunities found, go back to IDLE for next analysis cycle
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
        LEARNING: Recording the outcome and updating metrics.
        """
        logger.info("State: LEARNING - Recording outcome and updating metrics...")

        # For now, just transition back to perception for the next cycle
        # In a real implementation, we would record the outcome and update metrics
        await self._transition_to(AgentState.PERCEPTION)

    async def handle_analyzing_state(self):
        """
        Perception and Reasoning: Analyze assets to find trading opportunities.
        """
        logger.info("State: ANALYZING - Looking for trading opportunities...")
        # Check for open positions first. If trades are open, we should be monitoring.
        if self.trade_monitor.is_trade_open():
            logger.info("Open trades detected. Switching to MONITORING state.")
            self.state = AgentState.MONITORING
            return

        for asset_pair in self.config.asset_pairs:
            try:
                logger.debug(f"Analyzing {asset_pair}...")
                decision = self.engine.analyze_asset(asset_pair)
                
                # If a valid trade decision is found, move to execute
                if decision and decision.get('action') in ["BUY", "SELL"]:
                    if await self._should_execute(decision):
                        self._current_decision = decision
                        self.state = AgentState.EXECUTING
                        return # Exit analysis to handle the execution
                    else:
                        logger.info(f"Decision to {decision['action']} {asset_pair} not executed due to policy or low confidence.")
                else:
                    logger.info(f"Decision for {asset_pair}: HOLD. No action taken.")

            except Exception as e:
                logger.error(f"Error analyzing {asset_pair}: {e}")
                continue # Try next asset

        # If no opportunities found, go to IDLE before next analysis cycle
        logger.info("Analysis complete. No actionable trades found. Going to IDLE.")
        self.state = AgentState.IDLE

    async def handle_executing_state(self):
        """
        Action: Execute the trade decision.
        """
        if not self._current_decision:
            logger.warning("EXECUTING state reached without a decision. Returning to ANALYZING.")
            self.state = AgentState.ANALYZING
            return

        decision_id = self._current_decision.get('id')
        action = self._current_decision.get('action')
        asset_pair = self._current_decision.get('asset_pair')
        logger.info(f"State: EXECUTING - Attempting to {action} {asset_pair} (Decision ID: {decision_id})")
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
            # Reset state and decision without raising an exception
            self._current_decision = None
            self.state = AgentState.ANALYZING
            return

        try:
            execution_result = self.engine.execute_decision(decision_id)
            if execution_result.get('success'):
                logger.info("Trade executed successfully. Associating decision with monitor and switching to MONITORING state.")
                # Link this decision to the next trade detected for this asset
                self.trade_monitor.associate_decision_to_trade(decision_id, asset_pair)
                self.state = AgentState.MONITORING
            else:
                logger.error(f"Trade execution failed: {execution_result.get('message')}. Returning to ANALYZING.")
                self.state = AgentState.ANALYZING
        except Exception as e:
            logger.error(f"Exception during trade execution for decision {decision_id}: {e}")
            self.state = AgentState.ANALYZING # Go back to analyzing on failure
        
        self._current_decision = None # Clear decision after execution attempt

    async def handle_monitoring_state(self):
        """
        Feedback and Learning: Monitor open trades and handle outcomes.
        """
        logger.info("State: MONITORING - Checking status of open trades...")
        
        # The trade_monitor should run its own loop to check for closed trades
        # Here, we just check if any trades are still open.
        if not self.trade_monitor.is_trade_open():
            logger.info("No more open trades. Switching back to ANALYZING state.")
            self.state = AgentState.ANALYZING
            return

        # The TradeMonitor should be responsible for detecting when a trade is closed
        # and then calling the feedback loop (record_trade_outcome).
        # This requires changes to TradeMonitor to be fully functional.
        # For now, we assume a method get_closed_trades() exists.
        closed_trades = getattr(self.trade_monitor, 'get_closed_trades', lambda: [])()
        for trade in closed_trades:
            try:
                # Safely get attributes that might be missing
                product_id = getattr(trade, 'product_id', 'unknown')
                realized_pnl = getattr(trade, 'realized_pnl', None)
                if realized_pnl is None or not isinstance(realized_pnl, (int, float)):
                    logger.warning(f"Skipping trade for {product_id}: realized_pnl is missing or not numeric ({realized_pnl})")
                    continue
                decision_id = getattr(trade, 'decision_id', None)
                exit_price = getattr(trade, 'exit_price', None)
                exit_time = getattr(trade, 'exit_time', None)
                exit_reason = getattr(trade, 'exit_reason', None)
                
                logger.info(f"Processing closed trade: {product_id} with P&L: ${realized_pnl:.2f}")
                
                if not decision_id:
                    logger.warning(f"Cannot record outcome for trade {product_id} without a decision ID.")
                    continue
                
                # Check for required attributes for record_trade_outcome
                missing_attrs = []
                if exit_price is None:
                    missing_attrs.append('exit_price')
                if exit_time is None:
                    missing_attrs.append('exit_time')
                if exit_reason is None:
                    missing_attrs.append('exit_reason')
                
                if missing_attrs:
                    logger.warning(f"Cannot record outcome for trade {product_id}: missing required attributes {missing_attrs}")
                    continue
                
                self.engine.record_trade_outcome(
                    decision_id=decision_id,
                    exit_price=exit_price,
                    exit_timestamp=exit_time,
                    hit_stop_loss=exit_reason == 'stop_loss',
                    hit_take_profit=exit_reason == 'take_profit'
                )
            except Exception as e:
                product_id = getattr(trade, 'product_id', 'unknown')
                logger.error(f"Error recording trade outcome for {product_id}: {e}")

        # Wait before the next monitoring check
        await asyncio.sleep(self.config.monitoring_frequency_seconds)

    async def _should_execute(self, decision) -> bool:
        """Determine if a trade should be executed based on confidence and policy."""
        confidence = decision.get('confidence', 0)
        if confidence < self.config.min_confidence_threshold:
            logger.info(f"Skipping trade due to low confidence ({confidence}% < {self.config.min_confidence_threshold}%)")
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