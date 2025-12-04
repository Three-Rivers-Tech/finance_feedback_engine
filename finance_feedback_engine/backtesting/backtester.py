import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, List, Callable, Optional, Union, Tuple
import logging
import numpy as np
from dataclasses import dataclass
import json

from tqdm import tqdm

from finance_feedback_engine.utils.market_regime_detector import MarketRegimeDetector

from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider

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

    def __init__(self,
                 historical_data_provider: HistoricalDataProvider,
                 platform: Optional[Any] = None,  # Trading platform for margin/leverage fetching
                 initial_balance: float = 10000.0,
                 fee_percentage: float = 0.001, # 0.1% fee
                 slippage_percentage: float = 0.0001, # 0.01% base slippage
                 slippage_impact_factor: float = 0.01, # Volume impact: 1% slippage per 1% of volume
                 commission_per_trade: float = 0.0, # Fixed commission
                 stop_loss_percentage: float = 0.02, # 2% stop loss
                 take_profit_percentage: float = 0.05, # 5% take profit
                 override_leverage: Optional[float] = None,  # Override platform leverage
                 override_maintenance_margin: Optional[float] = None,  # Override maintenance margin %
                 enable_risk_gatekeeper: bool = True,  # Enable RiskGatekeeper validation
                 timeframe_aggregator: Optional[Any] = None,  # TimeframeAggregator for multi-timeframe pulse
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

        # Fetch platform margin parameters
        self.platform_leverage = 1.0  # Default to no leverage
        self.maintenance_margin_pct = 0.5  # Default 50% maintenance margin

        if platform:
            try:
                account_info = platform.get_account_info()
                fetched_leverage = account_info.get('max_leverage', 1.0)
                self.platform_leverage = override_leverage if override_leverage else fetched_leverage

                # Try to extract maintenance margin percentage from platform
                # Look for various possible field names
                maintenance_pct = account_info.get('maintenance_margin_percentage') or \
                                account_info.get('maintenance_margin_rate') or \
                                account_info.get('margin_closeout_percent')

                if override_maintenance_margin:
                    self.maintenance_margin_pct = override_maintenance_margin
                elif maintenance_pct:
                    self.maintenance_margin_pct = float(maintenance_pct)

                logger.info(f"Fetched platform margin parameters: leverage={self.platform_leverage}x, maintenance_margin={self.maintenance_margin_pct*100}%")
            except Exception as e:
                logger.warning(f"Could not fetch platform margin parameters: {e}. Using defaults.")
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
                self.risk_gatekeeper = RiskGatekeeper()
                logger.info("RiskGatekeeper initialized for backtest validation")
            except Exception as e:
                logger.warning(f"Could not initialize RiskGatekeeper: {e}")

        logger.info(f"Initialized Backtester with initial balance: ${initial_balance:.2f}, leverage: {self.platform_leverage}x")

    def _execute_trade(self,
                       current_balance: float,
                       current_price: float,
                       action: str,
                       amount_to_trade: float, # In base currency for BUY, quote for SELL
                       direction: str, # "BUY" or "SELL"
                       trade_timestamp: datetime, # Pass the timestamp from the candle
                       candle_volume: float = 0.0,  # Candle volume for slippage calculation
                       side: str = "LONG",  # "LONG" or "SHORT" - position side being opened/closed
                       is_liquidation: bool = False,  # True if forced liquidation
                       next_candle_open: Optional[float] = None  # For latency simulation
                       ) -> Tuple[float, float, float, Dict[str, Any]]: # new_balance, units, fee, trade_details
        """
        Simulates the execution of a single trade, applying fees, volume-based slippage, and latency.

        For SHORT positions: direction="SELL" opens a SHORT, direction="BUY" closes a SHORT
        For LONG positions: direction="BUY" opens a LONG, direction="SELL" closes a LONG
        """
        # Simulate order latency (0.2-2s range matching live trading)
        latency_seconds = np.random.lognormal(mean=np.log(0.5), sigma=0.6)

        # If latency pushes into next candle and we have next candle data, use its open price
        fill_price = current_price
        if next_candle_open is not None and latency_seconds > 60:  # Assuming 1-minute+ candles
            fill_price = next_candle_open
            logger.debug(f"Latency {latency_seconds:.2f}s pushed fill into next candle, using open price {fill_price:.2f}")

        # Calculate volume-based dynamic slippage
        base_slippage = self.slippage_percentage
        volume_slippage = 0.0

        if candle_volume > 0:
            order_size_usd = amount_to_trade if direction == "BUY" else (amount_to_trade * fill_price)
            order_size_base = order_size_usd / fill_price
            volume_impact = (order_size_base / candle_volume) * self.slippage_impact_factor
            volume_slippage = min(volume_impact, 0.05)  # Cap at 5% max slippage

        total_slippage = base_slippage + volume_slippage

        # Apply 3x slippage multiplier for forced liquidations
        if is_liquidation:
            total_slippage *= 3.0
            logger.warning(f"Forced liquidation - applying 3x slippage penalty: {total_slippage*100:.3f}%")

        effective_price = fill_price
        if direction == "BUY":
            effective_price *= (1 + total_slippage)
        elif direction == "SELL":
            effective_price *= (1 - total_slippage)

        # Calculate units or amount based on action and available balance/units
        units_traded = 0.0
        trade_value = 0.0
        fee = 0.0

        if direction == "BUY":
            # BUY: Opens LONG or closes SHORT position
            # amount_to_trade is in quote currency (e.g., USD)
            trade_value = amount_to_trade
            if current_balance < trade_value:
                logger.warning(f"Insufficient funds for BUY. Attempted: {trade_value:.2f}, Available: {current_balance:.2f}")
                return current_balance, 0.0, 0.0, {"status": "REJECTED", "reason": "Insufficient funds", "side": side}
            units_traded = trade_value / effective_price
            # For SHORT close, units are positive (buying back)
            if side == "SHORT":
                units_traded = abs(units_traded)  # Positive units to close negative SHORT position
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
            return current_balance, 0.0, 0.0, {"status": "REJECTED", "reason": "Invalid trade action", "side": side}

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
            "pnl_value": 0.0 # Placeholder, will be calculated when closing a position
        }

        logger.debug(f"Trade executed: {trade_details}")
        return new_balance, units_traded, fee, trade_details

    def _calculate_liquidation_price(self, position: Position, account_balance: float) -> Optional[float]:
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
            liquidation_price = position.entry_price - ((account_balance - maintenance_margin) / position.units)
        else:  # SHORT
            # SHORT liquidation: price rises until (balance + unrealized_pnl) = maintenance_margin
            # unrealized_pnl for SHORT = (entry_price - price) * abs(units)
            # balance + (entry_price - liq_price) * abs(units) = maintenance_margin
            # liq_price = entry_price - (maintenance_margin - balance) / abs(units)
            liquidation_price = position.entry_price + ((account_balance - maintenance_margin) / abs(position.units))

        return liquidation_price

    def _check_margin_liquidation(self, position: Position, current_price: float,
                                  candle_high: float, candle_low: float) -> bool:
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

    def run_backtest(self,
                     asset_pair: str,
                     start_date: Union[str, datetime],
                     end_date: Union[str, datetime],
                     decision_engine: DecisionEngine,
                     ) -> Dict[str, Any]:
        """
        Runs a backtest for a given asset, date range, and strategy.

        Args:
            asset_pair (str): The asset pair to backtest (e.g., "BTCUSD").
            start_date (Union[str, datetime]): The start date for the backtest.
            end_date (Union[str, datetime]): The end date for the backtest.
            decision_engine (DecisionEngine): The AI decision engine to use for generating signals.

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
            f"Starting backtest for {asset_pair} from {start_date} to {end_date}..."
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
                    market_data['market_regime'] = regime_info  # detect_regime returns a string
                except Exception as e:
                    logger.debug(f"Could not compute market regime at {timestamp}: {e}")
                    market_data['market_regime'] = 'UNKNOWN'
            else:
                market_data['market_regime_data'] = {}
                market_data['market_regime'] = 'UNKNOWN'

            # Extract base and quote currencies with robust parsing
            # Remove common delimiters and attempt to split known currency codes
            normalized_pair = asset_pair.replace('-', '').replace('/', '').replace('_', '').upper()

            # List of known quote currencies to check (ordered by likelihood)
            known_quotes = ['USDT', 'USDC', 'USD', 'EUR', 'GBP', 'JPY', 'BTC', 'ETH']
            base_currency = None
            quote_currency = 'USD'  # Default fallback

            for quote in known_quotes:
                if normalized_pair.endswith(quote):
                    quote_currency = quote
                    base_currency = normalized_pair[:-len(quote)]
                    break

            if not base_currency:
                # Fallback to original 3-char split if no known quote found
                base_currency = normalized_pair[:3] if len(normalized_pair) >= 6 else normalized_pair
                quote_currency = normalized_pair[3:] if len(normalized_pair) >= 6 else 'USD'

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

            # Prepare monitoring context (multi-timeframe pulse if available)
            monitoring_context = None
            if hasattr(self, 'timeframe_aggregator') and self.timeframe_aggregator and idx >= window_size:
                try:
                    # Compute historical pulse using data available up to current timestamp
                    historical_slice = data.iloc[max(0, idx - 200):idx + 1]  # Last 200 candles for indicators

                    if len(historical_slice) >= 50:  # Minimum for accurate indicators
                        pulse_data = self.timeframe_aggregator.analyze_multi_timeframe(
                            asset_pair=asset_pair,
                            candles=historical_slice.to_dict('records')
                        )

                        monitoring_context = {
                            'multi_timeframe_pulse': {
                                'timestamp': timestamp.timestamp(),
                                'age_seconds': 0,  # Computed on-demand for backtest
                                'timeframes': pulse_data
                            }
                        }
                        logger.debug(f"Generated historical pulse for {asset_pair} at {timestamp}")
                except Exception as e:
                    logger.debug(f"Could not generate pulse at {timestamp}: {e}")

            decision = decision_engine.generate_decision(
                asset_pair=asset_pair,
                market_data=market_data,
                balance={f'coinbase_{quote_currency}': current_balance} if 'BTC' in asset_pair or 'ETH' in asset_pair else {f'oanda_{quote_currency}': current_balance},
                portfolio={'holdings': portfolio_for_decision_engine},
                monitoring_context=monitoring_context  # Pass pulse data to decision engine
            )

            action = decision.get('action', 'HOLD')
            amount_to_trade = decision.get('suggested_amount', 0.0) # Using 'suggested_amount' from DecisionEngine

            # Handle existing open position for the asset pair
            current_position = open_positions.get(asset_pair)

            # Get next candle for latency simulation (if available)
            next_candle_open = None
            if idx + 1 < len(data):
                next_candle_open = data.iloc[idx + 1]['open']

            # Check for margin liquidation FIRST (highest priority)
            if current_position and self.platform_leverage > 1.0:
                if self._check_margin_liquidation(current_position, candle['close'], candle['high'], candle['low']):
                    # Force liquidate entire position at liquidation price with 3x slippage
                    liquidation_price = current_position.liquidation_price
                    sell_units = abs(current_position.units)

                    # Execute forced liquidation
                    if current_position.side == "LONG":
                        new_balance, units_traded_neg, fee, trade_details = self._execute_trade(
                            current_balance, liquidation_price, "SELL", sell_units, "SELL", timestamp,
                            candle_volume=candle.get('volume', 0), side="LONG", is_liquidation=True
                        )
                    else:  # SHORT
                        # Close SHORT by buying back
                        trade_amount_quote = sell_units * liquidation_price
                        new_balance, units_traded, fee, trade_details = self._execute_trade(
                            current_balance, liquidation_price, "BUY", trade_amount_quote, "BUY", timestamp,
                            candle_volume=candle.get('volume', 0), side="SHORT", is_liquidation=True
                        )

                    if trade_details['status'] == 'EXECUTED':
                        # Calculate P&L
                        if current_position.side == "LONG":
                            pnl = (trade_details['effective_price'] - current_position.entry_price) * sell_units
                        else:  # SHORT
                            pnl = (current_position.entry_price - trade_details['effective_price']) * sell_units

                        trade_details['pnl_value'] = pnl
                        trade_details['entry_price'] = current_position.entry_price
                        trade_details['event_type'] = 'LIQUIDATION'

                        current_balance = new_balance
                        total_fees += fee
                        trades_history.append(trade_details)

                        # Close the position
                        del open_positions[asset_pair]
                        logger.warning(f"LIQUIDATED {current_position.side} position for {asset_pair}: {sell_units:.4f} units at {trade_details['effective_price']:.4f}. Entry: {current_position.entry_price:.4f}, PnL: ${pnl:.2f}")
                        current_position = None  # Position is now closed

            # Check for intraday Stop Loss or Take Profit hit (using high/low, not close)
            if current_position:
                stop_triggered = False
                profit_triggered = False
                exit_price = None

                if current_position.side == "LONG":
                    # LONG: SL on low, TP on high
                    if current_position.stop_loss_price and candle['low'] <= current_position.stop_loss_price:
                        stop_triggered = True
                        exit_price = current_position.stop_loss_price
                        logger.info(f"Stop Loss hit for LONG {asset_pair} at {timestamp}. Low {candle['low']:.2f} <= SL {current_position.stop_loss_price:.2f}")
                    elif current_position.take_profit_price and candle['high'] >= current_position.take_profit_price:
                        profit_triggered = True
                        exit_price = current_position.take_profit_price
                        logger.info(f"Take Profit hit for LONG {asset_pair} at {timestamp}. High {candle['high']:.2f} >= TP {current_position.take_profit_price:.2f}")
                else:  # SHORT
                    # SHORT: SL on high (price rises), TP on low (price falls)
                    if current_position.stop_loss_price and candle['high'] >= current_position.stop_loss_price:
                        stop_triggered = True
                        exit_price = current_position.stop_loss_price
                        logger.info(f"Stop Loss hit for SHORT {asset_pair} at {timestamp}. High {candle['high']:.2f} >= SL {current_position.stop_loss_price:.2f}")
                    elif current_position.take_profit_price and candle['low'] <= current_position.take_profit_price:
                        profit_triggered = True
                        exit_price = current_position.take_profit_price
                        logger.info(f"Take Profit hit for SHORT {asset_pair} at {timestamp}. Low {candle['low']:.2f} <= TP {current_position.take_profit_price:.2f}")

                # Execute exit if stop or profit triggered
                if (stop_triggered or profit_triggered) and exit_price:
                    sell_units = abs(current_position.units)

                    if current_position.side == "LONG":
                        # Close LONG by selling
                        new_balance, units_traded_neg, fee, trade_details = self._execute_trade(
                            current_balance, exit_price, "SELL", sell_units, "SELL", timestamp,
                            candle_volume=candle.get('volume', 0), side="LONG", next_candle_open=next_candle_open
                        )
                        pnl = (trade_details['effective_price'] - current_position.entry_price) * sell_units
                    else:  # SHORT
                        # Close SHORT by buying back
                        trade_amount_quote = sell_units * exit_price
                        new_balance, units_traded, fee, trade_details = self._execute_trade(
                            current_balance, exit_price, "BUY", trade_amount_quote, "BUY", timestamp,
                            candle_volume=candle.get('volume', 0), side="SHORT", next_candle_open=next_candle_open
                        )
                        pnl = (current_position.entry_price - trade_details['effective_price']) * sell_units

                    if trade_details['status'] == 'EXECUTED':
                        trade_details['pnl_value'] = pnl
                        trade_details['entry_price'] = current_position.entry_price
                        trade_details['event_type'] = 'STOP_LOSS' if stop_triggered else 'TAKE_PROFIT'

                        current_balance = new_balance
                        total_fees += fee
                        trades_history.append(trade_details)

                        # Close the position
                        del open_positions[asset_pair]
                        logger.info(f"Closed {current_position.side} position for {asset_pair} via {'SL' if stop_triggered else 'TP'}: {sell_units:.4f} units at {trade_details['effective_price']:.4f}. Entry: {current_position.entry_price:.4f}, PnL: ${pnl:.2f}")
                        current_position = None  # Override action since we already closed
                        action = 'HOLD'  # Don't process decision action

            # Validate trade with RiskGatekeeper before execution
            if action != 'HOLD' and self.risk_gatekeeper:
                try:
                    # Build context for gatekeeper
                    gatekeeper_context = {
                        'current_balance': current_balance,
                        'open_positions': [{'asset_pair': p.asset_pair, 'units': p.units, 'side': p.side,
                                          'entry_price': p.entry_price, 'current_price': candle['close']}
                                          for p in open_positions.values()],
                        'equity_curve': equity_curve,
                        'initial_balance': self.initial_balance
                    }

                    validation_result = self.risk_gatekeeper.validate_trade(decision, gatekeeper_context)

                    if not validation_result[0]:  # validation_result is (bool, str)
                        # Trade rejected by gatekeeper
                        rejection_reason = validation_result[1]
                        logger.warning(f"Trade REJECTED by RiskGatekeeper at {timestamp}: {rejection_reason}")

                        trades_history.append({
                            'timestamp': timestamp.isoformat(),
                            'action': action,
                            'status': 'REJECTED_BY_GATEKEEPER',
                            'rejection_reason': rejection_reason,
                            'suggested_amount': amount_to_trade,
                            'side': 'LONG' if action == 'BUY' else 'SHORT' if not current_position else current_position.side
                        })
                        action = 'HOLD'  # Override to prevent execution
                except Exception as e:
                    logger.error(f"RiskGatekeeper error at {timestamp}: {e}")

            # Execute decision action
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

            # Execute decision action
            if action == 'BUY' and amount_to_trade > 0:
                if current_balance > 0:
                    # BUY can either: 1) Open new LONG, 2) Close existing SHORT, 3) Average LONG position

                    # Calculate max spendable accounting for fees
                    max_spendable_total = current_balance
                    if self.commission_per_trade > 0:
                        max_spendable_total -= self.commission_per_trade
                    max_principal_spendable = max_spendable_total / (1 + self.fee_percentage)
                    trade_amount_quote = min(amount_to_trade, max_principal_spendable)

                    if trade_amount_quote <= 0:
                        logger.info(f"Skipping BUY for {asset_pair} due to insufficient balance at {timestamp}")
                        continue

                    # Determine if closing SHORT or opening/averaging LONG
                    if current_position and current_position.side == "SHORT":
                        # Close SHORT position
                        new_balance, units_traded, fee, trade_details = self._execute_trade(
                            current_balance, candle['close'], "BUY", trade_amount_quote, "BUY", timestamp,
                            candle_volume=candle.get('volume', 0), side="SHORT", next_candle_open=next_candle_open
                        )

                        if trade_details['status'] == 'EXECUTED':
                            # Calculate SHORT P&L: (entry_price - exit_price) * abs(units)
                            pnl = (current_position.entry_price - trade_details['effective_price']) * abs(current_position.units)
                            trade_details['pnl_value'] = pnl
                            trade_details['entry_price'] = current_position.entry_price

                            current_balance = new_balance
                            total_fees += fee
                            trades_history.append(trade_details)

                            del open_positions[asset_pair]
                            logger.info(f"Closed SHORT position for {asset_pair}: {abs(current_position.units):.4f} units at {trade_details['effective_price']:.4f}. Entry: {current_position.entry_price:.4f}, PnL: ${pnl:.2f}")
                    else:
                        # Open new LONG or average existing LONG
                        new_balance, units_traded, fee, trade_details = self._execute_trade(
                            current_balance, candle['close'], "BUY", trade_amount_quote, "BUY", timestamp,
                            candle_volume=candle.get('volume', 0), side="LONG", next_candle_open=next_candle_open
                        )

                        if trade_details['status'] == 'EXECUTED':
                            current_balance = new_balance
                            total_fees += fee
                            trades_history.append(trade_details)

                            if current_position and current_position.side == "LONG":
                                # Average LONG position
                                total_cost = (current_position.units * current_position.entry_price) + (units_traded * trade_details['effective_price'])
                                total_units = current_position.units + units_traded
                                current_position.entry_price = total_cost / total_units
                                current_position.units = total_units

                                # Recalculate stop/take/liquidation prices
                                current_position.stop_loss_price = current_position.entry_price * (1 - self.stop_loss_percentage)
                                current_position.take_profit_price = current_position.entry_price * (1 + self.take_profit_percentage)
                                current_position.liquidation_price = self._calculate_liquidation_price(current_position, current_balance)

                                logger.info(f"Averaged LONG position for {asset_pair}: {current_position.units:.4f} units at avg {current_position.entry_price:.4f}")
                                if current_position.liquidation_price:
                                    logger.info(f"  Updated liquidation price: {current_position.liquidation_price:.4f}")
                            else:
                                # Open new LONG position
                                new_position = Position(
                                    asset_pair=asset_pair,
                                    units=units_traded,
                                    entry_price=trade_details['effective_price'],
                                    entry_timestamp=timestamp,
                                    side="LONG",
                                    stop_loss_price=trade_details['effective_price'] * (1 - self.stop_loss_percentage),
                                    take_profit_price=trade_details['effective_price'] * (1 + self.take_profit_percentage)
                                )
                                new_position.liquidation_price = self._calculate_liquidation_price(new_position, current_balance)
                                open_positions[asset_pair] = new_position

                                logger.info(f"Opened LONG position for {asset_pair}: {units_traded:.4f} units at {trade_details['effective_price']:.4f}, SL: {new_position.stop_loss_price:.4f}, TP: {new_position.take_profit_price:.4f}")
                                if new_position.liquidation_price:
                                    logger.info(f"  Liquidation price: {new_position.liquidation_price:.4f}")
                else:
                    logger.info(f"Skipping BUY for {asset_pair} due to insufficient balance at {timestamp}")

            elif action == 'SELL' and amount_to_trade > 0:
                # SELL can either: 1) Close existing LONG, 2) Open new SHORT

                if current_position and current_position.side == "LONG":
                    # Close LONG position
                    sell_units = abs(current_position.units)

                    new_balance, units_traded_neg, fee, trade_details = self._execute_trade(
                        current_balance, candle['close'], "SELL", sell_units, "SELL", timestamp,
                        candle_volume=candle.get('volume', 0), side="LONG", next_candle_open=next_candle_open
                    )

                    if trade_details['status'] == 'EXECUTED':
                        # Calculate LONG P&L: (exit_price - entry_price) * units
                        pnl = (trade_details['effective_price'] - current_position.entry_price) * sell_units
                        trade_details['pnl_value'] = pnl
                        trade_details['entry_price'] = current_position.entry_price

                        current_balance = new_balance
                        total_fees += fee
                        trades_history.append(trade_details)

                        del open_positions[asset_pair]
                        logger.info(f"Closed LONG position for {asset_pair}: {sell_units:.4f} units at {trade_details['effective_price']:.4f}. Entry: {current_position.entry_price:.4f}, PnL: ${pnl:.2f}")
                else:
                    # Open new SHORT position (if no LONG exists)
                    if current_balance > 0:
                        # Calculate position size in base currency for SHORT
                        # amount_to_trade is in quote currency, convert to base units
                        short_units = amount_to_trade / candle['close']

                        new_balance, units_traded, fee, trade_details = self._execute_trade(
                            current_balance, candle['close'], "SELL", short_units, "SELL", timestamp,
                            candle_volume=candle.get('volume', 0), side="SHORT", next_candle_open=next_candle_open
                        )

                        if trade_details['status'] == 'EXECUTED':
                            current_balance = new_balance
                            total_fees += fee
                            trades_history.append(trade_details)

                            # Open SHORT position with negative units
                            new_position = Position(
                                asset_pair=asset_pair,
                                units=units_traded,  # Already negative from _execute_trade
                                entry_price=trade_details['effective_price'],
                                entry_timestamp=timestamp,
                                side="SHORT",
                                stop_loss_price=trade_details['effective_price'] * (1 + self.stop_loss_percentage),  # Reversed for SHORT
                                take_profit_price=trade_details['effective_price'] * (1 - self.take_profit_percentage)  # Reversed for SHORT
                            )
                            new_position.liquidation_price = self._calculate_liquidation_price(new_position, current_balance)
                            open_positions[asset_pair] = new_position

                            logger.info(f"Opened SHORT position for {asset_pair}: {abs(units_traded):.4f} units at {trade_details['effective_price']:.4f}, SL: {new_position.stop_loss_price:.4f}, TP: {new_position.take_profit_price:.4f}")
                            if new_position.liquidation_price:
                                logger.info(f"  Liquidation price: {new_position.liquidation_price:.4f}")
                    else:
                        logger.info(f"Skipping SHORT for {asset_pair} due to insufficient balance at {timestamp}")

            elif action == 'HOLD':
                logger.debug(f"Holding for {asset_pair} at {timestamp}. Current balance: {current_balance:.2f}, Position: {current_position.side if current_position else 'None'} {abs(current_position.units) if current_position else 0:.4f} units")

            # Update equity curve at the end of each iteration
            current_portfolio_value = current_balance
            if current_position:
                # Calculate unrealized P&L for current position
                if current_position.side == "LONG":
                    unrealized_pnl = (candle['close'] - current_position.entry_price) * current_position.units
                else:  # SHORT
                    unrealized_pnl = (current_position.entry_price - candle['close']) * abs(current_position.units)
                current_portfolio_value += unrealized_pnl
            equity_curve.append(current_portfolio_value)

        # 4. Final P&L calculation (liquidate any remaining open positions)
        final_value = current_balance
        if open_positions:
            for pos in open_positions.values():
                if pos.asset_pair == asset_pair:
                    # Liquidate remaining position at the last close price
                    final_price = data['close'].iloc[-1]
                    units_abs = abs(pos.units)

                    if pos.side == "LONG":
                        trade_value = units_abs * final_price
                        pnl = (final_price - pos.entry_price) * units_abs
                    else:  # SHORT
                        trade_value = units_abs * final_price
                        pnl = (pos.entry_price - final_price) * units_abs

                    fee = (trade_value * self.fee_percentage) + self.commission_per_trade
                    final_value += pnl - fee  # Add realized P&L minus fees
                    total_fees += fee

                    # Add final liquidation to trade history
                    final_liquidation_trade = {
                        "timestamp": data.index[-1].isoformat(),
                        "action": "BUY" if pos.side == "SHORT" else "SELL",
                        "side": pos.side,
                        "entry_price": pos.entry_price,
                        "effective_price": final_price,
                        "units_traded": units_abs if pos.side == "SHORT" else -units_abs,
                        "trade_value": trade_value,
                        "fee": fee,
                        "status": "EXECUTED (Final Liquidation)",
                        "event_type": "FINAL_LIQUIDATION",
                        "pnl_value": pnl
                    }
                    trades_history.append(final_liquidation_trade)
                    logger.info(f"Final liquidation of {pos.side} position for {pos.asset_pair}: {units_abs:.4f} units at {final_price:.4f}. Entry: {pos.entry_price:.4f}, PnL: ${pnl:.2f}")

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

    def save_results(self, results: Dict[str, Any], output_file: str):
        """
        Saves the trade history from a backtest to a JSON file.

        Args:
            results (Dict[str, Any]): The results dictionary from a backtest run.
            output_file (str): The path to the output JSON file.
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results['trades'], f, indent=2)
            logger.info(f"Backtest trade history saved to {output_file}")
        except Exception as e:
            logger.error(f"Error saving backtest results to {output_file}: {e}")
