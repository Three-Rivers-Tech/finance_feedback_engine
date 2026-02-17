# Curriculum Learning Design for SHORT Trading Optimization

**Version:** 1.0  
**Created:** 2026-02-14  
**Purpose:** Progressive learning framework for bidirectional (LONG/SHORT) trading strategy optimization

---

## Overview

This curriculum learning pipeline uses a **progressive difficulty approach** to optimize trading strategies for SHORT positions, building upon proven LONG-only performance. The system learns from simple market conditions first, then gradually introduces complexity.

### Core Philosophy

1. **Start Simple**: Learn LONG-only on clear bull markets
2. **Introduce Inverse**: Learn SHORT-only on clear bear markets  
3. **Mix Strategies**: Train both directions on mixed market regimes
4. **Harden System**: Test robustness across all conditions including choppy/sideways markets

### Success Criteria Progression

| Level | Win Rate Target | Sharpe Target | Max Drawdown | Notes |
|-------|----------------|---------------|--------------|-------|
| 1     | 50%+           | 0.8+          | 15%          | Baseline LONG profitability |
| 2     | 50%+           | 0.8+          | 15%          | SHORT mirrors LONG performance |
| 3     | 52%+           | 1.0+          | 20%          | Both directions profitable |
| 4     | 53%+           | 1.2+          | 25%          | Robust to all regimes |

---

## Level 1: LONG-Only on Bull Markets

### Objective
Establish baseline profitability with LONG positions during clear uptrends.

### Dataset Definition

**Cryptocurrency (Coinbase):**
- **BTC/USD**: 2020-01-01 to 2021-12-31
  - Covers COVID crash recovery → ATH run
  - Clear bull trend with corrections
  - Timeframes: M5, M15, H1
  
**Forex (Oanda):**
- **EUR/USD**: 2024-Q1 (Jan-Mar)
  - Recent data with upward bias
  - Timeframes: M5, M15, H1

**Total Duration:** ~2 years BTC + 3 months EUR/USD

### Market Regime Characteristics
- **Trend**: Strong uptrends (bull markets)
- **Volatility**: Moderate to high (crypto), low to moderate (forex)
- **Sentiment**: Predominantly bullish
- **Corrections**: Brief, shallow pullbacks

### Parameter Ranges

```python
LEVEL_1_PARAM_RANGES = {
    'direction': ['LONG'],  # Fixed: LONG-only
    
    # Stop Loss (percentage of entry price)
    'stop_loss_pct': (0.5, 3.0),  # 0.5% to 3%
    
    # Take Profit (percentage of entry price)
    'take_profit_pct': (1.0, 5.0),  # 1% to 5%
    
    # Risk-Reward Ratio (TP/SL ratio)
    'rr_ratio': (1.5, 4.0),  # Minimum 1.5:1, up to 4:1
    
    # Position Size (percentage of capital)
    'position_size_pct': (1.0, 5.0),  # 1% to 5% per trade
    
    # Entry confidence threshold
    'confidence_threshold': (0.6, 0.85),  # Ensemble agreement level
    
    # Maximum concurrent positions
    'max_positions': [1, 2, 3],  # Discrete values
}
```

### Train/Validation Split

- **Training**: 80% (first 80% chronologically)
  - BTC: 2020-01-01 to 2021-09-30
  - EUR/USD: Jan-Feb 2024
  
- **Validation**: 20% (final 20% chronologically)
  - BTC: 2021-10-01 to 2021-12-31
  - EUR/USD: March 2024

### Success Criteria

**Minimum (to progress to Level 2):**
- ✅ Win Rate ≥ 50%
- ✅ Positive total return (>0%)
- ✅ Sharpe Ratio ≥ 0.8
- ✅ Max Drawdown ≤ 15%
- ✅ Profit Factor ≥ 1.3

**Target (strong performance):**
- 🎯 Win Rate ≥ 55%
- 🎯 Total Return ≥ 20%
- 🎯 Sharpe Ratio ≥ 1.0
- 🎯 Max Drawdown ≤ 10%
- 🎯 Profit Factor ≥ 1.5

### Optimization Configuration

