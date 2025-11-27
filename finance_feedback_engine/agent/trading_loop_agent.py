# finance_feedback_engine/agent/trading_loop_agent.py

import asyncio
import logging
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.trading_platforms.base_platform import BaseTradingPlatform

logger = logging.getLogger(__name__)

class TradingLoopAgent:
    """
    An autonomous agent that runs a continuous trading loop.
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

    async def run(self):
        """
        The main trading loop.
        """
        logger.info("Starting autonomous trading agent...")
        self.is_running = True

        while self.is_running:
            try:
                # Check for open trades
                if self.trade_monitor.is_trade_open():
                    # Monitor trade and apply risk management
                    await self._monitor_open_trade()
                else:
                    # Analyze assets and get trading signals
                    for asset_pair in self.config.asset_pairs:
                        try:
                            await self._analyze_and_trade(asset_pair)
                        except Exception as e:
                            logger.error(f"Error processing {asset_pair}: {e}")
                            continue
                
                # Wait before next analysis cycle
                await asyncio.sleep(self.config.analysis_frequency_seconds)
            except asyncio.CancelledError:
                logger.info("Trading loop cancelled.")
                break
            except Exception as e:
                logger.error(f"An error occurred in the trading loop: {e}", exc_info=True)
                # Backoff on error
                await asyncio.sleep(300)

    async def _monitor_open_trade(self):
        """Monitor open trades and apply risk management."""
        # Placeholder for trade monitoring logic
        pass

    async def _analyze_and_trade(self, asset_pair: str):
        """Analyze an asset and execute trade if conditions met."""
        logger.info(f"Analyzing {asset_pair}")
        
        # Fetch market data
        market_data = self.engine.data_provider.get_comprehensive_market_data(asset_pair)
        
        # Get balance
        balance = self.trading_platform.get_balance()
        
        # Get portfolio
        portfolio = None
        if hasattr(self.trading_platform, 'get_portfolio_breakdown'):
            try:
                portfolio = self.trading_platform.get_portfolio_breakdown()
            except Exception:
                pass
        
        # Get memory context
        memory_context = None
        if self.portfolio_memory:
            memory_context = self.portfolio_memory.generate_context(asset_pair=asset_pair)
        
        # Generate decision
        decision = self.engine.decision_engine.generate_decision(
            asset_pair=asset_pair,
            market_data=market_data,
            balance=balance,
            portfolio=portfolio,
            memory_context=memory_context
        )
        
        if not decision or decision.get('decision', 'HOLD') == "HOLD":
            logger.info(f"Decision: HOLD for {asset_pair}. No action taken.")
            return

        # Normalize confidence: support fractions (<=1) and percentages (>1)
        raw_conf = decision.get('confidence', 0)
        try:
            conf_val = float(raw_conf)
        except Exception:
            conf_val = 0.0

        if conf_val <= 1:
            confidence = conf_val * 100.0
        else:
            confidence = conf_val

        decision_label = decision.get('decision', 'UNKNOWN')
        reasoning = decision.get('reasoning', 'N/A')

        logger.info(
            (
                f"Decision: {decision_label} {asset_pair} with "
                f"{confidence:.2f}% confidence."
            )
        )
        logger.info(f"Reasoning: {reasoning}")
        
        # Check if should execute
        if await self._should_execute(decision):
            # Execute trade
            await self._execute_trade(decision)
        else:
            logger.info("Trade not executed due to approval policy.")

    async def _should_execute(self, decision) -> bool:
        """Determine if a trade should be executed."""
        if self.config.autonomous_execution:
            return True
        
        # For non-autonomous, check approval policy
        if self.config.approval_policy == "never":
            return False
        elif self.config.approval_policy == "always":
            # In async context, we can't use click.confirm easily
            # For now, assume no for safety
            logger.warning(
                "Approval required but cannot prompt in async context. "
                "Skipping trade."
            )
            return False
        else:
            # on_new_asset or other logic
            # For now, skip
            return False

    async def _execute_trade(self, decision):
        """Execute the trade."""
        try:
            # Use the trading platform to execute
            exec_result = self.trading_platform.execute_trade(decision)
            dec_label = decision.get('decision', 'UNKNOWN')
            asset_label = decision.get('asset_pair', '')
            logger.info(f"Executed trade: {dec_label} {asset_label}")
            logger.debug("Execution result: %s", exec_result)
            # Update portfolio memory if needed
            # self.portfolio_memory.record_trade(...)
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")

    def stop(self):
        """
        Stops the trading loop.
        """
        logger.info("Stopping autonomous trading agent...")
        self.is_running = False

