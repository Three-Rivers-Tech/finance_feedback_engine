import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from finance_feedback_engine.backtesting.backtest_validator import BacktestValidator
from finance_feedback_engine.backtesting.enhanced_risk_analyzer import (
    EnhancedRiskAnalyzer,
)
from finance_feedback_engine.backtesting.performance_analyzer import (
    BacktestPerformanceAnalyzer,
)
from finance_feedback_engine.data_providers.historical_data_provider import (
    HistoricalDataProvider,
)
from finance_feedback_engine.decision_engine.engine import DecisionEngine

logger = logging.getLogger(__name__)


@dataclass
class Position:
    asset_pair: str
    units: float  # Positive for LONG, negative for SHORT
    entry_price: float
    entry_timestamp: datetime
    side: str = "LONG"  # "LONG" or "SHORT"
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    liquidation_price: Optional[float] = None  # Margin liquidation trigger price


class Backtester:
    """
    A backtesting engine for simulating trading strategies with enhanced features.

    This class provides a robust environment to evaluate the performance of trading
    strategies and AI models against historical market data, incorporating realistic
    trading conditions, various performance metrics, and scenario analysis capabilities.
    For reproducibility, the backtest uses a mock portfolio with a fixed initial capital
    and is not connected to any live trading accounts.

    Implementation Notes:
    - **Modular Strategy Integration:** Designed to accept various trading strategies
      (e.g., rule-based, AI-driven) via a callable function or an AI model interface.
    - **Realistic Simulation:** Aims to simulate real-world trading by accounting
      for transaction fees, slippage (TODO), and position sizing.
    - **Comprehensive Metrics:** Calculates a wide range of performance metrics
      beyond simple profit/loss, including risk-adjusted returns (Sharpe, Sortino),
      drawdowns, and win rates.
    - **Scenario Analysis:** Allows for testing strategies under different market
      conditions or with perturbed inputs to assess robustness (TODO).
    - **Reproducibility:** Emphasizes logging all parameters and conditions to
      ensure backtest results are reproducible.

    TODO:
    - **Slippage Modeling:** Implement various slippage models (e.g., fixed, percentage,
      volume-dependent) to make simulations more realistic.
    - **Order Types & Execution:** Simulate different order types (market, limit, stop)
      and their execution logic.
    - **Portfolio Management:** Incorporate more complex portfolio management, including
      diversification, rebalancing, and risk allocation.
    - **Optimization:** Add features for hyperparameter optimization of strategies
      (e.g., genetic algorithms, grid search).
    - **Walk-Forward Optimization:** Implement walk-forward testing to combat overfitting.
    - **Parallel Processing:** For running multiple backtests simultaneously (e.g., for
      parameter sweeps or Monte Carlo simulations).
    - **Reporting & Visualization:** Integrate with reporting tools and charting libraries
      to generate comprehensive backtest reports and visualizations.
    - **Event-Driven Backtester:** Convert to an event-driven model for higher fidelity
      simulation if tick-level data is used.
    """

    def __init__(
        self,
        historical_data_provider: HistoricalDataProvider,
        platform: Optional[Any] = None,  # Trading platform for margin/leverage fetching
        initial_balance: float = 10000.0,
        fee_percentage: float = 0.001,  # 0.1% fee
        slippage_percentage: float = 0.0001,  # 0.01% base slippage
        slippage_impact_factor: float = 0.01,  # Volume impact: 1% slippage per 1% of volume
        commission_per_trade: float = 0.0,  # Fixed commission
        stop_loss_percentage: float = 0.02,  # 2% stop loss
        take_profit_percentage: float = 0.05,  # 5% take profit
        override_leverage: Optional[float] = None,  # Override platform leverage
        override_maintenance_margin: Optional[
            float
        ] = None,  # Override maintenance margin %
        enable_risk_gatekeeper: bool = True,  # Enable RiskGatekeeper validation
        timeframe_aggregator: Optional[
            Any
        ] = None,  # TimeframeAggregator for multi-timeframe pulse
        enable_decision_cache: bool = True,  # Enable decision caching
        enable_portfolio_memory: bool = True,  # Enable portfolio memory for learning
        memory_isolation_mode: bool = False,  # Use isolated memory storage
        force_local_providers: bool = True,  # Restrict ensemble to local providers only
        max_concurrent_positions: int = 5,  # Max simultaneous open positions
        timeframe: str = "1h",  # Candle timeframe ('1m', '5m', '15m', '30m', '1h', '1d')
        risk_free_rate: float = 0.02,  # Annual risk-free rate for Sharpe ratio (default 2%)
        position_sizing_strategy: str = "fixed_fraction",  # Position sizing strategy
        risk_per_trade: float = 0.02,  # Risk per trade (2% of balance)
        config: Optional[Dict[str, Any]] = None,  # Full config for memory engine
    ):
        self.historical_data_provider = historical_data_provider
        self.platform = platform
        self.timeframe_aggregator = timeframe_aggregator
        self.initial_balance = initial_balance
        self.fee_percentage = fee_percentage
        self.slippage_percentage = slippage_percentage
        self.slippage_impact_factor = slippage_impact_factor
        self.commission_per_trade = commission_per_trade
        self.stop_loss_percentage = stop_loss_percentage
        self.take_profit_percentage = take_profit_percentage
        self.max_concurrent_positions = max_concurrent_positions
        self.force_local_providers = force_local_providers
        self.timeframe = timeframe  # Store timeframe for use in run_backtest
        self.risk_free_rate = risk_free_rate  # Annual risk-free rate for Sharpe ratio
        self.position_sizing_strategy = position_sizing_strategy
        self.risk_per_trade = risk_per_trade  # For position sizing calculations
        self.config = config or {}

        # Initialize decision cache
        self.decision_cache = None
        if enable_decision_cache:
            try:
                from finance_feedback_engine.backtesting.decision_cache import (
                    DecisionCache,
                )

                self.decision_cache = DecisionCache()
                logger.info("Decision cache enabled for backtesting")
            except Exception as e:
                logger.warning(f"Could not initialize decision cache: {e}")

        # Initialize portfolio memory engine
        self.memory_engine = None
        if enable_portfolio_memory:
            try:
                from finance_feedback_engine.memory.portfolio_memory import (
                    PortfolioMemoryEngine,
                )

                # Determine storage path based on isolation mode
                if memory_isolation_mode:
                    memory_config = self.config.copy()
                    memory_config["persistence"] = {
                        "storage_path": "data/memory_backtest"
                    }
                    logger.info("Using isolated portfolio memory for backtesting")
                else:
                    memory_config = self.config.copy()
                    if "persistence" not in memory_config:
                        memory_config["persistence"] = {"storage_path": "data"}
                    logger.info("Using shared portfolio memory (training mode)")

                self.memory_engine = PortfolioMemoryEngine(memory_config)
            except Exception as e:
                logger.warning(f"Could not initialize portfolio memory: {e}")

        # Fetch platform margin parameters
        self.platform_leverage = 1.0  # Default to no leverage
        self.maintenance_margin_pct = 0.5  # Default 50% maintenance margin

        if platform:
            try:
                account_info = platform.get_account_info()
                fetched_leverage = account_info.get("max_leverage", 1.0)
                self.platform_leverage = (
                    override_leverage if override_leverage else fetched_leverage
                )

                # Try to extract maintenance margin percentage from platform
                # Look for various possible field names
                maintenance_pct = (
                    account_info.get("maintenance_margin_percentage")
                    or account_info.get("maintenance_margin_rate")
                    or account_info.get("margin_closeout_percent")
                )

                if override_maintenance_margin:
                    self.maintenance_margin_pct = override_maintenance_margin
                elif maintenance_pct:
                    self.maintenance_margin_pct = float(maintenance_pct)

                logger.info(
                    f"Fetched platform margin parameters: leverage={self.platform_leverage}x, maintenance_margin={self.maintenance_margin_pct*100}%"
                )
            except Exception as e:
                logger.warning(
                    f"Could not fetch platform margin parameters: {e}. Using defaults."
                )
                if override_leverage:
                    self.platform_leverage = override_leverage
                if override_maintenance_margin:
                    self.maintenance_margin_pct = override_maintenance_margin
        else:
            if override_leverage:
                self.platform_leverage = override_leverage
            if override_maintenance_margin:
                self.maintenance_margin_pct = override_maintenance_margin

        # Initialize RiskGatekeeper if enabled
        self.risk_gatekeeper = None
        if enable_risk_gatekeeper:
            try:
                from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper

                self.risk_gatekeeper = RiskGatekeeper(is_backtest=True)
                logger.info("RiskGatekeeper initialized for backtest validation")
            except Exception as e:
                logger.warning(f"Could not initialize RiskGatekeeper: {e}")

        logger.info(
            f"Initialized Backtester with initial balance: ${initial_balance:.2f}, leverage: {self.platform_leverage}x, timeframe: {timeframe}"
        )

    def _execute_trade(
        self,
        current_balance: float,
        current_price: float,
        action: str,
        amount_to_trade: float,  # In base currency for BUY, quote for SELL
        direction: str,  # "BUY" or "SELL"
        trade_timestamp: datetime,  # Pass the timestamp from the candle
        candle_volume: float = 0.0,  # Candle volume for slippage calculation
        side: str = "LONG",  # "LONG" or "SHORT" - position side being opened/closed
        is_liquidation: bool = False,  # True if forced liquidation
        next_candle_open: Optional[float] = None,  # For latency simulation
        candle_duration_seconds: float = 86400.0,  # Duration of candle in seconds (default: 1 day)
    ) -> Tuple[
        float, float, float, Dict[str, Any]
    ]:  # new_balance, units, fee, trade_details
        """
        Simulates the execution of a single trade, applying fees, volume-based slippage, and latency.

        For SHORT positions: direction="SELL" opens a SHORT, direction="BUY" closes a SHORT
        For LONG positions: direction="BUY" opens a LONG, direction="SELL" closes a LONG
        """
        # Simulate order latency (0.2-2s range matching live trading)
        latency_seconds = np.random.lognormal(mean=np.log(0.5), sigma=0.6)

        # If latency pushes into next candle and we have next candle data, use its open price
        fill_price = current_price
        if next_candle_open is not None and latency_seconds > candle_duration_seconds:
            fill_price = next_candle_open
            logger.debug(
                f"Latency {latency_seconds:.2f}s pushed fill into next candle (duration: {candle_duration_seconds:.0f}s), using open price {fill_price:.2f}"
            )

        # Calculate volume-based dynamic slippage
        base_slippage = self.slippage_percentage
        volume_slippage = 0.0

        if candle_volume > 0:
            order_size_usd = (
                amount_to_trade
                if direction == "BUY"
                else (amount_to_trade * fill_price)
            )
            order_size_base = order_size_usd / fill_price
            volume_impact = (
                order_size_base / candle_volume
            ) * self.slippage_impact_factor
            volume_slippage = min(volume_impact, 0.05)  # Cap at 5% max slippage

        total_slippage = base_slippage + volume_slippage

        # Apply 3x slippage multiplier for forced liquidations
        if is_liquidation:
            total_slippage *= 3.0
            logger.warning(
                f"Forced liquidation - applying 3x slippage penalty: {total_slippage*100:.3f}%"
            )

        effective_price = fill_price
        if direction == "BUY":
            effective_price *= 1 + total_slippage
        elif direction == "SELL":
            effective_price *= 1 - total_slippage

        # Calculate units or amount based on action and available balance/units
        units_traded = 0.0
        trade_value = 0.0
        fee = 0.0

        if direction == "BUY":
            # BUY: Opens LONG or closes SHORT position
            # amount_to_trade is in quote currency (e.g., USD)
            trade_value = amount_to_trade
            if current_balance < trade_value:
                logger.warning(
                    f"Insufficient funds for BUY. Attempted: {trade_value:.2f}, Available: {current_balance:.2f}"
                )
                return (
                    current_balance,
                    0.0,
                    0.0,
                    {
                        "status": "REJECTED",
                        "reason": "Insufficient funds",
                        "side": side,
                    },
                )
            units_traded = trade_value / effective_price
            # For SHORT close, units are positive (buying back)
            if side == "SHORT":
                units_traded = abs(
                    units_traded
                )  # Positive units to close negative SHORT position
            fee = (trade_value * self.fee_percentage) + self.commission_per_trade
            new_balance = current_balance - trade_value - fee
        elif direction == "SELL":
            # SELL: Opens SHORT or closes LONG position
            # amount_to_trade is in base currency (e.g., BTC)
            trade_value = amount_to_trade * effective_price
            if side == "SHORT":
                # Opening SHORT position - units are negative
                units_traded = -amount_to_trade
            else:
                # Closing LONG position - units are negative (selling)
                units_traded = -amount_to_trade
            fee = (trade_value * self.fee_percentage) + self.commission_per_trade
            new_balance = current_balance + trade_value - fee
        else:
            return (
                current_balance,
                0.0,
                0.0,
                {"status": "REJECTED", "reason": "Invalid trade action", "side": side},
            )

        trade_details = {
            "timestamp": trade_timestamp.isoformat(),
            "action": direction,
            "side": side,  # Track whether this is LONG or SHORT position
            "entry_price": current_price,
            "effective_price": effective_price,
            "units_traded": units_traded,
            "trade_value": trade_value,
            "fee": fee,
            "slippage_pct": total_slippage * 100,
            "latency_seconds": latency_seconds,
            "is_liquidation": is_liquidation,
            "status": "EXECUTED",
            "pnl_value": 0.0,  # Placeholder, will be calculated when closing a position
        }

        logger.debug(f"Trade executed: {trade_details}")
        return new_balance, units_traded, fee, trade_details

    def _calculate_liquidation_price(
        self, position: Position, account_balance: float
    ) -> Optional[float]:
        """
        Calculate the price at which a position would be liquidated due to margin requirements.

        For LONG: liquidation when price drops enough that equity < maintenance margin
        For SHORT: liquidation when price rises enough that equity < maintenance margin

        Returns:
            float: Liquidation price, or None if leverage is 1x (no margin)
        """
        if self.platform_leverage <= 1.0:
            return None  # No liquidation risk with no leverage        # Calculate initial margin required for this position
        position_value = abs(position.units * position.entry_price)
        initial_margin = position_value / self.platform_leverage
        maintenance_margin = initial_margin * self.maintenance_margin_pct

        # Calculate liquidation price
        if position.side == "LONG":
            # LONG liquidation: price drops until (balance + unrealized_pnl) = maintenance_margin
            # unrealized_pnl = (price - entry_price) * units
            # balance + (liq_price - entry_price) * units = maintenance_margin
            # liq_price = (maintenance_margin - balance) / units + entry_price
            liquidation_price = position.entry_price - (
                (account_balance - maintenance_margin) / position.units
            )
        else:  # SHORT
            # SHORT liquidation: price rises until (balance + unrealized_pnl) = maintenance_margin
            # unrealized_pnl for SHORT = (entry_price - price) * abs(units)
            # balance + (entry_price - liq_price) * abs(units) = maintenance_margin
            # liq_price = entry_price - (maintenance_margin - balance) / abs(units)
            liquidation_price = position.entry_price + (
                (account_balance - maintenance_margin) / abs(position.units)
            )

        return liquidation_price

    def _check_margin_liquidation(
        self,
        position: Position,
        current_price: float,
        candle_high: float,
        candle_low: float,
    ) -> bool:
        """
        Check if position should be liquidated due to margin requirements.

        Uses intraday high/low to check if liquidation price was hit during the candle.

        Returns:
            bool: True if position should be liquidated
        """
        if not position.liquidation_price:
            return False

        if position.side == "LONG":
            # LONG liquidates if price drops to or below liquidation price
            if candle_low <= position.liquidation_price:
                logger.warning(
                    f"MARGIN LIQUIDATION triggered for LONG {position.asset_pair}: "
                    f"Low {candle_low:.2f} hit liquidation price {position.liquidation_price:.2f}"
                )
                return True
        else:  # SHORT
            # SHORT liquidates if price rises to or above liquidation price
            if candle_high >= position.liquidation_price:
                logger.warning(
                    f"MARGIN LIQUIDATION triggered for SHORT {position.asset_pair}: "
                    f"High {candle_high:.2f} hit liquidation price {position.liquidation_price:.2f}"
                )
                return True

        return False

    def _calculate_position_size(
        self,
        current_balance: float,
        current_price: float,
        stop_loss_price: Optional[float] = None,
        volatility: Optional[float] = None,
    ) -> float:
        """
        Calculate position size based on the selected position sizing strategy.

        Args:
            current_balance: Current account balance
            current_price: Current asset price
            stop_loss_price: Optional stop loss price for calculating risk
            volatility: Optional volatility for Kelly Criterion

        Returns:
            float: Position size in quote currency (USD)
        """
        if self.position_sizing_strategy == "fixed_fraction":
            # Risk a fixed percentage of balance per trade
            risk_amount = current_balance * self.risk_per_trade
            return risk_amount
        elif self.position_sizing_strategy == "kelly_criterion":
            # Enhanced Kelly Criterion based on win rate and payoff ratio
            # This uses historical performance data to calculate optimal position size
            try:
                from finance_feedback_engine.decision_engine.kelly_criterion import (
                    KellyCriterionCalculator,
                )

                # Create a temporary config for Kelly Criterion
                temp_config = {
                    "kelly_criterion": {
                        "kelly_fraction_cap": 0.25,
                        "kelly_fraction_multiplier": 0.5,
                        "min_kelly_fraction": 0.001,
                        "max_position_size_pct": 0.10,
                    }
                }

                kelly_calc = KellyCriterionCalculator(temp_config)

                # Use default parameters if no historical data available
                # In a real implementation, these would come from historical performance
                win_rate = 0.55  # Default 55% win rate
                avg_win = 100.0  # Default $100 average win
                avg_loss = 75.0  # Default $75 average loss

                # Adjust for volatility if available
                if volatility and volatility > 0:
                    # Adjust position size based on market volatility
                    vol_factor = max(
                        0.1, 1.0 - volatility
                    )  # Reduce position in high volatility
                    avg_win *= vol_factor
                    avg_loss *= (
                        2.0 - vol_factor
                    )  # Increase loss impact in high volatility

                position_size_units, details = kelly_calc.calculate_position_size(
                    account_balance=current_balance,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    current_price=current_price if current_price > 0 else 1.0,
                )

                # Convert to dollar amount
                position_dollars = (
                    position_size_units * current_price
                    if current_price > 0
                    else position_size_units
                )

                return position_dollars
            except ImportError:
                logger.warning(
                    "Kelly Criterion calculator not available, falling back to fixed fraction"
                )
                # Fallback to simplified Kelly Criterion
                if volatility and volatility > 0:
                    # Inverse relationship: lower position size with higher volatility
                    position_fraction = min(
                        0.1, 0.05 / volatility
                    )  # Cap at 10% of balance
                    return current_balance * position_fraction
                else:
                    # Default to fixed fraction if no volatility data
                    return current_balance * self.risk_per_trade
        elif self.position_sizing_strategy == "fixed_amount":
            # Fixed dollar amount per trade
            return min(
                current_balance * 0.1, 1000
            )  # 10% of balance or $1000, whichever is smaller
        else:  # Default to fixed fraction
            return current_balance * self.risk_per_trade

    def _calculate_performance_metrics(
        self,
        trades_history: List[Dict[str, Any]],
        equity_curve: List[float],
        initial_balance: float,
        num_trading_days: int,
        timeframe: str = "daily",  # Add timeframe parameter
    ) -> Dict[str, Any]:
        """
        Calculates comprehensive performance metrics from the backtest results.
        """
        metrics = {}

        # Convert equity curve to a pandas Series for easier calculations
        equity_series = pd.Series(equity_curve)

        # Total Return
        total_return = (equity_series.iloc[-1] - initial_balance) / initial_balance
        metrics["total_return_pct"] = total_return * 100

        # Annualized Return - adjust for actual frequency
        if num_trading_days > 0:
            # Define periods per year based on timeframe
            periods_per_year = {
                "1min": 365
                * 24
                * 60,  # 525,600 minutes per year (assuming 24/7 trading)
                "5min": 365 * 24 * 12,  # 105,120 periods per year
                "15min": 365 * 24 * 4,  # 35,040 periods per year
                "1h": 365 * 24,  # 8,760 hours per year
                "4h": 365 * 6,  # 2,190 4-hour periods per year
                "daily": 252,  # 252 trading days per year (traditional)
                "weekly": 52,  # 52 weeks per year
                "monthly": 12,  # 12 months per year
            }

            # Default to daily if timeframe is not recognized
            freq_periods_per_year = periods_per_year.get(timeframe.lower(), 252)

            # Calculate the time period in years based on actual data points and frequency
            years = len(equity_curve) / freq_periods_per_year

            if years > 0:
                metrics["annualized_return_pct"] = (
                    (1 + total_return) ** (1 / years) - 1
                ) * 100
            else:
                metrics["annualized_return_pct"] = 0.0
        else:
            metrics["annualized_return_pct"] = 0.0

        # Volatility (Annualized Standard Deviation of Daily Returns)
        returns = equity_series.pct_change().dropna()
        if not returns.empty:
            annualized_volatility = returns.std() * np.sqrt(252)  # Assuming daily data
            metrics["annualized_volatility"] = annualized_volatility

            # Sharpe Ratio: (Return - Risk-Free Rate) / Volatility
            if annualized_volatility > 0:
                excess_return = (
                    metrics["annualized_return_pct"] / 100
                ) - self.risk_free_rate
                metrics["sharpe_ratio"] = excess_return / annualized_volatility
            else:
                metrics["sharpe_ratio"] = 0.0
        else:
            metrics["annualized_volatility"] = 0.0
            metrics["sharpe_ratio"] = 0.0

        # Max Drawdown
        if not equity_series.empty:
            peak = equity_series.expanding(min_periods=1).max()
            drawdown = (equity_series - peak) / peak
            max_drawdown = drawdown.min()
            metrics["max_drawdown_pct"] = max_drawdown * 100
        else:
            metrics["max_drawdown_pct"] = 0.0

        # Win Rate and Trade Statistics
        # Only count trades that have a pnl_value (i.e., completed/closed trades)
        completed_trades = [t for t in trades_history if "pnl_value" in t]
        winning_trades = [t for t in completed_trades if t["pnl_value"] > 0]
        losing_trades = [t for t in completed_trades if t["pnl_value"] < 0]
        breakeven_trades = [t for t in completed_trades if t["pnl_value"] == 0]

        metrics["total_trades"] = len(completed_trades)  # Only completed trades
        metrics["winning_trades"] = len(winning_trades)
        metrics["losing_trades"] = len(losing_trades)
        metrics["breakeven_trades"] = len(breakeven_trades)
        metrics["win_rate"] = (
            (len(winning_trades) / len(completed_trades)) * 100
            if len(completed_trades) > 0
            else 0.0
        )

        # Average Win/Loss
        metrics["avg_win"] = (
            np.mean([t["pnl_value"] for t in winning_trades]) if winning_trades else 0.0
        )
        metrics["avg_loss"] = (
            np.mean([t["pnl_value"] for t in losing_trades]) if losing_trades else 0.0
        )

        return metrics

    def run_backtest(
        self,
        asset_pair: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        decision_engine: DecisionEngine,
    ) -> Dict[str, Any]:
        """
        Runs a backtest for a given asset, date range, and strategy using TradingLoopAgent.

        This method eliminates duplicate P&L calculation logic by leveraging the real
        TradingLoopAgent with mock platform and data provider.

        Uses the timeframe specified in __init__ (default: '1h') for realistic
        intraday market simulation.

        Args:
            asset_pair (str): The asset pair to backtest (e.g., "BTCUSD").
            start_date (Union[str, datetime]): The start date for the backtest.
            end_date (Union[str, datetime]): The end date for the backtest.
            decision_engine (DecisionEngine): The AI decision engine to use for generating signals.

        Returns:
            Dict[str, Any]: A dictionary containing backtest results, trades, and performance metrics.
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
            f"Starting backtest for {asset_pair} from {start_date} to {end_date} with timeframe={self.timeframe}..."
        )

        # 1. Fetch historical data with the configured timeframe
        data = self.historical_data_provider.get_historical_data(
            asset_pair, start_date, end_date, timeframe=self.timeframe
        )
        if data.empty:
            logger.error(f"No historical data available for backtest for {asset_pair}.")
            return {"metrics": {"net_return_pct": 0, "total_trades": 0}, "trades": []}

        total_candles = len(data)
        logger.info(f"Processing {total_candles} {self.timeframe} candles for backtest")

        # Standardize asset pair
        asset_pair_std = standardize_asset_pair(asset_pair)

        # 2. Setup: Instantiate mock components
        # Initialize MockTradingPlatform with initial balance
        initial_balance_dict = {"FUTURES_USD": self.initial_balance}
        mock_platform = MockTradingPlatform(
            initial_balance=initial_balance_dict,
            slippage_config={
                "type": "percentage",
                "rate": self.slippage_percentage,
                "spread": 0.0005,
            },
        )

        # Initialize MockLiveProvider with historical data
        mock_provider = MockLiveProvider(
            historical_data=data, asset_pair=asset_pair_std, start_index=0
        )

        # Initialize pulse mode for realistic multi-timeframe simulation
        # This simulates how the real agent receives market data:
        # - At 5-minute intervals (not per-candle)
        # - With multi-timeframe pulse (1m, 5m, 15m, 1h, 4h, 1d simultaneously)
        mock_provider.initialize_pulse_mode(base_timeframe=self.timeframe)

        # Create agent config for backtesting
        agent_config = TradingAgentConfig(
            asset_pairs=[asset_pair_std],
            autonomous_execution=True,
            max_daily_trades=999,  # No limit for backtesting
            min_confidence_threshold=0.0,  # Accept all signals
            analysis_frequency_seconds=0,  # Immediate execution
            max_drawdown_percent=(
                self.stop_loss_percentage
                if hasattr(self, "stop_loss_percentage")
                else 0.15
            ),
            correlation_threshold=0.7,
            max_correlated_assets=5,
            max_var_pct=0.1,
            var_confidence=0.95,
            position_sizing_strategy=self.position_sizing_strategy,
            risk_per_trade=self.risk_per_trade,
        )

        # Create TradeMonitor (needed by TradingLoopAgent)
        # Use memory engine if available
        trade_monitor = TradeMonitor(
            platform=mock_platform,
            portfolio_memory=self.memory_engine if self.memory_engine else None,
        )

        # Create FinanceFeedbackEngine wrapper to provide analyze_asset interface
        # We'll use the decision_engine directly but need to wrap it
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
                self._decisions = {}  # Store decisions by ID

            async def analyze_asset(self, asset_pair):
                """Generate a decision using the decision engine and current mock data."""
                # Get current market data from mock provider
                market_data = await self.mock_provider.get_comprehensive_market_data(
                    asset_pair=asset_pair, include_sentiment=True
                )

                # Get current balance from platform
                balance = self.mock_platform.get_balance()
                current_balance = balance.get(
                    "FUTURES_USD", self.backtester.initial_balance
                )

                # Get current price for position sizing
                current_price = None
                if market_data and "timeframes" in market_data:
                    # Determine timeframe from config or input with safe fallbacks
                    cfg = getattr(self, "config", None)
                    timeframe = None
                    if isinstance(cfg, dict):
                        timeframe = cfg.get("timeframe")
                    # If not set, fall back to a sensible default or first available key
                    if not timeframe:
                        tf_keys = list(market_data.get("timeframes", {}).keys())
                        timeframe = tf_keys[0] if tf_keys else None

                    # Use local timeframe variable for indexing; guard for None
                    if timeframe:
                        tf_data = market_data["timeframes"].get(timeframe)
                        if tf_data and tf_data.get("candles"):
                            current_price = tf_data["candles"][-1].get("close")

                # Calculate position size using position sizing strategy
                effective_price = (
                    current_price if current_price else market_data.get("current_price")
                )
                if not effective_price or effective_price <= 0:
                    logger.warning(
                        "No valid price data for position sizing, skipping position size calculation."
                    )
                    position_size = 0
                else:
                    position_size = self.backtester._calculate_position_size(
                        current_balance=current_balance, current_price=effective_price
                    )

                # Generate decision
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

                # Update decision with calculated position size if decision is valid
                if decision:
                    # Modify the decision with position sizing if it contains position info
                    if "position_size" not in decision:
                        decision["position_size"] = position_size
                    else:
                        # If there's already a position size, adjust it according to our strategy
                        decision["position_size"] = min(
                            decision["position_size"], position_size
                        )

                    # Store decision for later execution
                    if "id" in decision:
                        self._decisions[decision["id"]] = decision

                return decision

            def execute_decision(self, decision_id):
                """Execute a decision through the mock platform."""
                decision = self._decisions.get(decision_id)
                if not decision:
                    logger.error(f"Decision {decision_id} not found in backtest engine")
                    return {
                        "success": False,
                        "message": f"Decision {decision_id} not found",
                    }

                # Execute via mock platform
                try:
                    result = self.mock_platform.execute_trade(decision)
                    return result
                except Exception as e:
                    logger.error(f"Error executing decision {decision_id}: {e}")
                    return {"success": False, "message": str(e)}

            def record_trade_outcome(self, outcome):
                """Record trade outcome to memory."""
                if self.memory_engine:
                    try:
                        self.memory_engine.record_outcome(outcome)
                    except Exception as e:
                        logger.debug(f"Error recording outcome to memory: {e}")

        backtest_engine = BacktestEngine(
            self,
            decision_engine,
            mock_provider,
            mock_platform,
            asset_pair_std,
            self.memory_engine,
        )  # Instantiate TradingLoopAgent
        agent = TradingLoopAgent(
            config=agent_config,
            engine=backtest_engine,
            trade_monitor=trade_monitor,
            portfolio_memory=self.memory_engine if self.memory_engine else None,
            trading_platform=mock_platform,
        )
        agent.is_running = True  # Enable agent for processing

        # 3. Execution Loop: Iterate through historical data at 5-minute pulse intervals
        logger.info(
            f"Running agent through {total_candles} historical candles (pulse-based 5min intervals)..."
        )

        async def run_backtest_loop():
            """Async function to run the backtest loop using 5-minute pulses."""
            pulse_count = 0
            while mock_provider.advance_pulse():
                pulse_count += 1

                # Get multi-timeframe pulse data matching real agent behavior
                try:
                    await mock_provider.get_pulse_data()
                    logger.debug(
                        f"Pulse {pulse_count}: candles processed {mock_provider.current_index}/{total_candles}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Error getting pulse data at pulse {pulse_count}: {e}"
                    )
                    break

                # Process one cycle of the agent
                # The agent now receives multi-timeframe pulse like in real-time
                cycle_result = await agent.process_cycle()

                if not cycle_result:
                    logger.debug(
                        f"Agent cycle paused at pulse {pulse_count}, continuing..."
                    )
                    # Don't break on cycle pause - agent may just be waiting

                if pulse_count % 100 == 0:
                    logger.info(
                        f"Pulse {pulse_count}: candle index {mock_provider.current_index}/{total_candles}"
                    )

        # Run the async loop
        asyncio.run(run_backtest_loop())

        # 4. Reporting: Calculate performance from mock_platform balance history
        logger.info("Backtest loop complete. Calculating performance metrics...")

        # Get final balance and trade history from mock platform
        final_balance_dict = mock_platform.get_balance()
        final_balance = final_balance_dict.get("FUTURES_USD", self.initial_balance)
        trades_history = mock_platform.get_trade_history()

        # Build equity curve from balance snapshots
        # Since MockPlatform doesn't track balance history by default, we'll
        # reconstruct it from trade history
        equity_curve = [self.initial_balance]
        running_balance = self.initial_balance

        for trade in trades_history:
            if trade.get("success", False):
                # Update running balance based on trade P&L
                pnl = trade.get("pnl_value", 0) or trade.get("realized_pnl", 0) or 0
                fee = trade.get("fee_amount", 0)
                running_balance += pnl - fee
                equity_curve.append(running_balance)

        # Ensure we have at least initial balance
        if len(equity_curve) == 1:
            equity_curve.append(final_balance)

        # Calculate basic performance metrics
        num_trading_days = len(data) if not data.empty else 0
        calculated_metrics = self._calculate_performance_metrics(
            trades_history,
            equity_curve,
            self.initial_balance,
            num_trading_days,
            self.timeframe,
        )

        # Calculate enhanced risk metrics using the new risk analyzer
        risk_analyzer = EnhancedRiskAnalyzer(risk_free_rate=self.risk_free_rate)
        enhanced_risk_metrics = risk_analyzer.calculate_advanced_metrics(
            equity_curve, trades_history
        )

        # Calculate total fees from trades
        total_fees = sum(
            trade.get("fee", 0)
            for trade in trades_history
            if trade.get("success", False)
        )

        # Combine basic and enhanced metrics
        metrics = {
            "initial_balance": self.initial_balance,
            "final_value": final_balance,
            "total_fees": total_fees,
            **calculated_metrics,
            **enhanced_risk_metrics,
        }

        # Validate the backtest results
        validator = BacktestValidator()
        validation_result = validator.validate_backtest_results(
            {
                "metrics": metrics,
                "trades": trades_history,
                "backtest_config": {"equity_curve": equity_curve},
            },
            start_date.isoformat() if isinstance(start_date, datetime) else start_date,
            end_date.isoformat() if isinstance(end_date, datetime) else end_date,
        )

        validation_report = validator.generate_validation_report(validation_result)

        # Generate performance analysis
        analyzer = BacktestPerformanceAnalyzer()
        performance_analysis = analyzer.analyze_strategy_performance(
            {
                "metrics": metrics,
                "trades": trades_history,
                "backtest_config": {"equity_curve": equity_curve},
            }
        )

        performance_report = analyzer.generate_performance_report(
            {
                "metrics": metrics,
                "trades": trades_history,
                "backtest_config": {"equity_curve": equity_curve},
            }
        )

        # Add agent-specific metrics for comparison with live trading
        agent_compatible_metrics = self._calculate_agent_compatible_metrics(
            trades_history, equity_curve
        )

        logger.info(
            f"Backtest completed for {asset_pair}. "
            f"Final value: ${final_balance:.2f}, "
            f"Net Return: {metrics.get('total_return_pct', 0.0):.2f}%"
        )

        return {
            "metrics": metrics,
            "trades": trades_history,
            "validation": {
                "result": {
                    "is_valid": validation_result.is_valid,
                    "score": validation_result.score,
                    "issues": validation_result.issues,
                    "recommendations": validation_result.recommendations,
                },
                "report": validation_report,
                "metrics": validation_result.metrics,
            },
            "performance_analysis": {
                "analysis": performance_analysis,
                "report": performance_report,
            },
            "agent_compatible_metrics": agent_compatible_metrics,
            "backtest_config": {
                "asset_pair": asset_pair,
                "start_date": (
                    start_date.isoformat()
                    if isinstance(start_date, datetime)
                    else start_date
                ),
                "end_date": (
                    end_date.isoformat() if isinstance(end_date, datetime) else end_date
                ),
                "timeframe": self.timeframe,
                "initial_balance": self.initial_balance,
                "fee_percentage": self.fee_percentage,
                "slippage_percentage": self.slippage_percentage,
                "stop_loss_percentage": self.stop_loss_percentage,
                "take_profit_percentage": self.take_profit_percentage,
                "total_candles": total_candles,
                "equity_curve": equity_curve,
            },
        }

    def _calculate_agent_compatible_metrics(
        self, trades_history: List[Dict[str, Any]], equity_curve: List[float]
    ) -> Dict[str, Any]:
        """
        Calculate metrics compatible with the agent's performance tracking system.

        Args:
            trades_history: List of completed trades
            equity_curve: Equity curve values over time

        Returns:
            Dictionary with agent-compatible metrics
        """
        # Initialize metrics similar to TradingLoopAgent's _performance_metrics
        compatible_metrics = {
            "total_pnl": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "current_streak": 0,
            "best_streak": 0,
            "worst_streak": 0,
            "max_drawdown": 0.0,
            "final_equity": equity_curve[-1] if equity_curve else 0.0,
            "initial_equity": equity_curve[0] if equity_curve else 0.0,
        }

        if not trades_history:
            return compatible_metrics

        # Calculate basic trade statistics
        realized_pnls = []
        wins = []
        losses = []
        current_streak = 0
        best_streak = 0
        worst_streak = 0

        for trade in trades_history:
            if trade.get("pnl_value") is not None:
                pnl = trade["pnl_value"]
                realized_pnls.append(pnl)

                if pnl > 0:
                    wins.append(pnl)
                    compatible_metrics["winning_trades"] += 1

                    # Update streaks
                    current_streak = max(1, current_streak + 1)
                    best_streak = max(best_streak, current_streak)
                elif pnl < 0:
                    losses.append(abs(pnl))
                    compatible_metrics["losing_trades"] += 1

                    # Update streaks
                    current_streak = min(-1, current_streak - 1)
                    worst_streak = min(worst_streak, current_streak)
                else:
                    # Breakeven trade, reset streak but keep current sign
                    if current_streak > 0:
                        current_streak = max(0, current_streak - 1)
                    else:
                        current_streak = min(0, current_streak + 1)

        # Update metrics
        compatible_metrics["total_trades"] = len(realized_pnls)
        compatible_metrics["total_pnl"] = sum(realized_pnls)
        compatible_metrics["current_streak"] = current_streak
        compatible_metrics["best_streak"] = best_streak
        compatible_metrics["worst_streak"] = worst_streak

        if compatible_metrics["total_trades"] > 0:
            compatible_metrics["win_rate"] = (
                compatible_metrics["winning_trades"]
                / compatible_metrics["total_trades"]
            ) * 100

        if wins:
            compatible_metrics["avg_win"] = sum(wins) / len(wins)

        if losses:
            compatible_metrics["avg_loss"] = sum(losses) / len(losses)

        # Calculate max drawdown from equity curve
        if len(equity_curve) > 1:
            equity_series = pd.Series(equity_curve)
            peak = equity_series.expanding(min_periods=1).max()
            drawdown = (equity_series - peak) / peak
            compatible_metrics["max_drawdown"] = float(drawdown.min() * 100)

        return compatible_metrics

    def save_results(self, results: Dict[str, Any], output_file: str):
        """
        Saves the trade history from a backtest to a JSON file.

        Args:
            results (Dict[str, Any]): The results dictionary from a backtest run.
            output_file (str): The path to the output JSON file.
        """
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results["trades"], f, indent=2)
            logger.info(f"Backtest trade history saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving backtest results to {output_file}: {e}")

    async def run_agent_compatible_backtest(
        self,
        asset_pair: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        decision_engine: DecisionEngine,
        agent_config=None,
    ) -> Dict[str, Any]:
        """
        Run a backtest in a way that's compatible with the TradingLoopAgent's state system.

        This method allows backtesting to be run in a similar way to the live agent,
        using similar decision-making and risk management logic.

        Args:
            asset_pair: Asset to backtest
            start_date: Start date for backtest
            end_date: End date for backtest
            decision_engine: Decision engine to use for generating signals
            agent_config: Agent configuration to apply

        Returns:
            Dictionary with detailed backtest results
        """
        logger.info(f"Running agent-compatible backtest for {asset_pair}")

        # Run the standard backtest
        results = self.run_backtest(asset_pair, start_date, end_date, decision_engine)

        # If agent config is provided, we can apply additional agent-specific validations
        if agent_config:
            # Apply agent-style risk validations to the backtest results
            results = self._apply_agent_risk_validations(results, agent_config)

        return results

    def _apply_agent_risk_validations(
        self, backtest_results: Dict[str, Any], agent_config
    ) -> Dict[str, Any]:
        """
        Apply agent-style risk validations to backtest results.

        Args:
            backtest_results: Standard backtest results
            agent_config: Agent configuration for validation parameters

        Returns:
            Updated backtest results with agent-style risk checks
        """
        # Add agent-compatible metrics if not already present
        if "agent_compatible_metrics" not in backtest_results:
            trades = backtest_results.get("trades", [])
            equity_curve = backtest_results.get("backtest_config", {}).get(
                "equity_curve", []
            )
            backtest_results["agent_compatible_metrics"] = (
                self._calculate_agent_compatible_metrics(trades, equity_curve)
            )

        # Calculate whether the backtest would have triggered any agent-style kill switches
        agent_metrics = backtest_results["agent_compatible_metrics"]
        kill_switch_triggers = []

        # Check for consecutive losses (similar to agent's kill switch)
        if agent_metrics["current_streak"] < -5:  # 6+ consecutive losses
            kill_switch_triggers.append(
                {
                    "type": "consecutive_losses",
                    "value": abs(agent_metrics["current_streak"]),
                    "threshold": 5,
                    "description": f"Would have triggered agent kill switch due to {abs(agent_metrics['current_streak'])} consecutive losses",
                }
            )

        # Check for low win rate (similar to agent's kill switch)
        if agent_metrics["total_trades"] >= 20 and agent_metrics["win_rate"] < 25:
            kill_switch_triggers.append(
                {
                    "type": "low_win_rate",
                    "value": agent_metrics["win_rate"],
                    "threshold": 25,
                    "description": f"Would have triggered agent kill switch due to low win rate ({agent_metrics['win_rate']:.1f}%)",
                }
            )

        # Add the kill switch triggers to the results
        backtest_results["agent_risk_analysis"] = {
            "kill_switch_triggers": kill_switch_triggers,
            "agent_compatible_metrics": agent_metrics,
        }

        # Add an assessment of how the strategy would perform with agent-style risk controls
        if kill_switch_triggers:
            backtest_results["agent_strategy_assessment"] = (
                "Strategy would trigger agent kill switches, consider improvements"
            )
        else:
            backtest_results["agent_strategy_assessment"] = (
                "Strategy passes agent-style risk checks"
            )

        return backtest_results
