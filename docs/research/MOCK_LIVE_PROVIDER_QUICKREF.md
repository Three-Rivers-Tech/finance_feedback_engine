# MockLiveProvider Quick Reference

## Installation
```python
from finance_feedback_engine.data_providers import MockLiveProvider
```

## Quick Start

```python
import pandas as pd
from finance_feedback_engine.data_providers import MockLiveProvider

# Load historical data
data = pd.DataFrame({
    'open': [100, 101, 102],
    'high': [105, 106, 107],
    'low': [98, 99, 100],
    'close': [102, 103, 104]
})

# Create provider
provider = MockLiveProvider(data, asset_pair='BTCUSD')

# Stream data
while provider.has_more_data():
    price = provider.get_current_price()
    print(f"Price: ${price:.2f}")
    provider.advance()
```

## Common Patterns

### Basic Streaming
```python
provider = MockLiveProvider(data)
for _ in range(len(provider)):
    price = provider.get_current_price()
    # Process...
    if not provider.advance():
        break
```

### With Historical Window (Moving Average)
```python
window_size = 20
provider.reset(window_size)  # Start after warmup

while provider.has_more_data():
    window = provider.get_historical_window(window_size, include_current=False)
    ma = window['close'].mean()
    current = provider.get_current_price()

    if current > ma:
        print("Buy signal")

    provider.advance()
```

### Progress Tracking
```python
while provider.has_more_data():
    progress = provider.get_progress()
    print(f"Progress: {progress['progress_pct']:.0f}%")
    provider.advance()
```

### Reset & Replay
```python
# First pass
provider.reset(0)
prices_1 = [provider.get_current_price() for _ in range(10) if provider.advance() or True]

# Second pass (identical)
provider.reset(0)
prices_2 = [provider.get_current_price() for _ in range(10) if provider.advance() or True]

assert prices_1 == prices_2
```

## API Reference

### Initialization
```python
MockLiveProvider(
    historical_data: pd.DataFrame,  # Required: OHLC columns
    asset_pair: str = 'BTCUSD',     # Optional: identifier
    start_index: int = 0             # Optional: starting position
)
```

### Core Methods
```python
advance() -> bool                   # Move to next, returns False at end
reset(index: int) -> None          # Jump to specific index
has_more_data() -> bool            # Check if more candles available
get_current_index() -> int         # Current position
get_current_price() -> float       # Current close price
```

### Data Access
```python
get_current_candle() -> dict                     # Current OHLCV
get_market_data() -> dict                        # Basic market data
get_comprehensive_market_data() -> dict (async)  # Full enriched data
```

### Analysis
```python
get_historical_window(
    window_size: int = 10,
    include_current: bool = True
) -> pd.DataFrame

peek_ahead(steps: int = 1) -> Optional[dict]
get_progress() -> dict
```

## Output Formats

### Current Candle
```python
{
    'open': 100.0,
    'high': 105.0,
    'low': 98.0,
    'close': 102.0,
    'volume': 1000000,      # If available
    'date': '2024-01-01'    # If available
}
```

### Comprehensive Data (AlphaVantage Compatible)
```python
{
    'open': 100.0, 'high': 105.0, 'low': 98.0, 'close': 102.0,
    'price_range': 7.0, 'trend': 'bullish', 'is_bullish': True,
    'rsi': 50.0, 'macd': 0.0, 'bbands_upper': 107.0,
    'asset_pair': 'BTCUSD', 'provider': 'mock_live'
}
```

## Common Use Cases

### Backtest with MA Strategy
```python
provider = MockLiveProvider(data, asset_pair='BTCUSD')
provider.reset(20)  # Warmup period

signals = []
while provider.has_more_data():
    window = provider.get_historical_window(20, include_current=False)
    ma = window['close'].mean()
    price = provider.get_current_price()

    if price > ma:
        signals.append(('BUY', price))

    provider.advance()
```

### Integration with Engine
```python
from finance_feedback_engine import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(
    data_provider=MockLiveProvider(historical_data)
)

decision = await engine.analyze_asset('BTCUSD')
```

## Error Handling

```python
# Empty data
try:
    provider = MockLiveProvider(pd.DataFrame())
except ValueError:
    # Handle: "Historical data cannot be None or empty"

# Missing columns
try:
    provider = MockLiveProvider(pd.DataFrame({'open': [100]}))
except ValueError:
    # Handle: "Missing required columns: ['high', 'low', 'close']"

# Out of bounds
try:
    provider.reset(1000)  # Beyond data length
except ValueError:
    # Handle: "Invalid start_index: 1000 >= 100"
```

## Tips & Best Practices

✅ **Do:**
- Use `include_current=False` for historical windows to avoid look-ahead
- Reset to starting index for repeated tests
- Check `has_more_data()` before advancing
- Combine with MockTradingPlatform for full simulation

❌ **Don't:**
- Don't use `peek_ahead()` in production strategies (testing only)
- Don't modify historical_data after initialization
- Don't assume data length - always check boundaries
- Don't call `get_current_candle()` after data exhausted

## Comparison Table

| Feature | MockLiveProvider | AlphaVantageProvider |
|---------|------------------|---------------------|
| Speed | Instant (< 1ms) | ~100-500ms API |
| Cost | Free | Rate limited |
| Replay | ✅ Yes | ❌ No |
| Use Case | Testing | Live trading |

## See Also

- Full Guide: `docs/MOCK_LIVE_PROVIDER_GUIDE.md`
- Demo Script: `demo_mock_live_provider.py`
- Implementation: `MOCK_LIVE_PROVIDER_IMPLEMENTATION.md`
- Mock Platform: `docs/MOCK_PLATFORM_GUIDE.md`
