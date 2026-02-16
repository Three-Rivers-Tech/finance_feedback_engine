# Exception Cleanup - Tier 3 Log

**Date:** 2026-02-15
**Branch:** exception-cleanup-tier3
**Target:** 15-20 critical exception handler improvements

## Files Analyzed

### 1. risk/gatekeeper.py
**Status:** ✅ Fixed (3 handlers)

**Issues Found:**
1. ❌ Line 142-156: Bare except on timestamp parsing with weak fallback
2. ❌ Line 161-165: Catch-all except on model install with no context
3. ❌ Line 236-244: Multiple except branches with no error tracking

**Fixes Applied:**
- Added specific exception types with proper logging
- Added error context (asset_pair, timestamp value)
- Distinguished backtest vs live mode failure handling
- Added TODO for monitoring/alerting

### 2. decision_engine/ai_decision_manager.py
**Status:** ✅ Fixed (3 handlers)

**Issues Found:**
1. ❌ Lines 180, 202, 224: Bare except Exception in debate mode with minimal logging

**Fixes Applied:**
- Distinguished TimeoutError from generic exceptions
- Added structured logging with provider role context
- Added error type classification for monitoring
- Added TODOs for alerting on repeated failures

### 3. trading_platforms/unified_platform.py
**Status:** ✅ Fixed (2 handlers)

**Issues Found:**
1. ❌ Line 102: Bare except Exception in get_balance() with minimal logging
2. ❌ Line 210: Bare except Exception in get_active_positions() with minimal logging

**Fixes Applied:**
- Distinguished ConnectionError from validation errors
- Added structured logging with platform context
- Fail-safe mode: continue with other platforms on errors
- Added TODOs for alerting

### 4. core.py
**Status:** ✅ Fixed (3 handlers)

**Issues Found:**
1. ❌ Line ~1145: Bare except Exception in price comparison with debug-level logging
2. ❌ Lines ~1180-1195: Multiple except blocks with minimal context in portfolio fetch
3. ❌ Line ~1220: Bare except Exception in transaction cost calculation

**Fixes Applied:**
- Upgraded logging levels from debug to warning/error
- Distinguished data format errors from connection errors
- Added structured logging with asset_pair and error type
- Added asyncio.TimeoutError handling for portfolio fetch
- Added TODOs for monitoring and alerting

## Summary
- **Handlers Improved:** 10 / 15-20 target
- **Files Modified:** 4
- **Tests Added:** 0
- **Commits:** 3