```python
LEVEL_1_OPTUNA_CONFIG = {
    'n_trials': 100,
    'n_jobs': 4,  # Parallel trials
    'sampler': 'TPESampler',
    'pruner': 'MedianPruner',
    'direction': 'maximize',  # Maximize Sharpe Ratio
    'timeout': 14400,  # 4 hours max
}
```

### Output Artifacts

1. `LEVEL_1_OPTIMIZATION_RESULTS.csv` - All trial results
2. `LEVEL_1_BEST_PARAMS.json` - Best parameters found
3. `LEVEL_1_PERFORMANCE_PLOTS.png` - Equity curves, drawdowns
4. `LEVEL_1_SUMMARY_REPORT.md` - Analysis and insights

---

## Level 2: SHORT-Only on Bear Markets

### Objective
Learn inverse strategy (SHORT) on clear downtrends. Validate that SHORT parameters mirror LONG effectiveness.

### Dataset Definition

**Cryptocurrency (Coinbase):**
- **BTC/USD**: 2022-01-01 to 2022-12-31
  - LUNA crash, FTX collapse period
  - Clear bear trend from $47k → $16k
  - Timeframes: M5, M15, H1

**Forex (Oanda):**
- **EUR/USD**: 2023-Q2 to 2023-Q4 (Apr-Dec)
  - ECB rate decision impacts
  - Downtrend bias
  - Timeframes: M5, M15, H1

**Total Duration:** 1 year BTC + 9 months EUR/USD

### Market Regime Characteristics
- **Trend**: Strong downtrends (bear markets)
- **Volatility**: High to extreme (crypto), moderate (forex)
- **Sentiment**: Predominantly bearish
- **Rallies**: Brief, weak relief rallies (dead cat bounces)

### Parameter Ranges

```python
LEVEL_2_PARAM_RANGES = {
    'direction': ['SHORT'],  # Fixed: SHORT-only
    
    # Stop Loss (percentage of entry price)
    'stop_loss_pct': (0.5, 3.0),
    
    # Take Profit (percentage of entry price)
    'take_profit_pct': (1.0, 5.0),
    
    # Risk-Reward Ratio
    'rr_ratio': (1.5, 4.0),
    
    # Position Size
    'position_size_pct': (1.0, 5.0),
    
    # Entry confidence threshold
    'confidence_threshold': (0.6, 0.85),
    
    # Maximum concurrent positions
    'max_positions': [1, 2, 3],
}
```

### Train/Validation Split

- **Training**: 80%
  - BTC: 2022-01-01 to 2022-10-15
  - EUR/USD: Apr-Oct 2023
  
- **Validation**: 20%
  - BTC: 2022-10-16 to 2022-12-31
  - EUR/USD: Nov-Dec 2023

### Success Criteria

**Minimum:**
- ✅ Win Rate ≥ 50%
- ✅ Positive total return (>0%)
- ✅ Sharpe Ratio ≥ 0.8
- ✅ Max Drawdown ≤ 15%
- ✅ Profit Factor ≥ 1.3
- ✅ **Comparison**: SHORT params within ±20% of LONG params (from Level 1)

**Target:**
- 🎯 Win Rate ≥ 55%
- 🎯 Total Return ≥ 20%
- 🎯 Sharpe Ratio ≥ 1.0
- 🎯 Max Drawdown ≤ 10%
- 🎯 SHORT/LONG parameter similarity analysis shows consistent risk management

### Optimization Configuration

```python
LEVEL_2_OPTUNA_CONFIG = {
    'n_trials': 100,
    'n_jobs': 4,
    'sampler': 'TPESampler',
    'pruner': 'MedianPruner',
    'direction': 'maximize',
    'timeout': 14400,
}
```

### Analysis Requirements

1. **Parameter Comparison**:
   - Compare optimal SHORT vs LONG parameters
   - Analyze symmetry/asymmetry in risk management
   - Document differences and hypothesize causes

2. **Performance Comparison**:
   - SHORT bear market performance vs LONG bull market performance
   - Risk-adjusted returns comparison
   - Drawdown behavior analysis

### Output Artifacts

1. `LEVEL_2_OPTIMIZATION_RESULTS.csv`
2. `LEVEL_2_BEST_PARAMS.json`
3. `LEVEL_2_PERFORMANCE_PLOTS.png`
4. `LEVEL_2_VS_LEVEL_1_COMPARISON.md` - **Key analysis document**
5. `LEVEL_2_SUMMARY_REPORT.md`

