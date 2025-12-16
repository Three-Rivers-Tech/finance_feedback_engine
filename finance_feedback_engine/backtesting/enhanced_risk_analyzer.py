"""Enhanced risk analysis for backtesting with advanced metrics and validation."""

import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class EnhancedRiskAnalyzer:
    """
    Advanced risk analysis for backtesting with sophisticated metrics and validation.

    This class provides enhanced risk management features including:
    - Advanced volatility measures (including ATR-based volatility)
    - Tail risk analysis (Value at Risk, Expected Shortfall)
    - Correlation analysis between trades/positions
    - Risk-adjusted performance metrics (Calmar, Sortino, etc.)
    - Drawdown analysis with duration and recovery metrics
    """

    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize the enhanced risk analyzer.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe ratio calculations (default 2%)
        """
        self.risk_free_rate = risk_free_rate

    def calculate_advanced_metrics(
        self, equity_curve: List[float], trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate advanced risk-adjusted metrics from equity curve and trade history.

        Args:
            equity_curve: List of portfolio values over time
            trades: List of completed trades with P&L information

        Returns:
            Dictionary with advanced risk metrics
        """
        if not equity_curve or len(equity_curve) < 2:
            return {}

        # Convert to pandas Series for easier calculations
        equity_series = pd.Series(equity_curve)

        # Calculate returns
        returns = equity_series.pct_change().dropna()

        # Basic metrics
        metrics = self._calculate_basic_metrics(equity_curve, returns)

        # Advanced risk metrics
        metrics.update(self._calculate_volatility_metrics(returns))
        metrics.update(self._calculate_tail_risk_metrics(returns))
        metrics.update(self._calculate_drawdown_metrics(equity_curve))
        metrics.update(self._calculate_trade_correlation_metrics(trades))

        # Risk-adjusted return metrics
        metrics.update(self._calculate_risk_adjusted_returns(returns))

        # Concentration risk metrics
        metrics.update(self._calculate_concentration_risk(trades))

        return metrics

    def _calculate_basic_metrics(
        self, equity_curve: List[float], returns: pd.Series
    ) -> Dict[str, Any]:
        """Calculate basic performance metrics."""
        initial_value = equity_curve[0]
        final_value = equity_curve[-1]

        total_return = (final_value - initial_value) / initial_value
        total_trades = len([t for t in returns if not pd.isna(t)])
        winning_trades = len([t for t in returns if t > 0])
        losing_trades = len([t for t in returns if t < 0])

        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0.0

        return {
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "avg_win": (
                np.mean([t for t in returns if t > 0]) * 100
                if winning_trades > 0
                else 0.0
            ),
            "avg_loss": (
                np.mean([t for t in returns if t < 0]) * 100
                if losing_trades > 0
                else 0.0
            ),
        }

    def _calculate_volatility_metrics(self, returns: pd.Series) -> Dict[str, Any]:
        """Calculate volatility-based metrics."""
        if returns.empty:
            return {"volatility": 0.0, "volatility_annualized": 0.0}

        volatility = returns.std()
        volatility_annualized = volatility * np.sqrt(252)  # Assuming daily returns

        # Calculate rolling volatility (20-day window)
        rolling_volatility = returns.rolling(window=20).std().dropna()
        avg_rolling_vol = (
            rolling_volatility.mean() if not rolling_volatility.empty else 0.0
        )

        # Calculate ATR-like volatility if we had OHLC data, but use returns std for now
        atr_volatility = self._calculate_atr_volatility(returns)

        return {
            "volatility": volatility,
            "volatility_annualized": volatility_annualized,
            "avg_rolling_volatility": avg_rolling_vol,
            "atr_volatility": atr_volatility,
        }

    def _calculate_atr_volatility(self, returns: pd.Series) -> float:
        """Calculate ATR-like volatility metric from returns."""
        if returns.empty:
            return 0.0

        # Calculate True Range equivalent from returns
        abs_returns = returns.abs()
        atr_vol = abs_returns.mean() * np.sqrt(252)  # Annualized
        return atr_vol

    def _calculate_tail_risk_metrics(self, returns: pd.Series) -> Dict[str, Any]:
        """Calculate tail risk metrics (VaR, Expected Shortfall)."""
        if returns.empty:
            return {
                "var_95": 0.0,
                "var_99": 0.0,
                "expected_shortfall_95": 0.0,
                "expected_shortfall_99": 0.0,
            }

        # Calculate Value at Risk (VaR) at 95% and 99% confidence
        var_95 = returns.quantile(0.05)
        var_99 = returns.quantile(0.01)

        # Calculate Expected Shortfall (Conditional VaR)
        worst_5_percent = returns[returns <= returns.quantile(0.05)]
        worst_1_percent = returns[returns <= returns.quantile(0.01)]

        expected_shortfall_95 = (
            worst_5_percent.mean() if not worst_5_percent.empty else 0.0
        )
        expected_shortfall_99 = (
            worst_1_percent.mean() if not worst_1_percent.empty else 0.0
        )

        return {
            "var_95": var_95,
            "var_99": var_99,
            "expected_shortfall_95": expected_shortfall_95,
            "expected_shortfall_99": expected_shortfall_99,
        }

    def _calculate_drawdown_metrics(self, equity_curve: List[float]) -> Dict[str, Any]:
        """Calculate drawdown metrics."""
        if not equity_curve:
            return {
                "max_drawdown": 0.0,
                "max_drawdown_pct": 0.0,
                "drawdown_duration": 0,
                "recovery_factor": 0.0,
            }

        curve = pd.Series(equity_curve)
        peak = curve.expanding(min_periods=1).max()
        drawdown = (curve - peak) / peak

        max_drawdown_abs = drawdown.min()
        max_drawdown_pct = max_drawdown_abs * 100

        # Calculate drawdown duration (in periods)
        drawdown_duration = self._calculate_drawdown_duration(drawdown)

        # Recovery factor: return / abs(max_drawdown)
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        recovery_factor = (
            abs(total_return / max_drawdown_abs) if max_drawdown_abs != 0 else 0.0
        )

        # Ulcer Index - measures severity and duration of drawdowns
        ulcer_index = self._calculate_ulcer_index(equity_curve)

        return {
            "max_drawdown": max_drawdown_abs,
            "max_drawdown_pct": max_drawdown_pct,
            "drawdown_duration": drawdown_duration,
            "recovery_factor": recovery_factor,
            "ulcer_index": ulcer_index,
        }

    def _calculate_drawdown_duration(self, drawdown: pd.Series) -> int:
        """Calculate maximum drawdown duration."""
        # Find periods where drawdown is at maximum
        drawdown_duration = 0
        current_duration = 0

        for dd in drawdown:
            if dd < 0:  # In drawdown
                current_duration += 1
                drawdown_duration = max(drawdown_duration, current_duration)
            else:  # Out of drawdown
                current_duration = 0

        return drawdown_duration

    def _calculate_ulcer_index(self, equity_curve: List[float]) -> float:
        """Calculate Ulcer Index - measure of risk-adjusted return."""
        if len(equity_curve) < 2:
            return 0.0

        curve = pd.Series(equity_curve)
        peak = curve.expanding(min_periods=1).max()
        drawdown_percent = 100 * (curve - peak) / peak

        # Calculate squared drawdowns
        squared_drawdowns = drawdown_percent**2

        # Ulcer Index is the square root of the average of squared drawdowns
        ulcer_index = np.sqrt(squared_drawdowns.mean())

        return ulcer_index

    def _calculate_risk_adjusted_returns(self, returns: pd.Series) -> Dict[str, Any]:
        """Calculate risk-adjusted return metrics."""
        if returns.empty:
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "treynor_ratio": 0.0,
            }

        # Annualized return
        avg_return = returns.mean()
        annualized_return = avg_return * 252  # Assuming daily returns

        # Sharpe Ratio: (Return - Risk Free Rate) / Volatility
        volatility = returns.std()
        if volatility > 0:
            sharpe_ratio = (annualized_return - self.risk_free_rate) / (
                volatility * np.sqrt(252)
            )
        else:
            sharpe_ratio = 0.0

        # Sortino Ratio: Similar to Sharpe, but uses downside deviation
        downside_returns = returns[returns < 0]  # Only negative returns
        if len(downside_returns) > 0:
            downside_deviation = downside_returns.std()
            if downside_deviation > 0:
                sortino_ratio = (annualized_return - self.risk_free_rate) / (
                    downside_deviation * np.sqrt(252)
                )
            else:
                sortino_ratio = 0.0
        else:
            sortino_ratio = 0.0  # No downside returns

        # For Calmar and Treynor ratios, we need max drawdown (calculated in drawdown_metrics)
        # But we'll calculate it here as well for completeness
        curve = returns + 1
        cumulative = curve.cumprod()
        peak = cumulative.expanding().max()
        drawdown = (cumulative - peak) / peak
        max_drawdown = drawdown.min() if not drawdown.empty else 0.0

        # Calmar Ratio: Annualized return / Max drawdown
        calmar_ratio = (
            annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0
        )

        # Treynor Ratio: (Return - Risk Free Rate) / Beta
        # For now, assume beta is 1.0 (market correlation) when not available
        treynor_ratio = (
            annualized_return - self.risk_free_rate
        ) / 1.0  # Assuming beta=1.0

        return {
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "treynor_ratio": treynor_ratio,
        }

    def _calculate_trade_correlation_metrics(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate correlation metrics between trades."""
        if not trades:
            return {}

        # Extract P&L and other metrics from trades
        pnl_values = []
        asset_types = []
        holding_periods = []

        for trade in trades:
            if trade.get("pnl_value") is not None:
                pnl_values.append(trade["pnl_value"])

            if trade.get("asset_pair"):
                # Classify asset types
                asset_pair = str(trade["asset_pair"]).upper()
                if "BTC" in asset_pair or "ETH" in asset_pair:
                    asset_types.append("crypto")
                elif any(
                    fx in asset_pair for fx in ["USD", "EUR", "GBP", "JPY", "CHF"]
                ):
                    asset_types.append("forex")
                else:
                    asset_types.append("other")

            if trade.get("holding_period_hours"):
                holding_periods.append(trade["holding_period_hours"])

        # Calculate trade-to-trade correlation
        correlation_metrics = {}
        if len(pnl_values) > 1:
            # Convert to returns if possible
            returns_series = pd.Series(pnl_values).pct_change().dropna()
            if len(returns_series) > 1:
                correlation_metrics["pnl_autocorrelation"] = returns_series.autocorr(
                    lag=1
                )
            else:
                correlation_metrics["pnl_autocorrelation"] = 0.0

        # Calculate concentration metrics
        if asset_types:
            unique_assets = set(asset_types)
            correlation_metrics["num_asset_types"] = len(unique_assets)

            # Calculate asset concentration (Herfindahl-Hirschman Index)
            asset_counts = {}
            for asset_type in asset_types:
                asset_counts[asset_type] = asset_counts.get(asset_type, 0) + 1

            total_trades = len(trades)
            if total_trades > 0:
                hhi = sum(
                    [(count / total_trades) ** 2 for count in asset_counts.values()]
                )
                correlation_metrics["concentration_hhi"] = hhi
            else:
                correlation_metrics["concentration_hhi"] = 0.0

        return correlation_metrics

    def _calculate_concentration_risk(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate concentration risk metrics."""
        if not trades:
            return {}

        # Calculate position size concentration
        position_sizes = [
            abs(trade.get("position_size", 0))
            for trade in trades
            if trade.get("position_size") is not None
        ]
        if position_sizes:
            total_position_size = sum(position_sizes)
            if total_position_size > 0:
                largest_position = max(position_sizes)
                concentration_ratio = largest_position / total_position_size
            else:
                concentration_ratio = 0.0
        else:
            concentration_ratio = 0.0

        return {
            "position_concentration_ratio": concentration_ratio,
        }

    def validate_risk_parameters(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate risk parameters against backtesting configuration.

        Args:
            config: Configuration dictionary with risk parameters

        Returns:
            List of validation errors or warnings
        """
        errors = []

        # Validate stop loss parameters
        stop_loss_pct = config.get("stop_loss_percentage", 0.02)
        if not (0.001 <= stop_loss_pct <= 0.5):  # 0.1% to 50%
            errors.append(
                f"Stop loss percentage ({stop_loss_pct:.3f}) should be between 0.1% and 50%"
            )

        # Validate take profit parameters
        take_profit_pct = config.get("take_profit_percentage", 0.05)
        if not (0.001 <= take_profit_pct <= 1.0):  # 0.1% to 100%
            errors.append(
                f"Take profit percentage ({take_profit_pct:.3f}) should be between 0.1% and 100%"
            )

        # Validate risk per trade
        risk_per_trade = config.get("risk_per_trade", 0.02)
        if not (0.001 <= risk_per_trade <= 0.1):  # 0.1% to 10%
            errors.append(
                f"Risk per trade ({risk_per_trade:.3f}) should be between 0.1% and 10%"
            )

        # Validate maximum daily trades
        max_daily_trades = config.get("max_daily_trades", 20)
        if max_daily_trades <= 0:
            errors.append(
                f"Maximum daily trades ({max_daily_trades}) should be positive"
            )

        # Validate correlation threshold
        correlation_threshold = config.get("correlation_threshold", 0.7)
        if not (0.0 <= correlation_threshold <= 1.0):
            errors.append(
                f"Correlation threshold ({correlation_threshold:.3f}) should be between 0.0 and 1.0"
            )

        return errors
