# Finance Feedback Engine - CLI Issues & Bug Tracking

**Report Date:** December 5, 2025  
**Status:** QA Analysis Complete  
**Last Updated:** December 5, 2025

---

## Issue Tracking Summary

| ID | Severity | Category | Status | Title | Priority |
|----|----------|----------|--------|-------|----------|
| C1 | CRITICAL | Bug | OPEN | Backtest AttributeError with active_positions | P0 |
| C2 | CRITICAL | Bug | OPEN | Backtest accepts invalid date ranges | P0 |
| M1 | MAJOR | Bug | OPEN | History command inconsistent error handling | P1 |
| M2 | MAJOR | Feature | OPEN | Walk-forward command not working | P1 |
| M3 | MAJOR | Feature | OPEN | Monte-carlo command not working | P1 |
| m1 | MINOR | UX | OPEN | Signal-only mode message misleading | P2 |
| m2 | MINOR | UX | OPEN | Invalid date ranges return silent $0 results | P2 |
| D1 | DOC GAP | Testing | OPEN | Missing interactive command tests | P2 |
| D2 | DOC GAP | Documentation | OPEN | Incomplete feature documentation | P2 |

---

## Issue Details

### CRITICAL ISSUES

#### C1: Backtest AttributeError with active_positions

**ID:** C1  
**Severity:** CRITICAL  
**Category:** Bug - Type Error  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P0 (URGENT)

**Title:** 
Backtest command crashes: `AttributeError: 'list' object has no attribute 'get'`

**Description:**
When running backtest command, the decision engine crashes when trying to access active_positions dictionary. The monitoring context provider returns a list, but the engine code expects a dict.

**Steps to Reproduce:**
```bash
python main.py backtest BTCUSD --start 2024-01-01 --end 2024-01-31
```

**Expected Behavior:**
Backtest completes and shows metrics table with trades executed.

**Actual Behavior:**
Command exits with error:
```
Error: 'list' object has no attribute 'get'
Traceback:
  File "finance_feedback_engine/decision_engine/engine.py", line 1898, in _create_decision
    futures_positions = active_positions.get('futures', [])
                        ^^^^^^^^^^^^^^^^^^^^
AttributeError: 'list' object has no attribute 'get'
```

**Affected Versions:**
- Current main branch

**Root Cause:**
In `engine.py:_create_decision()` (line 1898), the code assumes `active_positions` is always a dict:
```python
futures_positions = active_positions.get('futures', [])
spot_positions = active_positions.get('spot', [])
```

However, when the monitoring context provider returns position data in backtesting context, it may return a list instead of a dict, causing the `.get()` method to fail.

**Impact:**
- Backtest command completely non-functional
- Cannot analyze strategy performance
- Blocks all backtesting use cases

**Suggested Fix:**
```python
# In engine.py, _create_decision method
# Add type checking before accessing dict methods
if isinstance(active_positions, dict):
    futures_positions = active_positions.get('futures', [])
    spot_positions = active_positions.get('spot', [])
elif isinstance(active_positions, list):
    # If it's already a list, assume it's futures positions
    futures_positions = active_positions
    spot_positions = []
else:
    futures_positions = []
    spot_positions = []
```

**Testing Plan:**
1. Add unit test for both dict and list types
2. Run backtest with mock platform
3. Verify output matches expected metrics format

**Effort Estimate:** 30 minutes  
**Owner:** [Assign to developer]

---

#### C2: Backtest accepts invalid date ranges

**ID:** C2  
**Severity:** CRITICAL  
**Category:** Bug - Input Validation  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P0 (URGENT)

**Title:**
Backtest command doesn't validate date ranges; accepts start_date > end_date

**Description:**
When running backtest with start_date after end_date, the command silently succeeds and returns all $0 metrics, which is misleading.

**Steps to Reproduce:**
```bash
python main.py backtest BTCUSD --start 2024-01-31 --end 2024-01-01
```

**Expected Behavior:**
Command should reject the invalid range and display error message:
```
Error: start_date must be before end_date
```

**Actual Behavior:**
Command exits successfully (exit code 0) with metrics table showing all zeros:
```
Initial Balance:        $0.00
Final Balance:          $0.00
Total Return %:         0.00%
Max Drawdown %:         0.00%
Total Trades:           0
```

**Impact:**
- Users can run invalid backtests without knowing
- Zero results are misleading (looks like successful backtest with no trades)
- Poor user experience and potential for analysis errors

**Suggested Fix:**
```python
# In cli/main.py, backtest command
from datetime import datetime

# After parsing arguments, add validation:
start_dt = datetime.strptime(start, '%Y-%m-%d')
end_dt = datetime.strptime(end, '%Y-%m-%d')

if start_dt >= end_dt:
    raise click.BadParameter(
        f"start_date ({start}) must be before end_date ({end})"
    )
```

