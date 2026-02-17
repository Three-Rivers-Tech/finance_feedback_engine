# Optimization Pipeline Execution Plan - Option B (Thorough)

**Date:** 2026-02-14 14:20 EST  
**Decision:** Christian approved Option B (thorough approach)  
**Timeline:** 18-24 hours  
**Completion target:** 2026-02-15 14:20 - 20:20 EST (Sunday afternoon/evening)

---

## Execution Path: Option B (Thorough)

**Philosophy:** Do it right the first time. No shortcuts, full historical data, production-ready results.

---

## Phase 1: Historical Data Acquisition (3-4 hours)

**Objective:** Fetch 2020-2023 historical OHLCV data for all trading pairs

**Trading pairs:**
1. **BTC/USD** (crypto)
   - 2020-2021: Bull market (run from $10k to $69k)
   - 2022: Bear market (crash to $16k)
   - 2023: Recovery/consolidation
   - Timeframes: M5, M15, H1

2. **ETH/USD** (crypto)
   - 2020-2021: Bull market (run from $400 to $4,800)
   - 2022: Bear market (crash to $880)
   - 2023: Recovery/consolidation
   - Timeframes: M5, M15, H1

3. **EUR/USD** (forex)
   - 2020-2023: Full cycle with clear trends
   - Timeframes: M5, M15, H1

4. **GBP/USD** (forex)
   - 2020-2023: Full cycle with clear trends
   - Timeframes: M5, M15, H1

**Data source:** Alpha Vantage API
**Rate limit:** 5 requests/minute (respect carefully)
**Storage:** `data/historical/` directory
**Format:** OHLCV CSV files with timestamps

**Validation checklist:**
- [ ] No missing candles (gaps in time series)
- [ ] Valid OHLCV values (no NaN, no negatives)
- [ ] Proper timezone (UTC)
- [ ] File sizes reasonable (~500MB-2GB total)

**Expected duration:** 3-4 hours (includes API delays)

---

## Phase 2: Curriculum Learning Design (1 hour)

**Objective:** Define exact datasets, parameters, and success criteria for each level

**Deliverable:** `CURRICULUM_LEARNING_DESIGN.md`

**Contents:**
1. **Level 1 specification:**
   - Dataset: BTC 2020-2021 (bull only), EUR/USD Q1 2024
   - Parameters: SL range, TP range, position size range
   - Success: 50%+ win rate, positive returns
   - Exit criteria: Advance/repeat/skip rules

2. **Level 2 specification:**
   - Dataset: BTC 2022 (bear only), EUR/USD 2023 decline
   - Parameters: Same ranges as Level 1
   - Success: 50%+ win rate, positive returns
   - Compare: SHORT params vs LONG params (are they different?)

3. **Level 3 specification:**
   - Dataset: Full 2020-2023 cycle (both bull and bear)
   - Parameters: Possibly expanded ranges
   - Success: 52%+ win rate, profitable both directions

4. **Level 4 specification:**
   - Dataset: All data including choppy/sideways periods
   - Parameters: Final production ranges
   - Success: 53%+ win rate, 1.2+ Sharpe ratio

5. **Level 5 specification:**
   - Live market paper trading plan
   - Success: First profitable month (March 26, 2026)

**Expected duration:** 1 hour

---

## Phase 3: Level 1 Optimization (LONG-only on Bull Markets)

**Dataset:**
- BTC/USD 2020-01-01 to 2021-12-31 (bull run)
- EUR/USD 2024-01-01 to 2024-03-31 (recovery)

**Optuna configuration:**
- Trials: 100
- Parallel jobs: 4
- Timeout: 4 hours
- Objective: Maximize Sharpe ratio
- Constraints: Win rate >= 50%, max drawdown <= 15%

**Parameters to optimize:**
- `stop_loss_pct`: 0.5% to 5.0%
- `take_profit_pct`: 0.5% to 10.0%
- `position_size_pct`: 1.0% to 3.0%

