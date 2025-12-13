import time
import threading
import click
import warnings
from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.trading_platforms.unified_platform import UnifiedTradingPlatform
from finance_feedback_engine.utils.market_schedule import MarketSchedule
from finance_feedback_engine.utils.validation import standardize_asset_pair
# Additional imports will be needed for data providers, persistence, etc.


# DEPRECATION WARNING
warnings.warn(
    "TradingAgentOrchestrator is DEPRECATED and will be removed in v3.0. "
    "Use TradingLoopAgent from finance_feedback_engine.agent.trading_loop_agent instead. "
    "See docs/migration/ORCHESTRATOR_MIGRATION.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)


class TradingAgentOrchestrator:
    """
    The main orchestrator for the trading agent.

    This class runs a continuous loop to:
    1. Perceive: Gather market and portfolio data.
    2. Orient: Synthesize data into a context for the decision engine.
    3. Decide: Delegate decision-making to the existing DecisionEngine.
    4. Act: Execute trades based on the agent's configuration (e.g., requiring approval).
    """
    def __init__(self, config: TradingAgentConfig, engine: DecisionEngine, platform: UnifiedTradingPlatform):
        self.config = config
        self.engine = engine
        self.platform = platform

        # SAFETY: Prevent quicktest mode in live trading
        ensemble_config = getattr(config, 'ensemble_config', None) or {}
        quicktest_mode = ensemble_config.get('quicktest_mode', False)
        if quicktest_mode:
            raise ValueError(
                "quicktest_mode is ONLY allowed in testing/backtesting environments. "
                "It is unsafe for live trading as it disables debate mode and memory. "
                "Please set ensemble.quicktest_mode: false in your config."
            )

        # Warn if debate mode is disabled (should be standard)
        debate_mode = ensemble_config.get('debate_mode', True)
        if not debate_mode:
            click.echo(
                click.style(
                    "⚠️  WARNING: debate_mode is disabled. Debate mode is the standard across this repo.",
                    fg='yellow'
                )
            )
            click.echo(
                click.style(
                    "   Consider setting ensemble.debate_mode: true in your config for multi-provider consensus.",
                    fg='yellow'
                )
            )

        self.trades_today = 0
        self.analysis_failures = {}  # Track failed analysis attempts by asset pair
        # Snapshot initial portfolio value for P/L kill-switch calculations
        # Wait for a valid non-zero portfolio value (up to timeout)
        self.initial_portfolio_value = 0.0
        # Retry a fixed number of times (6 retries, 10s apart)
        retries = 6
        interval = 10.0  # seconds
        self.init_failed = False
        for attempt in range(1, retries + 1):
            try:
                breakdown = self.platform.get_portfolio_breakdown()
                val = breakdown.get('total_value_usd', 0.0)
                if val and val > 0:
                    self.initial_portfolio_value = val
                    break
            except Exception:
                pass
            if attempt < retries:
                time.sleep(interval)
        else:
            # All retries failed
            self.init_failed = True
        print("Trading Agent Orchestrator initialized.")
        self._stop_event = threading.Event()
        self._paused_by_monitor = False # Flag to indicate if paused by monitoring
        self.kill_switch_triggered = False  # Flag to indicate if kill-switch fired
        self.kill_switch_gain_pct = self.config.kill_switch_gain_pct
        self.kill_switch_loss_pct = self.config.kill_switch_loss_pct
        # Normalize max_drawdown_percent to decimal fraction (handle both percentage and decimal input)
        self.max_drawdown_pct = self.config.max_drawdown_percent if self.config.max_drawdown_percent <= 1.0 else self.config.max_drawdown_percent / 100.0
        self.peak_portfolio_value = self.initial_portfolio_value

    def pause_trading(self, reason: str = "Unknown reason"):
        """
        Pauses the trading agent's operation, usually triggered by the monitor
        due to portfolio-level stop-loss or take-profit.
        """
        self._paused_by_monitor = True
        print(f"Agent PAUSED by monitor: {reason}. No new trades will be executed.")

    def stop(self):
        """
        Stops the trading agent's operation.
        """
        self._stop_event.set()
        print("Agent STOP signal received. Shutting down gracefully.")

    def run(self, test_mode=False):
        """Starts the main agentic loop."""
        print(f"Agent starting with strategy: '{self.config.strategic_goal}' and risk appetite: '{self.config.risk_appetite}'.")
        print(f"Autonomous execution is {'ENABLED' if self.config.autonomous_execution else 'DISABLED'}.")

        if getattr(self, 'init_failed', False):
            print("Could not obtain initial portfolio snapshot after retries. Exiting gracefully.")
            return

        iteration_count = 0
        while not self._stop_event.is_set():
            iteration_count += 1

            # In test mode, limit to 1 iteration to prevent infinite loops
            if test_mode and iteration_count > 1:
                break
            # Check kill-switch conditions
            try:
                current_breakdown = self.platform.get_portfolio_breakdown()
                current_value = current_breakdown.get('total_value_usd', 0.0)
                if self.initial_portfolio_value > 0:
                    pnl_pct = (current_value - self.initial_portfolio_value) / self.initial_portfolio_value

                    # Update peak portfolio value for drawdown calculation
                    if current_value > self.peak_portfolio_value:
                        self.peak_portfolio_value = current_value

                    # Calculate current drawdown from peak
                    if self.peak_portfolio_value > 0:
                        drawdown_pct = (self.peak_portfolio_value - current_value) / self.peak_portfolio_value
                        if drawdown_pct >= self.max_drawdown_pct:
                            print(f"Kill-switch triggered: portfolio drawdown of {drawdown_pct:.2%} exceeds threshold {self.max_drawdown_pct:.2%}")
                            print("Agent stopping due to kill-switch activation.")
                            self.kill_switch_triggered = True
                            break

                    if pnl_pct >= self.kill_switch_gain_pct:
                        print(f"Kill-switch triggered: portfolio gain of {pnl_pct:.2%} exceeds threshold {self.kill_switch_gain_pct:.2%}")
                        print("Agent stopping due to kill-switch activation.")
                        self.kill_switch_triggered = True
                        break
                    elif pnl_pct <= -self.kill_switch_loss_pct:
                        print(f"Kill-switch triggered: portfolio loss of {pnl_pct:.2%} exceeds threshold -{self.kill_switch_loss_pct:.2%}")
                        print("Agent stopping due to kill-switch activation.")
                        self.kill_switch_triggered = True
                        break
            except Exception as e:
                print(f"Error checking kill-switch: {e}")
            if self._paused_by_monitor:
                print("Agent is paused by monitor. Waiting for resume signal or manual intervention.")
                time.sleep(self.config.analysis_frequency_seconds) # Wait before checking again
                continue

            for asset_pair in self.config.asset_pairs:
                asset_pair_std = standardize_asset_pair(asset_pair)
                asset_type = self._infer_asset_type(asset_pair_std)
                status = MarketSchedule.get_market_status(asset_pair_std, asset_type)

                if status.get("warning"):
                    print(
                        f"Warning for {asset_pair_std}: {status['warning']} (session={status['session']})"
                    )

                if not status.get("is_open", False):
                    # MarketSchedule provides time_to_open for closed sessions; fall back to 0 if absent
                    minutes = status.get("time_to_open", status.get("time_until_next_session", 0))
                    print(
                        f"Market closed for {asset_pair_std} ({asset_type}). "
                        f"Session={status.get('session', 'Closed')}. "
                        f"Reopens in ~{minutes} minutes. Skipping."
                    )
                    continue

                try:
                    print(f"--- Analyzing {asset_pair_std} ---")

                    # 1. PERCEIVE: Gather market data with retry logic
                    market_data = None
                    for attempt in range(3):
                        try:
                            market_data = self.engine.data_provider.get_comprehensive_market_data(
                                asset_pair_std,
                                include_sentiment=True,
                                include_macro=True
                            )
                            break
                        except Exception as e:
                            print(f"Attempt {attempt + 1}/3 failed for {asset_pair_std}: {e}")
                            if attempt == 2:
                                print(f"Failed to fetch data for {asset_pair_std} after 3 attempts, skipping")
                                self.analysis_failures[asset_pair_std] = time.time()
                                continue
                            time.sleep(2 ** attempt)  # Exponential backoff

                    if market_data is None:
                        continue

                    # 2. ORIENT: Build context
                    # The context should be enriched with portfolio status, strategic goals etc.
                    context = f"Strategic Goal: {self.config.strategic_goal}. Risk Appetite: {self.config.risk_appetite}. Market Regime: {market_data.get('market_regime', 'Unknown')}"

                    # 3. DECIDE: Use the existing "oneshot" decision engine
                    decision = self.engine.generate_decision(asset_pair_std)

                    if not decision or decision.decision == "HOLD":
                        print("Decision: HOLD. No action taken.")
                        continue

                    print(f"Decision: {decision.decision} {asset_pair_std} with {decision.confidence*100:.2f}% confidence.")
                    print(f"Reasoning: {decision.reasoning}")

                    # 4. ACT: Execute based on configuration
                    if self._should_execute(decision):
                        # platform.execute_trade(decision) # To be implemented
                        self.trades_today += 1
                        print(f"EXECUTING TRADE: {decision.decision} {asset_pair_std}")
                    else:
                        print("Trade not executed due to approval policy.")
                except Exception as e:
                    print(f"Error processing {asset_pair_std}: {e}")
                    # Continue to next asset pair instead of crashing

    @staticmethod
    def _infer_asset_type(asset_pair: str) -> str:
        """Infer asset type for routing schedule checks.

        Crypto: BTC/ETH hardcoded (aligned with AlphaVantage provider). Forex: both legs in common FX set or 6-char pair. Otherwise defaults to stocks.
        """
        upper = asset_pair.upper()
        if 'BTC' in upper or 'ETH' in upper:
            return 'crypto'

        fx_currencies = {'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'NZD', 'USD'}
        if '_' in upper:
            parts = upper.split('_')
            if len(parts) == 2 and parts[0] in fx_currencies and parts[1] in fx_currencies:
                return 'forex'
        elif len(upper) == 6 and upper[:3] in fx_currencies and upper[3:] in fx_currencies:
            return 'forex'
        return 'stocks'


    def _should_execute(self, decision) -> bool:
        """Determines if a trade should be executed based on the approval policy and daily limits."""
        if self.trades_today >= self.config.max_daily_trades:
            print(f"Daily trade limit ({self.config.max_daily_trades}) reached. No more trades today.")
            return False

        if self.config.autonomous_execution:
            return True

        # For non-autonomous mode, use the approval policy
        if self.config.approval_policy == "never":
            return False
        if self.config.approval_policy == "always":
            try:
                return click.confirm("Do you want to execute this trade?", default=True)
            except (EOFError, click.exceptions.Abort):
                print("Cannot prompt for approval in non-interactive mode. Skipping trade.")
                return False

        # Logic for 'on_new_asset' would go here
        # For now, default to asking
        try:
            return click.confirm(f"Execute trade for {decision.asset_pair}?", default=True)
        except (EOFError, click.exceptions.Abort):
            print("Cannot prompt for approval in non-interactive mode. Skipping trade.")
            return False