**Testing Plan:**
1. Add unit test for invalid date ranges
2. Verify error message is displayed
3. Verify exit code is non-zero
4. Test with valid ranges still works

**Effort Estimate:** 15 minutes  
**Owner:** [Assign to developer]

---

### MAJOR ISSUES

#### M1: History command inconsistent error handling

**ID:** M1  
**Severity:** MAJOR  
**Category:** Bug - Error Handling  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P1 (HIGH)

**Title:**
History command returns different exit codes depending on filter results

**Description:**
When filtering history with `--asset NONEXISTENT`, the command returns exit code 1 (error), but when no filter produces no results, it returns exit code 0 (success). This is inconsistent and breaks automation.

**Steps to Reproduce:**
```bash
# Case 1: No filter, returns exit code 0
python main.py history --limit 10
# Output: "No decisions found" + exit code 0

# Case 2: Invalid asset filter, returns exit code 1
python main.py history --asset NONEXISTENT --limit 10
# Output: "No decisions found" + exit code 1
```

**Expected Behavior:**
Both cases should return exit code 0 with "No decisions found" message. Empty result set is a valid result, not an error.

**Actual Behavior:**
Case 1 returns 0, Case 2 returns 1. Inconsistent.

**Impact:**
- Automation scripts may fail unexpectedly
- Difficult to distinguish between errors and empty results
- Violates Unix convention (0 = success, non-zero = error)

**Suggested Fix:**
```python
# In cli/main.py, history command
def history(asset, limit):
    decisions = get_decisions(asset_filter=asset, limit=limit)
    
    if not decisions:
        console.print("No decisions found")
        return  # Exit code 0 by default
    
    display_history_table(decisions)
    # No exception raised - always return exit code 0
```

**Testing Plan:**
1. Add test for history with no filters → should return 0
2. Add test for history with asset filter → should return 0
3. Add test for history with empty result → should return 0
4. Verify only actual errors (like IO failure) return non-zero

**Effort Estimate:** 20 minutes  
**Owner:** [Assign to developer]

---

#### M2: Walk-forward command not working

**ID:** M2  
**Severity:** MAJOR  
**Category:** Feature - Implementation  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P1 (HIGH)

**Title:**
Walk-forward analysis command exits with error code 1

**Description:**
The walk-forward command, which should run rolling window analysis to detect overfitting, returns exit code 1 with unspecified error.

**Steps to Reproduce:**
```bash
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-01-31 --train-ratio 0.7
```

**Expected Behavior:**
Display results table with train/test metrics and overfitting assessment.

**Actual Behavior:**
Exit code 1, error message TBD (needs investigation)

**Impact:**
- Walk-forward analysis feature completely unavailable
- Cannot validate strategy robustness against overfitting
- Users cannot use important backtesting feature

**Investigation Required:**
1. Check if command is fully implemented
2. Check for missing dependencies
3. Check for file path issues
4. Get actual error message

**Suggested Fix:**
TBD after investigation

**Testing Plan:**
1. Run command with verbose flag to get full error
2. Debug root cause
3. Implement or fix feature
4. Add test case

**Effort Estimate:** 2-4 hours (depends on root cause)  
**Owner:** [Assign to developer]

---

#### M3: Monte-carlo command not working

**ID:** M3  
**Severity:** MAJOR  
**Category:** Feature - Implementation  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P1 (HIGH)

**Title:**
Monte-carlo simulation command exits with error code 2

**Description:**
The monte-carlo command, which should run probabilistic simulation with price perturbations, returns exit code 2 (likely file/path issue).

**Steps to Reproduce:**
```bash
python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-01-31 --num-simulations 10
```

**Expected Behavior:**
Display simulation results table with confidence intervals and VaR metrics.

**Actual Behavior:**
Exit code 2, error message TBD (needs investigation)

**Impact:**
- Monte-carlo analysis feature completely unavailable
- Cannot assess strategy risk and probability distribution
- Users cannot use probabilistic analysis feature

**Investigation Required:**
1. Check if command is fully implemented
2. Check for file path issues (exit code 2 suggests file not found)
3. Check for missing dependencies
4. Get actual error message

**Suggested Fix:**
TBD after investigation

**Testing Plan:**
1. Run command with verbose flag (-v) to get full error
2. Debug root cause
3. Implement or fix feature
4. Add test case

**Effort Estimate:** 2-4 hours (depends on root cause)  
**Owner:** [Assign to developer]

---

### MINOR ISSUES

#### m1: Signal-only mode message misleading

