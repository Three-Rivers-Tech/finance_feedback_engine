# MockLiveProvider Guide

## Overview

`MockLiveProvider` is a data provider that simulates live data streaming by incrementally stepping through historical data one candle at a time. This is essential for realistic backtesting where you need to simulate how a trading strategy would behave with limited information (no looking ahead).

## Key Features

- ✅ **Candle-by-Candle Streaming**: Advances through data one step at a time
- ✅ **AlphaVantage-Compatible**: Output matches `AlphaVantageProvider` format exactly
- ✅ **Position Tracking**: Maintains current index pointer for state
- ✅ **Rich Technical Data**: Includes RSI, MACD, Bollinger Bands (dummy values)
- ✅ **Historical Windows**: Get sliding windows of past data
- ✅ **Reset & Replay**: Reset to any index for repeated testing

## Basic Usage

### Creating the Provider

```python
import pandas as pd
from finance_feedback_engine.data_providers import MockLiveProvider

# Load historical data
historical_data = pd.DataFrame({
    'open': [100.0, 101.0, 102.0],
    'high': [105.0, 106.0, 107.0],
    'low': [98.0, 99.0, 100.0],
    'close': [102.0, 103.0, 104.0],
    'volume': [1000000, 1100000, 1200000],
    'market_cap': [500000000, 510000000, 520000000]  # Optional for crypto
})

# Create provider
provider = MockLiveProvider(historical_data, asset_pair='BTCUSD')
```

### Streaming Data

```python
# Get current price
price = provider.get_current_price()  # 102.0

# Advance to next candle
provider.advance()

# Get new price
price = provider.get_current_price()  # 103.0

# Check if more data available
if provider.has_more_data():
    provider.advance()
```

### Full Streaming Loop

```python
prices = []

while provider.has_more_data():
    price = provider.get_current_price()
    prices.append(price)
    provider.advance()

# Get final price
prices.append(provider.get_current_price())
```

## Advanced Features

### Getting Comprehensive Market Data

```python
# Get full market data with technical indicators
data = await provider.get_comprehensive_market_data(
    'BTCUSD',
    include_sentiment=True,
    include_macro=True
)

# Output includes:
print(data['open'])           # OHLCV data
print(data['price_range'])    # Enrichments
print(data['rsi'])            # Technical indicators (dummy values)
print(data['sentiment'])      # Sentiment data (dummy)
```

### Historical Windows

```python
# Get last 10 candles including current
window = provider.get_historical_window(window_size=10, include_current=True)

# Get last 10 candles excluding current (look-back only)
window = provider.get_historical_window(window_size=10, include_current=False)
```

### Peeking Ahead (Testing Only)

```python
# Peek at next candle without advancing
future = provider.peek_ahead(1)
print(future['close'])

# Current index unchanged
print(provider.current_index)  # Still at same position

# Note: Use sparingly - in real trading you can't peek ahead!
```

### Reset and Replay

```python
# Reset to beginning
provider.reset(0)

# Reset to specific index
provider.reset(50)

# Re-run simulation with different parameters
```

## Backtesting Integration

### Simple Backtest Example

```python
from finance_feedback_engine.trading_platforms import MockTradingPlatform
from finance_feedback_engine.data_providers import MockLiveProvider
import pandas as pd

# Load historical data
data = pd.read_csv('btc_historical.csv')

# Create provider and platform
provider = MockLiveProvider(data, asset_pair='BTCUSD')
platform = MockTradingPlatform(initial_balance=10000.0)

# Simple moving average strategy
positions = []
window_size = 20

while provider.has_more_data():
    # Get historical window for MA calculation
    window = provider.get_historical_window(
        window_size=window_size,
        include_current=False  # Don't use current price in MA
    )

    if len(window) >= window_size:
        ma = window['close'].mean()
        current_price = provider.get_current_price()

        # Buy signal: price crosses above MA
        if current_price > ma and len(positions) == 0:
            result = platform.execute_trade(
                asset_pair='BTCUSD',
                action='buy',
                quantity=0.1,
                price=current_price
            )
            positions.append(result)

        # Sell signal: price crosses below MA
        elif current_price < ma and len(positions) > 0:
            result = platform.execute_trade(
                asset_pair='BTCUSD',
                action='sell',
                quantity=0.1,
                price=current_price
            )
            positions.clear()

    # Advance to next candle
    provider.advance()

# Check final balance
balance = platform.get_balance()
print(f"Final balance: ${balance:.2f}")
```

### Agent Simulation

```python
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator

# Create provider
provider = MockLiveProvider(historical_data, asset_pair='BTCUSD')

# Create orchestrator with mock provider
orchestrator = TradingAgentOrchestrator(
    config=config,
    data_provider=provider  # Pass mock provider
)

# Run agent simulation
orchestrator.run(
    take_profit_threshold=0.05,
    stop_loss_threshold=0.02
)
```

## Output Format