---

## Level 3: Mixed LONG/SHORT on Full Cycles

### Objective
Train strategy to select correct direction (LONG vs SHORT) across complete market cycles including bull, bear, and transitional periods.

### Dataset Definition

**Cryptocurrency (Coinbase):**
- **BTC/USD**: 2020-01-01 to 2023-12-31 (full 4 years)
  - Bull: 2020-2021
  - Bear: 2022
  - Recovery/Mixed: 2023
  - Timeframes: M5, M15, H1

- **ETH/USD**: 2020-01-01 to 2023-12-31 (full 4 years)
  - Similar cycle dynamics to BTC
  - Different volatility profile
  - Timeframes: M5, M15, H1

**Forex (Oanda):**
- **EUR/USD**: 2020-01-01 to 2023-12-31 (full 4 years)
  - COVID impact, ECB policy shifts
  - Multi-regime periods
  - Timeframes: M5, M15, H1

- **GBP/USD**: 2020-01-01 to 2023-12-31 (full 4 years)
  - Brexit impacts, BOE policy
  - High volatility events
  - Timeframes: M5, M15, H1

**Total Duration:** 4 years across 4 pairs

### Market Regime Characteristics
- **Trend**: Mixed (bull, bear, sideways transitions)
- **Volatility**: Full spectrum (low to extreme)
- **Sentiment**: Dynamic, shifting
- **Challenges**: Regime detection, direction selection

### Parameter Ranges

```python
LEVEL_3_PARAM_RANGES = {
    'direction': ['LONG', 'SHORT', 'BOTH'],  # Dynamic direction selection
    
    # Stop Loss (may differ by direction)
    'stop_loss_pct_long': (0.5, 3.0),
    'stop_loss_pct_short': (0.5, 3.0),
    
    # Take Profit (may differ by direction)
    'take_profit_pct_long': (1.0, 5.0),
    'take_profit_pct_short': (1.0, 5.0),
    
    # Risk-Reward Ratio
    'rr_ratio_long': (1.5, 4.0),
    'rr_ratio_short': (1.5, 4.0),
    
    # Position Size
    'position_size_pct': (1.0, 5.0),
    
    # Entry confidence thresholds
    'confidence_threshold_long': (0.6, 0.85),
    'confidence_threshold_short': (0.6, 0.85),
    
    # Regime detection parameters
    'regime_lookback_periods': [50, 100, 200],
    'regime_ma_fast': [10, 20, 50],
    'regime_ma_slow': [50, 100, 200],
    
    # Maximum concurrent positions
    'max_positions': [2, 3, 4],
    
    # LONG/SHORT balance
    'max_long_positions': [1, 2, 3],
    'max_short_positions': [1, 2, 3],
}
```

### Train/Validation Split

- **Training**: 75% (2020-01-01 to 2022-12-31)
  - 3 years of data
  - Includes full bull and bear cycles
  
- **Validation**: 25% (2023-01-01 to 2023-12-31)
  - 1 year of out-of-sample data
  - Tests generalization to new conditions

### Success Criteria

**Minimum:**
- ✅ Overall Win Rate ≥ 52%
- ✅ Win Rate LONG ≥ 50%
- ✅ Win Rate SHORT ≥ 50%
- ✅ Total Return ≥ 30% (over 3 years training)
- ✅ Sharpe Ratio ≥ 1.0
- ✅ Max Drawdown ≤ 20%
- ✅ Profit Factor ≥ 1.4
- ✅ Positive returns in both LONG and SHORT trades

**Target:**
- 🎯 Overall Win Rate ≥ 55%
- 🎯 Total Return ≥ 50%
- 🎯 Sharpe Ratio ≥ 1.3
- 🎯 Max Drawdown ≤ 15%
- 🎯 Consistent monthly returns (at least 70% of months profitable)
- 🎯 Calmar Ratio ≥ 2.0

### Optimization Configuration

```python
LEVEL_3_OPTUNA_CONFIG = {
    'n_trials': 150,  # More trials for increased complexity
    'n_jobs': 4,
    'sampler': 'TPESampler',
    'pruner': 'MedianPruner',
    'direction': 'maximize',
    'timeout': 21600,  # 6 hours max
}
```