**ID:** m1  
**Severity:** MINOR  
**Category:** UX - Message Clarity  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P2 (LOW)

**Title:**
Signal-only mode shows "Portfolio data unavailable" in mock platform context

**Description:**
When running analyze command with mock platform, the output shows:
```
⚠ Signal-Only Mode: Portfolio data unavailable, no position sizing provided
```

This message is accurate technically, but in a test environment with mock platform, it's more useful to show "Mock platform detected" instead.

**Suggestion:**
```python
# In decision display logic
if isinstance(platform, MockPlatform):
    console.print("📋 Mock Platform: Position sizing not available in test mode")
elif signal_only_mode:
    console.print("⚠️ Signal-Only Mode: Portfolio data unavailable")
```

**Effort Estimate:** 10 minutes  
**Owner:** [Low priority - nice to have]

---

#### m2: Invalid date ranges return silent $0 results

**ID:** m2  
**Severity:** MINOR  
**Category:** UX - Clarity  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P2 (LOW)

**Title:**
Backtest with start > end shows confusing $0 results table

**Description:**
When date range is invalid (start after end), the backtest command shows a table with all $0 values. This is misleading - users think backtest ran but found no trades.

**Suggestion:**
Add warning above results table when dates are likely invalid:
```python
if start_dt >= end_dt:
    console.print("[yellow]⚠ Warning: start_date is after end_date; no data to backtest[/]")
```

**Note:** This becomes moot once C2 is fixed (date validation added).

**Effort Estimate:** 5 minutes (covered by C2 fix)  
**Owner:** [Assign to C2 fixer]

---

### DOCUMENTATION GAPS

#### D1: Missing interactive command tests

**ID:** D1  
**Severity:** DOC GAP  
**Category:** Testing - Coverage  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P2 (LOW)

**Title:**
QA suite missing tests for interactive commands

**Description:**
The QA test harness (qa_test_harness.py) doesn't cover interactive commands because they require terminal input:
- `execute` (without decision ID)
- `approve` (full workflow with yes/no/modify)
- `run-agent` (startup and operation)
- Interactive shell (-i flag)

**Recommendation:**
Create separate test suite for interactive commands using `pexpect` or similar library to simulate terminal input.

**Effort Estimate:** 4-6 hours  
**Owner:** [Assign to QA lead]

---

#### D2: Incomplete feature documentation

**ID:** D2  
**Severity:** DOC GAP  
**Category:** Documentation  
**Status:** OPEN  
**Date Reported:** 2025-12-05  
**Priority:** P2 (LOW)

**Title:**
README and documentation incomplete for walk-forward and monte-carlo features

**Description:**
The main README and USAGE.md don't clearly document:
- Walk-forward analysis parameters and output
- Monte-carlo simulation parameters and output
- Expected use cases for each

**Recommendation:**
Update docs/USAGE.md with complete examples and output samples for each command.

**Effort Estimate:** 2-3 hours  
**Owner:** [Technical writer / developer]

---

## Issue Statistics

### By Severity
| Severity | Count | % of Total |
|----------|-------|-----------|
| CRITICAL | 2 | 22% |
| MAJOR | 3 | 33% |
| MINOR | 2 | 22% |
| DOC GAP | 2 | 22% |
| **TOTAL** | **9** | **100%** |

### By Category
| Category | Count |
|----------|-------|
| Bug | 4 |
| Feature | 2 |
| UX | 2 |
| Testing | 1 |
| Documentation | 1 |

### By Priority
| Priority | Count | Est. Fix Time |
|----------|-------|---------------|
| P0 (URGENT) | 2 | 45 min |
| P1 (HIGH) | 3 | 2-4 hours |
| P2 (LOW) | 4 | 6-9 hours |

---

## Resolution Plan

### Week 1 (URGENT)
- [ ] Fix C1: Backtest AttributeError (30 min)
- [ ] Fix C2: Backtest date validation (15 min)
- [ ] Fix M1: History error handling (20 min)
- **Total Time: 1 hour 5 minutes**

### Week 2 (HIGH)
- [ ] Debug M2: Walk-forward command (2-4 hours)
- [ ] Debug M3: Monte-carlo command (2-4 hours)
- **Total Time: 4-8 hours**

### Week 3 (MEDIUM)
- [ ] Implement D1: Interactive command tests (4-6 hours)
- [ ] Update D2: Feature documentation (2-3 hours)
- [ ] Fix m1: Signal-only message (10 min)
- **Total Time: 6-9 hours**

---

## Sign-Off

**QA Analysis Completed By:** Automated QA + Manual Verification  
**Date:** December 5, 2025  
**Status:** READY FOR DEVELOPER ASSIGNMENT  
**Next Step:** Assign issues to development team for resolution

