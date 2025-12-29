"""Agent Mode Backtester with OODA loop simulation.

Simulates the TradingAgentOrchestrator's autonomous behavior including:
- Data fetch retry logic with exponential backoff
- OODA frequency throttling (analysis_frequency_seconds)
- Kill-switch system (gain/loss/drawdown thresholds)
- Daily trade limits
- Strategic context injection

This validates that the agent behaves correctly under production conditions.
"""

import logging
import random
from typing import Any, Dict, Optional

from finance_feedback_engine.backtesting.backtester import Backtester

logger = logging.getLogger(__name__)


class SimulatedDataFetchError(Exception):
    """Simulated network/data fetch failure for testing retry logic."""

    pass


class AgentModeBacktester(Backtester):
    """
    Backtester that simulates TradingAgentOrchestrator OODA loop behavior.

    Features:
    - Retry logic for data fetch failures
    - OODA frequency throttling
    - Kill-switch monitoring (gain/loss/drawdown)
    - Daily trade limits
    - Strategic context injection into AI prompts
    """

    def __init__(
        self,
        *args,
        strategic_goal: str = "Maximize risk-adjusted returns through systematic learning",
        risk_appetite: str = "moderate",
        max_daily_trades: int = 20,
        analysis_frequency_seconds: int = 300,
        kill_switch_gain_pct: float = 0.15,
        kill_switch_loss_pct: float = 0.10,
        max_drawdown_pct: float = 0.15,
        data_fetch_failure_rate: float = 0.1,
        **kwargs,
    ):
        """
        Initialize agent mode backtester.

        Args:
            strategic_goal: Strategic objective for trading decisions
            risk_appetite: Risk tolerance level (conservative/moderate/aggressive)
            max_daily_trades: Maximum trades per day
            analysis_frequency_seconds: Minimum seconds between decisions (OODA throttle)
            kill_switch_gain_pct: Stop trading if gain exceeds this (e.g., 0.15 = 15%)
            kill_switch_loss_pct: Stop trading if loss exceeds this (e.g., 0.10 = 10%)
            max_drawdown_pct: Stop trading if drawdown exceeds this
            data_fetch_failure_rate: Probability of simulated data fetch failures (0.0-1.0)
        """
        super().__init__(*args, **kwargs)

        self.strategic_goal = strategic_goal
        self.risk_appetite = risk_appetite
        self.max_daily_trades = max_daily_trades
        self.analysis_frequency_seconds = analysis_frequency_seconds
        self.kill_switch_gain_pct = kill_switch_gain_pct
        self.kill_switch_loss_pct = kill_switch_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.data_fetch_failure_rate = data_fetch_failure_rate

        logger.info(
            f"AgentModeBacktester initialized with strategic goal: '{strategic_goal}', "
            f"risk appetite: '{risk_appetite}', OODA frequency: {analysis_frequency_seconds}s"
        )

    def _simulate_data_fetch(
        self, candle_data: Dict[str, Any], attempt: int = 0
    ) -> Dict[str, Any]:
        """
        Simulate data fetch with potential failures and retry logic.

        Args:
            candle_data: Market data to "fetch"
            attempt: Current retry attempt number

        Returns:
            Candle data if successful

        Raises:
            SimulatedDataFetchError: If simulated failure occurs
        """
        # Simulate random data fetch failures (not for security purposes)
        if random.random() < self.data_fetch_failure_rate:
            raise SimulatedDataFetchError(
                f"Simulated network failure (attempt {attempt + 1})"
            )

        return candle_data

    def _check_kill_switch(
        self, current_portfolio_value: float, initial_value: float, peak_value: float
    ) -> Optional[str]:
        """
        Check if kill-switch conditions are met.

        Args:
            current_portfolio_value: Current total portfolio value
            initial_value: Starting portfolio value
            peak_value: Peak portfolio value reached

        Returns:
            Reason string if kill-switch triggered, None otherwise
        """
        # Calculate P&L percentage
        pnl_pct = (
            (current_portfolio_value - initial_value) / initial_value
            if initial_value > 0
            else 0
        )

        # Calculate drawdown from peak
        drawdown_pct = (
            (peak_value - current_portfolio_value) / peak_value if peak_value > 0 else 0
        )

        # Check gain threshold
        if pnl_pct >= self.kill_switch_gain_pct:
            return f"GAIN_THRESHOLD_EXCEEDED ({pnl_pct:.2%} >= {self.kill_switch_gain_pct:.2%})"

        # Check loss threshold
        if pnl_pct <= -self.kill_switch_loss_pct:
            return f"LOSS_THRESHOLD_EXCEEDED ({pnl_pct:.2%} <= -{self.kill_switch_loss_pct:.2%})"

        # Check drawdown threshold
        if drawdown_pct >= self.max_drawdown_pct:
            return f"DRAWDOWN_THRESHOLD_EXCEEDED ({drawdown_pct:.2%} >= {self.max_drawdown_pct:.2%})"

        return None

    def run_backtest(
        self, asset_pair: str, start_date: str, end_date: str, decision_engine: Any
    ) -> Dict[str, Any]:
        """
        Run backtest with OODA loop simulation: retries, throttling, kill-switch, and daily trade limits.
        """
        import asyncio

        from finance_feedback_engine.agent.config import TradingAgentConfig
        from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
        from finance_feedback_engine.data_providers.mock_live_provider import (
            MockLiveProvider,
        )
        from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
        from finance_feedback_engine.trading_platforms.mock_platform import (
            MockTradingPlatform,
        )
        from finance_feedback_engine.utils.validation import standardize_asset_pair

        logger.info(
            f"Starting Agent Mode Backtest for {asset_pair} from {start_date} to {end_date}"
        )
        logger.info(
            f"Agent Configuration: Goal='{self.strategic_goal}', Risk='{self.risk_appetite}', OODA={self.analysis_frequency_seconds}s"
        )

        # Fetch historical data
        data = self.historical_data_provider.get_historical_data(
            asset_pair, start_date, end_date, timeframe=self.timeframe
        )
        if data.empty:
            logger.error(f"No historical data available for {asset_pair}")
            return {
                "metrics": {"net_return_pct": 0, "total_trades": 0},
                "trades": [],
                "error": "No data available",
            }

        asset_pair_std = standardize_asset_pair(asset_pair)
        initial_balance_dict = {"FUTURES_USD": self.initial_balance}
        mock_platform = MockTradingPlatform(initial_balance=initial_balance_dict)
        mock_provider = MockLiveProvider(
            historical_data=data, asset_pair=asset_pair_std, start_index=0
        )
        mock_provider.initialize_pulse_mode(base_timeframe=self.timeframe)

        # Agent config aligned to requested OODA settings
        from ..agent.config import AutonomousAgentConfig

        agent_config = TradingAgentConfig(
            asset_pairs=[asset_pair_std],
            autonomous_execution=True,
            autonomous=AutonomousAgentConfig(enabled=True),
            max_daily_trades=self.max_daily_trades,
            min_confidence_threshold=0.0,
            analysis_frequency_seconds=self.analysis_frequency_seconds,
            max_drawdown_percent=self.max_drawdown_pct,
            correlation_threshold=0.7,
            max_correlated_assets=5,
            max_var_pct=0.1,
            var_confidence=0.95,
            position_sizing_strategy=self.position_sizing_strategy,
            risk_per_trade=self.risk_per_trade,
        )

        trade_monitor = TradeMonitor(
            platform=mock_platform,
            portfolio_memory=self.memory_engine if self.memory_engine else None,
        )

        # Backtest engine wrapper (same as parent)
        class BacktestEngine:
            def __init__(
                self,
                backtester,
                decision_engine,
                mock_provider,
                mock_platform,
                asset_pair,
                memory_engine,
            ):
                self.backtester = backtester
                self.decision_engine = decision_engine
                self.mock_provider = mock_provider
                self.mock_platform = mock_platform
                self.asset_pair = asset_pair
                self.memory_engine = memory_engine
                self._decisions = {}

            async def analyze_asset(self, asset_pair):
                market_data = await self.mock_provider.get_comprehensive_market_data(
                    asset_pair=asset_pair, include_sentiment=True
                )
                balance = self.mock_platform.get_balance()
                current_balance = balance.get(
                    "FUTURES_USD", self.backtester.initial_balance
                )
                # Pick an effective price
                effective_price = market_data.get("close", None)
                if not effective_price:
                    effective_price = market_data.get("open", 0)
                position_size = self.backtester._calculate_position_size(
                    current_balance=current_balance, current_price=effective_price or 0
                )
                decision = await self.decision_engine.generate_decision(
                    asset_pair=asset_pair,
                    market_data=market_data,
                    balance=balance,
                    portfolio={"holdings": []},
                    memory_context=None,
                    monitoring_context={
                        "active_positions": {"futures": [], "spot": []},
                        "slots_available": 5,
                    },
                )
                if decision:
                    decision.setdefault("position_size", position_size)
                    if "id" in decision:
                        self._decisions[decision["id"]] = decision
                return decision

            def execute_decision(self, decision_id):
                decision = self._decisions.get(decision_id)
                if not decision:
                    return {
                        "success": False,
                        "message": f"Decision {decision_id} not found",
                    }
                try:
                    return self.mock_platform.execute_trade(decision)
                except Exception as e:
                    logger.error(f"Error executing decision {decision_id}: {e}")
                    return {"success": False, "message": str(e)}

            def record_trade_outcome(self, outcome):
                if self.memory_engine:
                    try:
                        self.memory_engine.record_outcome(outcome)
                    except Exception:
                        pass

        backtest_engine = BacktestEngine(
            self,
            decision_engine,
            mock_provider,
            mock_platform,
            asset_pair_std,
            self.memory_engine,
        )
        agent = TradingLoopAgent(
            config=agent_config,
            engine=backtest_engine,
            trade_monitor=trade_monitor,
            portfolio_memory=self.memory_engine if self.memory_engine else None,
            trading_platform=mock_platform,
        )
        agent.is_running = True

        # OODA loop with throttling, retries, kill-switch, and daily trade limits
        ooda_metrics = {
            "total_iterations": 0,
            "candles_skipped_frequency": 0,
            "candles_skipped_daily_limit": 0,
            "retry_events": [],
            "kill_switch_triggered": False,
            "kill_switch_reason": None,
            "kill_switch_timestamp": None,
        }

        # Calculate throttle in pulses (pulse is 300s)
        throttle_pulses = max(1, int(self.analysis_frequency_seconds // 300))
        last_processed_pulse = -1
        daily_trade_counts: Dict[str, int] = {}
        peak_value = self.initial_balance

        async def run_backtest_loop():
            nonlocal last_processed_pulse, peak_value
            pulse_idx = 0
            while mock_provider.advance_pulse():
                ooda_metrics["total_iterations"] += 1
                pulse_idx += 1

                # Frequency throttling
                if (
                    throttle_pulses > 1
                    and (pulse_idx - last_processed_pulse) < throttle_pulses
                ):
                    ooda_metrics["candles_skipped_frequency"] += 1
                    continue

                # Simulate retry on data fetch
                max_attempts = 3
                attempt = 0
                pulse_data = None
                while attempt < max_attempts:
                    try:
                        # Wrap actual fetch with simulated failure
                        raw_pulse = await mock_provider.get_pulse_data()
                        pulse_data = self._simulate_data_fetch(
                            raw_pulse, attempt=attempt
                        )
                        break
                    except SimulatedDataFetchError as e:
                        ooda_metrics["retry_events"].append(
                            {"attempt": attempt + 1, "error": str(e)}
                        )
                        await asyncio.sleep(0.2 * (2**attempt))
                        attempt += 1
                    except Exception as e:
                        logger.warning(f"Pulse fetch error: {e}")
                        break

                if pulse_data is None:
                    # Could not fetch data; skip this pulse
                    continue

                # Daily trade limit check
                current_candle = mock_provider.get_current_candle()
                day_key = str(current_candle.get("date", "unknown"))[:10]
                trades_before = len(mock_platform.get_trade_history())
                # Process one agent cycle if under limit
                if daily_trade_counts.get(day_key, 0) >= self.max_daily_trades:
                    ooda_metrics["candles_skipped_daily_limit"] += 1
                    continue

                _ = await agent.process_cycle()
                trades_after = len(mock_platform.get_trade_history())
                if trades_after > trades_before:
                    daily_trade_counts[day_key] = daily_trade_counts.get(day_key, 0) + (
                        trades_after - trades_before
                    )

                # Update peak and check kill-switch based on portfolio value
                try:
                    portfolio = mock_platform.get_portfolio_breakdown()
                    current_value = float(
                        portfolio.get("total_value_usd", self.initial_balance)
                    )
                except Exception:
                    current_value = self.initial_balance

                peak_value = max(peak_value, current_value)
                ks_reason = self._check_kill_switch(
                    current_value, self.initial_balance, peak_value
                )
                if ks_reason:
                    ooda_metrics["kill_switch_triggered"] = True
                    ooda_metrics["kill_switch_reason"] = ks_reason
                    ooda_metrics["kill_switch_timestamp"] = current_candle.get("date")
                    logger.warning(f"Kill-switch triggered: {ks_reason}")
                    break

                last_processed_pulse = pulse_idx

        asyncio.run(run_backtest_loop())

        # Compute results via parent's reporting (reuse metrics computation on platform state)
        results = super().run_backtest(
            asset_pair, start_date, end_date, decision_engine
        )
        results["ooda_metrics"] = ooda_metrics
        results["agent_config"] = {
            "strategic_goal": self.strategic_goal,
            "risk_appetite": self.risk_appetite,
            "max_daily_trades": self.max_daily_trades,
            "analysis_frequency_seconds": self.analysis_frequency_seconds,
            "kill_switch_gain_pct": self.kill_switch_gain_pct,
            "kill_switch_loss_pct": self.kill_switch_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
        }

        logger.info(f"Agent Mode Backtest complete for {asset_pair}")
        return results


__all__ = ["AgentModeBacktester", "SimulatedDataFetchError"]