### Analysis Requirements

1. **Regime Analysis**:
   - Identify bull/bear/sideways periods in training data
   - Performance breakdown by regime
   - Direction selection accuracy

2. **LONG vs SHORT Performance**:
   - Separate metrics for each direction
   - Trade count distribution
   - Risk-adjusted returns per direction

3. **Parameter Stability**:
   - Sensitivity analysis
   - Parameter correlation study
   - Overfitting checks

### Output Artifacts

1. `LEVEL_3_OPTIMIZATION_RESULTS.csv`
2. `LEVEL_3_BEST_PARAMS.json`
3. `LEVEL_3_PERFORMANCE_PLOTS.png`
4. `LEVEL_3_REGIME_ANALYSIS.md` - **Regime breakdown and insights**
5. `LEVEL_3_DIRECTION_ANALYSIS.md` - **LONG vs SHORT comparison**
6. `LEVEL_3_SUMMARY_REPORT.md`

---

## Level 4: All Market Regimes + Robustness Testing

### Objective
Stress-test the strategy across ALL conditions including choppy/sideways markets, high volatility events, and edge cases. Ensure production-ready robustness.

### Dataset Definition

**Full Dataset (2020-2023, all pairs, all timeframes):**
- BTC/USD: M5, M15, H1
- ETH/USD: M5, M15, H1
- EUR/USD: M5, M15, H1
- GBP/USD: M5, M15, H1

**Specific Stress Periods:**
- COVID crash (Mar 2020)
- BTC halving run (2020-2021)
- LUNA/UST collapse (May 2022)
- FTX collapse (Nov 2022)
- ECB rate hikes (2022-2023)
- Brexit volatility events

### Market Regime Characteristics
- **Trend**: All types (bull, bear, sideways, whipsaw)
- **Volatility**: Full spectrum including black swan events
- **Sentiment**: All market conditions
- **Challenges**: Choppy markets, false signals, regime changes

### Parameter Ranges

```python
LEVEL_4_PARAM_RANGES = {
    # Same as Level 3, plus:
    
    # Choppy market filter
    'adx_threshold': [15, 20, 25, 30],  # Minimum trend strength
    'volatility_filter': (0.5, 2.0),  # ATR-based filter
    
    # Dynamic position sizing
    'dynamic_sizing': [True, False],
    'size_volatility_adjust': (0.5, 1.5),
    
    # Risk management enhancements
    'max_daily_loss_pct': (2.0, 5.0),
    'max_weekly_loss_pct': (5.0, 10.0),
    'trailing_stop_activation': (1.0, 2.5),  # % profit before activation
    'trailing_stop_distance': (0.3, 1.5),  # % from peak
    
    # Market condition filters
    'min_volume_ratio': (0.5, 1.5),  # vs average volume
    'spread_max_pips': [2, 3, 5],  # Maximum acceptable spread
}
```

### Train/Validation/Test Split

- **Training**: 60% (2020-01-01 to 2022-05-31)
  - 2.5 years
  - Includes bull and early bear
  
- **Validation**: 20% (2022-06-01 to 2022-12-31)
  - 7 months
  - Deep bear market
  
- **Test (Hold-out)**: 20% (2023-01-01 to 2023-12-31)
  - 1 year
  - Never seen during optimization
  - Final robustness check

### Success Criteria

**Minimum:**
- ✅ Overall Win Rate ≥ 53%
- ✅ Win Rate in choppy periods ≥ 45%
- ✅ Total Return (all data) ≥ 40%
- ✅ Sharpe Ratio ≥ 1.2
- ✅ Max Drawdown ≤ 25%
- ✅ Profit Factor ≥ 1.5
- ✅ Sortino Ratio ≥ 1.5
- ✅ Calmar Ratio ≥ 1.8
- ✅ Positive returns in test set (2023)

**Target:**
- 🎯 Overall Win Rate ≥ 56%
- 🎯 Total Return ≥ 60%
- 🎯 Sharpe Ratio ≥ 1.5
- 🎯 Max Drawdown ≤ 20%
- 🎯 Calmar Ratio ≥ 2.5
- 🎯 Consistent performance across all timeframes
- 🎯 Robust to parameter variations (±10%)