**Metrics to track:**
- Win rate (% profitable trades)
- Profit factor (gross profit / gross loss)
- Sharpe ratio (risk-adjusted returns)
- Maximum drawdown (peak-to-trough)
- Average trade duration
- Total return (%)

**Deliverables:**
- `LEVEL_1_OPTIMIZATION_RESULTS.csv` (all 100 trials)
- `LEVEL_1_PARAMETER_IMPORTANCE.png` (heatmap)
- `LEVEL_1_CONVERGENCE.png` (trial progression)
- `LEVEL_1_PERFORMANCE_SUMMARY.md`

**Expected duration:** 3-4 hours

---

## Phase 4: Level 2 Optimization (SHORT-only on Bear Markets)

**Dataset:**
- BTC/USD 2022-01-01 to 2022-12-31 (bear crash)
- EUR/USD 2023-01-01 to 2023-06-30 (decline period)

**Optuna configuration:** Same as Level 1

**Parameters to optimize:** Same ranges as Level 1

**Additional analysis:**
- Compare SHORT optimal params vs LONG optimal params
- Test hypothesis: Are SHORT parameters different from LONG?
- Identify any asymmetry in risk management

**Deliverables:**
- `LEVEL_2_OPTIMIZATION_RESULTS.csv`
- `LEVEL_2_PARAMETER_IMPORTANCE.png`
- `LEVEL_2_CONVERGENCE.png`
- `LEVEL_2_PERFORMANCE_SUMMARY.md`
- `LEVEL_2_LONG_VS_SHORT_COMPARISON.md`

**Expected duration:** 3-4 hours

---

## Phase 5: Level 3 Optimization (Mixed LONG/SHORT)

**Dataset:**
- BTC/USD 2020-01-01 to 2023-12-31 (full cycle)
- EUR/USD 2020-01-01 to 2023-12-31 (full cycle)
- GBP/USD 2020-01-01 to 2023-12-31 (full cycle)

**Optuna configuration:**
- Trials: 150 (more complex search space)
- Parallel jobs: 4
- Timeout: 6 hours
- Objective: Maximize Sharpe ratio
- Constraints: Win rate >= 52%, max drawdown <= 12%

**Parameters to optimize:**
- Same as Levels 1-2
- Possibly add: `regime_detection_threshold` (when to flip LONG/SHORT)

**Additional analysis:**
- Regime detection: How well does it identify bull vs bear?
- Transition performance: How profitable are trend reversals?
- Portfolio metrics: Mixed LONG/SHORT vs LONG-only vs SHORT-only

**Deliverables:**
- `LEVEL_3_OPTIMIZATION_RESULTS.csv`
- `LEVEL_3_PARAMETER_IMPORTANCE.png`
- `LEVEL_3_CONVERGENCE.png`
- `LEVEL_3_PERFORMANCE_SUMMARY.md`
- `LEVEL_3_REGIME_ANALYSIS.md`

**Expected duration:** 4-6 hours

---

## Phase 6: Level 4 Optimization (All Market Regimes)

**Dataset:**
- All pairs, all timeframes, all data (2020-2023)
- Include choppy/sideways periods deliberately

**Optuna configuration:**
- Trials: 200 (comprehensive final optimization)
- Parallel jobs: 4
- Timeout: 8 hours
- Objective: Maximize Sharpe ratio with stability
- Constraints: Win rate >= 53%, max drawdown <= 10%, consistency score

**Parameters to optimize:**
- Final production parameter ranges
- Add robustness constraints

**Additional analysis:**
- Stress testing: How does it handle 2020 COVID crash? 2022 bear? 2023 chop?
- Consistency: Low variance across market regimes
- Production readiness: Confidence score for deployment

**Deliverables:**
- `LEVEL_4_OPTIMIZATION_RESULTS.csv`
- `LEVEL_4_PARAMETER_IMPORTANCE.png`
- `LEVEL_4_CONVERGENCE.png`
- `LEVEL_4_PERFORMANCE_SUMMARY.md`
- `LEVEL_4_STRESS_TEST_RESULTS.md`

