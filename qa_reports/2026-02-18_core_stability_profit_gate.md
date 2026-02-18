# FFE QA Hard Gate — Core Stability + Profit-Readiness

**Date:** 2026-02-18  
**Branch/Target:** `main` (current working tree)  
**Gate Owner:** QA Lead

---

## 1) Hard-Gate Checklist (Release Blocking)

A candidate is **PASS** only if **all** items below pass.

### A. State Transitions (Core OODA Path)
- [ ] Legal transitions enforced (no illegal state jumps).
- [ ] Startup path reaches `RECOVERING -> PERCEPTION`.
- [ ] Decision path reaches `PERCEPTION -> REASONING -> RISK_CHECK -> EXECUTION -> LEARNING` when preconditions pass.
- [ ] Empty/no-action path returns to `IDLE` without side effects.

### B. Risk Checks (Profit Protection)
- [ ] Stale data blocks trading progression before risk/execution.
- [ ] Risk gate rejects non-compliant decisions and emits rejection telemetry.
- [ ] Only approved decisions proceed to execution queue.
- [ ] Rejected decisions are added to rejection cooldown cache.

### C. Execution Path (Capital Safety)
- [ ] Successful execution associates decision to trade monitor and counts daily trade only when valid.
- [ ] Failed execution triggers exposure rollback.
- [ ] Batch cleanup clears stale exposure reservations.
- [ ] Execution handler always exits to `LEARNING` (or `IDLE` for empty queue) deterministically.

### D. Recovery (Startup Integrity)
- [ ] Recovery handles empty portfolio safely.
- [ ] Recovery retries transient platform failure once and proceeds deterministically.
- [ ] Recovery keeps max allowed positions and closes excess safely.
- [ ] Recovery emits `recovery_complete`/`recovery_failed` events with metadata.

### E. Data Freshness (Decision Input Integrity)
- [ ] Freshness validation runs in PERCEPTION every cycle.
- [ ] Missing timestamp is handled defensively (no crash).
- [ ] Stale market data emits `data_freshness_failed` event and halts transition.

---

## 2) Automated Regression Tests Added/Adjusted

### Added (new deterministic gate tests)
- `tests/agent/test_profit_readiness_gate.py`
  - `test_perception_halts_on_stale_data`
  - `test_risk_check_only_advances_approved_decisions`
  - `test_execution_failure_rolls_back_exposure`

**Why these are profitability-critical:**
- Prevent execution on stale signals.
- Ensure risk filter is actually enforced before execution.
- Ensure capital reservation is rolled back on failed orders.

---

## 3) Release Candidate PASS/FAIL Template (Use for every RC)

Copy this section for each candidate:

```md
## RC: <tag/sha>
Date: <YYYY-MM-DD HH:MM TZ>
Environment: <local/ci>

### Commands
1) ./.venv/bin/pytest -q -o addopts='' tests/agent/test_profit_readiness_gate.py
2) ./.venv/bin/pytest -q -o addopts='' tests/agent/test_agent_recovery.py
3) ./.venv/bin/pytest -q -o addopts='' tests/test_thr103_race_condition.py
4) ./.venv/bin/pytest -q -o addopts='' tests/risk/test_gatekeeper_data_freshness.py

### Expected outputs
- All tests `passed`
- No flaky/network-dependent assertions triggered
- No unexpected state transition exceptions
- No risk-gate bypass behavior

### Actual outputs
- <paste concise summaries>

### Gate verdict
- [ ] PASS
- [ ] FAIL

### Blockers (if FAIL)
- <blocking test name + failure reason>

### Notes
- <warnings, deprecations, non-blocking observations>
```

---

## 4) Current Main — Gate Execution Results

### Commands run
```bash
./.venv/bin/pytest -q -o addopts='' \
  tests/agent/test_profit_readiness_gate.py \
  tests/agent/test_agent_recovery.py \
  tests/test_thr103_race_condition.py \
  tests/risk/test_gatekeeper_data_freshness.py
```

### Actual result
- **31 passed** in 7.80s
- No test failures
- Warnings observed (non-blocking): async mock await warnings in legacy tests + datetime deprecation warnings

### Final Gate Verdict (current main)
# ✅ PASS

The hard gate for core stability + profit-readiness is currently passing for the scoped deterministic suite.
