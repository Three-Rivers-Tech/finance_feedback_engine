"""Performance analytics and visualization module for backtesting results."""

import base64
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)


class BacktestPerformanceAnalyzer:
    """
    Performance analysis and visualization for backtesting results.

    Provides analytical tools to understand strategy performance,
    risk characteristics, and areas for improvement.
    """

    def __init__(self):
        # Set up plotting style
        plt.style.use("seaborn-v0_8")
        sns.set_palette("husl")

    def analyze_strategy_performance(
        self, backtest_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze strategy performance and generate key insights.

        Args:
            backtest_results: Results from the backtester

        Returns:
            Dictionary with performance analysis insights
        """
        metrics = backtest_results.get("metrics", {})
        trades = backtest_results.get("trades", [])
        equity_curve = backtest_results.get("backtest_config", {}).get(
            "equity_curve", []
        )

        analysis = {}

        # Performance consistency analysis
        analysis["consistency"] = self._analyze_consistency(
            metrics, trades, equity_curve
        )

        # Risk-return profile
        analysis["risk_return_profile"] = self._analyze_risk_return_profile(metrics)

        # Trade-level analysis
        analysis["trade_analysis"] = self._analyze_trades(trades)

        # Market condition analysis (if we had market data)
        analysis["market_condition_analysis"] = self._analyze_market_conditions(trades)

        # Drawdown analysis
        analysis["drawdown_analysis"] = self._analyze_drawdowns(equity_curve)

        return analysis

    def _analyze_consistency(
        self,
        metrics: Dict[str, Any],
        trades: List[Dict[str, Any]],
        equity_curve: List[float],
    ) -> Dict[str, Any]:
        """Analyze performance consistency over time."""
        consistency_metrics = {}

        # Calculate rolling metrics
        if (
            len(equity_curve) > 60
        ):  # Need at least 60 points for meaningful rolling analysis
            series = pd.Series(equity_curve)
            returns = series.pct_change().dropna()

            # Rolling Sharpe ratio (30-period)
            if len(returns) >= 30:
                rolling_returns = returns.rolling(window=30)
                rolling_sharpe = (
                    (rolling_returns.mean() / rolling_returns.std()) * np.sqrt(252)
                    if rolling_returns.std().min() > 0
                    else pd.Series([np.nan] * len(returns))
                )

                consistency_metrics["avg_rolling_sharpe"] = (
                    rolling_sharpe.dropna().mean()
                )
                consistency_metrics["rolling_sharpe_stdev"] = (
                    rolling_sharpe.dropna().std()
                )

        # Trade consistency
        if len(trades) > 0:
            # Group trades by time period and analyze consistency
            pnl_values = [
                t.get("pnl_value", 0) for t in trades if t.get("pnl_value") is not None
            ]
            if pnl_values:
                consistency_metrics["pnl_stdev"] = np.std(pnl_values)
                consistency_metrics["pnl_mean"] = np.mean(pnl_values)
                consistency_metrics["pnl_coefficient_of_variation"] = (
                    consistency_metrics["pnl_stdev"]
                    / abs(consistency_metrics["pnl_mean"])
                    if consistency_metrics["pnl_mean"] != 0
                    else float("inf")
                )

        return consistency_metrics

    def _analyze_risk_return_profile(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the risk-return profile of the strategy."""
        profile = {}

        # Sharpe ratio analysis
        sharpe_ratio = metrics.get("sharpe_ratio", 0)
        sortino_ratio = metrics.get("sortino_ratio", 0)

        profile["sharpe_quality"] = self._rate_ratio_quality(sharpe_ratio, "Sharpe")
        profile["sortino_quality"] = self._rate_ratio_quality(sortino_ratio, "Sortino")

        # Max drawdown analysis
        max_drawdown_pct = abs(metrics.get("max_drawdown_pct", 0))
        profile["drawdown_risk_level"] = self._rate_drawdown_risk(max_drawdown_pct)

        # Return quality
        annualized_return_pct = metrics.get("annualized_return_pct", 0)
        profile["return_quality"] = self._rate_return_quality(
            annualized_return_pct, max_drawdown_pct
        )

        # Calmar ratio (return / max drawdown)
        if max_drawdown_pct != 0:
            calmar_ratio = annualized_return_pct / max_drawdown_pct
            profile["calmar_ratio"] = calmar_ratio
            profile["calmar_quality"] = self._rate_ratio_quality(calmar_ratio, "Calmar")
        else:
            profile["calmar_ratio"] = float("inf")
            profile["calmar_quality"] = "Excellent (no drawdown)"

        return profile

    def _analyze_trades(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze individual trades for patterns and insights."""
        if not trades:
            return {}

        # Extract P&L values
        pnl_values = [
            t.get("pnl_value", 0) for t in trades if t.get("pnl_value") is not None
        ]
        positive_pnl = [p for p in pnl_values if p > 0]
        negative_pnl = [p for p in pnl_values if p < 0]

        trade_analysis = {
            "total_trades": len(trades),
            "winning_trades": len(positive_pnl),
            "losing_trades": len(negative_pnl),
            "breakeven_trades": len(trades) - len(positive_pnl) - len(negative_pnl),
        }

        if pnl_values:
            trade_analysis["avg_pnl"] = np.mean(pnl_values)
            trade_analysis["pnl_stdev"] = np.std(pnl_values)
            trade_analysis["best_trade"] = max(pnl_values) if pnl_values else 0
            trade_analysis["worst_trade"] = min(pnl_values) if pnl_values else 0

        if positive_pnl:
            trade_analysis["avg_win"] = np.mean(positive_pnl)

        if negative_pnl:
            trade_analysis["avg_loss"] = np.mean(negative_pnl)

        # Win rate
        if len(pnl_values) > 0:
            trade_analysis["win_rate"] = len(positive_pnl) / len(pnl_values) * 100

        # Profit factor (gross profit / gross loss)
        if negative_pnl:
            gross_profit = sum(positive_pnl) if positive_pnl else 0
            gross_loss = abs(sum(negative_pnl))
            if gross_loss > 0:
                trade_analysis["profit_factor"] = gross_profit / gross_loss
            else:
                trade_analysis["profit_factor"] = float("inf")
        else:
            trade_analysis["profit_factor"] = float("inf") if positive_pnl else 0

        # Expectancy (average win * win rate - average loss * loss rate)
        win_rate = len(positive_pnl) / len(pnl_values) if pnl_values else 0
        loss_rate = len(negative_pnl) / len(pnl_values) if pnl_values else 0
        avg_win = np.mean(positive_pnl) if positive_pnl else 0
        avg_loss = abs(np.mean(negative_pnl)) if negative_pnl else 0

        trade_analysis["expectancy"] = (avg_win * win_rate) - (avg_loss * loss_rate)

        return trade_analysis

    def _analyze_market_conditions(
        self, trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze performance under different market conditions (conceptual)."""
        # In a more advanced implementation, this would analyze performance
        # under different market regimes (trending, ranging, high/low volatility)
        # For now, we'll provide a framework

        market_analysis = {
            "regime_performance": {
                "trending_up": {"trades": 0, "avg_pnl": 0, "win_rate": 0},
                "trending_down": {"trades": 0, "avg_pnl": 0, "win_rate": 0},
                "ranging": {"trades": 0, "avg_pnl": 0, "win_rate": 0},
            }
        }

        # This would require market regime detection which we don't have in the simple trade data
        # For now, we'll just return the structure
        return market_analysis

    def _analyze_drawdowns(self, equity_curve: List[float]) -> Dict[str, Any]:
        """Analyze drawdown characteristics."""
        if len(equity_curve) < 2:
            return {}

        equity_series = pd.Series(equity_curve)
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak
        drawdown_pct = drawdown * 100

        drawdown_analysis = {
            "max_drawdown_pct": drawdown.min() * 100,
            "avg_drawdown_pct": (
                drawdown[drawdown < 0].mean() * 100 if (drawdown < 0).any() else 0
            ),
            "max_drawdown_duration": self._calculate_drawdown_duration(drawdown),
        }

        # Count number of drawdowns exceeding certain thresholds
        drawdown_analysis["num_drawdowns_gt_5pct"] = len(drawdown[drawdown < -0.05])
        drawdown_analysis["num_drawdowns_gt_10pct"] = len(drawdown[drawdown < -0.10])

        return drawdown_analysis

    def _calculate_drawdown_duration(self, drawdown_series: pd.Series) -> int:
        """Calculate maximum drawdown duration in periods."""
        # Find sequences where drawdown is negative (in drawdown)
        in_drawdown = drawdown_series < 0
        if not in_drawdown.any():
            return 0

        # Calculate consecutive periods in drawdown
        durations = []
        current_duration = 0

        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
            else:
                if current_duration > 0:
                    durations.append(current_duration)
                    current_duration = 0

        # Add the final duration if we end in a drawdown
        if current_duration > 0:
            durations.append(current_duration)

        return max(durations) if durations else 0

    def _rate_ratio_quality(self, ratio: float, ratio_name: str) -> str:
        """Rate the quality of a risk-adjusted return ratio."""
        if ratio >= 2.0:
            return f"Excellent {ratio_name} Ratio"
        elif ratio >= 1.5:
            return f"Good {ratio_name} Ratio"
        elif ratio >= 1.0:
            return f"Adequate {ratio_name} Ratio"
        elif ratio >= 0.5:
            return f"Suboptimal {ratio_name} Ratio"
        else:
            return f"Poor {ratio_name} Ratio"

    def _rate_drawdown_risk(self, max_drawdown_pct: float) -> str:
        """Rate the level of drawdown risk."""
        if max_drawdown_pct <= 5:
            return "Low Drawdown Risk"
        elif max_drawdown_pct <= 10:
            return "Moderate Drawdown Risk"
        elif max_drawdown_pct <= 20:
            return "High Drawdown Risk"
        else:
            return "Very High Drawdown Risk"

    def _rate_return_quality(
        self, annual_return_pct: float, max_drawdown_pct: float
    ) -> str:
        """Rate the quality of returns relative to risk."""
        if max_drawdown_pct == 0:
            return "Excellent Return Quality (No Drawdown)"

        ratio = annual_return_pct / max_drawdown_pct

        if ratio >= 3.0:
            return "Excellent Return Quality"
        elif ratio >= 2.0:
            return "Good Return Quality"
        elif ratio >= 1.0:
            return "Adequate Return Quality"
        elif ratio >= 0.5:
            return "Poor Return Quality"
        else:
            return "Very Poor Return Quality"

    def generate_performance_report(self, backtest_results: Dict[str, Any]) -> str:
        """
        Generate a comprehensive performance report.

        Args:
            backtest_results: Results from the backtester

        Returns:
            Formatted performance report string
        """
        analysis = self.analyze_strategy_performance(backtest_results)
        metrics = backtest_results.get("metrics", {})

        report = ["STRATEGY PERFORMANCE ANALYSIS REPORT", "=" * 50, ""]

        # Summary statistics
        report.extend(
            [
                "SUMMARY STATISTICS:",
                "-" * 20,
                f"Total Return: {metrics.get('total_return_pct', 0):.2f}%",
                f"Annualized Return: {metrics.get('annualized_return_pct', 0):.2f}%",
                f"Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2f}%",
                f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.3f}",
                f"Win Rate: {metrics.get('win_rate', 0):.2f}%",
                f"Total Trades: {metrics.get('total_trades', 0)}",
                f"Average Win: ${metrics.get('avg_win', 0):.2f}",
                f"Average Loss: ${metrics.get('avg_loss', 0):.2f}",
                "",
            ]
        )

        # Consistency analysis
        consistency = analysis.get("consistency", {})
        if consistency:
            report.extend(
                [
                    "CONSISTENCY ANALYSIS:",
                    "-" * 20,
                ]
            )
            for key, value in consistency.items():
                if isinstance(value, float):
                    report.append(f"{key}: {value:.4f}")
                else:
                    report.append(f"{key}: {value}")
            report.append("")

        # Risk-return profile
        risk_return = analysis.get("risk_return_profile", {})
        if risk_return:
            report.extend(
                [
                    "RISK-RETURN PROFILE:",
                    "-" * 20,
                ]
            )
            for key, value in risk_return.items():
                report.append(f"{key}: {value}")
            report.append("")

        # Trade analysis
        trade_analysis = analysis.get("trade_analysis", {})
        if trade_analysis:
            report.extend(
                [
                    "TRADE ANALYSIS:",
                    "-" * 20,
                ]
            )
            for key, value in trade_analysis.items():
                if isinstance(value, float):
                    report.append(f"{key}: {value:.4f}")
                else:
                    report.append(f"{key}: {value}")
            report.append("")

        # Drawdown analysis
        dd_analysis = analysis.get("drawdown_analysis", {})
        if dd_analysis:
            report.extend(
                [
                    "DRAWDOWN ANALYSIS:",
                    "-" * 20,
                ]
            )
            for key, value in dd_analysis.items():
                if isinstance(value, float):
                    report.append(f"{key}: {value:.4f}")
                else:
                    report.append(f"{key}: {value}")
            report.append("")

        return "\n".join(report)

    def create_visualization(
        self, backtest_results: Dict[str, Any], plot_type: str = "equity_curve"
    ) -> Optional[str]:
        """
        Create a visualization of backtest results.

        Args:
            backtest_results: Results from the backtester
            plot_type: Type of visualization ('equity_curve', 'pnl_distribution', 'monthly_returns')

        Returns:
            Base64 encoded string of the plot image, or None if matplotlib not available
        """
        try:
            equity_curve = backtest_results.get("backtest_config", {}).get(
                "equity_curve", []
            )
            trades = backtest_results.get("trades", [])

            if plot_type == "equity_curve":
                return self._plot_equity_curve(equity_curve)
            elif plot_type == "pnl_distribution":
                return self._plot_pnl_distribution(trades)
            elif plot_type == "monthly_returns":
                return self._plot_monthly_returns(equity_curve)
            else:
                logger.warning(f"Unknown plot type: {plot_type}")
                return None
        except ImportError:
            logger.warning("Matplotlib not available for visualization")
            return None
        except Exception as e:
            logger.error(f"Error creating visualization: {e}")
            return None

    def _plot_equity_curve(self, equity_curve: List[float]) -> str:
        """Create equity curve plot."""
        fig, ax = plt.subplots(figsize=(12, 6))

        # Convert to pandas Series for easier plotting
        equity_series = pd.Series(equity_curve)
        returns = equity_series.pct_change()

        # Calculate drawdown
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak

        ax.plot(
            equity_series.index,
            equity_series.values,
            label="Equity Curve",
            linewidth=2.0,
        )
        ax.fill_between(
            equity_series.index,
            equity_series.values,
            peak.values,
            where=(equity_series.values < peak.values),
            color="red",
            alpha=0.3,
            label="Drawdown",
        )

        ax.set_title("Equity Curve Over Time")
        ax.set_xlabel("Time Period")
        ax.set_ylabel("Portfolio Value ($)")
        ax.legend()
        ax.grid(True, linestyle="--", alpha=0.6)

        # Save to bytes
        img_buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
        img_buffer.seek(0)

        # Encode to base64
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close(fig)  # Close to free memory

        return img_str

    def _plot_pnl_distribution(self, trades: List[Dict[str, Any]]) -> str:
        """Create P&L distribution histogram."""
        pnl_values = [
            t.get("pnl_value", 0) for t in trades if t.get("pnl_value") is not None
        ]

        if not pnl_values:
            # Create empty plot if no data
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(
                0.5,
                0.5,
                "No P&L data available",
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax.transAxes,
                fontsize=14,
            )
            ax.set_title("P&L Distribution")
            ax.set_xlabel("P&L ($)")
            ax.set_ylabel("Frequency")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))

            ax.hist(pnl_values, bins=30, edgecolor="black", alpha=0.7)
            ax.set_title("Distribution of Trade P&L")
            ax.set_xlabel("P&L ($)")
            ax.set_ylabel("Frequency")
            ax.grid(True, linestyle="--", alpha=0.6)

            # Add statistics to the plot
            avg_pnl = np.mean(pnl_values)
            std_pnl = np.std(pnl_values)
            ax.axvline(
                avg_pnl, color="red", linestyle="--", label=f"Mean: ${avg_pnl:.2f}"
            )
            ax.legend()

        # Save to bytes
        img_buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
        img_buffer.seek(0)

        # Encode to base64
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close(fig)  # Close to free memory

        return img_str

    def _plot_monthly_returns(self, equity_curve: List[float]) -> str:
        """Create monthly returns heatmap."""
        if len(equity_curve) < 30:  # Need at least 30 data points
            # Create empty plot if insufficient data
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(
                0.5,
                0.5,
                "Insufficient data for monthly returns",
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax.transAxes,
                fontsize=14,
            )
            ax.set_title("Monthly Returns")
            ax.set_xlabel("Month")
            ax.set_ylabel("Year")
        else:
            # Convert equity curve to returns and group by month
            equity_series = pd.Series(equity_curve)
            returns = equity_series.pct_change().dropna()

            # Create a date range for the returns
            dates = pd.date_range(start="2020-01-01", periods=len(returns), freq="D")
            df = pd.DataFrame({"returns": returns.values}, index=dates[: len(returns)])

            # Group by year and month
            monthly_returns = (
                df["returns"].groupby([df.index.year, df.index.month]).sum()
            )

            # Create a pivot table for heatmap
            years = sorted(set(df.index.year))
            months = list(range(1, 13))

            heatmap_data = pd.DataFrame(index=years, columns=months, dtype=float)
            for (year, month), ret in monthly_returns.items():
                if year in years and month in months:
                    heatmap_data.loc[year, month] = ret * 100  # Convert to percentage

            # Create the heatmap
            fig, ax = plt.subplots(figsize=(12, 8))
            sns.heatmap(
                heatmap_data.T.fillna(0),  # Transpose so years on x-axis
                annot=True,
                fmt=".2f",
                center=0,
                cmap="RdYlGn",
                cbar_kws={"label": "Monthly Return (%)"},
                ax=ax,
            )

            ax.set_title("Monthly Returns Heatmap")
            ax.set_xlabel("Year")
            ax.set_ylabel("Month")

        # Save to bytes
        img_buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(img_buffer, format="png", dpi=150, bbox_inches="tight")
        img_buffer.seek(0)

        # Encode to base64
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close(fig)  # Close to free memory

        return img_str
