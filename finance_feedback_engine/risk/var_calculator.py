"""Value at Risk (VaR) calculator with dual-portfolio support for isolated platforms."""

from typing import Dict, Any, List, Optional, Tuple
import logging
from statistics import mean, stdev
from datetime import datetime, timedelta

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
        self,
        returns: List[float],
        confidence_level: float = 0.95
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
        index = max(0, min(index, len(sorted_returns) - 1)) # Clamp to valid range
        
        # VaR is the return at the percentile (negative = loss)
        var = abs(sorted_returns[index])
        
        return var

    def calculate_portfolio_var(
        self,
        holdings: Dict[str, Dict[str, Any]],
        price_history: Dict[str, List[Dict[str, float]]],
        confidence_level: float = 0.95
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
                'var': 0.0,
                'var_usd': 0.0,
                'portfolio_value': 0.0,
                'confidence_level': confidence_level,
                'data_quality': 'no_holdings'
            }

        # Calculate current portfolio value
        portfolio_value = 0.0
        for asset_id, holding in holdings.items():
            quantity = holding.get('quantity', 0)
            price = holding.get('current_price', 0)
            portfolio_value += quantity * price

        if portfolio_value == 0:
            return {
                'var': 0.0,
                'var_usd': 0.0,
                'portfolio_value': 0.0,
                'confidence_level': confidence_level,
                'data_quality': 'zero_value'
            }

        # Calculate daily returns for each asset
        asset_returns = {}
        for asset_id, history in price_history.items():
            if not history or len(history) < 2:
                continue

            returns = []
            for i in range(1, len(history)):
                prev_price = history[i-1].get('price', 0)
                curr_price = history[i].get('price', 0)

                if prev_price > 0:
                    ret = (curr_price - prev_price) / prev_price
                    returns.append(ret)

            if returns:
                asset_returns[asset_id] = returns

        if not asset_returns:
            return {
                'var': 0.0,
                'var_usd': 0.0,
                'portfolio_value': portfolio_value,
                'confidence_level': confidence_level,
                'data_quality': 'no_price_history'
            }

        # Use only the common date range for all assets
        min_history_length = min(len(returns) for returns in asset_returns.values())
        if min_history_length < 30:
            logger.warning(
                f"Insufficient common history for VaR calculation (min {min_history_length} days, need 30+)"
            )
            return {
                'var': 0.0,
                'var_usd': 0.0,
                'portfolio_value': portfolio_value,
                'confidence_level': confidence_level,
                'data_quality': 'insufficient_common_history',
                'sample_size': min_history_length
            }

        # Check for assets in holdings without price history
        missing_history = set(holdings.keys()) - set(asset_returns.keys())
        if missing_history:
            logger.warning(f"Assets without price history: {missing_history}")

        # Calculate subset portfolio value (only assets with price history)
        subset_portfolio_value = 0.0
        for asset_id in asset_returns.keys():
            holding = holdings.get(asset_id, {})
            quantity = holding.get('quantity', 0)
            price = holding.get('current_price', 0)
            subset_portfolio_value += quantity * price

        if subset_portfolio_value == 0:
            logger.error("Subset portfolio value is zero after excluding missing assets")
            return {
                'var': 0.0,
                'var_usd': 0.0,
                'portfolio_value': portfolio_value,
                'confidence_level': confidence_level,
                'data_quality': 'missing_price_history',
                'missing_assets': list(missing_history)
            }

        portfolio_returns = []
        for i in range(min_history_length):
            daily_return = 0.0
            for asset_id, returns in asset_returns.items():
                holding = holdings.get(asset_id, {})
                quantity = holding.get('quantity', 0)
                price = holding.get('current_price', 0)
                asset_value = quantity * price
                # Use subset portfolio value so weights sum to 1
                weight = asset_value / subset_portfolio_value if subset_portfolio_value > 0 else 0
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
        data_quality = 'good' if not missing_history else 'incomplete'

        result = {
            'var': round(var, 4),
            'var_usd': round(var_usd, 2),
            'portfolio_value': round(portfolio_value, 2),
            'subset_portfolio_value': round(subset_portfolio_value, 2),
            'confidence_level': confidence_level,
            'data_quality': data_quality,
            'sample_size': len(portfolio_returns)
        }

        # Include missing assets in metadata if any
        if missing_history:
            result['missing_assets'] = sorted(list(missing_history))

        return result

    def calculate_dual_portfolio_var(
        self,
        coinbase_holdings: Dict[str, Dict[str, Any]],
        coinbase_price_history: Dict[str, List[Dict[str, float]]],
        oanda_holdings: Dict[str, Dict[str, Any]],
        oanda_price_history: Dict[str, List[Dict[str, float]]],
        confidence_level: float = 0.95
    ) -> Dict[str, Any]:
        """
        Calculate VaR for dual isolated portfolios (Coinbase + Oanda).
        
        Since funds cannot be transferred between platforms, calculates:
        1. Coinbase portfolio VaR (crypto)
        2. Oanda portfolio VaR (forex)
        3. Combined portfolio VaR (simple sum, platforms uncorrelated)
        
        Args:
            coinbase_holdings: Coinbase holdings
            coinbase_price_history: Coinbase historical prices
            oanda_holdings: Oanda holdings
            oanda_price_history: Oanda historical prices
            confidence_level: Confidence level (0.95 or 0.99)
        
        Returns:
            Dictionary with:
            - coinbase_var: VaR metrics for Coinbase portfolio
            - oanda_var: VaR metrics for Oanda portfolio
            - combined_var: VaR metrics for combined portfolio
            - total_portfolio_value: Sum of both portfolios
            - risk_concentration: Risk concentration analysis
        """
        logger.info(
            f"Calculating dual-portfolio VaR at {confidence_level*100}% confidence"
        )
        
        # Calculate individual portfolio VaRs
        coinbase_var = self.calculate_portfolio_var(
            coinbase_holdings,
            coinbase_price_history,
            confidence_level
        )
        
        oanda_var = self.calculate_portfolio_var(
            oanda_holdings,
            oanda_price_history,
            confidence_level
        )
        
        # Calculate combined metrics
        total_value = (
            coinbase_var['portfolio_value'] + 
            oanda_var['portfolio_value']
        )
        
        # Combined VaR (simple sum, assuming platforms are uncorrelated)
        # This is conservative - real combined VaR would be lower due to diversification
        combined_var_usd = coinbase_var['var_usd'] + oanda_var['var_usd']
        combined_var = combined_var_usd / total_value if total_value > 0 else 0
        
        # Risk concentration analysis
        risk_concentration = self._analyze_risk_concentration(
            coinbase_var, oanda_var
        )
        
        result = {
            'coinbase_var': coinbase_var,
            'oanda_var': oanda_var,
            'combined_var': {
                'var': round(combined_var, 4),
                'var_usd': round(combined_var_usd, 2),
                'portfolio_value': round(total_value, 2),
                'confidence_level': confidence_level
            },
            'total_portfolio_value': round(total_value, 2),
            'risk_concentration': risk_concentration,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(
            f"Dual-portfolio VaR: Coinbase=${coinbase_var['var_usd']:.2f}, "
            f"Oanda=${oanda_var['var_usd']:.2f}, "
            f"Combined=${combined_var_usd:.2f} ({confidence_level*100}%)"
        )
        
        return result

    def _analyze_risk_concentration(
        self,
        coinbase_var: Dict[str, Any],
        oanda_var: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze risk concentration between platforms.
        
        Args:
            coinbase_var: Coinbase VaR results
            oanda_var: Oanda VaR results
        
        Returns:
            Risk concentration metrics
        """
        coinbase_value = coinbase_var.get('portfolio_value', 0)
        oanda_value = oanda_var.get('portfolio_value', 0)
        total_value = coinbase_value + oanda_value
        
        if total_value == 0:
            return {
                'coinbase_pct': 0.0,
                'oanda_pct': 0.0,
                'concentration_warning': None
            }
        
        coinbase_pct = (coinbase_value / total_value) * 100
        oanda_pct = (oanda_value / total_value) * 100
        
        # Check for concentration warnings
        warning = None
        if coinbase_pct > 80 or oanda_pct > 80:
            dominant = 'Coinbase' if coinbase_pct > 80 else 'Oanda'
            warning = f"{dominant} accounts for >{int(max(coinbase_pct, oanda_pct))}% of portfolio"
        
        return {
            'coinbase_pct': round(coinbase_pct, 1),
            'oanda_pct': round(oanda_pct, 1),
            'concentration_warning': warning
        }

    def format_var_summary(self, var_result: Dict[str, Any]) -> str:
        """
        Generate human-readable VaR summary.
        
        Args:
            var_result: Result from calculate_dual_portfolio_var()
        
        Returns:
            Formatted text summary
        """
        lines = [
            "=== Value at Risk (VaR) Summary ===",
            f"Confidence Level: {var_result['combined_var']['confidence_level']*100}%",
            f"Total Portfolio Value: ${var_result['total_portfolio_value']:,.2f}",
            "",
            "Platform Breakdown:",
            f"  Coinbase: ${var_result['coinbase_var']['portfolio_value']:,.2f} "
            f"(VaR: ${var_result['coinbase_var']['var_usd']:,.2f})",
            f"  Oanda:    ${var_result['oanda_var']['portfolio_value']:,.2f} "
            f"(VaR: ${var_result['oanda_var']['var_usd']:,.2f})",
            "",
            f"Combined Portfolio VaR: ${var_result['combined_var']['var_usd']:,.2f} "
            f"({var_result['combined_var']['var']*100:.2f}%)",
        ]
        
        if var_result['risk_concentration']['concentration_warning']:
            lines.append("")
            lines.append(f"⚠️  {var_result['risk_concentration']['concentration_warning']}")
        
        return "\n".join(lines)
