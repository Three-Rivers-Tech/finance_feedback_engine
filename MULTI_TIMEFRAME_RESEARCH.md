# Multi-Timeframe Feature Extraction Research Summary

**Date:** 2025-01-28  
**Research Focus:** Multi-timeframe technical analysis and feature engineering for trading decision enhancement  
**Papers Reviewed:** 27 (Hugging Face ML research)

---

## Executive Summary

Multi-timeframe analysis is critical for robust trading decisions. Research shows that combining features across timeframes (1m, 5m, 15m, 1h, 4h, daily) significantly improves prediction accuracy and risk-adjusted returns compared to single-timeframe approaches.

**Key Decision:** Start with **Python ta-lib + tsfresh baseline** for technical indicators and basic feature engineering. Defer heavy ML (LSTM/xLSTM, transformers) to future phase given our constraints:
- 5-minute refresh cadence (performance-sensitive)
- Single GPU constraint
- Need for interpretable, debuggable features
- Existing mock AI provider architecture (works well for backtesting)

---

## Top Research Findings

### 1. Multi-Timeframe Analysis Effectiveness

**Paper:** *Neural Network-Based Algorithmic Trading Systems: Multi-Timeframe Analysis* ([2508.02356](https://hf.co/papers/2508.02356))

**Key Insights:**
- Multi-timeframe trend analysis + high-frequency prediction = positive risk-adjusted returns
- Cross-timeframe relationships enable sub-second trading decisions with statistical confidence
- Integrates market data, on-chain metrics, orderbook dynamics into unified buy/sell pressure signals

**Relevance to Our System:**
- Validates our approach of combining 1m, 5m, 15m, 1h, 4h, daily data
- TradeMonitor's 5-min pulse cadence aligns with "statistical confidence" from cross-timeframe patterns
- DecisionEngine should consume pulse as unified context, not fetch data per call

---

### 2. Wavelet Transform for Multi-Scale Feature Decomposition

**Paper:** *Stockformer: Wavelet Transform and Multi-Task Self-Attention* ([2401.06139](https://hf.co/papers/2401.06139))

**Key Insights:**
- Discrete wavelet transform decomposes stock returns into **high frequency (short-term fluctuations)** and **low frequency (long-term trends)**
- Captures abrupt events (e.g., sudden news, policy changes) missed by single-timeframe models
- Dual-Frequency Spatiotemporal Encoder + graph embedding for temporal/spatial relationships
- Outperforms baselines, maintains stability during downturns/volatility

**Implementation Considerations:**
- **Defer to Phase 2:** Wavelet transforms add complexity; ta-lib indicators (RSI, MACD, BBANDS) provide simpler trend/volatility decomposition
- **Future Enhancement:** If we see pattern-matching failures, revisit wavelets for short-term vs long-term signal separation

---

### 3. LSTM/xLSTM for Temporal Dependencies

**Paper:** *Deep Reinforcement Learning with xLSTM Networks* ([2503.09655](https://hf.co/papers/2503.09655))

**Key Insights:**
- xLSTM addresses gradient vanishing, captures long-term dependencies better than LSTM
- Used in actor-critic DRL (PPO) for automated trading
- Outperforms LSTM in: cumulative return, average profitability, max earning rate, Sharpe ratio

**Paper:** *Hedging Properties of Algorithmic Investment Strategies* ([2309.15640](https://hf.co/papers/2309.15640))

**Key Insights:**
- LSTM-based strategies outperform ARIMA-GARCH, momentum, contrarian models
- Higher frequency (1 hour) outperforms daily data
- Ensemble AIS (algorithmic investment strategies) built from diverse models improve diversification

**Implementation Decision:**
- **Current:** Keep mock AI provider for backtesting (fast, no Ollama overhead)
- **Future (Phase 2):** If ensemble needs predictive confidence, add LSTM/xLSTM as optional provider
- **Immediate:** Focus on feature pulse—LSTM can consume our multi-timeframe features later

---

### 4. Time Series Foundation Models (TSFMs)

**Paper:** *Kronos: Foundation Model for Financial K-line Data* ([2508.02739](https://hf.co/papers/2508.02739))

**Key Insights:**
- Pre-trained on 12 billion K-line records from 45 exchanges
- Specialized tokenizer discretizes continuous market data (price dynamics + trade activity)
- Zero-shot: +93% RankIC over leading TSFM, 9% lower MAE in volatility forecasting
- Achieves 22% improvement in synthetic K-line generation fidelity

**Relevance:**
- Demonstrates power of pre-trained models on massive financial time series
- Volatility forecasting directly aligns with our ADX/ATR regime detection needs
- **Defer to Phase 3:** Kronos is heavy (foundation model scale), but validates our volatility focus

---

### 5. Feature Engineering Frameworks

**Paper:** *Feature Programming for Multivariate Time Series* ([2306.06252](https://hf.co/papers/2306.06252))

**Key Insights:**
- Programmable feature engineering framework generates large amounts of predictive features for noisy time series
- Views time series as cumulative sum of fine-grained trajectory increments (spin-gas Ising model)
- Parsimonious set of operators for large-scale automated feature extraction
- Users incorporate inductive bias with minimal effort

**Paper:** *FinMultiTime: Four-Modal Bilingual Dataset* ([2506.05019](https://hf.co/papers/2506.05019))

**Key Insights:**
- Multi-modal fusion (financial news + structured tables + K-line charts + price series) yields gains in Transformers
- Minute-level, daily, quarterly resolutions capture short/medium/long-term signals
- Scale + data quality markedly boost prediction accuracy

**Implementation Approach:**
- **Immediate (Phase 1):** Use ta-lib (RSI, MACD, BBANDS, ADX, ATR) + tsfresh (basic statistical features) as "parsimonious operator set"
- **Future (Phase 2):** Add multi-modal inputs (news sentiment via existing sentiment_macro_features.md plan)
- **Future (Phase 3):** Automated feature generation framework if manual feature engineering becomes bottleneck

---

### 6. Technical Indicators in Practice

**Paper:** *Comparative Analysis of Neural Networks for FOREX Forecasting* ([2405.08045](https://hf.co/papers/2405.08045))

**Key Insights:**
- Custom ANN architecture based on **technical analysis indicator simulators** outperforms LSTM
- Better prediction quality, higher sensitivity, fewer resources, less time
- Ideal for low-power computing, fast decisions with least computational cost

**Implementation Validation:**
- **ta-lib indicators** (RSI, MACD, BBANDS, ADX, ATR) are industry-standard, CPU-efficient
- Aligns with our 5-min pulse cadence constraint (no GPU needed for indicators)
- Supports our decision to defer heavy ML until we validate baseline feature effectiveness

---

### 7. Multi-Timeframe Data Quality

**Paper:** *Rating Multi-Modal Time-Series Forecasting Models for Robustness* ([2406.12908](https://hf.co/papers/2406.12908))

**Key Insights:**
- Multi-modal (numeric + visual) forecasting more accurate AND more robust than numeric-only
- Causal analysis quantifies isolated impact of attributes on forecasting accuracy
- Robustness critical for noisy/incorrect data in real-world finance

**Relevance:**
- Our multi-timeframe pulse provides "multi-modal" view (short-term signals + long-term trends)
- Cache with TTL ensures data freshness, reduces noise from stale data
- Feature pulse acts as "causal layer" isolating timeframe-specific signals

---

## Implementation Plan (Baseline Architecture)

### Phase 1: Python ta-lib + tsfresh Baseline (Current Sprint)

**Rationale:**
- CPU-efficient, runs in <5 min refresh cycle
- Interpretable features (RSI, MACD, BBANDS) for human approval mode
- No GPU/Ollama overhead (matches current mock AI provider design)
- Industry-standard (ta-lib used in production trading systems)

**Technical Stack:**
1. **ta-lib** (Technical Analysis Library): RSI, MACD, BBANDS, ADX, ATR, SMA, EMA
2. **tsfresh** (Time Series Feature Extraction): statistical features (mean, std, trend, seasonality)
3. **Caching:** 5-min TTL in `_multi_timeframe_cache[asset]`
4. **Data Provider:** `UnifiedDataProvider.aggregate_all_timeframes()` returns dict of timeframe → OHLCV candles

**Feature Pulse Structure:**
```python
{
  "asset_pair": "BTCUSD",
  "timestamp": "2025-01-28T10:05:00Z",
  "timeframes": {
    "1m": {
      "rsi": 68.5,
      "macd": {"macd": 120, "signal": 115, "histogram": 5},
      "bbands": {"upper": 42500, "middle": 42000, "lower": 41500},
      "adx": 28.3,
      "atr": 150.2,
      "trend": "bullish",  # derived from MACD, ADX
      "volatility": "high",  # derived from ATR, Bollinger width
      "signal_strength": 0.72  # composite score
    },
    "5m": { ... },
    "15m": { ... },
    "1h": { ... },
    "4h": { ... },
    "1d": { ... }
  },
  "aggregated_signals": {
    "short_term_trend": "bullish",  # consensus from 1m, 5m, 15m
    "medium_term_trend": "neutral",  # 1h, 4h
    "long_term_trend": "bearish",  # 1d
    "regime": "HIGH_VOLATILITY_CHOP",  # from market_regime_detector.py
    "confidence": 0.68  # cross-timeframe agreement score
  }
}
```

**Key Methods:**

1. **`UnifiedDataProvider.aggregate_all_timeframes(asset_pair, timeframes=['1m','5m','15m','1h','4h','1d'])`**
   - Returns: `dict[timeframe, list[candles]]`
   - Handles missing data (e.g., crypto may lack 1m)
   - Applies 5-min TTL cache, shared rate limiter
   - Metadata: `source_provider`, `last_updated`, `is_cached`

2. **`TradeMonitor.compute_feature_pulse(asset, multi_tf_data)`**
   - Input: dict from `aggregate_all_timeframes()`
   - Compute per-timeframe indicators using ta-lib
   - Classify trend (bullish/neutral/bearish) from MACD histogram + ADX
   - Classify volatility (high/medium/low) from ATR/price ratio + Bollinger width
   - Calculate signal strength: weighted average of indicator confirmations
   - Aggregate cross-timeframe consensus (short/medium/long-term trends)
   - Emit to `_multi_timeframe_cache[asset]` with timestamp

3. **`DecisionEngine._create_decision_context(asset_pair)`**
   - **Require** multi_timeframe_pulse from `TradeMonitor._multi_timeframe_cache`
   - Fail-soft if stale (>5 min): log warning, fetch fresh data
   - Prefer cached pulse over per-call data fetching (performance)
   - Inject pulse summary into LLM prompt:
     ```
     Multi-Timeframe Analysis (as of 2025-01-28 10:05 UTC):
     - Short-term (1m-15m): BULLISH trend, HIGH volatility, RSI=68.5 (overbought warning)
     - Medium-term (1h-4h): NEUTRAL, divergence detected (MACD weakening)
     - Long-term (1d): BEARISH, ADX=28.3 (trending), support at $41,500
     - Market Regime: HIGH_VOLATILITY_CHOP (from ADX/ATR detector)
     - Cross-Timeframe Confidence: 68% (moderate agreement)
     ```

4. **`AdvancedBacktester.run(strategy, start_date, end_date)`**
   - Per candle step: inject historical feature pulse (compute from historical multi-timeframe data)
   - Use resampling fallback if historical multi-timeframe data unavailable (e.g., resample 1h to 4h)
   - Adapt metrics timebase: intra-day strategies (1m-15m) vs daily strategies (1h-1d)
   - Log pulse injection for debugging

---

### Phase 2: ML Enhancement (Future Sprint)

**Conditional Triggers:**
- Baseline ta-lib features show pattern-matching failures
- Ensemble needs predictive confidence (add LSTM/xLSTM provider)
- User requests sentiment analysis (integrate news/social media)

**Potential Additions:**
1. **LSTM/xLSTM provider** for temporal pattern learning
2. **Wavelet decomposition** for short-term vs long-term signal separation
3. **Sentiment analysis** from news/Twitter (align with `SENTIMENT_MACRO_FEATURES.md`)
4. **Graph Neural Networks** for inter-asset correlation (if multi-asset portfolio)

---

### Phase 3: Foundation Model Integration (Research Phase)

**Conditional Triggers:**
- Need zero-shot transfer to new assets/markets
- Volatility forecasting accuracy critical for risk management
- Synthetic data generation for stress testing

**Potential Models:**
- **Kronos** (financial K-line TSFM): volatility forecasting, synthetic data
- **FinMultiTime** approach: multi-modal fusion (price + news + charts)
- Custom pre-training on proprietary trade history

---

## Technical Indicator Reference

| Indicator | Purpose | ta-lib Function | Timeframes | Interpretation |
|-----------|---------|-----------------|------------|----------------|
| **RSI** | Overbought/Oversold | `RSI(close, timeperiod=14)` | All | >70 = overbought, <30 = oversold |
| **MACD** | Trend Momentum | `MACD(close, fast=12, slow=26, signal=9)` | All | Histogram crossover = trend change |
| **Bollinger Bands** | Volatility Envelope | `BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)` | All | Price near upper = overbought, near lower = oversold |
| **ADX** | Trend Strength | `ADX(high, low, close, timeperiod=14)` | 15m, 1h, 4h, 1d | >25 = trending, <20 = ranging |
| **ATR** | Volatility (absolute) | `ATR(high, low, close, timeperiod=14)` | All | Higher = more volatile, use for stop-loss sizing |
| **SMA** | Trend Direction | `SMA(close, timeperiod=50)` | 1h, 4h, 1d | Price > SMA = bullish, < SMA = bearish |
| **EMA** | Weighted Trend | `EMA(close, timeperiod=20)` | All | More responsive than SMA, use for fast signals |

**Composite Signals:**
- **Trend Classification:** MACD histogram sign + ADX value + price vs SMA
- **Volatility Regime:** ATR/price ratio + Bollinger band width
- **Signal Strength:** Count of aligned indicators (e.g., RSI + MACD + Bollinger all bullish = high strength)

---

## Dependencies

**Add to `requirements.txt`:**
```
TA-Lib==0.4.28  # Technical analysis indicators
tsfresh==0.20.1  # Time series feature extraction
```

**Installation (Ubuntu/Debian):**
```bash
# ta-lib C library (required before pip install)
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install

# Python packages
pip install TA-Lib tsfresh
```

**Installation (macOS):**
```bash
brew install ta-lib
pip install TA-Lib tsfresh
```

---

## Testing Strategy

1. **Unit Tests:**
   - `tests/test_unified_data_provider.py`: `aggregate_all_timeframes()` with mock data
   - `tests/test_trade_monitor.py`: `compute_feature_pulse()` with synthetic OHLCV
   - `tests/test_decision_engine.py`: pulse injection, stale data handling

2. **Integration Tests:**
   - `tests/test_multi_timeframe_integration.py`: End-to-end pulse generation → decision context → execution
   - Validate cache TTL behavior (fresh vs stale)
   - Test missing timeframe handling (e.g., crypto lacks 1m)

3. **Backtesting Validation:**
   - Run `AdvancedBacktester` on BTCUSD 2024-01-01 to 2024-12-01 with multi-timeframe pulse
   - Compare metrics (Sharpe, max drawdown, win rate) with vs without pulse
   - Verify pulse injection per candle step

4. **Manual Verification:**
   - CLI command: `python main.py analyze BTCUSD --show-pulse`
   - Display pulse summary before decision
   - Human approval mode: review pulse + decision before execution

---

## Success Metrics

| Metric | Baseline (No Pulse) | Target (With Pulse) | Measurement |
|--------|---------------------|---------------------|-------------|
| **Sharpe Ratio** | 0.8 | >1.2 | Backtesting 2024 data |
| **Max Drawdown** | -15% | <-10% | Worst peak-to-trough |
| **Win Rate** | 55% | >60% | Profitable trades / total trades |
| **Decision Latency** | <2s | <3s | Pulse compute + decision (5-min amortized) |
| **Feature Staleness** | N/A | <5 min | Cache TTL enforcement |
| **Cross-TF Agreement** | N/A | >70% | Aggregated confidence score |

---

## Known Limitations & Mitigations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **5-min refresh = stale intra-minute signals** | May miss sub-minute reversals | Trade Monitor supports on-demand pulse refresh for critical assets |
| **Missing 1m data for some assets** | Incomplete short-term analysis | Graceful degradation: use 5m as shortest timeframe, log warning |
| **ta-lib indicators lag real-time** | RSI/MACD calculated on historical close | Acceptable for 5-min cadence; real-time tick data deferred to Phase 2 |
| **No ML pattern recognition** | May miss complex multi-timeframe patterns | Baseline validates feature quality; add LSTM in Phase 2 if needed |
| **Cache invalidation risk** | Stale data if market gaps (weekend → Monday) | TTL + timestamp validation, force refresh on market open |

---

## References

### Key Papers (Full Citations)

1. **Multi-Timeframe Neural Networks** - [2508.02356](https://hf.co/papers/2508.02356): Wěi Zhāng, "Neural Network-Based Algorithmic Trading Systems: Multi-Timeframe Analysis and High-Frequency Execution in Cryptocurrency Markets" (Aug 2025)

2. **Wavelet Transform (Stockformer)** - [2401.06139](https://hf.co/papers/2401.06139): Bohan Ma et al., "Stockformer: A Price-Volume Factor Stock Selection Model Based on Wavelet Transform and Multi-Task Self-Attention Networks" (Nov 2023)

3. **xLSTM for Trading** - [2503.09655](https://hf.co/papers/2503.09655): Faezeh Sarlakifar et al., "A Deep Reinforcement Learning Approach to Automated Stock Trading, using xLSTM Networks" (Mar 2025)

4. **Kronos (TSFM)** - [2508.02739](https://hf.co/papers/2508.02739): Yu Shi et al., "Kronos: A Foundation Model for the Language of Financial Markets" (Aug 2025)

5. **Feature Programming** - [2306.06252](https://hf.co/papers/2306.06252): Alex Reneau et al., "Feature Programming for Multivariate Time Series Prediction" (Jun 2023)

6. **FinMultiTime** - [2506.05019](https://hf.co/papers/2506.05019): Wenyan Xu et al., "FinMultiTime: A Four-Modal Bilingual Dataset for Financial Time-Series Analysis" (Jun 2025)

7. **ANN Technical Indicators** - [2405.08045](https://hf.co/papers/2405.08045): Theodoros Zafeiriou et al., "Comparative analysis of neural network architectures for short-term FOREX forecasting" (May 2024)

8. **Robustness Rating** - [2406.12908](https://hf.co/papers/2406.12908): Kausik Lakkaraju et al., "Rating Multi-Modal Time-Series Forecasting Models (MM-TSFM) for Robustness Through a Causal Lens" (Jun 2024)

9. **LSTM-GNN Hybrid** - [2502.15813](https://hf.co/papers/2502.15813): Meet Satishbhai Sonani et al., "Stock Price Prediction Using a Hybrid LSTM-GNN Model: Integrating Time-Series and Graph-Based Analysis" (Feb 2025)

10. **Ensemble AIS** - [2309.15640](https://hf.co/papers/2309.15640): Jakub Michańków et al., "Hedging Properties of Algorithmic Investment Strategies using Long Short-Term Memory and Time Series models for Equity Indices" (Sep 2023)

### Additional References (Supporting)

- **Time2Vec + Transformers** - [2504.13801](https://hf.co/papers/2504.13801): Nguyen Kim Hai Bui et al., "Transformer Encoder and Multi-features Time2Vec for Financial Prediction" (Apr 2025)
- **HFT Optimization** - [2412.01062](https://hf.co/papers/2412.01062): Yuxin Fan et al., "Research on Optimizing Real-Time Data Processing in High-Frequency Trading Algorithms using Machine Learning" (Dec 2024)
- **Stock Pre-training** - [2506.16746](https://hf.co/papers/2506.16746): Mengyu Wang et al., "Pre-training Time Series Models with Stock Data Customization" (Jun 2025)
- **ROCKET (Feature Efficiency)** - [2204.01379](https://hf.co/papers/2204.01379): Leonardos Pantiskas et al., "Taking ROCKET on an Efficiency Mission: Multivariate Time Series Classification with LightWaveS" (Apr 2022)
- **Lead-Lag Relationships** - [2401.17548](https://hf.co/papers/2401.17548): Lifan Zhao et al., "Rethinking Channel Dependence for Multivariate Time Series Forecasting: Learning from Leading Indicators" (Jan 2024)

---

## Conclusion

Research validates our multi-timeframe approach and provides clear implementation path:

1. **Start Simple:** ta-lib + tsfresh baseline (Phase 1, current sprint)
2. **Measure Impact:** Backtest with vs without pulse, target >50% Sharpe improvement
3. **Iterate Conditionally:** Add ML (Phase 2) only if baseline shows pattern-matching failures
4. **Scale Strategically:** Foundation models (Phase 3) for zero-shot transfer, volatility forecasting

**Next Steps:**
1. ✅ Complete research (this document)
2. → Design pulse architecture (Task 2)
3. → Implement `aggregate_all_timeframes()` (Task 3)
4. → Build feature pulse computation (Task 4)
5. → Integrate into DecisionEngine (Task 5)
6. → Align AdvancedBacktester (Task 6)
7. → Documentation + demos (Task 7)

**Estimated Timeline:** 3-4 days for Phase 1 implementation + testing.
