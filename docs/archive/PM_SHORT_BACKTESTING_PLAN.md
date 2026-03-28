# PROJECT MANAGER: SHORT Position Backtesting Feature
**Date:** 2026-02-14  
**PM:** Subagent pm-short-backtesting  
**Objective:** Implement and validate SHORT position backtesting for Finance Feedback Engine

---

## Executive Summary

### Current State
- ✅ **Research Complete:** SIMILAR_PROJECTS_RESEARCH.md (15.8KB), SHORT_LOGIC_AUDIT.md (20KB)
- ✅ **MockPlatform supports SHORTs:** test_short_backtesting.py has 11 test cases
- ✅ **Backtester has SHORT infra:** Position dataclass, liquidation logic, P&L calculation
- ⚠️ **Critical Gaps Found:** Signal generation ambiguity, no position state awareness, missing validation

### Risk Assessment
- **Phase 3 Target:** 150 trades by Feb 27 (~75 will be SHORTs)
- **Current Validation:** ZERO SHORT trades executed in backtesting or live
- **Critical Path:** 3 issues must be fixed before any SHORT trading

---

## Task Decomposition

### Phase 1: Backend Implementation ✅ READY TO START
**Owner:** backend-dev agent  
**Duration:** 1-2 days (16-24 hours)  
**Priority:** CRITICAL