**Expected duration:** 4-6 hours

---

## Phase 7: Analysis & Deployment Recommendations (2-3 hours)

**Objective:** Synthesize all results into production deployment plan

**Deliverable:** `OPTIMIZATION_PIPELINE_FINAL_REPORT.md`

**Contents:**

1. **Executive Summary**
   - Overall findings
   - Recommended parameters per trading pair
   - Confidence scores
   - Risk assessment

2. **Performance Progression**
   - Level 1 → Level 2 → Level 3 → Level 4 metrics
   - Win rate evolution
   - Parameter stability analysis

3. **Comparison Analysis**
   - LONG-only vs SHORT-only vs Mixed performance
   - Bull market vs Bear market vs Mixed regime results
   - Best performing pairs (EUR, GBP, BTC, ETH)

4. **Parameter Recommendations**
   - **EUR/USD:** Optimal SL, TP, position size
   - **GBP/USD:** Optimal SL, TP, position size
   - **BTC/USD:** Optimal SL, TP, position size
   - **ETH/USD:** Optimal SL, TP, position size

5. **Deployment Plan**
   - Phase 3 execution strategy (30 trades by Feb 20, 150 by Feb 27)
   - Risk management rules
   - Monitoring checklist
   - Success criteria for first profitable month (March 26)

6. **Infrastructure Improvements**
   - Issues found during optimization
   - Linear tickets created (under THR-248 epic)
   - Future enhancements

**Expected duration:** 2-3 hours

---

## Timeline Summary

| Phase | Task | Duration | Cumulative |
|-------|------|----------|------------|
| 1 | Historical data fetch | 3-4 hrs | 4 hrs |
| 2 | Curriculum design | 1 hr | 5 hrs |
| 3 | Level 1 (LONG) | 3-4 hrs | 9 hrs |
| 4 | Level 2 (SHORT) | 3-4 hrs | 13 hrs |
| 5 | Level 3 (Mixed) | 4-6 hrs | 19 hrs |
| 6 | Level 4 (All regimes) | 4-6 hrs | 25 hrs |
| 7 | Analysis & recommendations | 2-3 hrs | 28 hrs |

**Total: 20-28 hours**  
**Target: 18-24 hours** (achievable with efficient execution)

**Start time:** 2026-02-14 14:20 EST  
**End time:** 2026-02-15 14:20 - 18:20 EST (Sunday afternoon)

---

## Success Criteria

**Minimum (Must Have):**
- [ ] All 2020-2023 historical data fetched and validated
- [ ] Levels 1-3 optimization complete (LONG, SHORT, Mixed)
- [ ] Win rate >= 50% on Levels 1-2, >= 52% on Level 3
- [ ] Production parameter recommendations generated

**Target (Should Have):**
- [ ] Level 4 optimization complete (all regimes)
- [ ] Win rate >= 53%, Sharpe >= 1.2 on Level 4
- [ ] Parameter stability validated (low variance)
- [ ] Deployment plan with confidence scores

**Stretch (Nice to Have):**
- [ ] Level 5 paper trading setup initiated
- [ ] Infrastructure improvements documented and ticketed
- [ ] Automated re-optimization pipeline designed

---

## Communication Plan

**Progress updates to Christian:**
- Phase completion milestones
- Any blockers or issues
- Final report delivery

**Delivery format:**
- Proactive Telegram updates at key milestones
- Not spammy - major progress only
- Final comprehensive report

---

## Risk Mitigation

**Data fetch failures:**
- Retry logic with exponential backoff
- Alternative data sources if Alpha Vantage fails
- Graceful degradation (fewer timeframes if needed)

**Optimization convergence issues:**
- Monitor trial progression
- Adjust parameter ranges if needed
- Extend trial count if not converging

**Time overruns:**
- Time-box each phase strictly
- Level 4 optional if running late
- Deliver what's complete vs delay everything

---

**Status:** PM agent executing Option B (Thorough). Historical data fetch beginning now. Expected completion: Sunday afternoon/evening.
