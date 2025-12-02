"""Multi-timeframe data aggregator with trend alignment and confluence detection."""

from typing import Dict, Any, List, Optional, Tuple
import logging
from statistics import mean

from .unified_data_provider import UnifiedDataProvider

logger = logging.getLogger(__name__)


class TimeframeAggregator:
    """
    Multi-timeframe data aggregator with intelligent trend detection.
    
    Analyzes price action across multiple timeframes to detect:
    - Trend alignment (confluence across timeframes)
    - Trend divergence (short-term vs long-term disagreement)
    - Key support/resistance levels
    - Momentum signals (RSI, MACD-like crossovers)
    
    Timeframe hierarchy (descending importance):
    1. Daily (1d) - Primary trend
    2. 4-hour (4h) - Intermediate trend
    3. 1-hour (1h) - Short-term trend
    4. 15-minute (15m) - Entry timing
    5. 5-minute (5m) - Fine entry trigger
    6. 1-minute (1m) - Execution timing
    """

    def __init__(self, data_provider: UnifiedDataProvider):
        """
        Initialize timeframe aggregator.

        Args:
            data_provider: UnifiedDataProvider instance
        """
        self.data_provider = data_provider
        logger.info("TimeframeAggregator initialized")

    def _calculate_sma(self, candles: List[Dict[str, Any]], period: int) -> Optional[float]:
        """Calculate Simple Moving Average."""
        if len(candles) < period:
            return None
        recent_closes = [c['close'] for c in candles[-period:]]
        return mean(recent_closes)

    def _calculate_rsi(self, candles: List[Dict[str, Any]], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index."""
        if len(candles) < period + 1:
            return None
        
        closes = [c['close'] for c in candles[-(period+1):]]
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = mean(gains) if gains else 0
        avg_loss = mean(losses) if losses else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _detect_trend(
        self,
        candles: List[Dict[str, Any]],
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Detect trend for a single timeframe.
        
        Args:
            candles: List of candles
            timeframe: Timeframe identifier
        
        Returns:
            Dictionary with trend analysis:
            - direction: 'uptrend', 'downtrend', 'ranging'
            - strength: 0-100 (confidence in trend)
            - sma_20: 20-period SMA
            - sma_50: 50-period SMA
            - rsi: RSI(14)
            - price: Current price
        """
        if not candles or len(candles) < 50:
            return {
                'direction': 'unknown',
                'strength': 0,
                'price': 0,
                'data_quality': 'insufficient'
            }
        
        current_price = candles[-1]['close']
        sma_20 = self._calculate_sma(candles, 20)
        sma_50 = self._calculate_sma(candles, 50)
        rsi = self._calculate_rsi(candles, 14)
        
        # Determine trend direction
        direction = 'ranging'
        strength = 50
        
        if sma_20 and sma_50:
            if sma_20 > sma_50:
                direction = 'uptrend'
                # Strength based on SMA separation
                separation_pct = ((sma_20 - sma_50) / sma_50) * 100
                strength = min(100, 50 + abs(separation_pct) * 200)
            elif sma_20 < sma_50:
                direction = 'downtrend'
                separation_pct = ((sma_50 - sma_20) / sma_50) * 100
                strength = min(100, 50 + abs(separation_pct) * 200)
        
        # Price position relative to SMAs
        if current_price and sma_20:
            if current_price > sma_20 * 1.02:
                if direction == 'downtrend':
                    direction = 'ranging'  # Conflicting signals
            elif current_price < sma_20 * 0.98:
                if direction == 'uptrend':
                    direction = 'ranging'  # Conflicting signals
        
        return {
            'direction': direction,
            'strength': int(strength),
            'sma_20': round(sma_20, 2) if sma_20 else None,
            'sma_50': round(sma_50, 2) if sma_50 else None,
            'rsi': round(rsi, 1) if rsi else None,
            'price': round(current_price, 2),
            'data_quality': 'good'
        }

    def analyze_multi_timeframe(
        self,
        asset_pair: str,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze asset across multiple timeframes for trend confluence.
        
        Args:
            asset_pair: Asset pair to analyze
            timeframes: List of timeframes (default: ['1m', '5m', '15m', '1h', '4h', '1d'])
        
        Returns:
            Dictionary with comprehensive multi-timeframe analysis:
            - timeframe_analysis: Dict of analysis per timeframe
            - trend_alignment: Overall trend consensus
            - confluence_strength: 0-100 (agreement across timeframes)
            - entry_signals: Short-term entry/exit signals
            - data_sources: Providers used per timeframe
        """
        if timeframes is None:
            timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        logger.info(f"Multi-timeframe analysis for {asset_pair}")
        
        # Fetch data across all timeframes
        multi_tf_data = self.data_provider.get_multi_timeframe_data(
            asset_pair, timeframes
        )
        
        # Analyze each timeframe
        timeframe_analysis = {}
        data_sources = {}
        
        for tf in timeframes:
            candles, provider = multi_tf_data.get(tf, ([], 'failed'))
            data_sources[tf] = provider
            
            if candles:
                timeframe_analysis[tf] = self._detect_trend(candles, tf)
            else:
                timeframe_analysis[tf] = {
                    'direction': 'unknown',
                    'strength': 0,
                    'data_quality': 'failed'
                }
        
        # Detect trend alignment
        trend_alignment = self._analyze_trend_alignment(timeframe_analysis)
        
        # Generate entry signals from short-term timeframes
        entry_signals = self._generate_entry_signals(timeframe_analysis)
        
        # Build summary
        summary = {
            'asset_pair': asset_pair,
            'timestamp': timeframe_analysis.get('1d', {}).get('price', 0),
            'timeframe_analysis': timeframe_analysis,
            'trend_alignment': trend_alignment,
            'entry_signals': entry_signals,
            'data_sources': data_sources
        }
        
        logger.info(
            f"Multi-timeframe analysis complete: "
            f"alignment={trend_alignment['direction']} "
            f"({trend_alignment['confluence_strength']}%)"
        )
        
        return summary

    def _analyze_trend_alignment(
        self,
        timeframe_analysis: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze trend alignment across timeframes.
        
        Args:
            timeframe_analysis: Analysis results per timeframe
        
        Returns:
            Dictionary with:
            - direction: Overall trend consensus
            - confluence_strength: 0-100 (agreement level)
            - conflicts: List of conflicting timeframes
        """
        # Timeframe weights (longer = more important)
        weights = {
            '1d': 40,
            '4h': 25,
            '1h': 15,
            '15m': 10,
            '5m': 5,
            '1m': 5
        }
        
        uptrend_score = 0
        downtrend_score = 0
        total_weight = 0
        conflicts = []
        
        for tf, analysis in timeframe_analysis.items():
            weight = weights.get(tf, 10)
            direction = analysis.get('direction', 'unknown')
            strength = analysis.get('strength', 0)
            
            if direction == 'uptrend':
                uptrend_score += weight * (strength / 100)
                total_weight += weight
            elif direction == 'downtrend':
                downtrend_score += weight * (strength / 100)
                total_weight += weight
            elif direction == 'ranging':
                total_weight += weight
                conflicts.append(tf)
        
        if total_weight == 0:
            return {
                'direction': 'unknown',
                'confluence_strength': 0,
                'conflicts': []
            }
        
        # Normalize scores
        uptrend_pct = (uptrend_score / total_weight) * 100
        downtrend_pct = (downtrend_score / total_weight) * 100
        
        # Determine consensus
        if uptrend_pct > 60:
            direction = 'uptrend'
            confluence_strength = int(uptrend_pct)
        elif downtrend_pct > 60:
            direction = 'downtrend'
            confluence_strength = int(downtrend_pct)
        else:
            direction = 'mixed'
            confluence_strength = int(max(uptrend_pct, downtrend_pct))
        
        return {
            'direction': direction,
            'confluence_strength': confluence_strength,
            'uptrend_pct': round(uptrend_pct, 1),
            'downtrend_pct': round(downtrend_pct, 1),
            'conflicts': conflicts
        }

    def _generate_entry_signals(
        self,
        timeframe_analysis: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate entry/exit signals from short-term timeframes.
        
        Args:
            timeframe_analysis: Analysis results per timeframe
        
        Returns:
            Dictionary with entry/exit signal recommendations
        """
        # Focus on short-term timeframes for entry timing
        tf_15m = timeframe_analysis.get('15m', {})
        tf_5m = timeframe_analysis.get('5m', {})
        
        rsi_15m = tf_15m.get('rsi', 50)
        rsi_5m = tf_5m.get('rsi', 50)
        
        signals = {
            'buy_signals': [],
            'sell_signals': [],
            'overall': 'neutral'
        }
        
        # RSI-based signals
        if rsi_15m and rsi_15m < 30:
            signals['buy_signals'].append('15m RSI oversold (< 30)')
        if rsi_5m and rsi_5m < 30:
            signals['buy_signals'].append('5m RSI oversold (< 30)')
        
        if rsi_15m and rsi_15m > 70:
            signals['sell_signals'].append('15m RSI overbought (> 70)')
        if rsi_5m and rsi_5m > 70:
            signals['sell_signals'].append('5m RSI overbought (> 70)')
        
        # Price vs SMA signals
        if tf_15m.get('price') and tf_15m.get('sma_20'):
            if tf_15m['price'] < tf_15m['sma_20'] * 0.98:
                signals['buy_signals'].append('15m price below SMA20 (pullback)')
            elif tf_15m['price'] > tf_15m['sma_20'] * 1.02:
                signals['sell_signals'].append('15m price above SMA20 (extended)')
        
        # Overall signal
        buy_count = len(signals['buy_signals'])
        sell_count = len(signals['sell_signals'])
        
        if buy_count > sell_count:
            signals['overall'] = 'bullish'
        elif sell_count > buy_count:
            signals['overall'] = 'bearish'
        
        return signals

    def get_summary_text(self, analysis: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of multi-timeframe analysis.
        
        Args:
            analysis: Result from analyze_multi_timeframe()
        
        Returns:
            Formatted text summary
        """
        alignment = analysis['trend_alignment']
        entry = analysis['entry_signals']
        
        summary_lines = [
            f"=== Multi-Timeframe Analysis: {analysis['asset_pair']} ===",
            f"Overall Trend: {alignment['direction'].upper()} (confidence: {alignment['confluence_strength']}%)",
            ""
        ]
        
        # Timeframe breakdown
        for tf in ['1d', '4h', '1h', '15m', '5m']:
            tf_data = analysis['timeframe_analysis'].get(tf, {})
            if tf_data.get('direction') != 'unknown':
                direction = tf_data['direction']
                rsi = tf_data.get('rsi', 'N/A')
                price = tf_data.get('price', 'N/A')
                summary_lines.append(
                    f"  {tf:>4s}: {direction:10s} | RSI: {rsi:>5} | Price: {price}"
                )
        
        summary_lines.append("")
        summary_lines.append(f"Entry Signals: {entry['overall'].upper()}")
        if entry['buy_signals']:
            summary_lines.append("  Buy: " + ", ".join(entry['buy_signals']))
        if entry['sell_signals']:
            summary_lines.append("  Sell: " + ", ".join(entry['sell_signals']))
        
        return "\n".join(summary_lines)
