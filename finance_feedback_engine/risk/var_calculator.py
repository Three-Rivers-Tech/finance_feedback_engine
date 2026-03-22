"""Value at Risk (VaR) calculator with dual-portfolio support for isolated platforms."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class VaRCalculator:
    """
    Historical Value at Risk (VaR) calculator for risk management.

    Calculates VaR separately for:
    - Coinbase portfolio (crypto futures/spot)
    - Oanda portfolio (forex)
    - Combined portfolio (simple sum, platforms are financially isolated)

    Uses 60-day historical window:
    - Balances institutional rigor (90+ days) with retail agility (30 days)
    - Captures ~3 months of market behavior
    - Includes major weekly/monthly cycles
    - Sufficient sample size for 95%/99% percentile stability

    Confidence levels:
    - 95% VaR: Expected maximum loss on a typical bad day
    - 99% VaR: Expected maximum loss on a rare extreme day
    """

    def __init__(self, lookback_days: int = 60):
        """
        Initialize VaR calculator.

        Args:
            lookback_days: Historical window for VaR calculation (default: 60)
        """
        self.lookback_days = lookback_days
        logger.info(f"VaRCalculator initialized with {lookback_days}-day lookback")

    def calculate_historical_var(
        self, returns: List[float], confidence_level: float = 0.95
    ) -> float:
        """
        Calculate historical VaR from return series.

        Args:
            returns: List of historical returns (as decimal fractions, e.g., 0.02 = 2%)
            confidence_level: Confidence level (0.95 or 0.99)

        Returns:
            VaR as decimal fraction (e.g., 0.05 = 5% loss)
        """
        if not returns or len(returns) < 30:
            logger.warning(
                f"Insufficient data for VaR calculation "
                f"({len(returns)} returns, need 30+)"
            )
            return 0.0

        # Sort returns (worst to best)
        sorted_returns = sorted(returns)

        # Calculate at the specified percentile
        percentile = 1 - confidence_level
        index = round(len(sorted_returns) * percentile)
        index = max(0, min(index, len(sorted_returns) - 1))  # Clamp to valid range

        # VaR is the return at the percentile (negative = loss)
        var = abs(sorted_returns[index])

        return var

    def calculate_portfolio_var(
        self,
        holdings: Dict[str, Dict[str, Any]],
        price_history: Dict[str, List[Dict[str, float]]],
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Calculate VaR for a portfolio of holdings.

        NOTE: This method assumes the current portfolio composition (weights) has remained constant over the historical period. If the portfolio composition changed, the VaR estimate may be inaccurate. For true historical VaR, historical portfolio weights are required.

        Args:
            holdings: Dictionary of holdings {asset_id: {'quantity': X, 'current_price': Y}}
            price_history: Historical prices {asset_id: [{'date': 'YYYY-MM-DD', 'price': X}, ...]}
            confidence_level: Confidence level (0.95 or 0.99)

        Returns:
            Dictionary with:
            - var: VaR value (decimal fraction)
            - var_usd: VaR in USD (if portfolio value provided)
            - portfolio_value: Current portfolio value
            - confidence_level: Confidence level used
            - data_quality: Quality assessment
        """
        if not holdings:
            return {
                "var": 0.0,
                "var_usd": 0.0,
                "portfolio_value": 0.0,
                "confidence_level": confidence_level,
                "data_quality": "no_holdings",
            }

        # Calculate current portfolio value
        portfolio_value = 0.0
        for asset_id, holding in holdings.items():
            quantity = holding.get("quantity", 0)
            price = holding.get("current_price", 0)
            portfolio_value += quantity * price

        if portfolio_value == 0:
            return {
                "var": 0.0,
                "var_usd": 0.0,
                "portfolio_value": 0.0,
                "confidence_level": confidence_level,
                "data_quality": "zero_value",
            }

        # Calculate daily returns for each asset
        asset_returns = {}
        for asset_id, history in price_history.items():
            if not history or len(history) < 2:
                continue

            returns = []
            for i in range(1, len(history)):
                prev_price = history[i - 1].get("price", 0)
                curr_price = history[i].get("price", 0)

                if prev_price > 0:
                    ret = (curr_price - prev_price) / prev_price
                    returns.append(ret)

            if returns:
                asset_returns[asset_id] = returns

        if not asset_returns:
            return {
                "var": 0.0,
                "var_usd": 0.0,
                "portfolio_value": portfolio_value,
                "confidence_level": confidence_level,
                "data_quality": "no_price_history",
            }

        # Use only the common date range for all assets
        min_history_length = min(len(returns) for returns in asset_returns.values())
        if min_history_length < 30:
            logger.warning(
                f"Insufficient common history for VaR calculation (min {min_history_length} days, need 30+)"
            )
            return {
                "var": 0.0,
                "var_usd": 0.0,
                "portfolio_value": portfolio_value,
                "confidence_level": confidence_level,
                "data_quality": "insufficient_common_history",
                "sample_size": min_history_length,
            }

        # Check for assets in holdings without price history
        missing_history = set(holdings.keys()) - set(asset_returns.keys())
        if missing_history:
            logger.warning(f"Assets without price history: {missing_history}")

        # Calculate subset portfolio value (only assets with price history)
        subset_portfolio_value = 0.0
        for asset_id in asset_returns.keys():
            holding = holdings.get(asset_id, {})
            quantity = holding.get("quantity", 0)
            price = holding.get("current_price", 0)
            subset_portfolio_value += quantity * price

        if subset_portfolio_value == 0:
            logger.error(
                "Subset portfolio value is zero after excluding missing assets"
            )
            return {
                "var": 0.0,
                "var_usd": 0.0,
                "portfolio_value": portfolio_value,
                "confidence_level": confidence_level,
                "data_quality": "missing_price_history",
                "missing_assets": sorted(list(missing_history)),
            }

        portfolio_returns = []
        for i in range(min_history_length):
            daily_return = 0.0
            for asset_id, returns in asset_returns.items():
                holding = holdings.get(asset_id, {})
                quantity = holding.get("quantity", 0)
                price = holding.get("current_price", 0)
                asset_value = quantity * price
                # Use subset portfolio value so weights sum to 1
                weight = (
                    asset_value / subset_portfolio_value
                    if subset_portfolio_value > 0
                    else 0
                )
                # Use the most recent min_history_length days (align from the end)
                daily_return += returns[-(min_history_length - i)] * weight
            portfolio_returns.append(daily_return)

        # Warn about the constant composition assumption
        logger.warning(
            "VaR calculation assumes constant portfolio composition over the historical window. "
            "If portfolio weights changed, VaR may be inaccurate."
        )

        # Calculate VaR from portfolio returns (based on subset portfolio)
        var = self.calculate_historical_var(portfolio_returns, confidence_level)
        var_usd = var * subset_portfolio_value

        # Determine data quality
        data_quality = "good" if not missing_history else "incomplete"

        result = {
            "var": round(var, 4),
            "var_usd": round(var_usd, 2),
            "portfolio_value": round(portfolio_value, 2),
            "subset_portfolio_value": round(subset_portfolio_value, 2),
            "confidence_level": confidence_level,
            "data_quality": data_quality,
            "sample_size": len(portfolio_returns),
        }

        # Include missing assets in metadata if any
        if missing_history:
            result["missing_assets"] = sorted(list(missing_history))

        return result

    def _resolve_active_platform_inputs(
        self,
        coinbase_holdings: Dict[str, Dict[str, Any]],
        coinbase_price_history: Dict[str, List[Dict[str, float]]],
        oanda_holdings: Dict[str, Dict[str, Any]],
        oanda_price_history: Dict[str, List[Dict[str, float]]],
    ) -> Dict[str, Dict[str, Any]]:
        platforms = {}
        if coinbase_holdings or coinbase_price_history:
            platforms["coinbase"] = {
                "holdings": coinbase_holdings,
                "price_history": coinbase_price_history,
            }
        if oanda_holdings or oanda_price_history:
            platforms["oanda"] = {
                "holdings": oanda_holdings,
                "price_history": oanda_price_history,
            }
        return platforms

    def calculate_dual_portfolio_var(
        self,
        coinbase_holdings: Dict[str, Dict[str, Any]],
        coinbase_price_history: Dict[str, List[Dict[str, float]]],
        oanda_holdings: Dict[str, Dict[str, Any]],
        oanda_price_history: Dict[str, List[Dict[str, float]]],
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """
        Calculate VaR for the active platform set.

        Preserves the legacy combined_var contract while adapting to single-platform
        runtimes that no longer have both Coinbase and Oanda active.
        """
        active_inputs = self._resolve_active_platform_inputs(
            coinbase_holdings,
            coinbase_price_history,
            oanda_holdings,
            oanda_price_history,
        )
        active_platforms = list(active_inputs.keys())

        if len(active_platforms) > 1:
            logger.info(
                f"Calculating dual-portfolio VaR at {confidence_level*100}% confidence"
            )
        elif len(active_platforms) == 1:
            logger.info(
                "Calculating single-platform VaR for %s at %.1f%% confidence",
                active_platforms[0],
                confidence_level * 100,
            )
        else:
            logger.info(
                "Calculating portfolio VaR at %.1f%% confidence with no active platforms",
                confidence_level * 100,
            )

        platform_vars: Dict[str, Dict[str, Any]] = {}
        for platform_name, inputs in active_inputs.items():
            platform_vars[platform_name] = self.calculate_portfolio_var(
                inputs["holdings"], inputs["price_history"], confidence_level
            )

        total_value = sum(v.get("portfolio_value", 0.0) for v in platform_vars.values())
        combined_var_usd = sum(v.get("var_usd", 0.0) for v in platform_vars.values())
        combined_var = combined_var_usd / total_value if total_value > 0 else 0.0

        result = {
            "active_platforms": active_platforms,
            "combined_var": {
                "var": round(combined_var, 4),
                "var_usd": round(combined_var_usd, 2),
                "portfolio_value": round(total_value, 2),
                "confidence_level": confidence_level,
            },
            "total_portfolio_value": round(total_value, 2),
            "risk_concentration": self._analyze_risk_concentration(platform_vars),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        result.update({f"{name}_var": value for name, value in platform_vars.items()})

        if len(active_platforms) == 1:
            only = active_platforms[0]
            logger.info(
                "Single-platform VaR: %s=$%.2f (%.1f%%)",
                only,
                platform_vars[only].get("var_usd", 0.0),
                confidence_level * 100,
            )
        else:
            logger.info(
                "Dual-portfolio VaR: Coinbase=$%.2f, Oanda=$%.2f, Combined=$%.2f (%.1f%%)",
                platform_vars.get("coinbase", {}).get("var_usd", 0.0),
                platform_vars.get("oanda", {}).get("var_usd", 0.0),
                combined_var_usd,
                confidence_level * 100,
            )

        return result

    def _analyze_risk_concentration(
        self, platform_vars: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze concentration across the currently active platforms."""
        total_value = sum(v.get("portfolio_value", 0.0) for v in platform_vars.values())
        allocations = {}

        if total_value == 0:
            return {"platform_allocations": {}, "concentration_warning": None}

        dominant_platform = None
        dominant_pct = 0.0
        for platform_name, var_result in platform_vars.items():
            pct = (var_result.get("portfolio_value", 0.0) / total_value) * 100
            allocations[platform_name] = round(pct, 1)
            if pct > dominant_pct:
                dominant_pct = pct
                dominant_platform = platform_name

        warning = None
        if len(platform_vars) > 1 and dominant_pct > 80 and dominant_platform:
            warning = (
                f"{dominant_platform.title()} accounts for >{int(dominant_pct)}% of portfolio"
            )

        result = {
            "platform_allocations": allocations,
            "concentration_warning": warning,
        }
        if "coinbase" in allocations:
            result["coinbase_pct"] = allocations["coinbase"]
        if "oanda" in allocations:
            result["oanda_pct"] = allocations["oanda"]
        return result

    def format_var_summary(self, var_result: Dict[str, Any]) -> str:
        """Generate human-readable VaR summary."""
        confidence_pct = var_result["combined_var"]["confidence_level"] * 100
        lines = [
            "=== Value at Risk (VaR) Summary ===",
            f"Confidence Level: {confidence_pct}%",
            f"Total Portfolio Value: ${var_result['total_portfolio_value']:,.2f}",
            "",
            "Platform Breakdown:",
        ]

        active_platforms = var_result.get("active_platforms") or [
            name.replace("_var", "")
            for name in ("coinbase_var", "oanda_var")
            if name in var_result
        ]

        for platform_name in active_platforms:
            key = f"{platform_name}_var"
            details = var_result.get(key, {})
            lines.append(
                f"  {platform_name.title()}: ${details.get('portfolio_value', 0.0):,.2f} "
                f"(VaR: ${details.get('var_usd', 0.0):,.2f})"
            )

        lines.extend(
            [
                "",
                f"Combined Portfolio VaR: ${var_result['combined_var']['var_usd']:,.2f} "
                f"({var_result['combined_var']['var']*100:.2f}%)",
            ]
        )

        warning = var_result.get("risk_concentration", {}).get("concentration_warning")
        if warning:
            lines.append("")
            lines.append(f"⚠️  {warning}")

        return "\n".join(lines)

