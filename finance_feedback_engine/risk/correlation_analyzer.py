"""Correlation analyzer for portfolio-aware concentration limits and cross-platform risk detection."""

from typing import Dict, Any, List, Optional, Tuple
import logging
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """
    Portfolio correlation analyzer with dual-platform support.
    
    Calculates Pearson correlation matrices for:
    - Coinbase holdings (crypto assets)
    - Oanda holdings (forex pairs)
    - Cross-platform correlation (warns when >0.5)
    
    Uses 30-day rolling window for correlation calculation:
    - Balances responsiveness with statistical significance
    - Captures recent market regime changes
    - Sufficient for detecting correlated movements
    
    Risk thresholds:
    - Per-platform: Max 2 assets with >0.7 correlation
    - Cross-platform: Warning when correlation >0.5 (log only, don't block)
    """

    def __init__(self, lookback_days: int = 30):
        """
        Initialize correlation analyzer.

        Args:
            lookback_days: Historical window for correlation (default: 30)
        """
        self.lookback_days = lookback_days
        self.correlation_threshold = 0.7  # Per-platform limit
        self.cross_platform_warning_threshold = 0.5
        logger.info(
            f"CorrelationAnalyzer initialized with {lookback_days}-day lookback"
        )

    def calculate_pearson_correlation(
        self,
        returns_a: List[float],
        returns_b: List[float]
    ) -> Optional[float]:
        """
        Calculate Pearson correlation coefficient between two return series.
        
        Args:
            returns_a: First return series
            returns_b: Second return series
        
        Returns:
            Correlation coefficient (-1 to 1) or None if insufficient data
        """
        if not returns_a or not returns_b or len(returns_a) != len(returns_b):
            return None
        
        if len(returns_a) < 10:
            logger.warning(
                f"Insufficient data for correlation ({len(returns_a)} points, need 10+)"
            )
            return None
        
        # Calculate means
        mean_a = mean(returns_a)
        mean_b = mean(returns_b)
        
        # Calculate covariance and standard deviations
        covariance = sum(
            (a - mean_a) * (b - mean_b) 
            for a, b in zip(returns_a, returns_b)
        ) / len(returns_a)
        
        std_a = stdev(returns_a)
        std_b = stdev(returns_b)
        
        if std_a == 0 or std_b == 0:
            return None
        
        correlation = covariance / (std_a * std_b)
        
        # Clamp to [-1, 1] (handle floating point errors)
        correlation = max(-1.0, min(1.0, correlation))
        
        return correlation

    def build_correlation_matrix(
        self,
        price_history: Dict[str, List[Dict[str, float]]]
    ) -> Dict[Tuple[str, str], float]:
        """
        Build correlation matrix from price history.
        
        Args:
            price_history: Historical prices {asset_id: [{'date': 'YYYY-MM-DD', 'price': X}, ...]}
        
        Returns:
            Dictionary mapping (asset_a, asset_b) to correlation coefficient
        """
        if not price_history or len(price_history) < 2:
            return {}
        
        # Calculate returns for each asset
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
        
        # Build correlation matrix
        correlation_matrix = {}
        assets = list(asset_returns.keys())
        
        for i, asset_a in enumerate(assets):
            for asset_b in assets[i+1:]:
                returns_a = asset_returns[asset_a]
                returns_b = asset_returns[asset_b]
                
                # Align return series (use minimum length)
                min_length = min(len(returns_a), len(returns_b))
                aligned_a = returns_a[-min_length:]
                aligned_b = returns_b[-min_length:]
                
                corr = self.calculate_pearson_correlation(aligned_a, aligned_b)
                
                if corr is not None:
                    correlation_matrix[(asset_a, asset_b)] = round(corr, 3)
                    correlation_matrix[(asset_b, asset_a)] = round(corr, 3)  # Symmetric
        
        return correlation_matrix

    def find_highly_correlated_pairs(
        self,
        correlation_matrix: Dict[Tuple[str, str], float],
        threshold: float = 0.7
    ) -> List[Tuple[str, str, float]]:
        """
        Find pairs of assets with correlation above threshold.
        
        Args:
            correlation_matrix: Correlation matrix from build_correlation_matrix()
            threshold: Minimum correlation (default: 0.7)
        
        Returns:
            List of (asset_a, asset_b, correlation) tuples
        """
        highly_correlated = []
        seen_pairs = set()
        
        for (asset_a, asset_b), corr in correlation_matrix.items():
            if abs(corr) >= threshold:
                # Avoid duplicates (a,b) and (b,a)
                pair = tuple(sorted([asset_a, asset_b]))
                if pair not in seen_pairs:
                    highly_correlated.append((asset_a, asset_b, corr))
                    seen_pairs.add(pair)
        
        # Sort by correlation (highest first)
        highly_correlated.sort(key=lambda x: abs(x[2]), reverse=True)
        
        return highly_correlated

    def analyze_platform_correlations(
        self,
        holdings: Dict[str, Dict[str, Any]],
        price_history: Dict[str, List[Dict[str, float]]],
        platform_name: str
    ) -> Dict[str, Any]:
        """
        Analyze correlations within a single platform's holdings.
        
        Args:
            holdings: Platform holdings {asset_id: {'quantity': X, ...}}
            price_history: Historical prices for assets
            platform_name: Platform identifier (e.g., 'coinbase', 'oanda')
        
        Returns:
            Dictionary with:
            - correlation_matrix: Full correlation matrix
            - highly_correlated: Pairs exceeding threshold
            - max_correlation: Highest correlation found
            - concentration_warning: Warning message if limits exceeded
        """
        logger.info(f"Analyzing correlations for {platform_name} platform")
        
        if not holdings or len(holdings) < 2:
            return {
                'correlation_matrix': {},
                'highly_correlated': [],
                'max_correlation': 0.0,
                'concentration_warning': None,
                'platform': platform_name
            }
        
        # Build correlation matrix
        correlation_matrix = self.build_correlation_matrix(price_history)
        
        # Find highly correlated pairs
        highly_correlated = self.find_highly_correlated_pairs(
            correlation_matrix,
            self.correlation_threshold
        )
        
        # Determine max correlation
        max_correlation = 0.0
        if correlation_matrix:
            max_correlation = max(
                abs(corr) for corr in correlation_matrix.values()
            )
        
        # Check for concentration warnings
        warning = None
        if len(highly_correlated) > 0:
            # Count how many assets are in highly correlated pairs
            correlated_assets = set()
            for asset_a, asset_b, corr in highly_correlated:
                correlated_assets.add(asset_a)
                correlated_assets.add(asset_b)
            
            if len(correlated_assets) > 2:
                warning = (
                    f"{len(correlated_assets)} assets with correlation >{self.correlation_threshold} "
                    f"on {platform_name} (limit: 2)"
                )
        
        result = {
            'correlation_matrix': correlation_matrix,
            'highly_correlated': highly_correlated,
            'max_correlation': round(max_correlation, 3),
            'concentration_warning': warning,
            'platform': platform_name,
            'num_holdings': len(holdings)
        }
        
        logger.info(
            f"{platform_name}: {len(highly_correlated)} highly correlated pairs, "
            f"max_correlation={max_correlation:.3f}"
        )
        
        return result

    def analyze_cross_platform_correlation(
        self,
        coinbase_price_history: Dict[str, List[Dict[str, float]]],
        oanda_price_history: Dict[str, List[Dict[str, float]]]
    ) -> Dict[str, Any]:
        """
        Analyze correlation between Coinbase and Oanda holdings.
        
        Warning-only (doesn't block trades) since platforms are financially isolated.
        Useful for understanding systemic risk during USD volatility events.
        
        Args:
            coinbase_price_history: Coinbase asset price history
            oanda_price_history: Oanda asset price history
        
        Returns:
            Dictionary with cross-platform correlation analysis
        """
        logger.info("Analyzing cross-platform correlations")
        
        if not coinbase_price_history or not oanda_price_history:
            return {
                'cross_correlations': [],
                'max_correlation': 0.0,
                'warning': None
            }
        
        # Calculate cross-platform correlations
        cross_correlations = []
        
        # Calculate returns for each asset
        def get_returns(price_history):
            returns_dict = {}
            for asset_id, history in price_history.items():
                if len(history) < 2:
                    continue
                returns = []
                for i in range(1, len(history)):
                    prev = history[i-1].get('price', 0)
                    curr = history[i].get('price', 0)
                    if prev > 0:
                        returns.append((curr - prev) / prev)
                if returns:
                    returns_dict[asset_id] = returns
            return returns_dict
        
        coinbase_returns = get_returns(coinbase_price_history)
        oanda_returns = get_returns(oanda_price_history)
        
        # Calculate correlations between all Coinbase-Oanda pairs
        for cb_asset, cb_returns in coinbase_returns.items():
            for oa_asset, oa_returns in oanda_returns.items():
                # Align return series
                min_length = min(len(cb_returns), len(oa_returns))
                if min_length < 10:
                    continue
                
                aligned_cb = cb_returns[-min_length:]
                aligned_oa = oa_returns[-min_length:]
                
                corr = self.calculate_pearson_correlation(aligned_cb, aligned_oa)
                
                if corr is not None:
                    cross_correlations.append({
                        'coinbase_asset': cb_asset,
                        'oanda_asset': oa_asset,
                        'correlation': round(corr, 3)
                    })
        
        # Find maximum correlation
        max_correlation = 0.0
        if cross_correlations:
            max_correlation = max(
                abs(c['correlation']) for c in cross_correlations
            )
        
        # Generate warning if threshold exceeded
        warning = None
        if max_correlation > self.cross_platform_warning_threshold:
            high_corr_pairs = [
                c for c in cross_correlations 
                if abs(c['correlation']) > self.cross_platform_warning_threshold
            ]
            if high_corr_pairs:
                pair = high_corr_pairs[0]
                warning = (
                    f"Cross-platform correlation detected: "
                    f"{pair['coinbase_asset']} ↔ {pair['oanda_asset']} "
                    f"({pair['correlation']:.3f}). Systemic risk possible."
                )
        
        result = {
            'cross_correlations': cross_correlations,
            'max_correlation': round(max_correlation, 3),
            'warning': warning
        }
        
        logger.info(
            f"Cross-platform: max_correlation={max_correlation:.3f}"
        )
        
        return result

    def analyze_dual_platform_correlations(
        self,
        coinbase_holdings: Dict[str, Dict[str, Any]],
        coinbase_price_history: Dict[str, List[Dict[str, float]]],
        oanda_holdings: Dict[str, Dict[str, Any]],
        oanda_price_history: Dict[str, List[Dict[str, float]]]
    ) -> Dict[str, Any]:
        """
        Comprehensive correlation analysis for dual isolated platforms.
        
        Args:
            coinbase_holdings: Coinbase holdings
            coinbase_price_history: Coinbase price history
            oanda_holdings: Oanda holdings
            oanda_price_history: Oanda price history
        
        Returns:
            Dictionary with complete correlation analysis for both platforms
        """
        logger.info("Performing dual-platform correlation analysis")
        
        # Analyze each platform separately
        coinbase_analysis = self.analyze_platform_correlations(
            coinbase_holdings,
            coinbase_price_history,
            'coinbase'
        )
        
        oanda_analysis = self.analyze_platform_correlations(
            oanda_holdings,
            oanda_price_history,
            'oanda'
        )
        
        # Analyze cross-platform correlations
        cross_platform = self.analyze_cross_platform_correlation(
            coinbase_price_history,
            oanda_price_history
        )
        
        # Combine results
        result = {
            'coinbase': coinbase_analysis,
            'oanda': oanda_analysis,
            'cross_platform': cross_platform,
            'overall_warnings': []
        }
        
        # Collect all warnings
        if coinbase_analysis['concentration_warning']:
            result['overall_warnings'].append(coinbase_analysis['concentration_warning'])
        if oanda_analysis['concentration_warning']:
            result['overall_warnings'].append(oanda_analysis['concentration_warning'])
        if cross_platform['warning']:
            result['overall_warnings'].append(cross_platform['warning'])
        
        logger.info(
            f"Dual-platform correlation analysis complete: "
            f"{len(result['overall_warnings'])} warnings"
        )
        
        return result

    def format_correlation_summary(self, analysis: Dict[str, Any]) -> str:
        """
        Generate human-readable correlation summary.
        
        Args:
            analysis: Result from analyze_dual_platform_correlations()
        
        Returns:
            Formatted text summary
        """
        lines = [
            "=== Correlation Analysis Summary ===",
            ""
        ]
        
        # Coinbase correlations
        cb = analysis['coinbase']
        lines.append(f"Coinbase ({cb['num_holdings']} holdings):")
        lines.append(f"  Max Correlation: {cb['max_correlation']:.3f}")
        if cb['highly_correlated']:
            lines.append(f"  Highly Correlated Pairs:")
            for asset_a, asset_b, corr in cb['highly_correlated'][:3]:
                lines.append(f"    • {asset_a} ↔ {asset_b}: {corr:.3f}")
        
        # Oanda correlations
        oa = analysis['oanda']
        lines.append(f"\nOanda ({oa['num_holdings']} holdings):")
        lines.append(f"  Max Correlation: {oa['max_correlation']:.3f}")
        if oa['highly_correlated']:
            lines.append(f"  Highly Correlated Pairs:")
            for asset_a, asset_b, corr in oa['highly_correlated'][:3]:
                lines.append(f"    • {asset_a} ↔ {asset_b}: {corr:.3f}")
        
        # Cross-platform
        cp = analysis['cross_platform']
        lines.append(f"\nCross-Platform:")
        lines.append(f"  Max Correlation: {cp['max_correlation']:.3f}")
        
        # Warnings
        if analysis['overall_warnings']:
            lines.append("\n⚠️  Warnings:")
            for warning in analysis['overall_warnings']:
                lines.append(f"  • {warning}")
        
        return "\n".join(lines)
