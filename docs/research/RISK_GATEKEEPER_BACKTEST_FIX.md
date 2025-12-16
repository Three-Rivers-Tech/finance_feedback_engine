# RiskGatekeeper Backtest Timestamp Fix

## Problem
The `RiskGatekeeper` was silently swallowing timestamp parse errors and falling back to live market hours in all modes. This corrupted backtesting by using current time instead of historical timestamps from the backtest data.

## Solution
Added mode-aware timestamp error handling:
- **Backtest mode** (`is_backtest=True`): Raises `ValueError` on timestamp parsing failures with descriptive error message
- **Live mode** (`is_backtest=False`, default): Preserves existing fallback behavior for backward compatibility

## Changes

### 1. `finance_feedback_engine/risk/gatekeeper.py`
- Added `is_backtest` parameter to `__init__()` (default: `False`)
- Updated timestamp parsing exception handler (lines 217-227):
  - Detects execution mode via `self.is_backtest`
  - Raises descriptive `ValueError` in backtest mode
  - Falls back to `MarketSchedule.get_market_status()` in live mode only

### 2. Backtester Integration
- `finance_feedback_engine/backtesting/backtester.py`: Set `is_backtest=True` in RiskGatekeeper instantiation (line 178)
- `finance_feedback_engine/backtesting/portfolio_backtester.py`: Set `is_backtest=True` in RiskGatekeeper instantiation (line 164)

### 3. Tests
- Created `tests/risk/test_gatekeeper_backtest_timestamp.py` with 4 comprehensive tests:
  - `test_backtest_mode_raises_on_invalid_timestamp`: Verifies ValueError raised in backtest mode
  - `test_live_mode_falls_back_on_invalid_timestamp`: Verifies fallback preserved in live mode
  - `test_backtest_mode_accepts_valid_iso_timestamp`: Validates ISO format parsing
  - `test_backtest_mode_accepts_valid_unix_timestamp`: Validates Unix timestamp parsing

## Impact
- **Breaking**: None (backward compatible; `is_backtest` defaults to `False`)
- **Fixes**: Backtesting now correctly fails fast on timestamp parsing errors instead of silently corrupting results
- **Preserves**: Live trading fallback behavior unchanged

## Testing
```bash
pytest tests/risk/test_gatekeeper_backtest_timestamp.py -v
# Result: 4/4 tests passed
```

## Error Message Format
```
ValueError: Failed to parse timestamp in backtest mode for BTCUSD:
timestamp=invalid-timestamp-format, error=<original exception>.
Backtest requires valid timestamps.
```

## Related Files
- `finance_feedback_engine/risk/gatekeeper.py` (main implementation)
- `finance_feedback_engine/backtesting/backtester.py` (consumer)
- `finance_feedback_engine/backtesting/portfolio_backtester.py` (consumer)
- `tests/risk/test_gatekeeper_backtest_timestamp.py` (test coverage)
