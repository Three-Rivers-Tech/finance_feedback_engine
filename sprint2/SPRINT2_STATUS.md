# Sprint 2 Status — Finance Feedback Engine

**Sprint:** Feb 17 – Mar 2, 2026  
**Goal:** Deploy production-ready trading parameters with validated optimization infrastructure  
**Board:** https://github.com/Three-Rivers-Tech/finance_feedback_engine/issues  
**Last Updated:** 2026-02-17 (Sprint Kickoff Night)

---

## 🎯 Sprint 2 Goal

> Deploy production-ready trading parameters with validated optimization infrastructure

The optimization pipeline (THR-248) is the centerpiece: build curriculum learning from simple momentum
(Phase 1) through bidirectional trading (Phase 2) to mixed-market strategies (Phase 3).

---

## 📋 Sprint 2 Ticket Status

| # | GitHub Issue | Title | Status | Notes |
|---|---|---|---|---|
| 1 | #69 | [THR-264] Simple Momentum Strategy (BUY-only) | ✅ **In Progress** | Implemented tonight — commit `e50179b` |
| 2 | #70 | [THR-265] Bidirectional Trading Optimization (BUY + SHORT) | 🔒 Blocked | Blocked by THR-264 |
| 3 | #71 | [THR-266] Mixed Market Curriculum (Choppy/Sideways) | 🔒 Blocked | Blocked by THR-265 |
| 4 | #68 | [THR-260] Build OptunaOptimizer Infrastructure | ✅ **DONE** | Already complete (pre-sprint) |
| 5 | #66 | [THR-248] EPIC: Optimization Pipeline & Curriculum Learning | 🔄 In Progress | Phase 1 started tonight |

---

## 🌙 Tonight's Completions (Feb 16–17, 2026)

### THR-264 — Simple Momentum Signal ✅

**Commit:** `e50179b feat: simple momentum signal for BTC-USD (THR-264)`  
**Files Added:**
- `finance_feedback_engine/optimization/momentum_signal.py` — 250 lines
- `tests/optimization/test_momentum_signal.py` — 380 lines, 38 tests

**What was built:**

#### `MomentumSignal` class
- 20-period vs 50-period EMA crossover signal
- `compute(prices)` → `"BUY"` on golden cross, `"HOLD"` otherwise
- `compute_series(prices)` → vectorized signal over full price series (for offline backtesting)
- `get_indicators(prices)` → diagnostic dict with EMA values and crossover status
- Configurable `fast_period` / `slow_period` → ready for Optuna search space

#### `MomentumDecisionEngine` class
- Async `generate_decision()` matching `DecisionEngine` interface
- Drop-in replacement for `Backtester.run_backtest()` — no AI API calls needed
- Stateful rolling price history (500-bar cap)
- `reset_price_history()` for clean trial isolation in Optuna runs
- Pre-load support via `price_history=` kwarg (warm-start from historical data)

#### Test Results
```
38 passed, 0 warnings in 2.72s
100% coverage on momentum_signal.py
```

**Test categories:**
- `TestMomentumSignalInit` — 7 tests (validation, defaults, custom periods)
- `TestMomentumSignalEMAComputation` — 4 tests (EMA math, uptrend/downtrend behavior)
- `TestMomentumSignalCompute` — 5 tests (BUY/HOLD logic, insufficient data, flat prices)
- `TestMomentumSignalComputeSeries` — 4 tests (vectorized output, BUY sparsity)
- `TestMomentumSignalGetIndicators` — 3 tests (diagnostic dict, data_sufficient flag)
- `TestMomentumDecisionEngine` — 12 tests (async interface, BUY-only enforcement, edge cases)
- `TestMomentumOptunaCompatibility` — 3 tests (import chain, Optuna readiness)

---

## 🧪 Regression Test Results (Sprint Kickoff)

**Suite:** `tests/` (excluding integration/ and e2e/)  
**Pre-existing failure (unrelated to sprint work):**
- `tests/config/test_schema_validation.py::TestPlatformCredentials::test_reject_placeholder_api_key`  
  — Pydantic validation bug, existed before Sprint 2. Not a regression.

**No new failures introduced.**

---

## 🗓️ Sprint 2 Work Plan (Remaining)

### Week 1 (Feb 17–21)
| Day | Task | Owner |
|---|---|---|
| Mon | Set up BTC-USD historical data pipeline for 2023-2024 bull market | Codex agent |
| Mon | Run THR-264 Optuna optimization (50 trials, EMA period search) | Codex agent |
| Tue | Analyze Phase 1 results, select best EMA parameters | Data agent |
| Tue | Start THR-265: extend to bidirectional (BUY + SHORT) | Codex agent |
| Wed-Thu | THR-265 Optuna run + analysis | Codex + Data agents |
| Fri | Deploy Phase 1/2 best parameters to config | DevOps agent |

### Week 2 (Feb 24 – Mar 2)
| Day | Task | Owner |
|---|---|---|
| Mon | THR-266: Mixed market curriculum (choppy/sideways) | Codex agent |
| Tue-Wed | Full optimization run across all curriculum levels | Codex + Data agents |
| Thu | Integration testing: new parameters in backtest vs. live | QA agent |
| Fri | Deploy production parameters, sprint review | PM agent |

---

## 🏗️ Architecture

```
THR-248 Curriculum Learning Pipeline
├── Level 1 (THR-264) ✅ — BUY-only momentum on bull market
│   └── MomentumSignal(fast=20, slow=50)
│   └── MomentumDecisionEngine → Backtester → Optuna
├── Level 2 (THR-265) 🔒 — BUY + SHORT bidirectional
├── Level 3 (THR-266) 🔒 — Mixed/choppy market
├── Level 4 (THR-267) 📋 — Full market cycle
└── Level 5 (THR-268) 📋 — Production deployment
```

---

## 📦 Key Files

| File | Description |
|---|---|
| `finance_feedback_engine/optimization/momentum_signal.py` | EMA crossover signal + DecisionEngine wrapper |
| `finance_feedback_engine/optimization/optuna_optimizer.py` | Optuna integration (THR-260, complete) |
| `finance_feedback_engine/optimization/__init__.py` | Module exports |
| `tests/optimization/test_momentum_signal.py` | 38 tests for momentum signal |
| `tests/optimization/test_optuna_optimizer.py` | Tests for Optuna optimizer |

---

## 📊 Metrics Targets (Sprint End)

| Metric | Target | Current |
|---|---|---|
| Phase 1 win rate (BTC bull 2023-24) | ≥50% | TBD (optimization not run yet) |
| Phase 1 Sharpe ratio | ≥0.8 | TBD |
| Phase 2 win rate (bidirectional) | ≥52% | TBD |
| Momentum signal test coverage | 100% | ✅ 100% |
| Regression failures introduced | 0 | ✅ 0 |

---

*Last updated: Sprint 2 Kickoff Night by pm-sprint2-kickoff agent*
