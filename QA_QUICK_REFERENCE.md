# Finance Feedback Engine - QA Quick Reference Guide

**Purpose:** Quick lookup for QA findings and bug fixes  
**Last Updated:** December 5, 2025

---

## 🚨 Critical Issues Summary

### Issue C1: Backtest Crash
```
Command: backtest BTCUSD --start 2024-01-01 --end 2024-01-31
Error:   'list' object has no attribute 'get'
File:    finance_feedback_engine/decision_engine/engine.py:1898
Fix:     Add type checking for active_positions (dict vs list)
Time:    30 minutes
```

### Issue C2: Backtest Invalid Dates
```
Command: backtest BTCUSD --start 2024-01-31 --end 2024-01-01
Error:   Silently returns $0.00 results (should error)
File:    finance_feedback_engine/cli/main.py (backtest command)
Fix:     Add date validation (start_dt < end_dt)
Time:    15 minutes
```

---

## ✅ What Works (8/22 Commands)

| Command | Status | Time | Note |
|---------|--------|------|------|
| analyze | ✓ | 10-18s | All providers work |
| balance | ✓ | 1-2s | Mock platform |
| status | ✓ | 1-2s | - |
| dashboard | ✓ | 1-2s | - |
| history | ✓* | 1-2s | *Non-existent asset exits 1; expected 0 with empty result (workaround: omit --asset or use valid asset) |
| wipe-decisions | ✓ | 1-2s | - |
| install-deps | ✓ | 1-2s | - |
| learning-report | ✓ | 1-2s | - |

---

## ❌ What's Broken (3/22 Commands)

| Command | Issue | Fix |
|---------|-------|-----|
| backtest | Crashes with AttributeError | See C1 above |
| walk-forward | Exit code 1, feature not working | TBD investigation |
| monte-carlo | Exit code 2, feature not working | TBD investigation |
---

## 📋 Asset Pair Formats (All Equivalent)

```
BTCUSD  ✓
btc-usd ✓
BTC/USD ✓
BTC-USD ✓
```

All formats are auto-normalized to BTCUSD.

---

## 🔧 Fix Priority

### Week 1 (Urgent) - 1 Hour 5 Minutes
- [ ] Fix C1: Backtest AttributeError (30 min)
- [ ] Fix C2: Backtest date validation (15 min)
- [ ] Fix M1: History error handling (20 min)

### Week 2 (High) - 4-8 Hours
- [ ] Debug walk-forward command
- [ ] Debug monte-carlo command

### Week 3+ (Medium/Low) - 6-12 Hours
- [ ] Interactive command tests
- [ ] Documentation updates

---

## 📊 Test Results Summary

```
Passing:    12/17 tests (70.6%)
Failing:    5/17 tests (29.4%)

P0 (Core):     6/8 (75%)
P1 (Workflow): 4/5 (80%)
P2 (Advanced): 2/4 (50%)
```

---

## 🎯 Sample Commands for Quick Testing

### Verify Core Functionality
```bash
# This works
python main.py analyze BTCUSD --provider local

# This should work but crashes
python main.py backtest BTCUSD --start 2024-01-01 --end 2024-01-31

# This works
python main.py balance

# This works
python main.py history --limit 5
```

### Test Consistency
```bash
# Should both return exit code 0
python main.py history
python main.py history --asset BTCUSD

# Currently: base command exits 0; --asset NONEXISTENT exits 1 instead of 0 (expected empty result)
python main.py history --asset NONEXISTENT
```

---

## 📁 QA Artifact Files

| File | Purpose | Size |
|------|---------|------|
| docs/QA_TEST_MATRIX.md | Test specifications | 800+ lines |
| docs/QA_ANALYSIS_REPORT.md | Full findings | 1200+ lines |
| docs/QA_ISSUES.md | Bug tracking | 800+ lines |
| docs/CLI_BEHAVIOR_REFERENCE.md | Command reference | 1000+ lines |
| qa_test_harness.py | Automation script | 400 lines |
| qa_results_full.json | Test results (JSON) | 50KB |

