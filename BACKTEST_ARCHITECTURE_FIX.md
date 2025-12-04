# Backtest Architecture Fix

## Problem Identified

The `backtest_mode=True` parameter was causing the DecisionEngine to use **rule-based SMA/ADX logic** instead of querying actual AI providers. This created a fundamental discrepancy:

- **Production**: Uses AI providers (local LLMs, ensemble, etc.)
- **Backtest**: Uses hardcoded technical indicators

**Result**: Backtests were testing a completely different system than production, making results meaningless for validating AI trading strategies.

## Root Cause

Historical performance concern: AI queries are slow when processing thousands of historical candles. The `backtest_mode` flag was added as a shortcut to speed up backtests.

## Solution Implemented

### 1. Deprecate Rule-Based Backtest Mode

- `backtest_mode=True` now logs a deprecation warning
- Decision generation **always** uses the configured AI provider
- The flag is kept for backward compatibility but doesn't change behavior

### 2. Recommended Approaches for Different Use Cases

#### For Realistic AI Backtesting (Primary Use Case)
```python
# Use real AI providers - slow but accurate
config = {
    'ai_provider': 'ensemble',  # or 'local', 'qwen', etc.
    'decision_engine': {
        'model_name': 'llama-3.2-3B'
    }
}
engine = DecisionEngine(config)
backtester.run_backtest(asset_pair, start, end, engine)
```

**Performance**: ~1-5 seconds per decision (depending on provider)
**Accuracy**: Tests actual production AI system

#### For Fast Testing/Development
```python
# Use mock provider for instant decisions
config = {
    'ai_provider': 'mock',  # Instant random decisions
}
engine = DecisionEngine(config)
backtester.run_backtest(asset_pair, start, end, engine)
```

**Performance**: <0.01 seconds per decision
**Accuracy**: Random decisions, good for code testing only

#### For Rule-Based Strategy Testing
```python
# Implement custom strategy function
def sma_crossover_strategy(market_data, balance):
    # Your SMA/ADX logic here
    return {'action': 'BUY', 'confidence': 75, ...}

# Use with backtester directly (future enhancement)
```

### 3. Future Enhancements

#### Decision Caching System
```python
# Cache AI decisions keyed by (asset_pair, timestamp, market_data_hash)
# Rerun same backtest → instant results from cache
cache = DecisionCache('data/backtest_cache.db')
engine = DecisionEngine(config, decision_cache=cache)
```

#### Parallel Batch Processing
```python
# Process multiple historical periods in parallel
# Queue up all decisions, batch process with GPU
engine.batch_generate_decisions(historical_candles)
```

#### Replay Mode
```python
# Replay previously recorded live decisions
engine = DecisionEngine(config, replay_from='data/decisions/')
```

## Migration Guide

### For Test Files

**Old (Deprecated)**:
```python
engine = DecisionEngine(config, backtest_mode=True)
decision = engine.generate_decision(...)
assert decision['action'] == 'BUY'  # Expected rule-based logic
```

**New (Recommended)**:
```python
# Option 1: Use mock provider for fast testing
config = {'ai_provider': 'mock'}
engine = DecisionEngine(config)
decision = engine.generate_decision(...)
# Accept any valid action - mock is random
assert decision['action'] in ['BUY', 'SELL', 'HOLD']

# Option 2: Test actual AI provider (integration test)
config = {'ai_provider': 'local', 'model_name': 'llama-3.2-3B'}
engine = DecisionEngine(config)
decision = engine.generate_decision(...)
# Verify AI response structure, not specific action
assert 'reasoning' in decision
assert decision['confidence'] > 0
```

### For Production Backtests

**Old**:
```python
# Incorrectly used rule-based logic
engine = DecisionEngine(config, backtest_mode=True)
results = backtester.run_backtest('BTCUSD', '2024-01-01', '2024-12-01', engine)
```

**New**:
```python
# Uses actual AI provider configured in production
engine = DecisionEngine(config)  # backtest_mode removed
results = backtester.run_backtest('BTCUSD', '2024-01-01', '2024-12-01', engine)

# Or use mock for quick validation
config_fast = {**config, 'ai_provider': 'mock'}
engine_fast = DecisionEngine(config_fast)
results_fast = backtester.run_backtest('BTCUSD', '2024-01-01', '2024-12-01', engine_fast)
```

## Benefits

1. **Accuracy**: Backtests now test the actual AI system used in production
2. **Reproducibility**: Same AI models → consistent backtest results
3. **Validation**: Can verify AI provider performance with historical data
4. **Flexibility**: Choose speed (mock) vs accuracy (real AI) based on needs
5. **Transparency**: Clear separation between AI testing and rule-based testing

## Performance Considerations

### Typical Backtest Times

| Provider | Decisions/Hour | 1 Year Daily | 1 Year Hourly |
|----------|----------------|--------------|---------------|
| Mock | ~1,000,000 | <1 second | ~3 seconds |
| Local LLM | ~720 | ~30 minutes | ~365 hours |
| Ensemble (3 providers) | ~240 | ~90 minutes | ~1,095 hours |

### Optimization Strategies

1. **Use Daily Candles**: 365 decisions vs 8,760 for hourly
2. **Shorter Periods**: Focus on recent 3-6 months
3. **Sample Selection**: Test key market conditions, not every candle
4. **Caching** (Future): Store decisions, reuse for parameter tweaks
5. **Parallel Processing** (Future): Distribute across multiple GPUs

## Files Modified

- `finance_feedback_engine/decision_engine/engine.py`
  - Line 207-212: Changed backtest_mode to log deprecation warning only
  - Line 2178: Added `backtest_mode` flag to decision dict for tracking
    - `_generate_backtest_decision()` has been fully removed from `engine.py` (not present as a placeholder or dead code). Backtest logic now exclusively uses AI providers or mock providers as described above.

## Testing Updates Needed

- `tests/test_backtest_mode.py`: Update to use mock provider or test actual AI
- Integration tests: Verify backtest uses same provider as production
- Performance benchmarks: Document expected backtest durations

## Conclusion

This fix ensures that **backtests accurately reflect production AI behavior**, which is critical for:
- Validating AI model performance
- Tuning ensemble weights
- Evaluating strategy modifications
- Building confidence in live deployment

The tradeoff is slower backtests, but the accuracy gain is essential for a machine learning trading system.
