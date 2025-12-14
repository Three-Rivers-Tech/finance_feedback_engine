"""Multi-timeframe data aggregator with trend alignment and confluence detection."""

from typing import Dict, Any, List, Optional
import logging
from statistics import mean
import pandas as pd
import pandas_ta as ta

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

    def _calculate_macd(
        self,
        candles: List[Dict[str, Any]],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        Args:
            candles: List of candle dictionaries
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line EMA period (default 9)

        Returns:
            Dict with 'macd', 'signal', 'histogram' or None if insufficient data
        """
        if len(candles) < slow_period + signal_period:
            return None

        closes = pd.Series([c['close'] for c in candles])
        macd_result = ta.macd(closes, fast=fast_period, slow=slow_period, signal=signal_period)

        if macd_result is None or macd_result.empty:
            return None

        # pandas-ta returns DataFrame with columns: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        last_row = macd_result.iloc[-1]
        return {
            'macd': round(float(last_row[f'MACD_{fast_period}_{slow_period}_{signal_period}']), 4),
            'signal': round(float(last_row[f'MACDs_{fast_period}_{slow_period}_{signal_period}']), 4),
            'histogram': round(float(last_row[f'MACDh_{fast_period}_{slow_period}_{signal_period}']), 4)
        }

    def _calculate_stochastic_oscillator(
        self,
        candles: List[Dict[str, Any]],
        k_period: int = 14,
        d_period: int = 3
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Stochastic Oscillator (KD).

        Args:
            candles: List of candle dictionaries with high, low, close
            k_period: Period for the %K line (default 14)
            d_period: Period for the %D line (default 3)

        Returns:
            Dict with 'k', 'd' or None if insufficient data
        """
        if len(candles) < max(k_period, d_period) + 1:
            return None

        df = pd.DataFrame([
            {'high': c['high'], 'low': c['low'], 'close': c['close']}
            for c in candles
        ])

        stoch_result = ta.stoch(df['high'], df['low'], df['close'], k=k_period, d=d_period, smooth_k=1)

        if stoch_result is None or stoch_result.empty:
            return None

        last_row = stoch_result.iloc[-1]
        # pandas-ta column names: STOCHk_14_3_1, STOCHd_14_3_1
        k_val = float(last_row[f'STOCHk_{k_period}_{d_period}_1'])
        d_val = float(last_row[f'STOCHd_{k_period}_{d_period}_1'])

        return {
            'k': round(k_val, 2),
            'd': round(d_val, 2)
        }

    def _calculate_cci(
        self,
        candles: List[Dict[str, Any]],
        period: int = 20
    ) -> Optional[float]:
        """
        Calculate Commodity Channel Index (CCI).

        Args:
            candles: List of candle dictionaries with high, low, close
            period: CCI period (default 20)

        Returns:
            CCI value or None if insufficient data
        """
        if len(candles) < period + 1:
            return None

        df = pd.DataFrame([
            {'high': c['high'], 'low': c['low'], 'close': c['close']}
            for c in candles
        ])

        cci_result = ta.cci(df['high'], df['low'], df['close'], length=period)

        if cci_result is None or cci_result.empty:
            return None

        return round(float(cci_result.iloc[-1]), 2)

    def _calculate_williams_r(
        self,
        candles: List[Dict[str, Any]],
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate Williams %R (Williams Percent Range).

        Args:
            candles: List of candle dictionaries with high, low, close
            period: Lookback period (default 14)

        Returns:
            Williams %R value (range -100 to 0) or None if insufficient data
        """
        if len(candles) < period + 1:
            return None

        highs = pd.Series([c['high'] for c in candles])
        lows = pd.Series([c['low'] for c in candles])
        closes = pd.Series([c['close'] for c in candles])

        # Calculate Williams %R
        period_high = highs.rolling(window=period).max()
        period_low = lows.rolling(window=period).min()

        williams_r = -100 * ((period_high - closes) / (period_high - period_low))

        # Handle division by zero when period_high == period_low
        williams_r = williams_r.replace([np.inf, -np.inf], np.nan)

        return round(float(williams_r.iloc[-1]), 2)

    def _calculate_ichimoku_cloud(
        self,
        candles: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate Ichimoku Cloud components.

        Args:
            candles: List of candle dictionaries with high, low, close

        Returns:
            Dict with Ichimoku components or None if insufficient data
        """
        if len(candles) < 52:  # Need at least 52 candles for standard Ichimoku
            return None

        df = pd.DataFrame([
            {'high': c['high'], 'low': c['low'], 'close': c['close']}
            for c in candles
        ])

        # Standard Ichimoku periods
        tenkan_period = 9
        kijun_period = 26
        senkou_period = 52

        # Tenkan-sen (conversion line)
        high_9 = df['high'].rolling(window=tenkan_period).max()
        low_9 = df['low'].rolling(window=tenkan_period).min()
        tenkan_sen = (high_9 + low_9) / 2

        # Kijun-sen (base line)
        high_26 = df['high'].rolling(window=kijun_period).max()
        low_26 = df['low'].rolling(window=kijun_period).min()
        kijun_sen = (high_26 + low_26) / 2

        # Senkou Span A (leading span A)
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)

        # Senkou Span B (leading span B)
        high_52 = df['high'].rolling(window=senkou_period).max()
        low_52 = df['low'].rolling(window=senkou_period).min()
        senkou_b = ((high_52 + low_52) / 2).shift(kijun_period)

        # Chikou Span (lagging span)
        chikou_span = df['close'].shift(-kijun_period)

        # Get most recent values
        current_price = df['close'].iloc[-1]
        tenkan_current = tenkan_sen.iloc[-1]
        kijun_current = kijun_sen.iloc[-1]
        senkou_a_current = senkou_a.iloc[-1]
        senkou_b_current = senkou_b.iloc[-1]
        chikou_current = chikou_span.iloc[-1]

        return {
            'current_price': round(current_price, 2),
            'tenkan_sen': round(tenkan_current, 2) if not pd.isna(tenkan_current) else None,
            'kijun_sen': round(kijun_current, 2) if not pd.isna(kijun_current) else None,
            'senkou_a': round(senkou_a_current, 2) if not pd.isna(senkou_a_current) else None,
            'senkou_b': round(senkou_b_current, 2) if not pd.isna(senkou_b_current) else None,
            'chikou_span': round(chikou_current, 2) if not pd.isna(chikou_current) else None,
            'is_price_above_cloud': (
                current_price > senkou_a_current and current_price > senkou_b_current
                if not (pd.isna(senkou_a_current) or pd.isna(senkou_b_current))
                else None
            )
        }

    def _calculate_bollinger_bands(
        self,
        candles: List[Dict[str, Any]],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Calculate Bollinger Bands.

        Args:
            candles: List of candle dictionaries
            period: SMA period (default 20)
            std_dev: Standard deviation multiplier (default 2.0)

        Returns:
            Dict with 'upper', 'middle', 'lower', 'percent_b' or None if insufficient data
        """
        if len(candles) < period:
            return None

        closes = pd.Series([c['close'] for c in candles])
        bb_result = ta.bbands(closes, length=period, std=std_dev)

        if bb_result is None or bb_result.empty:
            return None

        # pandas-ta column names: BBL_period_std_std, BBM_period_std_std, BBU_period_std_std
        last_row = bb_result.iloc[-1]
        current_price = candles[-1]['close']

        # Column pattern: BBU_20_2.0_2.0 (period_std_std)
        col_suffix = f"{period}_{std_dev}_{std_dev}"
        upper = float(last_row[f'BBU_{col_suffix}'])
        middle = float(last_row[f'BBM_{col_suffix}'])
        lower = float(last_row[f'BBL_{col_suffix}'])

        # Calculate %B (position within bands)
        percent_b = ((current_price - lower) / (upper - lower)) * 100 if upper != lower else 50.0

        return {
            'upper': round(upper, 2),
            'middle': round(middle, 2),
            'lower': round(lower, 2),
            'percent_b': round(percent_b, 1)
        }

    def _calculate_adx(
        self,
        candles: List[Dict[str, Any]],
        period: int = 14
    ) -> Optional[Dict[str, float]]:
        """
        Calculate ADX (Average Directional Index) for trend strength.

        Args:
            candles: List of candle dictionaries with high, low, close
            period: ADX period (default 14)

        Returns:
            Dict with 'adx', 'plus_di', 'minus_di' or None if insufficient data
        """
        if len(candles) < period * 2:
            return None

        # Create DataFrame with required columns
        df = pd.DataFrame([
            {'high': c['high'], 'low': c['low'], 'close': c['close']}
            for c in candles
        ])

        adx_result = ta.adx(df['high'], df['low'], df['close'], length=period)

        if adx_result is None or adx_result.empty:
            return None

        # pandas-ta returns DataFrame with columns: ADX_14, DMP_14, DMN_14
        last_row = adx_result.iloc[-1]
        return {
            'adx': round(float(last_row[f'ADX_{period}']), 1),
            'plus_di': round(float(last_row[f'DMP_{period}']), 1),
            'minus_di': round(float(last_row[f'DMN_{period}']), 1)
        }

    def _calculate_atr(
        self,
        candles: List[Dict[str, Any]],
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate ATR (Average True Range) for volatility measurement.

        Args:
            candles: List of candle dictionaries with high, low, close
            period: ATR period (default 14)

        Returns:
            ATR value or None if insufficient data
        """
        if len(candles) < period + 1:
            return None

        # Create DataFrame with required columns
        df = pd.DataFrame([
            {'high': c['high'], 'low': c['low'], 'close': c['close']}
            for c in candles
        ])

        atr_result = ta.atr(df['high'], df['low'], df['close'], length=period)

        if atr_result is None or atr_result.empty:
            return None

        return round(float(atr_result.iloc[-1]), 4)

    def _classify_volatility(self, atr: float, current_price: float) -> str:
        """
        Classify volatility level based on ATR/price ratio.

        Args:
            atr: Average True Range value
            current_price: Current asset price

        Returns:
            'low', 'medium', or 'high'
        """
        if not atr or not current_price or current_price == 0:
            return 'unknown'

        atr_pct = (atr / current_price) * 100

        if atr_pct < 1.0:
            return 'low'
        elif atr_pct < 2.5:
            return 'medium'
        else:
            return 'high'

    def _calculate_signal_strength(
        self,
        indicators: Dict[str, Any]
    ) -> int:
        """
        Calculate overall signal strength (0-100) from multiple indicators.

        Args:
            indicators: Dict containing RSI, MACD, ADX, Bollinger Bands data

        Returns:
            Signal strength score 0-100
        """
        signals = []

        # RSI contribution (oversold/overbought = strong signal)
        rsi = indicators.get('rsi')
        if rsi:
            if rsi < 30:
                signals.append(80)  # Strong oversold
            elif rsi < 40:
                signals.append(60)  # Moderate oversold
            elif rsi > 70:
                signals.append(80)  # Strong overbought
            elif rsi > 60:
                signals.append(60)  # Moderate overbought
            else:
                signals.append(40)  # Neutral

        # MACD contribution (histogram divergence)
        macd = indicators.get('macd')
        if macd and isinstance(macd, dict):
            hist = abs(macd.get('histogram', 0))
            # Larger histogram = stronger signal
            if hist > 1.0:
                signals.append(80)
            elif hist > 0.5:
                signals.append(65)
            else:
                signals.append(50)

        # ADX contribution (trend strength)
        adx = indicators.get('adx')
        if adx and isinstance(adx, dict):
            adx_val = adx.get('adx', 0)
            if adx_val > 25:
                signals.append(min(100, 50 + adx_val))  # Strong trend
            else:
                signals.append(30)  # Weak trend

        # Bollinger Bands contribution (%B position)
        bbands = indicators.get('bbands')
        if bbands and isinstance(bbands, dict):
            percent_b = bbands.get('percent_b', 50)
            if percent_b < 10 or percent_b > 90:
                signals.append(85)  # Extreme position
            elif percent_b < 30 or percent_b > 70:
                signals.append(65)  # Strong position
            else:
                signals.append(45)  # Neutral position

        # Average all signal strengths
        return int(mean(signals)) if signals else 50

    def _detect_trend(
        self,
        candles: List[Dict[str, Any]],
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Detect trend for a single timeframe with advanced indicators.

        Args:
            candles: List of candles
            timeframe: Timeframe identifier

        Returns:
            Dictionary with comprehensive trend analysis:
            - direction: 'uptrend', 'downtrend', 'ranging'
            - strength: 0-100 (confidence in trend)
            - sma_20: 20-period SMA
            - sma_50: 50-period SMA
            - rsi: RSI(14)
            - macd: MACD indicator dict
            - bbands: Bollinger Bands dict
            - adx: ADX trend strength dict
            - atr: Average True Range
            - volatility: 'low', 'medium', 'high'
            - signal_strength: Overall signal strength 0-100
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

        # New advanced indicators
        macd = self._calculate_macd(candles)
        bbands = self._calculate_bollinger_bands(candles)
        adx = self._calculate_adx(candles)
        atr = self._calculate_atr(candles)

        # Additional advanced indicators
        stochastic = self._calculate_stochastic_oscillator(candles)
        cci = self._calculate_cci(candles)
        williams_r = self._calculate_williams_r(candles)
        ichimoku = self._calculate_ichimoku_cloud(candles)

        # Volatility classification
        volatility = self._classify_volatility(atr, current_price) if atr else 'unknown'

        # Determine trend direction (SMA-based baseline)
        direction = 'ranging'
        strength = 50

        if sma_20 and sma_50:
            if sma_20 > sma_50:
                direction = 'uptrend'
                separation_pct = ((sma_20 - sma_50) / sma_50) * 100
                strength = min(100, 50 + abs(separation_pct) * 200)
            elif sma_20 < sma_50:
                direction = 'downtrend'
                separation_pct = ((sma_50 - sma_20) / sma_50) * 100
                strength = min(100, 50 + abs(separation_pct) * 200)

        # ADX confirmation (strong trend if ADX > 25)
        if adx and isinstance(adx, dict):
            adx_val = adx.get('adx', 0)
            if adx_val > 25:
                # Strong trend confirmed
                plus_di = adx.get('plus_di', 0)
                minus_di = adx.get('minus_di', 0)

                if plus_di > minus_di and direction == 'uptrend':
                    strength = min(100, strength + 10)  # Boost confidence
                elif minus_di > plus_di and direction == 'downtrend':
                    strength = min(100, strength + 10)  # Boost confidence
            else:
                # Weak trend - reduce confidence
                if direction in ['uptrend', 'downtrend']:
                    strength = max(30, strength - 15)

        # MACD confirmation
        if macd and isinstance(macd, dict):
            macd_val = macd.get('macd', 0)
            signal_val = macd.get('signal', 0)

            if macd_val > signal_val and direction == 'uptrend':
                strength = min(100, strength + 5)  # Bullish crossover
            elif macd_val < signal_val and direction == 'downtrend':
                strength = min(100, strength + 5)  # Bearish crossover

        # Price position relative to SMAs
        if current_price and sma_20:
            if current_price > sma_20 * 1.02:
                if direction == 'downtrend':
                    direction = 'ranging'  # Conflicting signals
            elif current_price < sma_20 * 0.98:
                if direction == 'uptrend':
                    direction = 'ranging'  # Conflicting signals

        # Calculate overall signal strength
        indicators = {
            'rsi': rsi,
            'macd': macd,
            'adx': adx,
            'bbands': bbands,
            'stochastic': stochastic,
            'cci': cci,
            'williams_r': williams_r,
            'ichimoku': ichimoku
        }
        signal_strength = self._calculate_signal_strength(indicators)

        return {
            'direction': direction,
            'strength': int(strength),
            'sma_20': round(sma_20, 2) if sma_20 else None,
            'sma_50': round(sma_50, 2) if sma_50 else None,
            'rsi': round(rsi, 1) if rsi else None,
            'macd': macd,
            'bbands': bbands,
            'adx': adx,
            'atr': round(atr, 4) if atr else None,
            'stochastic': stochastic,
            'cci': cci,
            'williams_r': williams_r,
            'ichimoku': ichimoku,
            'volatility': volatility,
            'signal_strength': signal_strength,
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
