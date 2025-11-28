# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import logging
from enum import Enum, auto
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)

class AgentState(Enum):
    """Represents the current state of the trading agent."""
    IDLE = auto()
    ANALYZING = auto()
    EXECUTING = auto()
    MONITORING = auto()

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
        self.is_running = False
        self.state = AgentState.IDLE
        self._current_decision = None

    async def run(self):
        """
        The main trading loop, implemented as a state machine.
        """
        logger.info("Starting autonomous trading agent...")
        self.is_running = True
        self.state = AgentState.ANALYZING  # Start by analyzing

        while self.is_running:
            try:
                if self.state == AgentState.ANALYZING:
                    await self.handle_analyzing_state()
                elif self.state == AgentState.EXECUTING:
                    await self.handle_executing_state()
                elif self.state == AgentState.MONITORING:
                    await self.handle_monitoring_state()
                elif self.state == AgentState.IDLE:
                    await asyncio.sleep(self.config.analysis_frequency_seconds)
                    self.state = AgentState.ANALYZING

            except asyncio.CancelledError:
                logger.info("Trading loop cancelled.")
                break
            except Exception as e:
                logger.error(f"An error occurred in the trading loop: {e}", exc_info=True)
                self.state = AgentState.IDLE # Go to idle on error and wait before retrying
                await asyncio.sleep(300) # Backoff on error

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
                logger.info(f"Processing closed trade: {trade.product_id} with P&L: ${trade.realized_pnl:.2f}")
                decision_id = trade.decision_id 
                if decision_id:
                    self.engine.record_trade_outcome(
                        decision_id=decision_id,
                        exit_price=trade.exit_price,
                        exit_timestamp=trade.exit_time,
                        hit_stop_loss=trade.exit_reason == 'stop_loss',
                        hit_take_profit=trade.exit_reason == 'take_profit'
                    )
                else:
                    logger.warning(f"Cannot record outcome for trade {trade.product_id} without a decision ID.")
            except Exception as e:
                logger.error(f"Error recording trade outcome for {trade.product_id}: {e}")

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