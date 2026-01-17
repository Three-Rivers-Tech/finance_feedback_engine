"""
Kelly Criterion implementation for position sizing in trading systems.

Implements the Kelly Criterion formula for optimal position sizing based on
win rate and payoff ratio to maximize long-term growth of capital.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class KellyCriterionCalculator:
    """
    Calculator for position sizing using the Kelly Criterion formula.

    The Kelly Criterion determines the optimal fraction of capital to risk
    on each trade based on the win rate and payoff ratio (average win/average loss).
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the Kelly Criterion calculator.

        Args:
            config: Configuration dictionary containing Kelly Criterion settings
        """
        self.config = config
        self.kelly_config = config.get("kelly_criterion", {})

        # Kelly fraction cap to prevent overbetting
        self.kelly_fraction_cap = self.kelly_config.get("kelly_fraction_cap", 0.25)

        # Kelly fraction multiplier to reduce optimal bet size for safety
        self.kelly_fraction_multiplier = self.kelly_config.get(
            "kelly_fraction_multiplier", 0.5
        )

        # Minimum Kelly fraction to prevent zero position sizes
        self.min_kelly_fraction = self.kelly_config.get("min_kelly_fraction", 0.001)

        # Maximum position size in percentage of account
        self.max_position_size_pct = self.kelly_config.get(
            "max_position_size_pct", 0.10
        )

    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        payoff_ratio: Optional[float] = None,
    ) -> float:
        """
        Calculate the Kelly fraction based on win rate and payoff ratio.

        The Kelly Criterion formula is:
        f = (bp - q) / b

        Where:
        - f = Kelly fraction (optimal fraction of capital to risk)
        - b = payoff ratio (average win / average loss)
        - p = win rate (probability of winning)
        - q = 1 - p (probability of losing)

        Args:
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win: Average winning trade amount (positive value)
            avg_loss: Average losing trade amount (positive value)
            payoff_ratio: Pre-calculated payoff ratio (optional, will be calculated if not provided)

        Returns:
            Optimal Kelly fraction (0.0 to 1.0)
        """
        if payoff_ratio is None:
            # Validate avg_win first
            if avg_win <= 0:
                logger.error(
                    "Invalid avg_win=%s (<= 0). "
                    "This indicates no winning trades or invalid parameters. "
                    "Returning 0 to signal no trade.", avg_win
                )
                return 0.0  # Return 0 to signal "don't trade"

            if avg_loss < 0:
                logger.error(
                    "Invalid avg_loss=%s (< 0). "
                    "avg_loss should be a positive value. "
                    "Returning 0 to signal no trade.", avg_loss
                )
                return 0.0

            if avg_loss == 0:
                logger.warning("Average loss is zero, using large payoff ratio")
                payoff_ratio = 10.0  # Large number to avoid division by zero
            else:
                payoff_ratio = avg_win / avg_loss

        # Validate payoff_ratio (whether calculated or explicitly provided)
        if payoff_ratio <= 0:
            logger.error(
                "Invalid payoff_ratio=%s (<= 0). "
                "This indicates avg_win <= 0 or invalid parameters. "
                "Returning 0 to signal no trade.", payoff_ratio
            )
            return 0.0  # Return 0 to signal "don't trade"

        # Validate inputs
        if not (0 <= win_rate <= 1):
            logger.warning(
                "Win rate %s is outside valid range [0, 1], clipping to range", win_rate
            )
            win_rate = np.clip(win_rate, 0, 1)

        # Calculate Kelly fraction
        b = payoff_ratio
        p = win_rate
        q = 1 - p

        if b == 0:
            logger.critical(
                "Payoff ratio (b) is zero - this should have been caught earlier! "
                "Returning 0 to prevent division by zero."
            )
            return 0.0  # Return 0 to signal "don't trade"

        # Apply Kelly Criterion formula
        kelly_fraction = (b * p - q) / b

        # If Kelly is negative or zero, it means -EV or break-even trade - don't trade
        if kelly_fraction <= 0:
            logger.info(
                "Kelly fraction (%.4f) indicates -EV or break-even trade, "
                "returning 0 to signal no trade", kelly_fraction
            )
            return 0.0  # Return 0 to signal "don't trade" (not forced minimum)

        # Apply safety constraints (only for positive Kelly)
        kelly_fraction = min(kelly_fraction, self.kelly_fraction_cap)

        # Apply multiplier for safety
        kelly_fraction = kelly_fraction * self.kelly_fraction_multiplier

        # Ensure minimum fraction only for positive Kelly values
        kelly_fraction = max(kelly_fraction, self.min_kelly_fraction)

        return kelly_fraction

    def calculate_position_size(
        self,
        account_balance: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        current_price: float,
        payoff_ratio: Optional[float] = None,
        max_position_size_pct: Optional[float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate the optimal position size using the Kelly Criterion.

        Args:
            account_balance: Current account balance
            win_rate: Historical win rate (0.0 to 1.0)
            avg_win: Average winning trade amount
            avg_loss: Average losing trade amount
            current_price: Current asset price
            payoff_ratio: Pre-calculated payoff ratio (optional)
            max_position_size_pct: Maximum position size as percentage of account (optional)

        Returns:
            Tuple of (position_size_in_units, calculation_details)
        """
        # Calculate Kelly fraction
        kelly_fraction = self.calculate_kelly_fraction(
            win_rate, avg_win, avg_loss, payoff_ratio
        )

        # Apply maximum position size constraint
        max_pct = max_position_size_pct or self.max_position_size_pct
        kelly_fraction = min(kelly_fraction, max_pct)

        # Calculate position size in dollars
        position_size_dollars = account_balance * kelly_fraction

        # Convert to units of the asset
        if current_price <= 0:
            logger.error(
                f"Invalid current price: {current_price}, cannot calculate position size in units"
            )
            return 0.0, {
                "kelly_fraction": 0.0,
                "position_size_dollars": 0.0,
                "position_size_units": 0.0,
                "account_balance": account_balance,
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "current_price": current_price,
                "kelly_calculation_error": "Invalid current price",
            }

        position_size_units = position_size_dollars / current_price

        # Prepare calculation details
        calculation_details = {
            "kelly_fraction": kelly_fraction,
            "position_size_dollars": position_size_dollars,
            "position_size_units": position_size_units,
            "account_balance": account_balance,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "current_price": current_price,
            "payoff_ratio": payoff_ratio or (avg_win / avg_loss if avg_loss > 0 else 0),
            "kelly_fraction_cap": self.kelly_fraction_cap,
            "kelly_fraction_multiplier": self.kelly_fraction_multiplier,
            "max_position_size_pct": max_pct,
        }

        logger.debug(f"Kelly Criterion calculation: {calculation_details}")

        return position_size_units, calculation_details

    def calculate_dynamic_kelly_fraction(
        self, historical_trades: list, lookback_period: int = 50
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate Kelly fraction based on recent trading performance.

        Args:
            historical_trades: List of historical trade dictionaries
            lookback_period: Number of recent trades to consider

        Returns:
            Tuple of (kelly_fraction, performance_metrics)
        """
        if not historical_trades:
            logger.info(
                "No historical trades available, returning default Kelly fraction"
            )
            return self.min_kelly_fraction, {
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "trades_analyzed": 0,
            }

        # Consider only recent trades
        recent_trades = historical_trades[-lookback_period:]

        # Calculate performance metrics
        wins = [t for t in recent_trades if t.get("pnl", 0) > 0]
        losses = [t for t in recent_trades if t.get("pnl", 0) < 0]

        win_rate = len(wins) / len(recent_trades) if recent_trades else 0.0
        avg_win = np.mean([abs(t.get("pnl", 0)) for t in wins]) if wins else 0.0
        avg_loss = np.mean([abs(t.get("pnl", 0)) for t in losses]) if losses else 0.0

        # Calculate Kelly fraction
        kelly_fraction = self.calculate_kelly_fraction(win_rate, avg_win, avg_loss)

        performance_metrics = {
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "trades_analyzed": len(recent_trades),
            "total_wins": len(wins),
            "total_losses": len(losses),
            "kelly_fraction": kelly_fraction,
        }

        logger.info(
            f"Dynamic Kelly calculation: win_rate={win_rate:.3f}, "
            f"avg_win=${avg_win:.2f}, avg_loss=${avg_loss:.2f}, "
            f"kelly_fraction={kelly_fraction:.4f}"
        )

        return kelly_fraction, performance_metrics

    def adjust_for_market_conditions(
        self,
        kelly_fraction: float,
        volatility: Optional[float] = None,
        correlation: Optional[float] = None,
        trend_strength: Optional[float] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Adjust the Kelly fraction based on current market conditions.

        Args:
            kelly_fraction: Base Kelly fraction
            volatility: Current market volatility (0.0 to 1.0)
            correlation: Market correlation (0.0 to 1.0)
            trend_strength: Trend strength (-1.0 to 1.0)

        Returns:
            Tuple of (adjusted_kelly_fraction, adjustment_details)
        """
        adjustment_details = {
            "original_kelly_fraction": kelly_fraction,
            "volatility": volatility,
            "correlation": correlation,
            "trend_strength": trend_strength,
            "volatility_adjustment": 1.0,
            "correlation_adjustment": 1.0,
            "trend_adjustment": 1.0,
        }

        adjusted_fraction = kelly_fraction

        # Adjust for volatility (reduce position size in high volatility)
        if volatility is not None:
            # Reduce position size when volatility is high
            volatility_factor = max(
                0.1, 1.0 - volatility
            )  # Reduce up to 90% in high volatility
            adjusted_fraction *= volatility_factor
            adjustment_details["volatility_adjustment"] = volatility_factor

        # Adjust for correlation (reduce position size when markets are highly correlated)
        if correlation is not None:
            # Reduce position size when correlation is high
            correlation_factor = max(
                0.2, 1.0 - correlation
            )  # Reduce up to 80% in high correlation
            adjusted_fraction *= correlation_factor
            adjustment_details["correlation_adjustment"] = correlation_factor

        # Adjust for trend strength (increase position size in strong trends)
        if trend_strength is not None:
            # Adjust position size based on trend strength (can be positive or negative)
            trend_factor = 1.0 + (abs(trend_strength) * 0.5)  # Up to 50% adjustment
            if trend_strength < 0:
                trend_factor = 1.0 / trend_factor  # Inverse for negative trends
            adjusted_fraction *= trend_factor
            adjustment_details["trend_adjustment"] = trend_factor

        # Ensure the adjusted fraction is within bounds
        adjusted_fraction = max(
            self.min_kelly_fraction, min(adjusted_fraction, self.kelly_fraction_cap)
        )

        adjustment_details["adjusted_kelly_fraction"] = adjusted_fraction

        logger.debug(f"Market condition adjustment: {adjustment_details}")

        return adjusted_fraction, adjustment_details


# Example usage and testing
if __name__ == "__main__":
    # Example configuration
    config = {
        "kelly_criterion": {
            "kelly_fraction_cap": 0.25,
            "kelly_fraction_multiplier": 0.5,
            "min_kelly_fraction": 0.001,
            "max_position_size_pct": 0.10,
        }
    }

    # Initialize calculator
    kelly_calc = KellyCriterionCalculator(config)

    # Example 1: Basic Kelly calculation
    win_rate = 0.6  # 60% win rate
    avg_win = 150.0  # Average win $150
    avg_loss = 100.0  # Average loss $100
    account_balance = 10000.0  # $10,000 account
    current_price = 100.0  # Current asset price $100

    position_size, details = kelly_calc.calculate_position_size(
        account_balance, win_rate, avg_win, avg_loss, current_price
    )

    print(f"Position size: {position_size:.4f} units")
    print(f"Details: {details}")

    # Example 2: Dynamic Kelly with historical trades
    historical_trades = [
        {"pnl": 150.0},
        {"pnl": -50.0},
        {"pnl": 200.0},
        {"pnl": -75.0},
        {"pnl": 120.0},
        {"pnl": 180.0},
        {"pnl": -30.0},
        {"pnl": -100.0},
        {"pnl": 250.0},
        {"pnl": 90.0},
    ]

    kelly_fraction, metrics = kelly_calc.calculate_dynamic_kelly_fraction(
        historical_trades
    )
    print(f"Dynamic Kelly fraction: {kelly_fraction:.4f}")
    print(f"Metrics: {metrics}")

    # Example 3: Market condition adjustment
    adjusted_fraction, adj_details = kelly_calc.adjust_for_market_conditions(
        kelly_fraction, volatility=0.3, correlation=0.6, trend_strength=0.4
    )
    print(f"Adjusted Kelly fraction: {adjusted_fraction:.4f}")
    print(f"Adjustment details: {adj_details}")