### Current Candle Structure

```python
candle = provider.get_current_candle()

{
    'open': 100.0,
    'high': 105.0,
    'low': 98.0,
    'close': 102.0,
    'volume': 1000000,
    'date': '2024-01-01',  # If available
    'market_cap': 500000000  # If available (crypto)
}
```

### Comprehensive Market Data Structure

Matches `AlphaVantageProvider` exactly:

```python
{
    # Base OHLCV
    'open': 100.0,
    'high': 105.0,
    'low': 98.0,
    'close': 102.0,
    'volume': 1000000,

    # Enrichments
    'price_range': 7.0,
    'price_range_pct': 6.86,
    'body_size': 2.0,
    'body_pct': 28.57,
    'upper_wick': 3.0,
    'lower_wick': 2.0,
    'trend': 'bullish',
    'is_bullish': True,

    # Technical Indicators (dummy values)
    'rsi': 50.0,
    'rsi_signal': 'neutral',
    'macd': 0.0,
    'macd_signal': 0.0,
    'macd_histogram': 0.0,
    'bbands_upper': 107.0,
    'bbands_middle': 102.0,
    'bbands_lower': 97.0,

    # Metadata
    'asset_pair': 'BTCUSD',
    'provider': 'mock_live',
    'timestamp': '2024-01-01T00:00:00Z',

    # Sentiment (dummy if requested)
    'sentiment': {
        'available': False,
        'overall_sentiment': 'neutral',
        'sentiment_score': 0.0
    },

    # Macro indicators (dummy if requested)
    'macro': {
        'available': False,
        'indicators': {}
    }
}
```

## Progress Tracking

```python
# Get current progress
progress = provider.get_progress()

{
    'current_index': 25,
    'total_candles': 100,
    'progress_pct': 25.0,
    'has_more': True
}

# Get current index
index = provider.get_current_index()  # 25

# Get total candles
total = len(provider)  # 100
```

## Error Handling

```python
# Empty data
try:
    provider = MockLiveProvider(pd.DataFrame())
except ValueError as e:
    print(e)  # "Historical data cannot be None or empty"

# Missing required columns
try:
    provider = MockLiveProvider(pd.DataFrame({'open': [100]}))
except ValueError as e:
    print(e)  # "Missing required columns: ['high', 'low', 'close']"

# Out of bounds index
try:
    provider.current_index = 1000
    candle = provider.get_current_candle()
except IndexError as e:
    print(e)  # "Current index 1000 out of bounds"

# Invalid reset
try:
    provider.reset(-1)
except ValueError as e:
    print(e)  # "Invalid start_index: -1"
```

## Best Practices

### ✅ Do's

- **Use for backtesting**: Perfect for testing strategies with realistic data flow
- **Avoid look-ahead bias**: Use `include_current=False` in historical windows
- **Reset between runs**: Reset to starting index for repeated tests
- **Combine with MockTradingPlatform**: Full simulated environment
- **Test edge cases**: Start at different indices, test boundary conditions

### ❌ Don'ts

- **Don't peek ahead in production**: `peek_ahead()` is for testing only
- **Don't modify historical data**: Provider copies data to prevent mutations
- **Don't assume indices**: Always check `has_more_data()` before advancing
- **Don't skip validation**: Provider validates columns at initialization

## Configuration Integration

Add to `config.yaml`:

```yaml
data_provider:
  type: "mock_live"  # For backtesting
  mock_live:
    data_source: "data/historical/btc_usd_daily.csv"
    start_index: 0
```

## Testing

```python
import pytest
from finance_feedback_engine.data_providers import MockLiveProvider

def test_streaming():
    data = pd.DataFrame({
        'open': [100, 101],
        'high': [105, 106],
        'low': [98, 99],
        'close': [102, 103]
    })

    provider = MockLiveProvider(data)

    # Test initial state
    assert provider.current_index == 0
    assert provider.get_current_price() == 102

    # Test advance
    assert provider.advance() is True
    assert provider.current_index == 1
    assert provider.get_current_price() == 103

    # Test end of data
    assert provider.advance() is False
```

## Comparison: MockLiveProvider vs AlphaVantageProvider

| Feature | MockLiveProvider | AlphaVantageProvider |
|---------|------------------|---------------------|
| Data Source | Historical DataFrame | Alpha Vantage API |
| Cost | Free | API rate limits |
| Speed | Instant | API latency |
| Output Format | Identical | Identical |
| Use Case | Backtesting | Live trading |
| Technical Indicators | Dummy values | Real calculations |
| Sentiment Data | Dummy | Real news sentiment |

## See Also

- [Mock Trading Platform Guide](MOCK_PLATFORM_GUIDE.md)
- [Backtesting Guide](../BACKTESTER_TRAINING_FIRST_QUICKREF.md)
- [AlphaVantage Provider Docs](../finance_feedback_engine/data_providers/alpha_vantage_provider.py)
