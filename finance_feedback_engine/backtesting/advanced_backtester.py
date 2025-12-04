import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, List, Callable, Optional, Union, Tuple
import logging
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone # Added datetime import
from tqdm import tqdm

from finance_feedback_engine.utils.market_regime_detector import MarketRegimeDetector

from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider

logger = logging.getLogger(__name__)

@dataclass
class Position:
    asset_pair: str
    units: float
    entry_price: float
    entry_timestamp: datetime
    side: str = "LONG" # For now, only support LONG positions
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

class AdvancedBacktester:
    """
    An advanced backtesting engine for simulating trading strategies with enhanced features.

    This class provides a robust environment to evaluate the performance of trading
    strategies and AI models against historical market data, incorporating realistic
    trading conditions, various performance metrics, and scenario analysis capabilities.

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

    def __init__(self,
                 historical_data_provider: HistoricalDataProvider,
                 initial_balance: float = 10000.0,
                 fee_percentage: float = 0.001, # 0.1% fee
                 slippage_percentage: float = 0.0001, # 0.01% slippage
                 commission_per_trade: float = 0.0, # Fixed commission
                 stop_loss_percentage: float = 0.02, # 2% stop loss
                 take_profit_percentage: float = 0.05, # 5% take profit
                 unified_data_provider=None,  # For multi-timeframe pulse
                 timeframe_aggregator=None    # For technical indicators
                 ):
        self.historical_data_provider = historical_data_provider
        self.initial_balance = initial_balance
        self.fee_percentage = fee_percentage
        self.slippage_percentage = slippage_percentage
        self.commission_per_trade = commission_per_trade
        self.stop_loss_percentage = stop_loss_percentage
        self.take_profit_percentage = take_profit_percentage
        self.unified_data_provider = unified_data_provider
        self.timeframe_aggregator = timeframe_aggregator
        logger.info(f"Initialized AdvancedBacktester with initial balance: ${initial_balance:.2f}")

    def _execute_trade(self,
                       current_balance: float,
                       current_price: float,
                       action: str,
                       amount_to_trade: float, # In base currency for BUY, quote for SELL
                       direction: str, # "BUY" or "SELL"
                       trade_timestamp: datetime # Pass the timestamp from the candle
                       ) -> Tuple[float, float, float, Dict[str, Any]]: # new_balance, units, fee, trade_details
        """
        Simulates the execution of a single trade, applying fees and slippage.
        """
        # TODO: Implement more complex slippage modeling
        effective_price = current_price
        if direction == "BUY":
            effective_price *= (1 + self.slippage_percentage)
        elif direction == "SELL":
            effective_price *= (1 - self.slippage_percentage)

        # Calculate units or amount based on action and available balance/units
        units_traded = 0.0
        trade_value = 0.0
        fee = 0.0

        if direction == "BUY":
            # amount_to_trade is in quote currency (e.g., USD)
            trade_value = amount_to_trade
            if current_balance < trade_value:
                logger.warning(f"Insufficient funds for BUY. Attempted: {trade_value:.2f}, Available: {current_balance:.2f}")
                return current_balance, 0.0, 0.0, {"status": "REJECTED", "reason": "Insufficient funds"}
            units_traded = trade_value / effective_price
            fee = (trade_value * self.fee_percentage) + self.commission_per_trade
            new_balance = current_balance - trade_value - fee
        elif direction == "SELL":
            # amount_to_trade is in base currency (e.g., BTC)
            trade_value = amount_to_trade * effective_price
            # TODO: Need to track asset units. For simplicity, assume we always have enough to sell.
            # In a full backtester, you'd manage a portfolio of assets.
            units_traded = -amount_to_trade # Negative for sell
            fee = (trade_value * self.fee_percentage) + self.commission_per_trade
            new_balance = current_balance + trade_value - fee
        else:
            return current_balance, 0.0, 0.0, {"status": "REJECTED", "reason": "Invalid trade action"}

        trade_details = {
            "timestamp": trade_timestamp.isoformat(), # Use the passed timestamp
            "action": direction,
            "entry_price": current_price,
            "effective_price": effective_price,
            "units_traded": units_traded,
            "trade_value": trade_value,
            "fee": fee,
            "status": "EXECUTED",
            "pnl_value": 0.0 # Placeholder, will be calculated when closing a position
        }

        logger.debug(f"Trade executed: {trade_details}")
        return new_balance, units_traded, fee, trade_details

    def _calculate_performance_metrics(self,
                                       trades_history: List[Dict[str, Any]],
                                       equity_curve: List[float],
                                       initial_balance: float,
                                       num_trading_days: int) -> Dict[str, Any]:
        """
        Calculates comprehensive performance metrics from the backtest results.
        """
        metrics = {}

        # Convert equity curve to a pandas Series for easier calculations
        equity_series = pd.Series(equity_curve)

        # Total Return
        total_return = (equity_series.iloc[-1] - initial_balance) / initial_balance
        metrics["total_return_pct"] = total_return * 100

        # Annualized Return (assuming daily data)
        # TODO: Adjust this for actual frequency if not daily
        if num_trading_days > 0:
            years = num_trading_days / 252 # Approx. trading days in a year
            if years > 0:
                metrics["annualized_return_pct"] = ((1 + total_return)**(1/years) - 1) * 100
            else:
                metrics["annualized_return_pct"] = 0.0
        else:
            metrics["annualized_return_pct"] = 0.0


        # Volatility (Annualized Standard Deviation of Daily Returns)
        returns = equity_series.pct_change().dropna()
        if not returns.empty:
            annualized_volatility = returns.std() * np.sqrt(252) # Assuming daily data
            metrics["annualized_volatility"] = annualized_volatility

            # Sharpe Ratio (assuming risk-free rate is 0 for simplicity)
            # TODO: Allow configuration of risk-free rate
            if annualized_volatility > 0:
                metrics["sharpe_ratio"] = (metrics["annualized_return_pct"] / 100) / annualized_volatility
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
        winning_trades = [t for t in trades_history if t.get("pnl_value", 0) > 0]
        losing_trades = [t for t in trades_history if t.get("pnl_value", 0) < 0]

        metrics["total_trades"] = len(trades_history)
        metrics["winning_trades"] = len(winning_trades)
        metrics["losing_trades"] = len(losing_trades)
        metrics["win_rate"] = (len(winning_trades) / len(trades_history)) * 100 if len(trades_history) > 0 else 0.0

        # Average Win/Loss
        metrics["avg_win"] = np.mean([t["pnl_value"] for t in winning_trades]) if winning_trades else 0.0
        metrics["avg_loss"] = np.mean([t["pnl_value"] for t in losing_trades]) if losing_trades else 0.0

        return metrics

    def _compute_historical_pulse(
        self,
        asset_pair: str,
        current_timestamp: datetime,
        historical_data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Compute multi-timeframe pulse at a specific historical timestamp.

        Uses historical data up to (but not including) current_timestamp to
        calculate technical indicators across multiple timeframes, simulating
        what would have been known at that point in time.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD')
            current_timestamp: The timestamp for which to compute the pulse
            historical_data: Full historical DataFrame with OHLCV data

        Returns:
            Pulse dict with timeframes and indicators, or None if cannot compute
        """
        if not self.unified_data_provider or not self.timeframe_aggregator:
            return None

        try:
            # Get historical data up to current_timestamp (lookback window)
            # We need enough data to compute indicators (at least 50 candles for daily)
            lookback_data = historical_data[historical_data.index < current_timestamp]

            if len(lookback_data) < 50:  # Minimum data for indicators
                return None

            # Convert DataFrame to list of candle dicts for aggregator
            timeframes_data = {}

            # For each timeframe, aggregate historical data
            timeframe_configs = [
                ('1m', 1),
                ('5m', 5),
                ('15m', 15),
                ('1h', 60),
                ('4h', 240),
                ('daily', 1440)
            ]

            for tf_name, minutes in timeframe_configs:
                # Resample to target timeframe
                if minutes == 1:
                    # Already 1-minute data (assuming base data is 1m)
                    tf_data = lookback_data.tail(100)  # Last 100 candles
                else:
                    # Resample to larger timeframe
                    resampled = lookback_data.resample(f'{minutes}min').agg({
                        'open': 'first',
                        'high': 'max',
                        'low': 'min',
                        'close': 'last',
                        'volume': 'sum'
                    }).dropna()
                    tf_data = resampled.tail(100)

                if len(tf_data) < 30:  # Need minimum data for indicators
                    continue

                # Convert to candle list
                candles = []
                for idx, row in tf_data.iterrows():
                    candles.append({
                        'timestamp': idx.isoformat(),
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'volume': row.get('volume', 0)
                    })

                # Compute trend and indicators
                trend_data = self.timeframe_aggregator._detect_trend(
                    candles,
                    period=14
                )

                timeframes_data[tf_name] = trend_data

            if not timeframes_data:
                return None

            # Return pulse structure
            return {
                'timestamp': current_timestamp.timestamp(),
                'age_seconds': 0,  # Fresh computation
                'timeframes': timeframes_data
            }

        except Exception as e:
            logger.debug(f"Failed to compute historical pulse at {current_timestamp}: {e}")
            return None


    def run_backtest(self,
                     asset_pair: str,
                     start_date: Union[str, datetime],
                     end_date: Union[str, datetime],
                     decision_engine: DecisionEngine,
                     inject_pulse: bool = True  # Enable multi-timeframe pulse by default
                     ) -> Dict[str, Any]:
        """
        Runs a backtest for a given asset, date range, and strategy.

        Args:
            asset_pair (str): The asset pair to backtest (e.g., "BTCUSD").
            start_date (Union[str, datetime]): The start date for the backtest.
            end_date (Union[str, datetime]): The end date for the backtest.
            decision_engine (DecisionEngine): The AI decision engine to use for generating signals.
            inject_pulse (bool): Whether to inject multi-timeframe pulse data into decisions.
                                 Requires unified_data_provider and timeframe_aggregator.
                                 Default True for enhanced decision quality.

        Returns:
            Dict[str, Any]: A dictionary containing backtest results, trades, and performance metrics.

        TODO:
        - Implement comprehensive portfolio management (tracking multiple assets,
          managing long/short positions).
        - Detailed P&L calculation, including unrealized P&L for open positions.
        - Add support for Stop Loss and Take Profit levels.
        - Support for different backtest modes (e.g., vectorization vs. event-driven).
        """
        logger.info(
            f"Starting backtest for {asset_pair} from {start_date} to {end_date} "
            f"(pulse injection: {inject_pulse})..."
        )

        # 1. Fetch historical data
        data = self.historical_data_provider.get_historical_data(asset_pair, start_date, end_date)
        if data.empty:
            logger.error(f"No historical data available for backtest for {asset_pair}.")
            return {"metrics": {"net_return_pct": 0, "total_trades": 0}, "trades": []}

        # 2. Initialize portfolio
        current_balance = self.initial_balance
        open_positions: Dict[str, Position] = {} # For the base asset (e.g., BTC units)
        total_fees = 0.0
        trades_history: List[Dict[str, Any]] = []
        equity_curve: List[float] = [self.initial_balance] # Track portfolio value over time

        # 3. Iterate through data and execute strategy
        total_candles = len(data)
        logger.info(f"Processing {total_candles} candles for backtest")

        for idx, (timestamp, candle) in enumerate(tqdm(
            data.iterrows(),
            total=total_candles,
            desc=f"Backtesting {asset_pair}",
            unit="candle",
            ncols=100
        )):
            market_data = candle.to_dict()
            market_data['timestamp'] = timestamp.isoformat() # Add timestamp to market_data for decision engine

            # Build historical context window (last 50 candles for technical indicators)
            window_size = 50
            if idx >= window_size:
                historical_window = data.iloc[idx - window_size:idx]
                market_data['historical_data'] = historical_window.to_dict('records')
            else:
                # Not enough history yet - provide what we have
                market_data['historical_data'] = data.iloc[:idx].to_dict('records') if idx > 0 else []

            # Calculate market regime data (ADX, ATR) from historical window
            if idx == 0:
                regime_detector = MarketRegimeDetector()
            if idx >= 20:  # Need at least 14-20 candles for ADX
                try:
                    recent_data = data.iloc[max(0, idx - 50):idx + 1]
                    regime_info = regime_detector.detect_regime(recent_data)
                    market_data['market_regime_data'] = regime_info
                    market_data['market_regime'] = regime_info.get('regime', 'UNKNOWN')
                except Exception as e:
                    logger.debug(f"Could not compute market regime at {timestamp}: {e}")
                    market_data['market_regime_data'] = {}
                    market_data['market_regime'] = 'UNKNOWN'
            else:
                market_data['market_regime_data'] = {}
                market_data['market_regime'] = 'UNKNOWN'

            # Extract base and quote currencies (assuming 3-char codes)
            # This logic should be more robust, potentially using a currency parsing utility
            base_currency = asset_pair[:3] if len(asset_pair) >= 6 else asset_pair
            quote_currency = asset_pair[3:] if len(asset_pair) >= 6 else 'USD' # Default to USD if not found

            # Prepare portfolio state for decision engine
            portfolio_for_decision_engine = []
            for pos in open_positions.values():
                portfolio_for_decision_engine.append({
                    'asset_pair': pos.asset_pair,
                    'units': pos.units,
                    'entry_price': pos.entry_price,
                    'side': pos.side,
                    'current_price': candle['close'] # Pass current price for P&L calculation
                })

            # --- Inject multi-timeframe pulse (if enabled) ---
            pulse_context = None
            if inject_pulse:
                pulse_context = self._compute_historical_pulse(
                    asset_pair,
                    timestamp,
                    data
                )
                if pulse_context:
                    logger.debug(
                        f"Injected historical pulse at {timestamp}: "
                        f"{len(pulse_context.get('timeframes', {}))} timeframes"
                    )

            decision = decision_engine.generate_decision(
                asset_pair=asset_pair,
                market_data=market_data,
                balance={quote_currency: current_balance},
                portfolio={'holdings': portfolio_for_decision_engine},
            )

            action = decision.get('action', 'HOLD')
            amount_to_trade = decision.get('suggested_amount', 0.0) # Using 'suggested_amount' from DecisionEngine

            # Handle existing open position for the asset pair
            current_position = open_positions.get(asset_pair)

            # Check for Stop Loss or Take Profit hit for the current position
            if current_position:
                # Assuming LONG position
                if current_position.stop_loss_price and candle['close'] <= current_position.stop_loss_price:
                    logger.info(f"Stop Loss hit for {asset_pair} at {timestamp}. Closing position.")
                    action = 'SELL'
                elif current_position.take_profit_price and candle['close'] >= current_position.take_profit_price:
                    logger.info(f"Take Profit hit for {asset_pair} at {timestamp}. Closing position.")
                    action = 'SELL'

            if action == 'BUY' and amount_to_trade > 0:
                if current_balance > 0:
                    # Calculate how much of the quote currency to spend, accounting for fees
                    # The total cost (trade_value + fee) must not exceed current_balance
                    # Also consider slippage in effective price for units calculation
                    effective_buy_price = candle['close'] * (1 + self.slippage_percentage)

                    # Maximum amount of quote currency we can spend including fee
                    max_spendable_total = current_balance
                    # If commission_per_trade is fixed, deduct it first
                    if self.commission_per_trade > 0:
                        max_spendable_total -= self.commission_per_trade

                    # Max principal we can trade given remaining balance and percentage fee
                    max_principal_spendable = max_spendable_total / (1 + self.fee_percentage)

                    trade_amount_quote = min(amount_to_trade, max_principal_spendable)

                    if trade_amount_quote <= 0:
                        logger.info(f"Skipping BUY for {asset_pair} due to insufficient effective balance to cover principal and fees at {timestamp}")
                        continue # Skip this iteration

                    # Execute trade
                    new_balance, units_traded, fee, trade_details = self._execute_trade(
                        current_balance, candle['close'], "BUY", trade_amount_quote, "BUY", timestamp
                    )

                    if trade_details['status'] == 'EXECUTED':
                        current_balance = new_balance
                        total_fees += fee
                        trades_history.append(trade_details)

                        if current_position:
                            # Averaging down/up
                            total_cost = (current_position.units * current_position.entry_price) + (units_traded * trade_details['effective_price'])
                            total_units = current_position.units + units_traded
                            current_position.entry_price = total_cost / total_units
                            current_position.units = total_units
                            logger.info(f"Position for {asset_pair} averaged. New units: {current_position.units:.4f}, Avg Entry: {current_position.entry_price:.4f}")
                        else:
                            # Open a new position
                            open_positions[asset_pair] = Position(
                                asset_pair=asset_pair,
                                units=units_traded,
                                entry_price=trade_details['effective_price'],
                                entry_timestamp=timestamp,
                                side="LONG",
                                stop_loss_price=trade_details['effective_price'] * (1 - self.stop_loss_percentage),
                                take_profit_price=trade_details['effective_price'] * (1 + self.take_profit_percentage)
                            )
                            logger.info(f"Opened new LONG position for {asset_pair}: {units_traded:.4f} units at {trade_details['effective_price']:.4f}, SL: {open_positions[asset_pair].stop_loss_price:.4f}, TP: {open_positions[asset_pair].take_profit_price:.4f}")
                else:
                    logger.info(f"Skipping BUY for {asset_pair} due to insufficient balance at {timestamp}")

            elif action == 'SELL' and current_position and current_position.units > 0:
                # Sell all units of the current position
                sell_units = current_position.units

                # Execute trade
                new_balance, units_traded_neg, fee, trade_details = self._execute_trade(
                    current_balance, candle['close'], "SELL", sell_units, "SELL", timestamp
                )

                if trade_details['status'] == 'EXECUTED':
                    current_balance = new_balance
                    total_fees += fee

                    # Calculate PnL for the closed position
                    pnl = (trade_details['effective_price'] - current_position.entry_price) * sell_units
                    trade_details['pnl_value'] = pnl
                    trade_details['entry_price'] = current_position.entry_price # Add entry price to trade details

                    trades_history.append(trade_details)

                    # Close the position
                    del open_positions[asset_pair]
                    logger.info(f"Closed LONG position for {asset_pair}: {sell_units:.4f} units at {trade_details['effective_price']:.4f}. PnL: {pnl:.2f}")
            elif action == 'HOLD':
                logger.debug(f"Holding for {asset_pair} at {timestamp}. Current balance: {current_balance:.2f}, units: {current_position.units if current_position else 0:.4f}")

            # Update equity curve at the end of each iteration
            current_portfolio_value = current_balance
            if current_position: # Check if there's an open position for the current asset
                current_portfolio_value += current_position.units * candle['close']
            equity_curve.append(current_portfolio_value)

        # 4. Final P&L calculation (if any open positions)
        final_value = current_balance
        if open_positions:
            for pos in open_positions.values():
                if pos.asset_pair == asset_pair: # Only consider the asset being backtested
                    # Liquidate remaining position at the last close price
                    trade_value = pos.units * data['close'].iloc[-1]
                    fee = (trade_value * self.fee_percentage) + self.commission_per_trade
                    final_value += trade_value - fee
                    total_fees += fee
                    # Add this final liquidation as a trade
                    final_liquidation_trade = {
                        "timestamp": data.index[-1].isoformat(),
                        "action": "SELL (Liquidation)",
                        "entry_price": pos.entry_price,
                        "effective_price": data['close'].iloc[-1],
                        "units_traded": -pos.units,
                        "trade_value": trade_value,
                        "fee": fee,
                        "status": "EXECUTED (Liquidation)",
                        "pnl_value": (data['close'].iloc[-1] - pos.entry_price) * pos.units # Calculate PnL for liquidation
                    }
                    trades_history.append(final_liquidation_trade)
                    logger.info(f"Liquidating remaining position for {pos.asset_pair}: {pos.units:.4f} units at final price {data['close'].iloc[-1]:.4f}. PnL: {final_liquidation_trade['pnl_value']:.2f}")

        # Ensure equity_curve has a final value if the backtest data was processed
        if not equity_curve:
            equity_curve.append(self.initial_balance) # Start with initial balance if no data was processed

        # 5. Calculate performance metrics
        num_trading_days = len(data) if not data.empty else 0
        calculated_metrics = self._calculate_performance_metrics(trades_history, equity_curve, self.initial_balance, num_trading_days)

        # Merge calculated metrics with basic metrics
        metrics = {
            "initial_balance": self.initial_balance,
            "final_value": final_value,
            "total_fees": total_fees,
            **calculated_metrics # Unpack calculated metrics
        }

        logger.info(f"Backtest completed for {asset_pair}. Final value: ${final_value:.2f}, Net Return: {metrics.get('total_return_pct', 0.0):.2f}%")

        return {
            "metrics": metrics,
            "trades": trades_history,
            "backtest_config": {
                "asset_pair": asset_pair,
                "start_date": start_date.isoformat() if isinstance(start_date, datetime) else start_date,
                "end_date": end_date.isoformat() if isinstance(end_date, datetime) else end_date,
                "initial_balance": self.initial_balance,
                "fee_percentage": self.fee_percentage,
                "slippage_percentage": self.slippage_percentage,
                "stop_loss_percentage": self.stop_loss_percentage,
                "take_profit_percentage": self.take_profit_percentage,
                "equity_curve": equity_curve # Add equity curve to config for full context
            }
        }
