# Multi-Timeframe Feature Pulse Architecture Design

**Version:** 1.0  
**Date:** 2025-01-28  
**Status:** Design Phase (Task 2 - In Progress)

---

## Table of Contents

1. [Overview](#overview)
2. [Current State Analysis](#current-state-analysis)
3. [Proposed Enhancements](#proposed-enhancements)
4. [Feature Pulse Structure](#feature-pulse-structure)
5. [Component Design](#component-design)
6. [Data Flow](#data-flow)
7. [Dependencies](#dependencies)
8. [Testing Strategy](#testing-strategy)
9. [Migration Path](#migration-path)

---

## Overview

### Objectives

Enhance the trading engine with comprehensive multi-timeframe technical analysis by:

1. **Expanding existing `TimeframeAggregator`** with ta-lib indicators (RSI, MACD, BBANDS, ADX, ATR)
2. **Enriching `TradeMonitor._multi_timeframe_cache`** with feature pulse data
3. **Integrating pulse into `DecisionEngine` prompts** for AI-driven decisions
4. **Aligning `AdvancedBacktester`** to inject historical multi-timeframe pulse

### Design Principles

- **Backward Compatible:** Extend existing components, don't break current functionality
- **Performance-Conscious:** 5-minute refresh cadence, CPU-efficient (ta-lib, no heavy ML)
- **Fail-Soft:** Graceful degradation if data unavailable (e.g., crypto lacks 1m)
- **Cache-First:** Use `_multi_timeframe_cache` with TTL, avoid redundant API calls
- **Testable:** Modular design with clear interfaces, injectable dependencies

---

## Current State Analysis

### Existing Components (Verified via Serena)

#### 1. **UnifiedDataProvider** (`finance_feedback_engine/data_providers/unified_data_provider.py`)

**Methods:**
- `get_candles(asset_pair, timeframe)` → `(List[candles], provider_name)`
- `get_multi_timeframe_data(asset_pair, timeframes=['1m','5m','15m','1h','4h','1d'])` → `Dict[tf, (candles, provider)]`

**Capabilities:**
- ✅ Multi-provider support (Alpha Vantage, Coinbase, Oanda)
- ✅ 5-min TTL cache (`_cache`)
- ✅ Rate limiting via shared `rate_limiter`
- ✅ Crypto/forex detection (`_is_crypto`, `_is_forex`)

**Gap:**
- ❌ No metadata about data freshness/staleness
- ❌ No source provenance tracking per timeframe
- ❌ No aggregated multi-timeframe response

---

#### 2. **TimeframeAggregator** (`finance_feedback_engine/data_providers/timeframe_aggregator.py`)

**Methods:**
- `_calculate_sma(prices, period)` → Simple Moving Average
- `_calculate_rsi(prices, period=14)` → Relative Strength Index
- `_detect_trend(candles)` → `{"direction": str, "strength": float, "sma_50": float, "sma_200": float, "rsi": float}`
- `analyze_multi_timeframe(asset_pair)` → `{"timeframes": {...}, "trend_alignment": {...}, "entry_signals": {...}}`
- `get_summary_text(analysis)` → Human-readable summary

**Capabilities:**
- ✅ SMA-based trend detection (50/200 periods)
- ✅ RSI calculation (14 periods)
- ✅ Cross-timeframe trend alignment analysis
- ✅ Entry signal generation based on trend confluence

**Gaps:**
- ❌ No MACD indicator
- ❌ No Bollinger Bands
- ❌ No ADX (trend strength)
- ❌ No ATR (volatility)
- ❌ Volatility regime classification missing
- ❌ Signal strength scoring rudimentary

---

#### 3. **TradeMonitor** (`finance_feedback_engine/monitoring/trade_monitor.py`)

**Attributes:**
- `unified_data_provider` → UnifiedDataProvider instance
- `timeframe_aggregator` → TimeframeAggregator instance
- `pulse_interval` → Configurable (default: 300s = 5 min)
- `_last_pulse_time` → Timestamp of last pulse execution
- `_multi_timeframe_cache` → `Dict[asset, (analysis, timestamp)]`

**Methods:**
- `_maybe_execute_market_pulse()` → Runs every `pulse_interval`, calls `timeframe_aggregator.analyze_multi_timeframe()`
- `get_latest_market_context(asset_pair)` → Returns cached pulse or None
- `_get_assets_to_pulse()` → Returns list of watched assets (currently active trades + configured watchlist)

**Capabilities:**
- ✅ Automated 5-min pulse execution
- ✅ Multi-timeframe cache with timestamp
- ✅ Watchlist-based pulse targeting

**Gaps:**
- ❌ No ta-lib indicators in pulse (relies on basic SMA/RSI)
- ❌ Cache staleness validation (>5 min old = stale)
- ❌ No force-refresh mechanism for critical assets
- ❌ Pulse data not persisted (memory-only)

---

#### 4. **DecisionEngine** (`finance_feedback_engine/decision_engine/engine.py`)

**Methods (Inferred):**
- `_create_decision_context(asset_pair)` → Builds context dict for LLM prompt
- `make_decision(asset_pair)` → Returns decision with action/confidence/reasoning
- `set_monitoring_context(provider)` → Integrates TradeMonitor as context source

**Capabilities:**
- ✅ Monitoring context integration available
- ✅ Prompt construction with trading fundamentals

**Gaps:**
- ❌ Multi-timeframe pulse not required in context
- ❌ No pulse summary injection into prompts
- ❌ No fail-soft handling if pulse stale/unavailable

---

## Proposed Enhancements

### Phase 1: ta-lib Indicator Integration (This Sprint)

#### Component 1: Enhanced `TimeframeAggregator`

**New Methods:**

```python
def _calculate_macd(
    self, 
    prices: List[float], 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Dict[str, float]:
    """
    Calculate MACD using ta-lib.
    
    Returns:
        {"macd": float, "signal": float, "histogram": float}
    """
```

```python
def _calculate_bollinger_bands(
    self, 
    prices: List[float], 
    period: int = 20, 
    std_dev: float = 2.0
) -> Dict[str, float]:
    """
    Calculate Bollinger Bands using ta-lib.
    
    Returns:
        {"upper": float, "middle": float, "lower": float, "width": float}
    """
```

```python
def _calculate_adx(
    self, 
    high: List[float], 
    low: List[float], 
    close: List[float], 
    period: int = 14
) -> float:
    """
    Calculate ADX (Average Directional Index) using ta-lib.
    
    Returns:
        ADX value (0-100, >25 = trending)
    """
```

```python
def _calculate_atr(
    self, 
    high: List[float], 
    low: List[float], 
    close: List[float], 
    period: int = 14
) -> float:
    """
    Calculate ATR (Average True Range) using ta-lib.
    
    Returns:
        ATR value (absolute volatility measure)
    """
```

```python
def _classify_volatility(
    self, 
    atr: float, 
    price: float, 
    bbands_width: float
) -> Dict[str, Any]:
    """
    Classify volatility regime.
    
    Args:
        atr: Average True Range
        price: Current price
        bbands_width: Bollinger Bands width (upper - lower)
    
    Returns:
        {
            "regime": "high" | "medium" | "low",
            "atr_ratio": float,  # ATR/price
            "bbands_width_pct": float  # width/middle * 100
        }
    """
```

```python
def _calculate_signal_strength(
    self, 
    rsi: float, 
    macd_histogram: float, 
    bbands_position: float,  # (price - lower) / (upper - lower)
    adx: float
) -> Dict[str, Any]:
    """
    Calculate composite signal strength.
    
    Returns:
        {
            "score": float (0.0-1.0),
            "confidence": "high" | "medium" | "low",
            "aligned_indicators": List[str],  # e.g., ["rsi_bullish", "macd_bullish"]
            "divergent_indicators": List[str]
        }
    """
```

**Modified Method:**

```python
def analyze_multi_timeframe(
    self, 
    asset_pair: str
) -> Dict[str, Any]:
    """
    Enhanced multi-timeframe analysis with ta-lib indicators.
    
    Returns:
        {
            "asset_pair": str,
            "timestamp": str,  # ISO 8601 UTC
            "timeframes": {
                "1m": {...},   # Per-timeframe analysis
                "5m": {...},
                "15m": {...},
                "1h": {...},
                "4h": {...},
                "1d": {...}
            },
            "aggregated_signals": {
                "short_term_trend": str,    # 1m-15m consensus
                "medium_term_trend": str,   # 1h-4h consensus
                "long_term_trend": str,     # 1d consensus
                "regime": str,              # from MarketRegimeDetector
                "confidence": float,        # cross-timeframe agreement (0.0-1.0)
                "entry_signals": {...}      # Current implementation
            }
        }
    """
```

**Per-Timeframe Analysis Structure:**

```python
{
    "timeframe": "1m",
    "candles_count": 100,
    "latest_price": 42000.0,
    "indicators": {
        "rsi": 68.5,
        "macd": {
            "macd": 120.0,
            "signal": 115.0,
            "histogram": 5.0
        },
        "bollinger_bands": {
            "upper": 42500.0,
            "middle": 42000.0,
            "lower": 41500.0,
            "width": 1000.0,
            "width_pct": 2.38
        },
        "adx": 28.3,
        "atr": 150.2,
        "sma_50": 41900.0,
        "sma_200": 41500.0
    },
    "trend": {
        "direction": "bullish",        # "bullish" | "neutral" | "bearish"
        "strength": 0.72,              # 0.0-1.0
        "classification": "trending"    # "trending" | "ranging"
    },
    "volatility": {
        "regime": "high",              # "high" | "medium" | "low"
        "atr_ratio": 0.00357,          # ATR / price
        "bbands_width_pct": 2.38       # (upper - lower) / middle * 100
    },
    "signal_strength": {
        "score": 0.72,
        "confidence": "high",
        "aligned_indicators": ["rsi_bullish", "macd_bullish", "adx_trending"],
        "divergent_indicators": ["bbands_overbought"]
    }
}
```

---

#### Component 2: Enriched `UnifiedDataProvider`

**New Method:**

```python
def aggregate_all_timeframes(
    self,
    asset_pair: str,
    timeframes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Fetch and synchronize multi-timeframe data with metadata.
    
    Args:
        asset_pair: Asset pair (e.g., "BTCUSD")
        timeframes: List of timeframes (default: ['1m','5m','15m','1h','4h','1d'])
    
    Returns:
        {
            "asset_pair": str,
            "timestamp": str,  # ISO 8601 UTC
            "timeframes": {
                "1m": {
                    "candles": List[Dict],
                    "source_provider": str,
                    "last_updated": str,
                    "is_cached": bool,
                    "candles_count": int
                },
                # ... other timeframes
            },
            "metadata": {
                "requested_timeframes": List[str],
                "available_timeframes": List[str],
                "missing_timeframes": List[str],
                "cache_hit_rate": float
            }
        }
    """
```

**Implementation Notes:**
- Reuse existing `get_multi_timeframe_data()` internally
- Add timestamp, metadata tracking
- Handle missing timeframes gracefully (e.g., crypto lacks 1m)
- Log warnings for missing data, don't fail

---

#### Component 3: Enhanced `TradeMonitor`

**Modified Method:**

```python
def _maybe_execute_market_pulse(self):
    """
    Enhanced pulse with ta-lib indicators and cache staleness validation.
    
    Changes:
    - Call `timeframe_aggregator.analyze_multi_timeframe()` (now with ta-lib)
    - Validate cache staleness before returning in `get_latest_market_context()`
    - Log feature pulse summary at INFO level
    - Track pulse execution metrics (success rate, latency)
    """
```

**New Method:**

```python
def force_refresh_pulse(self, asset_pair: str) -> Dict[str, Any]:
    """
    Force immediate pulse refresh for critical assets.
    
    Use case: User requests analysis, cache is stale, need fresh data.
    
    Args:
        asset_pair: Asset to refresh
    
    Returns:
        Analysis dict from TimeframeAggregator
    """
```

**Modified Method:**

```python
def get_latest_market_context(
    self, 
    asset_pair: str,
    max_staleness_sec: int = 300  # 5 min default
) -> Optional[Dict[str, Any]]:
    """
    Enhanced cache retrieval with staleness validation.
    
    Args:
        asset_pair: Asset pair
        max_staleness_sec: Max allowed age of cached data
    
    Returns:
        Cached pulse if fresh, None if stale or unavailable
    
    Behavior:
    - Check cache timestamp
    - If >max_staleness_sec old, log warning and return None
    - Caller can decide: use stale data or force refresh
    """
```

---

#### Component 4: Integrated `DecisionEngine`

**Modified Method:**

```python
def _create_decision_context(
    self, 
    asset_pair: str
) -> Dict[str, Any]:
    """
    Enhanced context with mandatory multi-timeframe pulse.
    
    Changes:
    1. Call `monitoring_context_provider.get_latest_market_context(asset_pair)`
    2. If pulse None or stale (>5 min):
       - Log warning: "Multi-timeframe pulse unavailable/stale for {asset}"
       - Attempt force refresh via `force_refresh_pulse(asset_pair)`
       - If still fails, proceed WITHOUT pulse (fail-soft)
    3. Inject pulse summary into prompt construction
    
    Prompt Enhancement:
    ```
    === Multi-Timeframe Analysis (as of 2025-01-28 10:05:00 UTC) ===
    
    SHORT-TERM TRENDS (1m-15m):
    - Direction: BULLISH
    - Confidence: 72% (high agreement)
    - Key Signals:
      * RSI: 68.5 (approaching overbought)
      * MACD: Bullish crossover (histogram: +5.0)
      * Bollinger: Price at upper band (potential resistance)
    
    MEDIUM-TERM TRENDS (1h-4h):
    - Direction: NEUTRAL
    - Confidence: 58% (moderate agreement)
    - Divergence: MACD weakening, ADX declining (from 32 → 28)
    
    LONG-TERM TREND (1d):
    - Direction: BEARISH
    - Key Support: $41,500 (200-day SMA)
    - ADX: 28.3 (trending market)
    
    MARKET REGIME: HIGH_VOLATILITY_CHOP
    - ATR/Price: 0.357% (high volatility)
    - Bollinger Width: 2.38% (expanded bands)
    
    RECOMMENDATION CONTEXT:
    Given the multi-timeframe divergence (short-term bullish, long-term bearish),
    consider position sizing caution. High volatility suggests wider stop-loss.
    ```
    """
```

---

#### Component 5: Aligned `AdvancedBacktester`

**Modified Method:**

```python
def run(
    self,
    strategy: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10000.0,
    **kwargs
) -> Dict[str, Any]:
    """
    Enhanced backtesting with multi-timeframe pulse injection.
    
    Changes:
    1. Per candle step:
       a. Compute historical multi-timeframe pulse using `TimeframeAggregator`
       b. Inject pulse into decision context (same as live trading)
       c. Log pulse injection for debugging
    
    2. Use historical data from `HistoricalDataProvider`:
       - Fetch all timeframes for date range
       - Resample if missing (e.g., 1h → 4h)
       - Handle missing 1m data gracefully (log warning)
    
    3. Adapt metrics timebase:
       - Intra-day strategies (1m-15m): Sharpe/drawdown on hourly basis
       - Daily strategies (1h-1d): Sharpe/drawdown on daily basis
    
    Implementation:
    - Add `inject_pulse: bool = True` kwarg (default True)
    - If inject_pulse=False, skip (for A/B testing)
    - Log pulse summary per candle at DEBUG level
    """
```

**New Helper Method:**

```python
def _compute_historical_pulse(
    self,
    asset_pair: str,
    timestamp: datetime,
    lookback_candles: int = 200  # For SMA-200
) -> Dict[str, Any]:
    """
    Compute multi-timeframe pulse for historical timestamp.
    
    Args:
        asset_pair: Asset pair
        timestamp: Target timestamp
        lookback_candles: How many candles to fetch before timestamp
    
    Returns:
        Same structure as TimeframeAggregator.analyze_multi_timeframe()
    
    Implementation:
    - Fetch historical candles for each timeframe ending at `timestamp`
    - Call `TimeframeAggregator` methods directly
    - Cache results per timestamp to avoid redundant computation
    """
```

---

## Feature Pulse Structure

### Complete Pulse Schema

```python
{
    "asset_pair": "BTCUSD",
    "timestamp": "2025-01-28T10:05:00.000Z",  # ISO 8601 UTC
    "data_sources": {
        "1m": {"provider": "coinbase", "last_updated": "2025-01-28T10:04:55Z", "candles_count": 100},
        "5m": {"provider": "coinbase", "last_updated": "2025-01-28T10:05:00Z", "candles_count": 100},
        "15m": {"provider": "coinbase", "last_updated": "2025-01-28T10:00:00Z", "candles_count": 100},
        "1h": {"provider": "alpha_vantage", "last_updated": "2025-01-28T10:00:00Z", "candles_count": 200},
        "4h": {"provider": "alpha_vantage", "last_updated": "2025-01-28T08:00:00Z", "candles_count": 200},
        "1d": {"provider": "alpha_vantage", "last_updated": "2025-01-28T00:00:00Z", "candles_count": 365}
    },
    "timeframes": {
        "1m": {
            "timeframe": "1m",
            "candles_count": 100,
            "latest_price": 42000.0,
            "indicators": {
                "rsi": 68.5,
                "macd": {"macd": 120.0, "signal": 115.0, "histogram": 5.0},
                "bollinger_bands": {
                    "upper": 42500.0,
                    "middle": 42000.0,
                    "lower": 41500.0,
                    "width": 1000.0,
                    "width_pct": 2.38
                },
                "adx": 28.3,
                "atr": 150.2,
                "sma_50": 41900.0,
                "sma_200": 41500.0
            },
            "trend": {
                "direction": "bullish",
                "strength": 0.72,
                "classification": "trending"
            },
            "volatility": {
                "regime": "high",
                "atr_ratio": 0.00357,
                "bbands_width_pct": 2.38
            },
            "signal_strength": {
                "score": 0.72,
                "confidence": "high",
                "aligned_indicators": ["rsi_bullish", "macd_bullish", "adx_trending"],
                "divergent_indicators": ["bbands_overbought"]
            }
        },
        "5m": { ... },   # Same structure
        "15m": { ... },
        "1h": { ... },
        "4h": { ... },
        "1d": { ... }
    },
    "aggregated_signals": {
        "short_term_trend": {
            "direction": "bullish",
            "confidence": 0.72,
            "timeframes_aligned": ["1m", "5m", "15m"],
            "timeframes_divergent": []
        },
        "medium_term_trend": {
            "direction": "neutral",
            "confidence": 0.58,
            "timeframes_aligned": ["1h"],
            "timeframes_divergent": ["4h"]
        },
        "long_term_trend": {
            "direction": "bearish",
            "confidence": 0.85,
            "timeframes_aligned": ["1d"],
            "timeframes_divergent": []
        },
        "regime": "HIGH_VOLATILITY_CHOP",  # From MarketRegimeDetector
        "cross_timeframe_agreement": 0.68,  # Weighted average of all TF confidences
        "entry_signals": {
            "action": "BUY",
            "strength": 0.65,
            "conditions": [
                "Short-term bullish breakout",
                "Medium-term consolidation",
                "Long-term at support (200 SMA)"
            ],
            "warnings": [
                "High volatility - use wider stop-loss",
                "Multi-timeframe divergence - reduce position size"
            ]
        }
    },
    "metadata": {
        "pulse_duration_ms": 1250,
        "providers_used": ["coinbase", "alpha_vantage"],
        "cache_hit_rate": 0.67,
        "missing_timeframes": [],
        "warnings": []
    }
}
```

---

## Data Flow

### 1. Live Trading Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ TradeMonitor (every 5 min)                                       │
│   ├─> _maybe_execute_market_pulse()                             │
│   │     ├─> UnifiedDataProvider.aggregate_all_timeframes()      │
│   │     │     ├─> get_candles("BTCUSD", "1m") → (candles, prov) │
│   │     │     ├─> get_candles("BTCUSD", "5m") → (candles, prov) │
│   │     │     ├─> ... (all timeframes)                          │
│   │     │     └─> Returns: Dict[tf, (candles, provider)]        │
│   │     │                                                         │
│   │     ├─> TimeframeAggregator.analyze_multi_timeframe()       │
│   │     │     ├─> _calculate_rsi()      (ta-lib)                │
│   │     │     ├─> _calculate_macd()     (ta-lib)                │
│   │     │     ├─> _calculate_bollinger_bands() (ta-lib)         │
│   │     │     ├─> _calculate_adx()      (ta-lib)                │
│   │     │     ├─> _calculate_atr()      (ta-lib)                │
│   │     │     ├─> _classify_volatility()                        │
│   │     │     ├─> _calculate_signal_strength()                  │
│   │     │     └─> Returns: Feature Pulse (see schema above)     │
│   │     │                                                         │
│   │     └─> Store in _multi_timeframe_cache[asset] = (pulse, now)│
│   │                                                               │
│   └─> DecisionEngine.make_decision(asset_pair)                  │
│         ├─> _create_decision_context(asset_pair)                │
│         │     ├─> get_latest_market_context(asset_pair)         │
│         │     │     └─> Returns: cached pulse (if fresh)        │
│         │     │                                                  │
│         │     └─> Inject pulse summary into LLM prompt          │
│         │                                                        │
│         └─> Returns: Decision with action/confidence/reasoning  │
└──────────────────────────────────────────────────────────────────┘
```

### 2. Backtesting Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ AdvancedBacktester.run()                                         │
│   ├─> For each candle (start_date → end_date):                  │
│   │     │                                                         │
│   │     ├─> _compute_historical_pulse(asset, timestamp)         │
│   │     │     ├─> HistoricalDataProvider.get_historical_data()  │
│   │     │     │     └─> Returns: candles for each TF            │
│   │     │     │                                                  │
│   │     │     └─> TimeframeAggregator.analyze_multi_timeframe() │
│   │     │           (same as live, using historical data)       │
│   │     │                                                        │
│   │     ├─> Inject pulse into decision context                  │
│   │     ├─> DecisionEngine.make_decision()                      │
│   │     ├─> Simulate trade execution                            │
│   │     └─> Update metrics (Sharpe, drawdown, P&L)              │
│   │                                                               │
│   └─> Returns: Backtest results with metrics                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Python Packages

**Add to `requirements.txt`:**

```
TA-Lib==0.4.28  # Technical analysis indicators
```

**No need for tsfresh** (deferred to Phase 2 - basic ta-lib indicators sufficient for now)

### System Dependencies (ta-lib C Library)

**Ubuntu/Debian:**
```bash
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
ldconfig  # Update library cache
```

**macOS:**
```bash
brew install ta-lib
```

**Verification:**
```python
import talib
print(talib.__version__)  # Should print "0.4.0" or similar
```

---

## Testing Strategy

### Unit Tests

#### 1. **TimeframeAggregator** (`tests/test_timeframe_aggregator.py`)

```python
def test_calculate_macd_with_synthetic_data():
    """Test MACD calculation using known price series."""
    prices = generate_synthetic_prices(trend="bullish", volatility="low", count=100)
    aggregator = TimeframeAggregator(mock_data_provider)
    
    macd = aggregator._calculate_macd(prices)
    
    assert "macd" in macd
    assert "signal" in macd
    assert "histogram" in macd
    assert macd["histogram"] > 0  # Bullish trend should have positive histogram

def test_bollinger_bands_volatility_regime():
    """Test Bollinger width correlates with volatility."""
    high_vol_prices = generate_synthetic_prices(volatility="high", count=100)
    low_vol_prices = generate_synthetic_prices(volatility="low", count=100)
    
    aggregator = TimeframeAggregator(mock_data_provider)
    
    high_vol_bbands = aggregator._calculate_bollinger_bands(high_vol_prices)
    low_vol_bbands = aggregator._calculate_bollinger_bands(low_vol_prices)
    
    assert high_vol_bbands["width"] > low_vol_bbands["width"]

def test_signal_strength_alignment():
    """Test composite signal strength with aligned indicators."""
    # All bullish indicators
    signal = aggregator._calculate_signal_strength(
        rsi=65.0,              # Bullish but not overbought
        macd_histogram=5.0,    # Bullish crossover
        bbands_position=0.7,   # Above middle
        adx=30.0               # Trending
    )
    
    assert signal["score"] > 0.7
    assert signal["confidence"] == "high"
    assert len(signal["aligned_indicators"]) >= 3
```

#### 2. **UnifiedDataProvider** (`tests/test_unified_data_provider.py`)

```python
def test_aggregate_all_timeframes_with_missing_data():
    """Test graceful handling of missing 1m data for crypto."""
    provider = UnifiedDataProvider(config)
    
    # Mock: Coinbase doesn't support 1m for some assets
    result = provider.aggregate_all_timeframes("ETHUSD", timeframes=["1m", "5m", "1h"])
    
    assert "1m" in result["timeframes"]
    assert result["timeframes"]["1m"]["candles"] == []  # Empty but present
    assert "1m" in result["metadata"]["missing_timeframes"]
    assert result["metadata"]["cache_hit_rate"] >= 0.0

def test_aggregate_metadata_tracking():
    """Test metadata fields populated correctly."""
    provider = UnifiedDataProvider(config)
    
    result = provider.aggregate_all_timeframes("BTCUSD")
    
    assert "timestamp" in result
    assert "metadata" in result
    assert "requested_timeframes" in result["metadata"]
    assert len(result["metadata"]["requested_timeframes"]) == 6
```

#### 3. **TradeMonitor** (`tests/test_trade_monitor.py`)

```python
def test_pulse_staleness_validation():
    """Test get_latest_market_context rejects stale pulse."""
    monitor = TradeMonitor(...)
    
    # Inject old pulse (10 min ago)
    old_pulse = {"timestamp": (datetime.utcnow() - timedelta(minutes=10)).isoformat()}
    monitor._multi_timeframe_cache["BTCUSD"] = (old_pulse, time.time() - 600)
    
    result = monitor.get_latest_market_context("BTCUSD", max_staleness_sec=300)
    
    assert result is None  # Should reject stale data

def test_force_refresh_pulse():
    """Test force refresh bypasses cache."""
    monitor = TradeMonitor(...)
    
    # Cache exists but stale
    monitor._multi_timeframe_cache["BTCUSD"] = (old_pulse, time.time() - 600)
    
    fresh_pulse = monitor.force_refresh_pulse("BTCUSD")
    
    assert fresh_pulse is not None
    assert (time.time() - monitor._multi_timeframe_cache["BTCUSD"][1]) < 5  # Fresh timestamp
```

#### 4. **DecisionEngine** (`tests/test_decision_engine.py`)

```python
def test_decision_context_with_pulse():
    """Test pulse injection into decision context."""
    engine = DecisionEngine(config, ai_provider="mock")
    engine.set_monitoring_context(mock_monitor_with_pulse)
    
    context = engine._create_decision_context("BTCUSD")
    
    assert "multi_timeframe_pulse" in context
    assert context["multi_timeframe_pulse"]["asset_pair"] == "BTCUSD"
    assert "aggregated_signals" in context["multi_timeframe_pulse"]

def test_decision_prompt_includes_pulse_summary():
    """Test LLM prompt contains multi-timeframe analysis."""
    engine = DecisionEngine(config, ai_provider="mock")
    engine.set_monitoring_context(mock_monitor_with_pulse)
    
    decision = engine.make_decision("BTCUSD")
    
    # Check if prompt (logged or inspectable) contains pulse keywords
    assert "SHORT-TERM TRENDS" in decision["debug_prompt"]  # If exposed
    assert "MARKET REGIME" in decision["debug_prompt"]
```

#### 5. **AdvancedBacktester** (`tests/test_advanced_backtester.py`)

```python
def test_backtest_with_pulse_injection():
    """Test backtesting injects historical pulse per candle."""
    backtester = AdvancedBacktester(config, ai_provider="mock")
    
    results = backtester.run(
        strategy="ai_ensemble",
        start_date="2024-01-01",
        end_date="2024-01-31",
        inject_pulse=True
    )
    
    assert results["total_trades"] > 0
    # Check logs for pulse injection (if logged at DEBUG)

def test_backtest_without_pulse_for_ab_testing():
    """Test disabling pulse for comparison."""
    backtester = AdvancedBacktester(config, ai_provider="mock")
    
    results_no_pulse = backtester.run(..., inject_pulse=False)
    results_with_pulse = backtester.run(..., inject_pulse=True)
    
    # Compare Sharpe ratios (with pulse should be >=)
    assert results_with_pulse["sharpe_ratio"] >= results_no_pulse["sharpe_ratio"]
```

### Integration Tests

```python
def test_end_to_end_pulse_flow():
    """Test full flow: TradeMonitor → pulse → DecisionEngine → trade."""
    # Setup
    config = load_config("config.test.mock.yaml")
    engine = FinanceFeedbackEngine(config)
    monitor = TradeMonitor(...)
    monitor.start()
    
    # Wait for pulse
    time.sleep(6)  # Wait for 5-min pulse + buffer
    
    # Make decision
    decision = engine.analyze_asset("BTCUSD", provider="mock")
    
    # Verify pulse was used
    assert "multi_timeframe_analysis" in decision["metadata"]
    assert decision["metadata"]["multi_timeframe_analysis"]["timestamp"] is not None
    
    monitor.stop()
```

---

## Migration Path

### Step-by-Step Implementation

#### **Task 3: Implement aggregate_all_timeframes()**

**File:** `finance_feedback_engine/data_providers/unified_data_provider.py`

1. Add method after existing `get_multi_timeframe_data()`
2. Reuse internal `get_multi_timeframe_data()` call
3. Wrap result with metadata structure
4. Add timestamp generation (ISO 8601 UTC)
5. Track cache hit rate
6. Handle missing timeframes (log warning, add to metadata)
7. Write tests in `tests/test_unified_data_provider.py`

**Expected Changes:**
- New method: ~30 lines
- Tests: ~50 lines
- No breaking changes to existing methods

---

#### **Task 4: Extend TimeframeAggregator with ta-lib**

**File:** `finance_feedback_engine/data_providers/timeframe_aggregator.py`

**Dependencies:** Install ta-lib system library + Python wrapper

1. Add import: `import talib`
2. Implement helper methods:
   - `_calculate_macd()` → ~15 lines
   - `_calculate_bollinger_bands()` → ~15 lines
   - `_calculate_adx()` → ~10 lines
   - `_calculate_atr()` → ~10 lines
   - `_classify_volatility()` → ~20 lines
   - `_calculate_signal_strength()` → ~30 lines

3. Modify `analyze_multi_timeframe()`:
   - Call new indicator methods per timeframe
   - Add volatility classification
   - Add signal strength calculation
   - Aggregate cross-timeframe trends
   - ~50 lines of additions

4. Write tests in `tests/test_timeframe_aggregator.py`:
   - Test each indicator calculation
   - Test volatility classification
   - Test signal strength scoring
   - ~150 lines

**Expected Changes:**
- New methods: ~100 lines
- Modified method: ~50 lines
- Tests: ~150 lines
- **Backward compatible:** Existing `analyze_multi_timeframe()` callers see enriched data

---

#### **Task 5: Integrate Pulse into DecisionEngine**

**File:** `finance_feedback_engine/decision_engine/engine.py`

1. Modify `_create_decision_context()`:
   - Call `self.monitoring_context_provider.get_latest_market_context(asset_pair)`
   - Validate pulse freshness (<5 min)
   - If stale/unavailable, attempt `force_refresh_pulse()`
   - Inject pulse summary into prompt
   - ~40 lines of additions

2. Add prompt construction helper:
   - `_format_pulse_summary(pulse)` → ~50 lines
   - Generates multi-timeframe analysis text for LLM

3. Write tests in `tests/test_decision_engine.py`:
   - Test pulse requirement
   - Test staleness handling
   - Test prompt injection
   - ~100 lines

**Expected Changes:**
- Modified method: ~40 lines
- New helper: ~50 lines
- Tests: ~100 lines
- **Risk:** Medium — decision prompts change, may affect AI provider responses
- **Mitigation:** Test with mock AI provider first, compare decision quality

---

#### **Task 6: Align AdvancedBacktester**

**File:** `finance_feedback_engine/backtesting/advanced_backtester.py`

1. Add helper method `_compute_historical_pulse()`:
   - Fetch historical candles for all timeframes
   - Call `TimeframeAggregator.analyze_multi_timeframe()` with historical data
   - Cache per timestamp
   - ~60 lines

2. Modify `run()`:
   - Add `inject_pulse: bool = True` kwarg
   - Per candle: call `_compute_historical_pulse()` if inject_pulse=True
   - Inject into decision context (same as live trading)
   - Log pulse injection at DEBUG level
   - ~40 lines of additions

3. Write tests in `tests/test_advanced_backtester.py`:
   - Test pulse injection enabled/disabled
   - Compare metrics with vs without pulse
   - ~80 lines

**Expected Changes:**
- New method: ~60 lines
- Modified method: ~40 lines
- Tests: ~80 lines
- **Risk:** High — backtesting results will change
- **Mitigation:** Run A/B tests (inject_pulse=True vs False), document baseline metrics

---

#### **Task 7: Update Documentation**

1. **Add ta-lib to `requirements.txt`:**
   ```
   TA-Lib==0.4.28
   ```

2. **Update README.md:**
   - Add installation instructions for ta-lib system library
   - Ubuntu/macOS commands
   - Verification steps

3. **Create `docs/MULTI_TIMEFRAME_PULSE.md`:**
   - API reference for new methods
   - Feature pulse schema
   - Integration guide for custom AI providers

4. **Add demo script `demos/demo_multi_timeframe_pulse.py`:**
   - Show CLI usage: `python main.py analyze BTCUSD --show-pulse`
   - Display pulse summary
   - Compare with/without pulse

5. **Update CLI help text:**
   - Add `--show-pulse` flag to `analyze` command
   - Show pulse summary before decision

**Expected Changes:**
- requirements.txt: 1 line
- README.md: ~30 lines
- docs/MULTI_TIMEFRAME_PULSE.md: ~200 lines (copy from this design doc)
- demos/demo_multi_timeframe_pulse.py: ~80 lines
- cli/main.py: ~20 lines (--show-pulse flag)

---

## Success Metrics

| Metric | Baseline (Current) | Target (Phase 1 Complete) | Measurement Method |
|--------|-------------------|-----------------------------|---------------------|
| **Sharpe Ratio** | 0.8 | >1.2 (+50%) | Backtesting 2024 data, BTCUSD |
| **Max Drawdown** | -15% | <-10% | Worst peak-to-trough |
| **Win Rate** | 55% | >60% | Profitable trades / total |
| **Decision Latency** | <2s | <3s | Pulse compute + decision (amortized over 5-min cache) |
| **Feature Staleness** | N/A | <5 min | Cache TTL enforcement |
| **Cross-TF Agreement** | N/A | >70% | Aggregated confidence score |
| **Test Coverage** | 10.9% (isolated) | >70% | pytest --cov |

---

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **ta-lib installation fails (CI/CD)** | High (blocks deployment) | Medium | Docker image with pre-installed ta-lib, document manual steps |
| **Pulse latency >5s** | Medium (breaks real-time constraint) | Low | Profile with cProfile, optimize indicator calculations, reduce lookback periods |
| **AI provider prompt changes break decisions** | High (erratic trading) | Medium | Extensive testing with mock provider, A/B test with live provider (paper trading) |
| **Backtesting results diverge significantly** | Medium (lose confidence in backtest) | High | Expected — document baseline metrics, run A/B tests, communicate changes |
| **Missing 1m data for crypto** | Low (graceful degradation designed) | High | Test with multiple assets, log warnings clearly |
| **Cache staleness undetected** | High (decisions on stale data) | Low | Unit tests enforce staleness validation, monitor logs for warnings |

---

## Open Questions

1. **Should we persist pulse data to disk** (e.g., `data/pulses/YYYY-MM-DD_<uuid>.json`)?
   - **Pro:** Enables post-mortem analysis, debugging historical decisions
   - **Con:** Increases disk usage, adds I/O overhead
   - **Decision:** Defer to Phase 2 — start with memory-only cache, add persistence if debugging needs arise

2. **How to handle asset pairs with limited historical data** (e.g., new tokens)?
   - **Current:** Skip 200-period SMA if <200 candles
   - **Question:** Should we use shorter periods (e.g., SMA-20) dynamically?
   - **Decision:** Log warning, use available indicators, mark analysis as "incomplete" in metadata

3. **CLI flag naming: `--show-pulse` or `--verbose-analysis`?**
   - **Option 1:** `--show-pulse` (clear intent, specific to this feature)
   - **Option 2:** `--verbose-analysis` (more general, could include other analysis later)
   - **Decision:** Use `--show-pulse` for specificity, add `--verbose-analysis` in future if needed

4. **Should AdvancedBacktester support variable pulse intervals** (e.g., 1-min pulse for intra-day strategies)?
   - **Current:** Fixed 5-min pulse (matches live trading)
   - **Question:** Intra-day strategies may benefit from faster pulse (higher latency cost)
   - **Decision:** Defer to Phase 2 — start with 5-min, add configurability if performance allows

---

## Next Steps (Immediate)

1. ✅ **Research complete** (MULTI_TIMEFRAME_RESEARCH.md)
2. ✅ **Design complete** (this document)
3. → **Task 3:** Implement `aggregate_all_timeframes()` in UnifiedDataProvider
4. → **Task 4:** Extend TimeframeAggregator with ta-lib indicators
5. → **Task 5:** Integrate pulse into DecisionEngine
6. → **Task 6:** Align AdvancedBacktester with pulse injection
7. → **Task 7:** Update documentation and demos

**Timeline Estimate:** 3-4 days for implementation + testing (Tasks 3-7).

---

**Document Status:** DESIGN APPROVED — Ready for Implementation  
**Last Updated:** 2025-01-28  
**Author:** GitHub Copilot (Claude Sonnet 4.5) + User (c-penrod)