---

## 🚀 Running QA Tests

```bash
# Run all tests
python qa_test_harness.py

# Run only P0 (core) tests
python qa_test_harness.py --level P0

# Run specific command
python qa_test_harness.py --command analyze

# Verbose with test details
python qa_test_harness.py --verbose
```

---

## 📖 Reading QA Documents

**For Executives:**
→ Read: `QA_ANALYSIS_REPORT.md` (Executive Summary section)

**For Developers:**
→ Read: `QA_ISSUES.md` (Full issue specifications with fix suggestions)

**For QA/Testing:**
→ Read: `CLI_BEHAVIOR_REFERENCE.md` (Expected command outputs)

**For Release Planning:**
→ Read: `QA_TEST_MATRIX.md` (Test coverage by command)

---

## 🔍 Common Questions Answered

### Q: How many CLI commands are there?
**A:** 22 total commands across 5 categories (core, workflow, advanced, utility, interactive)

### Q: What's the pass rate?
**A:** 70.6% (12/17 automated tests passing); 2 critical bugs block major features

### Q: Which command is most important to fix?
**A:** BACKTEST - it's broken (crashes) and blocks core functionality

### Q: Can I use the CLI in production now?
**A:** Partially. Analyze/balance/history work, but BACKTEST (critical) is broken. Recommend fixing C1+C2 before production use.

### Q: How long to fix everything?
**A:** ~10-15 hours total (1 hour urgent, 4-8 hours medium, 6-9 hours low priority)

### Q: Can I automate these tests?
**A:** Yes - use `qa_test_harness.py` and parse `qa_results.json` in CI/CD

---

## 📞 For Support

**Found a CLI bug not in this list?**
1. Run: `python main.py -v [command] [args]` (verbose mode)
2. Capture full error output
3. Add to `docs/QA_ISSUES.md` following the template
4. Include: command, expected behavior, actual behavior, steps to reproduce

**Want to add a new test?**
1. Edit `qa_test_harness.py`
2. Add test case to `define_*_tests()` function
3. Run: `python qa_test_harness.py --command [command]`
4. Verify output in `qa_results.json`

---

## 📈 Metrics at a Glance

```
CLI Maturity:      70% (mostly functional)
Test Automation:   60% (basic tests in place)
Documentation:    85% (comprehensive QA docs)
Production Ready:  No (critical bugs present)
```

---

## ✨ What Works Really Well

- ✓ Asset pair format normalization
- ✓ Multi-provider ensemble voting
- ✓ Error messages are clear and actionable
- ✓ Mock platform for testing works perfectly
- ✓ Config file loading and overrides
- ✓ Decision persistence and retrieval

---

## 🐛 What Needs Work

- ✗ Backtest engine crashes on valid input
- ✗ Date range validation missing
- ✗ Error handling inconsistencies
- ✗ Advanced features incomplete (walk-forward, monte-carlo)
- ✗ Interactive commands not tested
- ✗ Some documentation gaps

---

## 🎓 Learning Resources

**To understand the codebase better:**
1. Read `finance_feedback_engine/cli/main.py` (CLI entry points)
2. Read `finance_feedback_engine/core.py` (engine architecture)
3. Read `docs/USAGE.md` (user-facing documentation)
4. Reference `docs/PROJECT_SUMMARY.md` (architecture overview)

**To understand QA results:**
1. Start: `QA_IMPLEMENTATION_COMPLETE.md` (this summary)
2. Then: `QA_ANALYSIS_REPORT.md` (detailed findings)
3. Reference: `CLI_BEHAVIOR_REFERENCE.md` (command specs)
4. Deep dive: `QA_ISSUES.md` (issue specifications)

---

**Last Updated:** December 5, 2025  
**Status:** QA Analysis Complete ✅  
**Ready for:** Development Assignment & Release Planning

