# Code Review Request: aiohttp Session Cleanup (THR-206)

## Context
Fixed memory leaks in Finance Feedback Engine CLI commands. AlphaVantageProvider was leaving unclosed aiohttp sessions causing asyncio warnings and memory leaks.

## Changes Summary

### 1. UnifiedDataProvider cleanup (unified_data_provider.py)
- Added async `close()` method that closes all providers (AlphaVantage, Coinbase, Oanda)
- Added `__aenter__` and `__aexit__` for async context manager support
- Checks if `close()` result is awaitable before awaiting

### 2. FinanceFeedbackEngine cleanup (core.py)
- Enhanced `close()` to clean up unified_provider and historical_data_provider
- Uses `inspect.iscoroutine/isawaitable` checks before awaiting

### 3. CLI commands cleanup pattern (11 commands across 5 files)
```python
def command(ctx, ...):
    engine = None
    try:
        engine = FinanceFeedbackEngine(config)
        # command logic
    finally:
        if engine is not None:
            try:
                asyncio.run(engine.close())
            except Exception:
                pass  # Silent cleanup
```

## Review Questions

1. **Try/finally pattern**: Is this correct for preventing leaks even on exceptions?
2. **Silent exception swallowing**: Is `pass` on Exception in cleanup acceptable?
3. **Awaitable checks**: Are `inspect.iscoroutine/isawaitable` checks the right way to handle optional async?
4. **asyncio.run() in finally**: Should this be used in finally blocks, or is there a better pattern?
5. **Race conditions**: Any edge cases or race conditions missed?
6. **Context manager**: Is the implementation in UnifiedDataProvider correct?
7. **Memory safety**: Will this eliminate all session leaks?
8. **Error handling**: Any scenarios where cleanup could still fail silently?

## Test Results
- All CLI commands run without asyncio warnings
- Demo script: 6 engines created/closed with 0 leaks
- Unit tests: 0 leaks detected

## Request
Please rate this implementation (1-10) and suggest any improvements for:
- Memory safety
- Error handling
- Async patterns
- Best practices compliance
