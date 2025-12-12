# [MEDIUM] docs/QA_ANALYSIS_REPORT.md:502

**Location:** `docs/QA_ANALYSIS_REPORT.md` line 502

**Match:** 1. **Debug walk-forward command**

**Command syntax:** `python main.py walk-forward <ASSET_PAIR> --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> [--train-ratio <0-1>] [--provider <provider>]

Usage example:** `python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-01-31 --train-ratio 0.7`

**Resolution:** Deferred — the walk-forward CLI is currently failing in QA (see `docs/QA_ISSUES.md` and `qa_results_full.json`) due to implementation errors (import/argument mismatches). Created follow-up ticket `TICKET-WF-001` to track debugging and fix. Rationale: several QA runs show exceptions (import errors and unexpected keyword arguments), so applying a fix requires code changes and tests.

**Context before:**
```

### Phase 2: Feature Completion (HIGH)
```
**Context after:**
```
   - Identify error root cause
```

**Suggested action:** Review and schedule as appropriate (bug, docs, or improvement).
