# Stabilization & Standardization Plan

## Objective
Fix the broken "fast" test suite (currently 41 failures) and repair the pre-commit configuration to enable a stable development gate.

## 1. Fix Pre-commit Configuration (Immediate)
**Issue:** `pre-commit` fails because it hardcodes `python3.12`, but the environment is running Python 3.13.
**Action:**
- Modify `.pre-commit-config.yaml` to remove specific python version constraints for hooks, allowing them to use the active environment.

## 2. Fix Data Provider Test Failures (High Priority)
**Issue:** Refactoring to `BaseDataProvider` has broken tests in `test_data_providers_comprehensive.py`.
**Specific Failures:**
- `AttributeError: 'CoinbaseDataProvider' object has no attribute 'api_key'`
- `AttributeError: 'UnifiedDataProvider' object has no attribute 'get_market_data'`
- `ImportError: No module named 'oandapyV20'`
**Action:**
- Update `tests/test_data_providers_comprehensive.py` to use the correct attributes (likely inherited from `BaseDataProvider`).
- Verify `oandapyV20` dependency or fix mocking in `tests/test_platform_error_handling.py`.

## 3. Fix Ensemble & Logic Tests
**Issue:** Failures in `test_ensemble_tiers.py` and `test_veto_thompson_ensemble_regression.py`.
**Action:**
- Investigate assertion errors in fallback logic (e.g., `expected 'majority_fallback', got 'weighted'`).
- Update test expectations to match current ensemble behavior.

## 4. Fix Integration & Environment Tests
**Issue:** `TestRedisManager` and `TestTunnelManager` failures.
**Action:**
- Fix mocking for `shlex` and `ngrok` interactions.
- Ensure tests gracefully skip if external tools aren't present (or mock them effectively).

## 5. Code Quality & Linting
**Issue:** Pre-commit is currently broken, so linting state is unknown.
**Action:**
- Once pre-commit is fixed, run full linting (`black`, `flake8`, `mypy`).
- Address high-priority linting violations.

## 6. Coverage Improvement
**Target:** Increase coverage from ~45% to 70% (long term).
**Immediate Step:**
- After stabilization, create new tests for `finance_feedback_engine/agent/trading_loop_agent.py` (currently 30% coverage) as identified in QA plans.
