"""
Portfolio Backtester - Multi-Asset Portfolio Management

This module implements backtesting for multi-asset portfolios with:
- Correlation-aware position sizing
- Portfolio-level risk management
- Cross-asset learning and memory
- Rebalancing and hedging strategies

Preserves backward compatibility - does not modify AdvancedBacktester.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from finance_feedback_engine.data_providers.historical_data_provider import (
    HistoricalDataProvider,
)
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.memory.portfolio_memory_adapter import PortfolioMemoryEngineAdapter
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper

logger = logging.getLogger(__name__)


@dataclass
class PortfolioPosition:
    """
    Represents a position in a multi-asset portfolio.

    Attributes:
        asset_pair: Trading pair (e.g., "BTCUSD")
        entry_price: Price at position entry
        units: Number of units held
        entry_time: Timestamp of position entry
        stop_loss: Stop-loss price level
        take_profit: Take-profit price level
        unrealized_pnl: Current unrealized profit/loss
    """

    asset_pair: str
    entry_price: float
    units: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    unrealized_pnl: float = 0.0
    side: str = "LONG"  # LONG or SHORT

    def update_pnl(self, current_price: float) -> float:
        """Update and return unrealized P&L."""
        if self.side == "SHORT":
            self.unrealized_pnl = (self.entry_price - current_price) * abs(self.units)
        else:
            self.unrealized_pnl = (current_price - self.entry_price) * self.units
        return self.unrealized_pnl


@dataclass
class PortfolioState:
    """
    Current state of the multi-asset portfolio.

    Attributes:
        cash: Available cash balance
        positions: Dict mapping asset_pair to PortfolioPosition
        equity_curve: Historical portfolio values
        trade_history: List of executed trades
        correlation_matrix: Current asset correlation matrix
    """

    cash: float
    positions: Dict[str, PortfolioPosition] = field(default_factory=dict)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    trade_history: List[Dict[str, Any]] = field(default_factory=list)
    correlation_matrix: Optional[pd.DataFrame] = None

    def total_value(self, current_prices: Dict[str, float]) -> float:
        """Calculate total portfolio value (cash + positions)."""
        position_value = sum(
            pos.units * current_prices.get(asset, pos.entry_price)
            for asset, pos in self.positions.items()
        )
        return self.cash + position_value

    def position_weights(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """Calculate current position weights."""
        total = self.total_value(current_prices)
        if total == 0:
            return {}

        weights = {}
        for asset, pos in self.positions.items():
            position_value = pos.units * current_prices.get(asset, pos.entry_price)
            weights[asset] = position_value / total

        return weights


class PortfolioBacktester:
    """
    Multi-asset portfolio backtester with correlation-aware position sizing.

    Features:
    - Simultaneous trading across multiple assets
    - Correlation-based position adjustment
    - Portfolio-level risk management (VaR, max drawdown)
    - Cross-asset learning via Portfolio Memory Engine
    - Rebalancing and hedging strategies

    Example:
        backtester = PortfolioBacktester(
            asset_pairs=["BTCUSD", "ETHUSD", "EURUSD"],
            initial_balance=10000,
            config=config
        )
        results = backtester.run_backtest(
            start_date="2025-01-01",
            end_date="2025-03-01"
        )
    """

    def __init__(
        self,
        asset_pairs: List[str],
        initial_balance: float,
        config: Dict[str, Any],
        decision_engine: Optional[DecisionEngine] = None,
        data_provider: Optional[HistoricalDataProvider] = None,
        risk_gatekeeper: Optional[RiskGatekeeper] = None,
        memory_engine: Optional[PortfolioMemoryEngine] = None,
    ):
        """
        Initialize portfolio backtester.

        Args:
            asset_pairs: List of trading pairs to include in portfolio
            initial_balance: Starting cash balance
            config: Configuration dictionary
            decision_engine: AI decision engine (created if None)
            data_provider: Historical data provider (created if None)
            risk_gatekeeper: Risk validation (created if None)
            memory_engine: Portfolio memory (created if None)
        """
        self.asset_pairs = asset_pairs
        self.initial_balance = initial_balance
        self.config = config

        # Initialize components
        self.decision_engine = decision_engine or DecisionEngine(config)
        self.data_provider = data_provider or HistoricalDataProvider(config)

        # Initialize risk gatekeeper with portfolio config
        if risk_gatekeeper:
            self.risk_gatekeeper = risk_gatekeeper
        else:
            portfolio_config = config.get("portfolio", {})
            self.risk_gatekeeper = RiskGatekeeper(
                max_drawdown_pct=portfolio_config.get("max_drawdown", 0.05),
                correlation_threshold=portfolio_config.get(
                    "correlation_threshold", 0.7
                ),
                max_correlated_assets=portfolio_config.get("max_positions", 5),
                max_var_pct=portfolio_config.get("max_portfolio_risk", 0.05),
                var_confidence=0.95,
                is_backtest=True,
            )

        self.memory_engine = memory_engine or PortfolioMemoryEngineAdapter(config)

        # Portfolio configuration
        self.fee_rate = config.get("backtesting", {}).get("fee_rate", 0.001)  # 0.1%
        self.slippage_rate = config.get("backtesting", {}).get(
            "slippage_rate", 0.0001
        )  # 0.01%
        self.max_positions = config.get("portfolio", {}).get(
            "max_positions", len(asset_pairs)
        )
        self.correlation_threshold = config.get("portfolio", {}).get(
            "correlation_threshold", 0.7
        )
        self.correlation_window = config.get("portfolio", {}).get(
            "correlation_window", 30
        )
        self.max_portfolio_risk = config.get("portfolio", {}).get(
            "max_portfolio_risk", 0.02
        )  # 2%
        self.trading_dates_mode = config.get("backtesting", {}).get(
            "trading_dates_mode", "intersection"
        )
        self.min_overlapping_trading_dates = config.get("backtesting", {}).get(
            "min_overlapping_trading_dates", 5
        )

        # State tracking
        self.portfolio_state: Optional[PortfolioState] = None
        self.price_history: Dict[str, pd.DataFrame] = {}

        logger.info(
            f"PortfolioBacktester initialized with {len(asset_pairs)} assets: {asset_pairs}"
        )

    def run_backtest(
        self, start_date: str, end_date: str, rebalance_frequency: str = "daily"
    ) -> Dict[str, Any]:
        """
        Run multi-asset portfolio backtest.

        Args:
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            rebalance_frequency: How often to rebalance ("daily", "weekly", "monthly")

        Returns:
            Dictionary containing:
            - portfolio_metrics: Sharpe, drawdown, returns, VaR
            - asset_attribution: Per-asset performance contribution
            - trade_history: All executed trades
            - equity_curve: Portfolio value over time
            - correlation_analysis: Asset correlation insights
        """
        logger.info(f"Starting portfolio backtest from {start_date} to {end_date}")
        logger.info(
            f"Assets: {self.asset_pairs}, Initial balance: ${self.initial_balance:,.2f}"
        )

        # Initialize portfolio state
        self.portfolio_state = PortfolioState(cash=self.initial_balance)

        # Load historical data for all assets
        self._load_historical_data(start_date, end_date)

        # Get common trading dates across all assets
        trading_dates = self._get_trading_dates()
        logger.info(
            f"Found {len(trading_dates)} trading dates using {self.trading_dates_mode} mode"
        )

        # Main backtest loop
        for i, current_date in enumerate(trading_dates):
            logger.debug(f"Processing {current_date} ({i+1}/{len(trading_dates)})")

            # Get current prices for all assets
            current_prices = self._get_current_prices(current_date)

            # Update correlation matrix
            self._update_correlation_matrix(current_date)

            # Update existing positions (P&L, stop-loss, take-profit)
            self._update_positions(current_prices, current_date)

            # Generate decisions for each asset
            decisions = self._generate_portfolio_decisions(current_date, current_prices)

            # Execute validated trades
            self._execute_portfolio_trades(decisions, current_prices, current_date)

            # Record portfolio value
            portfolio_value = self.portfolio_state.total_value(current_prices)
            self.portfolio_state.equity_curve.append((current_date, portfolio_value))

            # Check portfolio-level risk limits
            if self._check_portfolio_stop_loss(portfolio_value):
                logger.warning(f"Portfolio stop-loss triggered at {current_date}")
                self._close_all_positions(current_prices, current_date)
                break

        # Calculate final metrics
        results = self._calculate_portfolio_metrics()

        logger.info(
            f"Backtest complete. Final portfolio value: ${results['final_value']:,.2f}"
        )
        logger.info(f"Total return: {results['total_return']:.2f}%")

        return results

    def _load_historical_data(self, start_date: str, end_date: str) -> None:
        """Load historical price data for all assets."""
        for asset_pair in self.asset_pairs:
            logger.info(f"Loading historical data for {asset_pair}")
            df = self.data_provider.get_historical_data(
                asset_pair=asset_pair, start_date=start_date, end_date=end_date
            )
            self.price_history[asset_pair] = df
            logger.info(f"Loaded {len(df)} candles for {asset_pair}")

    def _get_trading_dates(self) -> List[datetime]:
        """Compute trading dates across assets using intersection by default."""
        date_sets = []

        for asset, df in self.price_history.items():
            if df.empty:
                logger.warning(
                    f"No historical data for {asset}; skipping date alignment"
                )
                continue
            date_sets.append(set(df.index))

        if not date_sets:
            return []

        mode = self.trading_dates_mode
        if mode not in {"union", "intersection"}:
            logger.warning(
                "Unknown trading_dates_mode '%s'; defaulting to intersection",
                self.trading_dates_mode,
            )
            mode = "intersection"
        self.trading_dates_mode = mode

        if mode == "union":
            trading_dates = sorted(set().union(*date_sets))
        else:
            trading_dates = sorted(set.intersection(*date_sets))

        self._validate_trading_dates(trading_dates)
        return trading_dates

    def _validate_trading_dates(self, trading_dates: List[datetime]) -> None:
        """Validate overlap and alert when intersection is too small."""
        if not trading_dates:
            msg = (
                "No overlapping trading dates found across assets. "
                "Adjust date range or set backtesting.trading_dates_mode='union' if intentional."
            )
            logger.error(msg)
            raise ValueError(msg)

        if len(trading_dates) < self.min_overlapping_trading_dates:
            logger.warning(
                "Only %d trading dates available across all assets (mode=%s); "
                "results may be unreliable. Consider expanding the date range or using union mode.",
                len(trading_dates),
                self.trading_dates_mode,
            )

    def _get_current_prices(self, date: datetime) -> Dict[str, float]:
        """Get current prices for all assets."""
        prices = {}
        for asset_pair in self.asset_pairs:
            if date in self.price_history[asset_pair].index:
                prices[asset_pair] = self.price_history[asset_pair].loc[date, "close"]
        return prices

    def _update_correlation_matrix(self, current_date: datetime) -> None:
        """Update correlation matrix using recent price history."""
        # Get recent returns for correlation window
        returns_data = {}

        for asset_pair in self.asset_pairs:
            df = self.price_history[asset_pair]
            if current_date not in df.index:
                continue

            # Get window of returns
            idx = df.index.get_loc(current_date)
            start_idx = max(0, idx - self.correlation_window)
            window_df = df.iloc[start_idx : idx + 1]

            if len(window_df) > 1:
                returns = window_df["close"].pct_change().dropna()
                returns_data[asset_pair] = returns

        # Calculate correlation matrix
        if len(returns_data) >= 2:
            returns_df = pd.DataFrame(returns_data)
            self.portfolio_state.correlation_matrix = returns_df.corr()

    def _update_positions(
        self, current_prices: Dict[str, float], date: datetime
    ) -> None:
        """Update existing positions (P&L, stop-loss, take-profit triggers)."""
        positions_to_close = []

        for asset_pair, position in self.portfolio_state.positions.items():
            current_price = current_prices.get(asset_pair)
            if current_price is None:
                continue

            # Update unrealized P&L
            position.update_pnl(current_price)

            # Check stop-loss / take-profit with side awareness
            if position.side == "SHORT":
                if position.stop_loss and current_price >= position.stop_loss:
                    logger.info(
                        f"Stop-loss triggered for {asset_pair} at {current_price}"
                    )
                    positions_to_close.append(asset_pair)
                elif position.take_profit and current_price <= position.take_profit:
                    logger.info(
                        f"Take-profit triggered for {asset_pair} at {current_price}"
                    )
                    positions_to_close.append(asset_pair)
            else:
                if position.stop_loss and current_price <= position.stop_loss:
                    logger.info(
                        f"Stop-loss triggered for {asset_pair} at {current_price}"
                    )
                    positions_to_close.append(asset_pair)
                elif position.take_profit and current_price >= position.take_profit:
                    logger.info(
                        f"Take-profit triggered for {asset_pair} at {current_price}"
                    )
                    positions_to_close.append(asset_pair)

        # Close triggered positions
        for asset_pair in positions_to_close:
            if asset_pair in current_prices:
                self._close_position(
                    asset_pair, current_prices[asset_pair], "trigger", date
                )

    def _generate_portfolio_decisions(
        self, current_date: datetime, current_prices: Dict[str, float]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate AI decisions for all assets with portfolio context.

        Returns:
            Dict mapping asset_pair to decision dict
        """
        decisions = {}

        # Build portfolio context for AI
        portfolio_context = self._build_portfolio_context(current_prices)

        for asset_pair in self.asset_pairs:
            if asset_pair not in current_prices:
                continue

            # Get market data for this asset
            df = self.price_history[asset_pair]
            if current_date not in df.index:
                continue

            idx = df.index.get_loc(current_date)
            current_candle = df.iloc[idx]

            # Build market data dict for decision engine
            market_data = {
                "close": current_prices[asset_pair],
                "open": current_candle.get("open", current_prices[asset_pair]),
                "high": current_candle.get("high", current_prices[asset_pair]),
                "low": current_candle.get("low", current_prices[asset_pair]),
                "volume": current_candle.get("volume", 0),
            }

            # Unified cash balance; decision engine now falls back to USD when platform-specific keys are absent
            balance_dict = {"USD": self.portfolio_state.cash}

            # Build portfolio context with correlation info
            portfolio_dict = {
                "positions": portfolio_context.get("position_weights", {}),
                "total_value": portfolio_context.get("total_value", 0),
                "cash_pct": portfolio_context.get("cash_pct", 1.0),
                "correlation_matrix": (
                    self.portfolio_state.correlation_matrix.to_dict()
                    if self.portfolio_state.correlation_matrix is not None
                    else None
                ),
            }

            # Generate decision via AI ensemble
            try:
                decision = self.decision_engine.generate_decision(
                    asset_pair=asset_pair,
                    market_data=market_data,
                    balance=balance_dict,
                    portfolio=portfolio_dict,
                )
                decisions[asset_pair] = decision
                logger.debug(
                    f"{asset_pair}: {decision['action']} (confidence: {decision['confidence']})"
                )
            except Exception as e:
                logger.error(f"Error generating decision for {asset_pair}: {e}")

        return decisions

    def _build_portfolio_context(
        self, current_prices: Dict[str, float]
    ) -> Dict[str, Any]:
        """Build portfolio-level context for AI decision-making."""
        total_value = self.portfolio_state.total_value(current_prices)
        weights = self.portfolio_state.position_weights(current_prices)

        return {
            "total_value": total_value,
            "cash": self.portfolio_state.cash,
            "cash_pct": (
                self.portfolio_state.cash / total_value if total_value > 0 else 1.0
            ),
            "num_positions": len(self.portfolio_state.positions),
            "position_weights": weights,
            "total_unrealized_pnl": sum(
                pos.unrealized_pnl for pos in self.portfolio_state.positions.values()
            ),
        }

    def _execute_portfolio_trades(
        self,
        decisions: Dict[str, Dict[str, Any]],
        current_prices: Dict[str, float],
        current_date: datetime,
    ) -> None:
        """Execute validated trades with correlation-aware position sizing."""
        for asset_pair, decision in decisions.items():
            action = decision.get("action", "HOLD")
            current_position = self.portfolio_state.positions.get(asset_pair)

            if action == "HOLD":
                continue

            # Build risk context for validation
            # Calculate current PnL
            total_value = self.portfolio_state.total_value(current_prices)
            pnl = (total_value - self.initial_balance) / self.initial_balance

            risk_context = {
                "recent_performance": {"total_pnl": pnl},
                "holdings": {
                    asset: "crypto" if "_" not in asset else "forex"
                    for asset in self.portfolio_state.positions.keys()
                },
            }

            # Validate with risk gatekeeper
            is_valid, validation_msg = self.risk_gatekeeper.validate_trade(
                decision, risk_context
            )
            if not is_valid:
                logger.debug(
                    f"Risk gatekeeper rejected {asset_pair} {action}: {validation_msg}"
                )
                continue

            # Calculate correlation-adjusted position size
            position_size = self._calculate_position_size(
                asset_pair=asset_pair, decision=decision, current_prices=current_prices
            )

            if position_size == 0:
                logger.debug(f"Position size zero for {asset_pair}, skipping")
                continue

            # Execute trade
            if action == "BUY":
                if current_position:
                    if current_position.side == "SHORT":
                        # Flip from short to long
                        self._close_position(
                            asset_pair,
                            current_prices[asset_pair],
                            "decision_close_short",
                            current_date,
                        )
                        self._execute_buy(
                            asset_pair,
                            position_size,
                            current_prices[asset_pair],
                            current_date,
                            decision,
                        )
                    elif current_position.side == "LONG":
                        # Close existing long before re-entering to preserve history and P&L
                        self._close_position(
                            asset_pair,
                            current_prices[asset_pair],
                            "decision_close_long",
                            current_date,
                        )
                        self._execute_buy(
                            asset_pair,
                            position_size,
                            current_prices[asset_pair],
                            current_date,
                            decision,
                        )
                else:
                    self._execute_buy(
                        asset_pair,
                        position_size,
                        current_prices[asset_pair],
                        current_date,
                        decision,
                    )
            elif action == "SELL":
                # Close existing LONG; if none, open SHORT
                if current_position and current_position.side == "LONG":
                    self._close_position(
                        asset_pair,
                        current_prices[asset_pair],
                        "decision_close_long",
                        current_date,
                    )
                elif not current_position:
                    self._execute_short(
                        asset_pair,
                        position_size,
                        current_prices[asset_pair],
                        current_date,
                        decision,
                    )

    def _calculate_position_size(
        self,
        asset_pair: str,
        decision: Dict[str, Any],
        current_prices: Dict[str, float],
    ) -> float:
        """
        Calculate position size with correlation adjustment.

        Reduces position size when:
        - High correlation with existing positions (> threshold)
        - Portfolio risk limits reached
        - Insufficient cash available
        """
        # Base position size (1% risk rule)
        portfolio_value = self.portfolio_state.total_value(current_prices)
        base_size = portfolio_value * 0.01  # 1% of portfolio

        # Correlation adjustment
        correlation_factor = self._get_correlation_adjustment(asset_pair)

        # Confidence adjustment
        confidence = decision.get("confidence", 50) / 100.0
        confidence_factor = max(0.5, confidence)  # Min 50% of base size

        # Available cash constraint
        max_size = self.portfolio_state.cash * 0.9  # Leave 10% cash buffer

        # Calculate final size
        adjusted_size = base_size * correlation_factor * confidence_factor
        final_size = min(adjusted_size, max_size)

        logger.debug(
            f"{asset_pair} position sizing: base=${base_size:.2f}, "
            f"corr_factor={correlation_factor:.2f}, conf_factor={confidence_factor:.2f}, "
            f"final=${final_size:.2f}"
        )

        return final_size

    def _get_correlation_adjustment(self, asset_pair: str) -> float:
        """
        Calculate correlation-based position size adjustment.

        Returns factor between 0.5 and 1.0:
        - 1.0 if no correlation with existing positions
        - 0.5 if high correlation (reduces position size by 50%)
        """
        if self.portfolio_state.correlation_matrix is None:
            return 1.0

        if not self.portfolio_state.positions:
            return 1.0

        # Guard against invalid threshold (avoid division by zero)
        if self.correlation_threshold >= 1.0:
            return 1.0

        # Find maximum correlation with existing positions
        max_correlation = 0.0
        for existing_asset in self.portfolio_state.positions.keys():
            if existing_asset == asset_pair:
                continue

            try:
                corr = abs(
                    self.portfolio_state.correlation_matrix.loc[
                        asset_pair, existing_asset
                    ]
                )
                max_correlation = max(max_correlation, corr)
            except (KeyError, TypeError):
                continue

        # Reduce position size if correlation exceeds threshold
        if max_correlation > self.correlation_threshold:
            reduction = (max_correlation - self.correlation_threshold) / (
                1.0 - self.correlation_threshold
            )
            return 1.0 - (reduction * 0.5)  # Max 50% reduction

        return 1.0

    def _execute_buy(
        self,
        asset_pair: str,
        position_size: float,
        price: float,
        date: datetime,
        decision: Dict[str, Any],
    ) -> None:
        """Execute buy order with fees and slippage."""
        # Apply slippage
        execution_price = price * (1 + self.slippage_rate)

        # Calculate units
        units = position_size / execution_price

        # Apply fees
        fee = position_size * self.fee_rate
        total_cost = position_size + fee

        if total_cost > self.portfolio_state.cash:
            logger.debug(
                f"Insufficient cash for {asset_pair} buy: need ${total_cost:.2f}, have ${self.portfolio_state.cash:.2f}"
            )
            return

        # Update cash
        self.portfolio_state.cash -= total_cost

        # Create/average position (LONG)
        position = PortfolioPosition(
            asset_pair=asset_pair,
            entry_price=execution_price,
            units=units,
            entry_time=date,
            stop_loss=execution_price * 0.98,  # 2% stop-loss
            take_profit=execution_price * 1.05,  # 5% take-profit
            side="LONG",
        )
        self.portfolio_state.positions[asset_pair] = position

        # Record trade
        trade = {
            "asset_pair": asset_pair,
            "action": "BUY",
            "price": execution_price,
            "units": units,
            "cost": total_cost,
            "fee": fee,
            "date": date,
            "decision": decision,
        }
        self.portfolio_state.trade_history.append(trade)

        logger.info(
            f"BUY {asset_pair}: {units:.4f} units @ ${execution_price:.2f}, cost=${total_cost:.2f}"
        )

    def _execute_short(
        self,
        asset_pair: str,
        position_size: float,
        price: float,
        date: datetime,
        decision: Dict[str, Any],
    ) -> None:
        """Open a SHORT position (SELL to open)."""
        execution_price = price * (1 - self.slippage_rate)

        units = position_size / execution_price

        fee = position_size * self.fee_rate
        proceeds = position_size - fee  # Cash received from opening short

        # Update cash (receive proceeds)
        self.portfolio_state.cash += proceeds

        position = PortfolioPosition(
            asset_pair=asset_pair,
            entry_price=execution_price,
            units=-units,  # Negative units for short
            entry_time=date,
            stop_loss=execution_price * 1.02,  # reversed for short
            take_profit=execution_price * 0.95,  # reversed for short
            side="SHORT",
        )
        self.portfolio_state.positions[asset_pair] = position

        trade = {
            "asset_pair": asset_pair,
            "action": "SELL_OPEN",
            "price": execution_price,
            "units": -units,
            "proceeds": proceeds,
            "fee": fee,
            "date": date,
            "decision": decision,
        }
        self.portfolio_state.trade_history.append(trade)

        logger.info(
            f"OPEN SHORT {asset_pair}: {units:.4f} units @ ${execution_price:.2f}, proceeds=${proceeds:.2f}"
        )

    def _close_position(
        self,
        asset_pair: str,
        price: float,
        reason: str,
        date: Optional[datetime] = None,
    ) -> None:
        """Close an existing position."""
        if asset_pair not in self.portfolio_state.positions:
            return

        position = self.portfolio_state.positions[asset_pair]

        # Apply slippage (sell for LONG, buy-to-close for SHORT)
        if position.side == "SHORT":
            execution_price = price * (1 + self.slippage_rate)
        else:
            execution_price = price * (1 - self.slippage_rate)

        if position.side == "SHORT":
            units_abs = abs(position.units)
            cost = units_abs * execution_price
            fee = cost * self.fee_rate
            pnl = (position.entry_price - execution_price) * units_abs - fee

            # Update cash: pay to buy back
            self.portfolio_state.cash -= cost + fee
            pnl_pct = (
                (pnl / (position.entry_price * units_abs)) * 100
                if position.entry_price > 0
                else 0
            )
        else:
            # LONG close
            gross_proceeds = position.units * execution_price
            fee = gross_proceeds * self.fee_rate
            net_proceeds = gross_proceeds - fee

            self.portfolio_state.cash += net_proceeds

            cost = position.units * position.entry_price
            pnl = net_proceeds - cost
            pnl_pct = (pnl / cost) * 100 if cost != 0 else 0
            units_abs = position.units
            cost_basis = cost

        # Record trade
        trade_action = "SELL" if position.side == "LONG" else "BUY_CLOSE"

        trade = {
            "asset_pair": asset_pair,
            "action": trade_action,
            "price": execution_price,
            "units": position.units,
            "proceeds": None if position.side == "SHORT" else net_proceeds,
            "cost": cost if position.side == "SHORT" else cost_basis,
            "fee": fee,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "date": date,
            "reason": reason,
            "hold_time": (date - position.entry_time).days if date else None,
        }
        self.portfolio_state.trade_history.append(trade)

        # Remove position
        del self.portfolio_state.positions[asset_pair]

        logger.info(
            f"{trade_action} {asset_pair}: {position.units:.4f} units @ ${execution_price:.2f}, "
            f"P&L=${pnl:.2f} ({pnl_pct:.2f}%), reason={reason}"
        )

    def _close_all_positions(
        self, current_prices: Dict[str, float], date: datetime
    ) -> None:
        """Close all open positions."""
        for asset_pair in list(self.portfolio_state.positions.keys()):
            if asset_pair in current_prices:
                self._close_position(
                    asset_pair, current_prices[asset_pair], "portfolio_stop", date
                )

    def _check_portfolio_stop_loss(self, current_value: float) -> bool:
        """Check if portfolio-level stop-loss triggered."""
        max_drawdown = self.config.get("portfolio", {}).get("max_drawdown", 0.05)  # 5%

        if current_value < self.initial_balance * (1 - max_drawdown):
            return True

        return False

    def _calculate_portfolio_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive portfolio performance metrics."""
        if not self.portfolio_state.equity_curve:
            return {}

        # Extract equity curve data
        dates, values = zip(*self.portfolio_state.equity_curve)
        equity_series = pd.Series(values, index=dates)

        # Calculate returns
        returns = equity_series.pct_change().dropna()

        # Final value and return
        final_value = values[-1]
        total_return = (
            (final_value - self.initial_balance) / self.initial_balance
        ) * 100

        # Sharpe ratio (annualized)
        if len(returns) > 1 and returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0

        # Maximum drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100

        # Trade statistics
        total_trades = len(self.portfolio_state.trade_history)
        completed_trades = [t for t in self.portfolio_state.trade_history if "pnl" in t]
        winning_trades = [t for t in completed_trades if t["pnl"] > 0]

        win_rate = (
            (len(winning_trades) / len(completed_trades) * 100)
            if completed_trades
            else 0
        )
        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
        avg_loss = (
            np.mean([t["pnl"] for t in completed_trades if t["pnl"] < 0])
            if completed_trades
            else 0
        )

        # Per-asset attribution
        asset_attribution = self._calculate_asset_attribution()

        results = {
            "initial_value": self.initial_balance,
            "final_value": final_value,
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,
            "total_trades": total_trades,
            "completed_trades": len(completed_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "asset_attribution": asset_attribution,
            "equity_curve": self.portfolio_state.equity_curve,
            "trade_history": self.portfolio_state.trade_history,
        }

        return results

    def _calculate_asset_attribution(self) -> Dict[str, Dict[str, float]]:
        """Calculate per-asset performance contribution."""
        attribution = {}

        for asset_pair in self.asset_pairs:
            asset_trades = [
                t
                for t in self.portfolio_state.trade_history
                if t["asset_pair"] == asset_pair and "pnl" in t
            ]

            if not asset_trades:
                attribution[asset_pair] = {
                    "total_pnl": 0.0,
                    "num_trades": 0,
                    "win_rate": 0.0,
                }
                continue

            total_pnl = sum(t["pnl"] for t in asset_trades)
            winning = [t for t in asset_trades if t["pnl"] > 0]
            win_rate = (len(winning) / len(asset_trades) * 100) if asset_trades else 0

            attribution[asset_pair] = {
                "total_pnl": total_pnl,
                "num_trades": len(asset_trades),
                "win_rate": win_rate,
                "contribution_pct": (
                    (total_pnl / (self.initial_balance * 0.01))
                    if self.initial_balance > 0
                    else 0
                ),
            }

        return attribution
