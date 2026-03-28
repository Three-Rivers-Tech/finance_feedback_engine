# Optimization Pipeline & Curriculum Learning - Status

**Date:** 2026-02-14 13:50 EST  
**Objective:** Re-optimize FFE parameters with curriculum learning for bidirectional trading  
**Requested by:** Christian

---

## Context

**Problem:** Previous Optuna optimizations only tested LONG positions. Parameters are biased and won't work for SHORT trading.

**Christian's research:** Agents don't do well when they can go LONG and SHORT at once. Need obvious scenarios to build memory, slowly increasing difficulty.

**Solution:** 5-level curriculum learning progression from simple (LONG-only uptrends) to complex (mixed signals, all regimes).

---

## New Agent Role Created

**Infrastructure & Optimization Engineer**
- **Model:** Claude Sonnet 4
- **Specialization:** Optuna, curriculum learning, infrastructure, performance tuning
- **Role spec:** AGENT_ROLE_INFRASTRUCTURE_OPTIMIZATION.md (11,036 bytes)

**Core responsibilities:**
1. Design curriculum learning levels
2. Run Optuna optimizations per level
3. Track performance metrics (win rate, Sharpe, drawdown)
4. Infrastructure setup and monitoring
5. Results analysis and deployment recommendations

---

## Curriculum Learning Design (5 Levels)

### Level 1: LONG-only on Obvious Uptrends
- **Data:** Bull markets (BTC 2020-2021, EUR/USD Q1 2024)
- **Goal:** Learn profitable LONG entry/exit
- **Success:** 50%+ win rate, positive returns
- **Duration:** 3-4 hours

### Level 2: SHORT-only on Obvious Downtrends
- **Data:** Bear markets (BTC 2022 crash, EUR/USD 2023 decline)
- **Goal:** Learn profitable SHORT entry/exit
- **Success:** 50%+ win rate, positive returns
- **Duration:** 3-4 hours

### Level 3: Alternating LONG/SHORT on Clear Trends
- **Data:** 2020-2023 full cycle with trend reversals
- **Goal:** Learn to switch between directions
- **Success:** 52%+ win rate, maintain profitability both ways
- **Duration:** 4-6 hours

### Level 4: Mixed Signals on All Regimes
- **Data:** Full historical + choppy/sideways markets
- **Goal:** Handle all market conditions
- **Success:** 53%+ win rate, 1.2+ Sharpe ratio
- **Duration:** 4-6 hours

### Level 5: Production Deployment
- **Data:** Live markets (paper trading first)
- **Goal:** Real-world validation
- **Success:** First profitable month (March 26, 2026)

---

## PM Agent Spawned

**Session:** `pm-optimization-pipeline` (Opus 4)  
**Status:** Running (just spawned)  
**Timeout:** 8 hours  
**Responsibility:** Orchestrate Infrastructure & Optimization Engineer

**PM's workflow:**
1. Delegate Phase 1: Infrastructure readiness check
2. Delegate Phase 2: Curriculum design (exact datasets, success criteria)
3. Delegate Phases 3-6: Run optimizations per level
4. Delegate Phase 7: Analysis and recommendations
5. Create Linear tickets for infrastructure improvements
6. Integrate into final deployment recommendation

---

## Linear Integration

**EPIC planned:** "Optimization Pipeline & Curriculum Learning for SHORT Trading"
- Team: THR
- Priority: P1
- Scope: All optimization and infrastructure work

**Sub-issues to create (via PM):**
- Infrastructure readiness checks
- Curriculum level implementations
- Performance improvement tasks
- Deployment preparation

---

## Expected Outputs

### Per Level (Levels 1-4):
- Optimization results CSV
- Parameter importance plots
- Convergence charts
- Performance metrics report

### Final Deliverables:
- Curriculum learning design document
- Optimization pipeline final report
- Deployment recommendations with confidence scores
- Linear tickets for infrastructure improvements
- Production-ready parameters for each trading pair

---

## Timeline

**Total estimated:** 24 hours (time-boxed)  
**Started:** 2026-02-14 13:50 EST  
**Target completion:** 2026-02-15 13:50 EST (Sunday afternoon)

**Breakdown:**
- Infrastructure setup: 1-2 hours
- Curriculum design: 1 hour
- Level 1 optimization: 3-4 hours
- Level 2 optimization: 3-4 hours
- Level 3 optimization: 4-6 hours
- Level 4 (optional): 4-6 hours
- Analysis & recommendations: 2-3 hours

---

## Success Metrics

### Optimization Quality:
- [ ] Win rate progression across levels (50% → 50% → 52% → 53%+)
- [ ] Parameter stability (low variance across levels)
- [ ] Performance improvement vs LONG-only baseline

### Infrastructure:
- [ ] Optimizations run without crashes
- [ ] Results cached and reproducible
- [ ] Resource usage within limits

### Deployment Readiness:
- [ ] Clear parameter recommendations
- [ ] Confidence scores per trading pair
- [ ] Risk assessment (max drawdown, volatility)

---

## Integration with Previous Work

**Builds on:**
- ✅ SHORT backtesting implementation (commit 4304b71)
- ✅ SHORT logic fixes (23 tests passing)
- ✅ Previous LONG-only optimizations (baseline for comparison)

**Enables:**
- Phase 3 deployment (30 trades by Feb 20, 150 by Feb 27)
- First profitable month target (March 26, 2026)
- Curriculum learning for other strategies (future)

---

## Agent System Working

**Total agents now:**
1. ✅ Project Manager (Opus 4)
2. ✅ Research Agent (Sonnet 4)
3. ✅ Backend Developer (Sonnet 4)
4. ✅ Frontend Developer (Sonnet 4)
5. ✅ QA Lead (Sonnet 4)
6. ✅ Code Reviewer (Gemini 3 Pro)
7. ✅ DevOps Engineer (Sonnet 4)
8. ✅ Security Reviewer (Sonnet 4)
9. ✅ **Infrastructure & Optimization Engineer** (Sonnet 4) ← NEW

**First successful deployment:**
- SHORT backtesting feature completed autonomously in 22 minutes
- PM coordinated 3 sub-agents (audit, implementation, fixes)
- All deliverables production-ready

**Second deployment (in progress):**
- Optimization pipeline with curriculum learning
- PM coordinating Infrastructure & Optimization Engineer
- Expected 24-hour completion

---

**Status:** PM agent running, will delegate to Infrastructure Engineer shortly. Linear epic creation pending (CLI syntax check needed).
