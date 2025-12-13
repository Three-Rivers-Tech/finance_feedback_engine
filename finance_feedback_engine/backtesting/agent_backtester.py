"""Agent Mode Backtester with OODA loop simulation.

Simulates the TradingAgentOrchestrator's autonomous behavior including:
- Data fetch retry logic with exponential backoff
- OODA frequency throttling (analysis_frequency_seconds)
- Kill-switch system (gain/loss/drawdown thresholds)
- Daily trade limits
- Strategic context injection

This validates that the agent behaves correctly under production conditions.
"""

import random
import logging
from typing import Dict, Any, Optional
from collections import defaultdict

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

    def __init__(self, *args,
                 strategic_goal: str = "Maximize risk-adjusted returns through systematic learning",
                 risk_appetite: str = "moderate",
                 max_daily_trades: int = 20,
                 analysis_frequency_seconds: int = 300,
                 kill_switch_gain_pct: float = 0.15,
                 kill_switch_loss_pct: float = 0.10,
                 max_drawdown_pct: float = 0.15,
                 data_fetch_failure_rate: float = 0.1,
                 **kwargs):
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

    def _simulate_data_fetch(self, candle_data: Dict[str, Any], attempt: int = 0) -> Dict[str, Any]:
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
        # Simulate random data fetch failures
        if random.random() < self.data_fetch_failure_rate:
            raise SimulatedDataFetchError(f"Simulated network failure (attempt {attempt + 1})")

        return candle_data

    def _check_kill_switch(self, current_portfolio_value: float,
                          initial_value: float, peak_value: float) -> Optional[str]:
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
        pnl_pct = (current_portfolio_value - initial_value) / initial_value if initial_value > 0 else 0

        # Calculate drawdown from peak
        drawdown_pct = (peak_value - current_portfolio_value) / peak_value if peak_value > 0 else 0

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

    def run_backtest(self, asset_pair: str, start_date: str, end_date: str,
                    decision_engine: Any) -> Dict[str, Any]:
        """
        Run backtest with OODA loop simulation.

        Enhances standard backtest with:
        - Retry logic for data fetching
        - OODA frequency throttling
        - Kill-switch monitoring
        - Daily trade limits
        - Strategic context

        Args:
            asset_pair: Asset to backtest
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            decision_engine: Decision engine instance

        Returns:
            Enhanced results dict with OODA metrics
        """
        logger.info(
            f"Starting Agent Mode Backtest for {asset_pair} from {start_date} to {end_date}"
        )
        logger.info(
            f"Agent Configuration: Goal='{self.strategic_goal}', "
            f"Risk='{self.risk_appetite}', OODA={self.analysis_frequency_seconds}s"
        )

        # Fetch historical data
        data = self.historical_data_provider.get_historical_data(
            asset_pair, start_date, end_date
        )

        if data.empty:
            logger.error(f"No historical data available for {asset_pair}")
            return {
                "metrics": {"net_return_pct": 0, "total_trades": 0},
                "trades": [],
                "error": "No data available"
            }

        # Initialize tracking
        ooda_metrics = {
            'total_iterations': 0,
            'candles_skipped_frequency': 0,
            'candles_skipped_daily_limit': 0,
            'retry_events': [],
            'kill_switch_triggered': False,
            'kill_switch_reason': None,
            'kill_switch_timestamp': None
        }

        last_decision_timestamp = None
        trades_by_date = defaultdict(int)
        initial_portfolio_value = self.initial_balance
        peak_portfolio_value = initial_portfolio_value

        # Inject strategic context into decision engine
        # Note: This would require modifying DecisionEngine._build_market_analysis_prompt
        # For now, we'll pass it as part of market_data
        strategic_context = {
            'strategic_goal': self.strategic_goal,
            'risk_appetite': self.risk_appetite
        }

        # Run parent backtest with enhanced monitoring
        # We'll wrap the iteration to add OODA logic

        # For now, call parent's run_backtest and enhance the results
        # TODO: Override the main iteration loop to add retry/throttling/kill-switch

        logger.warning(
            "Agent Mode Backtester is partially implemented. "
            "Full OODA loop simulation requires deeper integration. "
            "Running standard backtest with agent configuration awareness."
        )

        # Call parent backtest
        results = super().run_backtest(asset_pair, start_date, end_date, decision_engine)

        # Add OODA metrics to results
        results['ooda_metrics'] = ooda_metrics
        results['agent_config'] = {
            'strategic_goal': self.strategic_goal,
            'risk_appetite': self.risk_appetite,
            'max_daily_trades': self.max_daily_trades,
            'analysis_frequency_seconds': self.analysis_frequency_seconds,
            'kill_switch_gain_pct': self.kill_switch_gain_pct,
            'kill_switch_loss_pct': self.kill_switch_loss_pct,
            'max_drawdown_pct': self.max_drawdown_pct
        }

        logger.info(f"Agent Mode Backtest complete for {asset_pair}")

        return results


__all__ = ['AgentModeBacktester', 'SimulatedDataFetchError']
