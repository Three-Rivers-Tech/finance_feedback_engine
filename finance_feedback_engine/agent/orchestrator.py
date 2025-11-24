import time
import click
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.trading_platforms.unified_platform import UnifiedPlatform
# Additional imports will be needed for data providers, persistence, etc.

class TradingAgentOrchestrator:
    """
    The main orchestrator for the trading agent.

    This class runs a continuous loop to:
    1. Perceive: Gather market and portfolio data.
    2. Orient: Synthesize data into a context for the decision engine.
    3. Decide: Delegate decision-making to the existing DecisionEngine.
    4. Act: Execute trades based on the agent's configuration (e.g., requiring approval).
    """
    def __init__(self, config: TradingAgentConfig, engine: DecisionEngine, platform: UnifiedPlatform):
        self.config = config
        self.engine = engine
        self.platform = platform
        self.trades_today = 0
        print("Trading Agent Orchestrator initialized.")

    def run(self):
        """Starts the main agentic loop."""
        print(f"Agent starting with strategy: '{self.config.strategic_goal}' and risk appetite: '{self.config.risk_appetite}'.")
        print(f"Autonomous execution is {'ENABLED' if self.config.autonomous_execution else 'DISABLED'}.")

        while True:
            if self.trades_today >= self.config.max_daily_trades:
                print("Maximum daily trades reached. Stopping for today.")
                break

            for asset_pair in self.config.asset_pairs:
                print(f"--- Analyzing {asset_pair} ---")
                
                # 1. PERCEIVE: Gather data (to be implemented)
                # This is where you would call your data providers
                market_data = "..." 

                # 2. ORIENT: Build context
                # The context should be enriched with portfolio status, strategic goals etc.
                context = f"Strategic Goal: {self.config.strategic_goal}. Risk Appetite: {self.config.risk_appetite}. Market Data: {market_data}"

                # 3. DECIDE: Use the existing "oneshot" decision engine
                decision = self.engine.analyze(asset_pair, provider_name='default') # Assuming 'default' provider

                if not decision or decision.decision == "HOLD":
                    print(f"Decision: HOLD. No action taken.")
                    continue
                
                print(f"Decision: {decision.decision} {asset_pair} with {decision.confidence*100:.2f}% confidence.")
                print(f"Reasoning: {decision.reasoning}")

                # 4. ACT: Execute based on configuration
                if self._should_execute(decision):
                    # platform.execute_trade(decision) # To be implemented
                    self.trades_today += 1
                    print(f"EXECUTING TRADE: {decision.decision} {asset_pair}")
                else:
                    print("Trade not executed due to approval policy.")

            print(f"Cycle complete. Waiting for {self.config.analysis_frequency_seconds} seconds...")
            time.sleep(self.config.analysis_frequency_seconds)

    def _should_execute(self, decision) -> bool:
        """Determines if a trade should be executed based on the approval policy."""
        if self.config.autonomous_execution:
            return True
        
        # For non-autonomous mode, use the approval policy
        if self.config.approval_policy == "never":
            return False
        if self.config.approval_policy == "always":
            return click.confirm("Do you want to execute this trade?", default=True)
        
        # Logic for 'on_new_asset' would go here
        # For now, default to asking
        return click.confirm(f"Execute trade for {decision.asset_pair}?", default=True)
