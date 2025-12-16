# Critical Issue: Backtester Uses Daily Candles Only

**Status**: Root cause identified
**Severity**: CRITICAL - Breaks realistic market state simulation
**Date Identified**: December 2025

## Problem Statement

The backtester currently uses **daily candles only** instead of intraday candles, making it impossible to simulate real market conditions. For a 31-day backtest:
- **Actual daily candles used**: ~22 candles (trading days only)
- **Realistic 1h intraday needed**: ~528 candles
- **Realistic 15m intraday needed**: ~2112 candles
- **Realistic 5m intraday needed**: ~6336 candles

This means the backtester cannot capture:
- Intraday price volatility and momentum
- Realistic trade entry/exit fills
- Intraday pullbacks and reversals
- True support/resistance levels
- Market microstructure effects

## Root Cause

**File**: `finance_feedback_engine/data_providers/alpha_vantage_provider.py`
**Method**: `AlphaVantageProvider.get_historical_data()` (lines 252-357)

### Problematic Code
```python
async def get_historical_data(self, asset_pair: str, start: str, end: str) -> list:
    """Return a list of daily OHLC dictionaries within [start,end]."""
    # ...
    if 'BTC' in asset_pair or 'ETH' in asset_pair:
        # Crypto - uses DAILY endpoint only
        params = {
            'function': 'DIGITAL_CURRENCY_DAILY',  # ← DAILY ONLY
            'symbol': symbol,
            'market': market,
            'apikey': self.api_key,
        }
    else:
        # Forex - uses DAILY endpoint only
        params = {
            'function': 'FX_DAILY',  # ← DAILY ONLY
            'from_symbol': from_currency,
            'to_symbol': to_currency,
            'apikey': self.api_key,
        }
```

## Alpha Vantage API Limitations

The current implementation has these limitations:
1. **Crypto**: Uses `DIGITAL_CURRENCY_DAILY` (daily only) instead of `DIGITAL_CURRENCY_INTRADAY` (supports 1min, 5min, 15min, 30min, 60min)
2. **Forex**: Uses `FX_DAILY` (daily only) instead of `FX_INTRADAY` (supports 1min, 5min, 15min, 30min, 60min)
3. **No timeframe parameter**: Neither `get_historical_data()` nor the backtester accept a timeframe parameter

## Impact on Backtesting

### Current Behavior
```bash
python main.py backtest -s 2025-10-01 -e 2025-11-01 ethusd
# Uses ~22 daily candles for 31-day period
# Backtester loops 22 times (not realistic)
# No intraday market dynamics captured
```

### Expected Behavior
```bash
python main.py backtest -s 2025-10-01 -e 2025-11-01 ethusd --timeframe 1h
# Should use ~528 hourly candles for 31-day period
# Backtester loops 528 times (realistic intraday simulation)
# Captures intraday momentum, volatility, reversals
```

## Solution Plan

### 1. Extend AlphaVantageProvider (CRITICAL)
- Add `timeframe` parameter to `get_historical_data()` signature
- Add conditional logic to use `DIGITAL_CURRENCY_INTRADAY` / `FX_INTRADAY` for intraday timeframes
- Support timeframes: `['1m', '5m', '15m', '30m', '1h', '1d']` (Alpha Vantage limitations)
- Handle API rate limits (intraday requests return 100 candles, may need pagination)

### 2. Update Backtester
- Add `timeframe: str = '1h'` parameter to `Backtester.__init__()`
- Pass timeframe to `self.historical_data_provider.get_historical_data()` call
- Default to 1h (reasonable intraday resolution that respects API limits)

### 3. Update HistoricalDataProvider
- Modify `get_historical_data()` signature to accept optional `timeframe` parameter
- Pass timeframe through to Alpha Vantage provider

### 4. Update CLI
- Add `--timeframe` argument to `backtest` command
- Valid values: `1m`, `5m`, `15m`, `30m`, `1h`, `1d`
- Default: `1h`

### 5. Documentation
- Update `BACKTESTER_TRAINING_FIRST_QUICKREF.md` with timeframe examples
- Add note about API rate limits
- Document expected candle counts for different timeframes

## Implementation Notes

### Alpha Vantage API Details
- **DIGITAL_CURRENCY_INTRADAY**: Returns last 100 candles (may need to loop backwards)
- **FX_INTRADAY**: Returns last 100 candles (may need to loop backwards)
- **Rate limit**: Free tier is 5 requests/min (tight for intraday backtesting)
- **Caching critical**: Must cache intraday responses (different cache key per timeframe)

### Backward Compatibility
- Default to `1h` timeframe (not daily) to fix realism
- Existing scripts may expect daily; will need documentation
- Consider adding deprecation warning for daily-only mode

## Testing Strategy

1. **Unit Test**: Verify `get_historical_data(asset, dates, timeframe='1h')` returns 528 candles for 31-day EURUSD
2. **Integration Test**: Run backtester with `--timeframe 1h` and verify candle loop count
3. **Validation**: Check that intraday candles show realistic OHLC ranges (not just daily open/close)
4. **Performance**: Measure backtester speed with 528 candles vs 22 (will be slower but realistic)

## Files Affected

1. `finance_feedback_engine/data_providers/alpha_vantage_provider.py`
   - Add `timeframe` parameter to `get_historical_data()`
   - Add intraday endpoint logic

2. `finance_feedback_engine/data_providers/historical_data_provider.py`
   - Add `timeframe` parameter to `get_historical_data()`
   - Pass to Alpha Vantage provider

3. `finance_feedback_engine/backtesting/backtester.py`
   - Add `timeframe` to `__init__()` and `run_backtest()`
   - Pass to historical_data_provider

4. `finance_feedback_engine/cli/main.py`
   - Add `--timeframe` argument to backtest command

5. `BACKTESTER_TRAINING_FIRST_QUICKREF.md`
   - Document timeframe examples

## Next Steps

1. ✅ Root cause analysis (completed)
2. Implement AlphaVantageProvider intraday support
3. Update Backtester to accept and use timeframe
4. Update CLI to expose timeframe parameter
5. Comprehensive testing with intraday data
6. Update documentation

## References

- **Issue Discovery**: User noted backtest seemed unrealistic (22 candles for 31 days)
- **Root Cause**: AlphaVantageProvider uses DAILY endpoints exclusively
- **Key Code**: `alpha_vantage_provider.py` lines 252-357