### Optimization Configuration

```python
LEVEL_4_OPTUNA_CONFIG = {
    'n_trials': 200,  # Maximum trials for final optimization
    'n_jobs': 4,
    'sampler': 'TPESampler',
    'pruner': 'MedianPruner',
    'direction': 'maximize',
    'timeout': 28800,  # 8 hours max
}
```

### Robustness Tests

1. **Walk-Forward Analysis**:
   - Split data into 6-month windows
   - Optimize on each window, test on next
   - Measure performance degradation

2. **Monte Carlo Simulation**:
   - 1000 random trade sequences
   - Measure distribution of outcomes
   - Calculate confidence intervals

3. **Parameter Sensitivity Analysis**:
   - Vary each parameter ±10%, ±20%
   - Measure impact on key metrics
   - Identify brittle parameters

4. **Stress Testing**:
   - Remove best 20% of trades (luck removal)
   - Add transaction costs (slippage, commissions)
   - Test with reduced capital
   - Test with higher position limits

5. **Market Regime Breakdown**:
   - Classify all periods by regime
   - Performance metrics per regime
   - Failure mode analysis

### Output Artifacts

1. `LEVEL_4_OPTIMIZATION_RESULTS.csv`
2. `LEVEL_4_BEST_PARAMS.json`
3. `LEVEL_4_PERFORMANCE_PLOTS.png`
4. `LEVEL_4_ROBUSTNESS_TESTS.md` - **Comprehensive stress test results**
5. `LEVEL_4_WALK_FORWARD_ANALYSIS.md`
6. `LEVEL_4_MONTE_CARLO_RESULTS.csv`
7. `LEVEL_4_PARAMETER_SENSITIVITY.md`
8. `LEVEL_4_SUMMARY_REPORT.md`

---

## Progression Rules

### Level Advancement Criteria

**To advance from Level N to Level N+1:**
1. All **minimum** success criteria must be met
2. At least 80% of **target** criteria should be met
3. No critical failures (e.g., catastrophic drawdowns)
4. Manual review and approval

### Failure Handling

**If a level fails to meet minimum criteria:**
1. Analyze failure modes
2. Adjust parameter ranges if needed
3. Increase trial count by 50%
4. Re-run optimization
5. If still failing after 3 attempts, escalate for design review

### Parameter Inheritance

- **Level 2**: Use Level 1 best params as starting point for SHORT optimization
- **Level 3**: Use both Level 1 and Level 2 best params as priors
- **Level 4**: Use Level 3 best params as baseline, expand search space for robustness

---

## Implementation Details

### Objective Function

```python
def curriculum_objective_function(trial, level, data, params):
    """
    Multi-objective optimization function.
    Primary: Sharpe Ratio
    Secondary: Win Rate, Max Drawdown, Profit Factor
    """
    
    # Suggest parameters based on level ranges
    suggested_params = suggest_params_for_level(trial, level)
    
    # Run backtest
    results = run_backtest(data, suggested_params)
    
    # Calculate primary metric
    sharpe_ratio = results['sharpe_ratio']
    
    # Apply penalties for constraint violations
    if results['win_rate'] < 0.50:
        sharpe_ratio *= 0.5  # Heavy penalty
    
    if results['max_drawdown'] > get_level_max_dd(level):
        sharpe_ratio *= 0.7
    
    if results['profit_factor'] < 1.3:
        sharpe_ratio *= 0.8
    
    # Bonus for exceeding targets
    if results['win_rate'] > 0.55:
        sharpe_ratio *= 1.1
    
    return sharpe_ratio
```

### Data Loading Strategy

```python
def load_level_data(level):
    """Load appropriate dataset for curriculum level"""
    
    if level == 1:
        return load_bull_market_data()
    elif level == 2:
        return load_bear_market_data()
    elif level == 3:
        return load_full_cycle_data()
    elif level == 4:
        return load_all_data_with_stress_periods()
```

### Logging and Tracking

- All trials logged to Optuna study database (PostgreSQL)
- Real-time progress tracking
- Intermediate results saved every 10 trials
- Best parameters checkpointed after each improvement
- Comprehensive logs in `data/optimization_logs/`

---

## Timeline Estimates