**Tasks:**
1. **Fix Signal Ambiguity (Issue #1 from audit)**
   - Implement 4-signal system or auto-conversion logic
   - Modify decision_engine/engine.py to check current position before generating signal
   - Update oanda_platform.py execution layer to handle CLOSE_LONG/CLOSE_SHORT actions
   - Update prompts to clarify SELL signal meaning

2. **Add Position State Awareness (Issue #2 from audit)**
   - Pass current position state to AI prompt in decision_engine/engine.py
   - Update prompt template to include position context
   - Implement signal constraints: "If LONG, only HOLD or SELL allowed"

3. **Harden Stop-Loss Validation (Issue #3 from audit)**
   - Add edge case validation in position_sizing.py
   - Ensure stop-loss never at entry price (minimum distance check)
   - Add SHORT-specific validation: `assert stop_loss_price > entry_price for SHORTs`

**Inputs:**
- SHORT_LOGIC_AUDIT.md (issue specifications)
- SIMILAR_PROJECTS_RESEARCH.md (Backtesting.py pattern)
- finance_feedback_engine/decision_engine/engine.py
- finance_feedback_engine/decision_engine/position_sizing.py
- finance_feedback_engine/trading_platforms/oanda_platform.py

**Outputs:**
- Modified backtester.py (if needed)
- Modified decision_engine/engine.py
- Modified position_sizing.py
- Modified oanda_platform.py
- BACKEND_IMPLEMENTATION_NOTES.md (changelog + migration guide)

**Success Criteria:**
- [ ] SELL signal with LONG position closes LONG (not opens SHORT)
- [ ] SELL signal when FLAT opens SHORT
- [ ] BUY signal with SHORT position closes SHORT (not opens LONG)
- [ ] BUY signal when FLAT opens LONG
- [ ] Stop-loss for SHORT positions is above entry price
- [ ] Position state visible in AI prompt context

---

### Phase 2: QA & Testing 🔄 DEPENDS ON PHASE 1
**Owner:** qa-lead agent  
**Duration:** 1-2 days (12-16 hours)  
**Priority:** HIGH

**Tasks:**
1. **Expand Unit Test Coverage**
   - Add missing tests identified in SHORT_LOGIC_AUDIT.md
   - Test SHORT entry on SELL signal
   - Test SHORT close on BUY signal
   - Test inverted SL/TP triggers
   - Test signal ambiguity fixes (SELL when LONG vs SELL when FLAT)
   - Target: 70%+ coverage for new SHORT code

2. **Integration Testing**
   - Run backtest on falling market data (EUR/USD downtrend or BTC/USD 2022 crash)
   - Verify at least 10 SHORT trades executed
   - Measure win rate, profit factor for SHORT-only strategy
   - Compare SHORT vs LONG performance metrics

3. **Stress Testing**
   - Test rapid position reversals (LONG → SHORT → LONG)
   - Test margin liquidation scenarios for SHORTs
   - Test SHORT positions across weekend gaps (forex)
   - Test SHORT positions with high leverage (5x-30x)

**Inputs:**
- Backend implementation from Phase 1
- tests/test_short_backtesting.py (existing tests)
- Historical market data (EUR/USD, BTC/USD downtrends)

**Outputs:**
- tests/test_short_signal_generation.py (NEW)
- tests/test_short_position_state.py (NEW)
- tests/test_short_stop_loss.py (NEW)
- Enhanced tests/test_short_backtesting.py
- QA_TEST_RESULTS.md (coverage report, backtest results, win rate)

**Success Criteria:**
- [ ] Test coverage 70%+ for SHORT code paths
- [ ] At least 10 SHORT trades in backtest
- [ ] Win rate >45% for SHORT-only strategy
- [ ] No regressions in LONG position backtesting
- [ ] All stress tests pass without crashes

---

### Phase 3: Code Review (Gemini) 🔄 DEPENDS ON PHASE 1+2
**Owner:** code-reviewer agent (Gemini 2.0 Flash Exp)  
**Duration:** 4-6 hours  
**Priority:** MEDIUM

**Tasks:**
1. **Review SHORT Implementation**
   - Check correctness of inverted logic (SL above entry for SHORTs)
   - Validate signal generation fixes
   - Check edge cases and error handling
   - Verify no breaking changes to LONG logic

2. **Cross-Model Validation**
   - Use Gemini (different model than Claude) to catch blind spots
   - Review test coverage and quality
   - Identify any remaining risks

**Inputs:**
- All modified files from Phase 1
- Test suite from Phase 2
- SHORT_LOGIC_AUDIT.md (known issues)

**Outputs:**
- GEMINI_CODE_REVIEW_SHORT_BACKTESTING.md (rating, issues found, recommendations)

**Success Criteria:**
- [ ] Gemini rating 8/10 or higher
- [ ] Zero critical issues found
- [ ] No more than 3 medium-severity issues
- [ ] All issues documented with fix recommendations

---

### Phase 4: Integration & Validation 🔄 DEPENDS ON ALL ABOVE
**Owner:** PM (this agent)  
**Duration:** 4-6 hours  
**Priority:** CRITICAL

**Tasks:**
1. **Compile Deliverables**
   - Gather all implementation notes, test results, review reports
   - Create unified changelog
   - Document migration steps (if any)

2. **Run Regression Tests**
   - Ensure LONG position backtesting still works
   - Run full test suite (pytest)
   - Verify no breaking changes to existing functionality

3. **Create Completion Report**
   - Document what was implemented
   - List any remaining work (deferred medium/low priority items)
   - Provide deployment recommendations

**Inputs:**
- All outputs from Phases 1-3

**Outputs:**
- SHORT_BACKTESTING_COMPLETE_PM_REPORT.md (final deliverable)
- REGRESSION_TEST_RESULTS.md
- DEPLOYMENT_CHECKLIST.md

**Success Criteria:**
- [ ] All Phase 1-3 deliverables complete
- [ ] Zero regressions in LONG backtesting
- [ ] Full test suite passes
- [ ] Deployment checklist ready
- [ ] Remaining work documented

---

## Agent Pool & Budget

### Agents Available
1. **backend-dev** (claude-sonnet-4)
   - Budget: 50K tokens
   - Role: Implementation (Phase 1)

2. **qa-lead** (claude-sonnet-4)
   - Budget: 50K tokens
   - Role: Testing (Phase 2)

3. **code-reviewer** (gemini-2.0-flash-exp)
   - Budget: 50K tokens
   - Role: Cross-model review (Phase 3)

4. **PM** (claude-opus-4, this agent)
   - Budget: 100K tokens
   - Role: Orchestration, integration, final report

**Total Team Budget:** ~250K tokens

---

## Success Criteria (Overall)

### Functional Requirements
- [x] SHORT entry works (SELL signal without position) - MockPlatform supports
- [ ] SHORT entry properly distinguishes from LONG close - **CRITICAL FIX NEEDED**
- [ ] SHORT stop-loss triggers on upward price movement
- [ ] SHORT take-profit triggers on downward price movement
- [ ] P&L calculated correctly: (entry - exit) × units
- [ ] At least 10 SHORT trades in backtest
- [ ] Position tracking works for shorts (CLI display)

### Quality Requirements
- [ ] Test coverage 70%+ for new code
- [ ] Gemini code review rating 8/10+
- [ ] Zero regressions in LONG position backtesting
- [ ] All critical issues from audit fixed

### Deployment Requirements
- [ ] Documentation complete (implementation notes, migration guide)
- [ ] Regression tests pass
- [ ] Deployment checklist ready

---

## Timeline

**Total Duration:** 3-4 days (assuming serial execution, single agent at a time)

- **Day 1:** Backend implementation (Phase 1)
- **Day 2:** QA & Testing (Phase 2)
- **Day 3:** Code review + Integration (Phases 3+4)
- **Day 4:** Buffer for issues / final validation

**Parallel Execution Possible:**
- Phase 2 testing can START as Phase 1 completes features incrementally
- Phase 3 review can START as Phase 2 writes tests

---

## Communication Protocol

### Status Updates
- Each agent reports completion to PM
- PM tracks progress in this file (update status emojis)
- PM escalates blockers to main agent if needed

### Deliverable Format
- All agents output markdown files to ~/finance_feedback_engine/
- Naming convention: `{PHASE}_{AGENT}_{TOPIC}.md`
- Example: `PHASE1_BACKEND_IMPLEMENTATION_NOTES.md`

### Issue Escalation
- Critical blockers: Escalate to PM immediately
- Medium issues: Document in deliverable, PM decides priority
- Low issues: Document for future work

---

## Next Steps (Immediate)

1. ✅ Read current backtester.py structure - DONE
2. ✅ Review existing SHORT tests - DONE
3. ✅ Create this project plan - DONE
4. 🔄 Spawn backend-dev agent for Phase 1 - **IN PROGRESS**
5. ⏳ Monitor backend-dev progress
6. ⏳ Spawn qa-lead agent when Phase 1 completes
7. ⏳ Spawn code-reviewer when Phase 2 completes
8. ⏳ Execute Phase 4 integration & create final report

---

**Status:** Phase 1 starting now...  
**Next Action:** Spawn backend-dev agent with detailed task spec