| Phase | Level | Estimated Duration | Notes |
|-------|-------|-------------------|-------|
| Data Acquisition | - | 3-4 hours | Parallel API fetches |
| Level 1 Optimization | 1 | 3-4 hours | 100 trials, simpler data |
| Level 2 Optimization | 2 | 3-4 hours | 100 trials, similar complexity |
| Level 3 Optimization | 3 | 4-6 hours | 150 trials, more data |
| Level 4 Optimization | 4 | 4-6 hours | 200 trials, full dataset |
| Analysis & Reporting | All | 2-3 hours | Compile results |
| **TOTAL** | | **19-27 hours** | Conservative estimate |

---

## Success Metrics Summary

| Metric | Level 1 | Level 2 | Level 3 | Level 4 |
|--------|---------|---------|---------|---------|
| **Win Rate (min)** | 50% | 50% | 52% | 53% |
| **Win Rate (target)** | 55% | 55% | 55% | 56% |
| **Sharpe Ratio (min)** | 0.8 | 0.8 | 1.0 | 1.2 |
| **Sharpe Ratio (target)** | 1.0 | 1.0 | 1.3 | 1.5 |
| **Max Drawdown (max)** | 15% | 15% | 20% | 25% |
| **Profit Factor (min)** | 1.3 | 1.3 | 1.4 | 1.5 |

---

## Infrastructure Requirements

### Compute Resources
- CPU: 4+ cores for parallel trials
- RAM: 16GB+ (for large datasets)
- Disk: 50GB+ for data and results storage

### Software Dependencies
- Python 3.13+
- Optuna 3.0+
- PostgreSQL 14+ (for study storage)
- pandas, numpy, scipy (data processing)
- matplotlib, seaborn (visualization)

### Monitoring
- Optuna dashboard for real-time progress
- Custom metrics dashboard
- Alert system for failures

---

## Output Structure

```
finance_feedback_engine/
├── data/
│   └── historical/
│       └── curriculum_2020_2023/
│           ├── BTC_USD_M5_2020_2023.parquet
│           ├── BTC_USD_M15_2020_2023.parquet
│           ├── BTC_USD_H1_2020_2023.parquet
│           ├── ETH_USD_M5_2020_2023.parquet
│           ├── ... (all pairs/timeframes)
│           └── acquisition_summary.csv
│
├── optimization_results/
│   ├── level_1/
│   │   ├── LEVEL_1_OPTIMIZATION_RESULTS.csv
│   │   ├── LEVEL_1_BEST_PARAMS.json
│   │   ├── LEVEL_1_PERFORMANCE_PLOTS.png
│   │   └── LEVEL_1_SUMMARY_REPORT.md
│   ├── level_2/
│   │   ├── LEVEL_2_OPTIMIZATION_RESULTS.csv
│   │   ├── LEVEL_2_BEST_PARAMS.json
│   │   ├── LEVEL_2_VS_LEVEL_1_COMPARISON.md
│   │   └── LEVEL_2_SUMMARY_REPORT.md
│   ├── level_3/
│   │   ├── LEVEL_3_OPTIMIZATION_RESULTS.csv
│   │   ├── LEVEL_3_BEST_PARAMS.json
│   │   ├── LEVEL_3_REGIME_ANALYSIS.md
│   │   └── LEVEL_3_SUMMARY_REPORT.md
│   └── level_4/
│       ├── LEVEL_4_OPTIMIZATION_RESULTS.csv
│       ├── LEVEL_4_BEST_PARAMS.json
│       ├── LEVEL_4_ROBUSTNESS_TESTS.md
│       └── LEVEL_4_SUMMARY_REPORT.md
│
└── OPTIMIZATION_PIPELINE_FINAL_REPORT.md
```

---

## Next Steps

1. ✅ **Phase 1 Complete**: Historical data acquisition (in progress, ~2 hours remaining)
2. ⏳ **Phase 2 Current**: Curriculum design document (THIS DOCUMENT)
3. 🔜 **Phase 3**: Implement Level 1 optimization pipeline
4. 🔜 **Phase 4**: Execute Levels 1-4 sequentially
5. 🔜 **Phase 5**: Compile final recommendations

---

**Document Status:** ✅ COMPLETE  
**Ready for Implementation:** YES  
**Next Action:** Begin Level 1 optimization once data acquisition completes
