# MockTradingPlatform Usage Guide

## Overview

`MockTradingPlatform` is a comprehensive mock trading platform that simulates real trading behavior without hitting actual APIs. It's ideal for backtesting, agent testing, and development.

## Features

- ✅ Full state tracking (balances, positions, trades)
- ✅ Realistic slippage and fees simulation
- ✅ Position management (long/short tracking)
- ✅ Portfolio breakdown matching Coinbase format
- ✅ Trade history logging
- ✅ Price update functionality for backtesting
- ✅ Circuit breaker compatible
- ✅ Reset functionality for multiple test runs

## Installation

The mock platform is already integrated into the Finance Feedback Engine 2.0:

```python
from finance_feedback_engine.trading_platforms import MockTradingPlatform
from finance_feedback_engine.trading_platforms import PlatformFactory
```

## Basic Usage

### 1. Direct Instantiation

```python
from finance_feedback_engine.trading_platforms import MockTradingPlatform

# Create platform with default balance
platform = MockTradingPlatform()

# Or with custom initial balance
platform = MockTradingPlatform(
    initial_balance={
        'FUTURES_USD': 50000.0,
        'SPOT_USD': 10000.0,
        'SPOT_USDC': 5000.0
    }
)

# Configure slippage
platform = MockTradingPlatform(
    initial_balance={'FUTURES_USD': 25000.0},
    slippage_config={
        'type': 'percentage',  # or 'fixed'
        'rate': 0.002,         # 0.2% slippage
        'spread': 0.001        # 0.1% spread
    }
)
```

### 2. Via PlatformFactory

```python
from finance_feedback_engine.trading_platforms import PlatformFactory

# Create mock platform via factory
platform = PlatformFactory.create_platform('mock', {})

# Circuit breaker is automatically attached
```

## Core Operations

### Get Balance

```python
balance = platform.get_balance()
# Returns: {'FUTURES_USD': 10000.0, 'SPOT_USD': 5000.0, 'SPOT_USDC': 3000.0}
```

### Execute Trade

```python
decision = {
    'id': 'trade-001',
    'action': 'BUY',           # or 'SELL'
    'asset_pair': 'BTCUSD',    # or 'BTC-USD', 'BTC/USD'
    'suggested_amount': 5000.0, # USD notional
    'entry_price': 50000.0,
    'timestamp': '2024-01-01T10:00:00'
}

result = platform.execute_trade(decision)

if result['success']:
    print(f"Order ID: {result['order_id']}")
    print(f"Execution Price: ${result['execution_price']:.2f}")
    print(f"Slippage: {result['slippage_pct']:.3f}%")
```

### Portfolio Breakdown

```python
portfolio = platform.get_portfolio_breakdown()

print(f"Total Value: ${portfolio['total_value_usd']:.2f}")
print(f"Futures Balance: ${portfolio['futures_value_usd']:.2f}")
print(f"Unrealized P&L: ${portfolio['unrealized_pnl']:.2f}")

# View positions
for position in portfolio['futures_positions']:
    print(f"{position['product_id']}: {position['contracts']:.4f} contracts")
    print(f"  Entry: ${position['entry_price']:.2f}")
    print(f"  Current: ${position['current_price']:.2f}")
    print(f"  P&L: ${position['unrealized_pnl']:.2f}")
```

### Account Info

```python
account_info = platform.get_account_info()

print(f"Platform: {account_info['platform']}")
print(f"Status: {account_info['status']}")
print(f"Max Leverage: {account_info['max_leverage']}x")
```

## Backtesting Workflows

### Single Backtest Run

```python
from finance_feedback_engine.trading_platforms import MockTradingPlatform
from datetime import datetime

# Initialize
platform = MockTradingPlatform(
    initial_balance={'FUTURES_USD': 25000.0, 'SPOT_USD': 5000.0}
)

# Simulate trading decisions over time
decisions = [
    {
        'id': 'backtest-001',
        'action': 'BUY',
        'asset_pair': 'BTCUSD',
        'suggested_amount': 5000.0,
        'entry_price': 45000.0,
        'timestamp': '2024-01-01T10:00:00'
    },
    {
        'id': 'backtest-002',
        'action': 'BUY',
        'asset_pair': 'ETHUSD',
        'suggested_amount': 3000.0,
        'entry_price': 2500.0,
        'timestamp': '2024-01-01T12:00:00'
    }
]

# Execute trades
for decision in decisions:
    result = platform.execute_trade(decision)
    print(f"{decision['id']}: {result['success']}")

# Simulate price changes
platform.update_position_prices({
    'BTC-USD': 48000.0,  # +6.67%
    'ETH-USD': 2700.0    # +8%
})

# Check results
portfolio = platform.get_portfolio_breakdown()
print(f"Unrealized P&L: ${portfolio['unrealized_pnl']:.2f}")

# View trade history
history = platform.get_trade_history()
for trade in history:
    print(f"{trade['timestamp']}: {trade['action']} {trade['asset_pair']}")
    print(f"  Price: ${trade['execution_price']:.2f}")
```

### Multiple Backtest Runs

```python
results = []

for run in range(10):
    # Reset platform for new run
    platform.reset({
        'FUTURES_USD': 20000.0,
        'SPOT_USD': 5000.0,
        'SPOT_USDC': 3000.0
    })
    
    # Run your backtest logic
    # ...
    
    # Collect results
    final_portfolio = platform.get_portfolio_breakdown()
    results.append({
        'run': run,
        'final_value': final_portfolio['total_value_usd'],
        'unrealized_pnl': final_portfolio['unrealized_pnl']
    })

# Analyze results
avg_pnl = sum(r['unrealized_pnl'] for r in results) / len(results)
print(f"Average P&L: ${avg_pnl:.2f}")
```

## Agent Integration

### TradingLoopAgent with MockPlatform

```python
from finance_feedback_engine.agent import TradingAgentOrchestrator
from finance_feedback_engine.trading_platforms import MockTradingPlatform

# Create mock platform
platform = MockTradingPlatform(
    initial_balance={'FUTURES_USD': 50000.0}
)

# In your config.yaml, set:
# trading_platform: mock

# Agent will automatically use MockPlatform
# No API calls, perfect for testing agent logic
```

### Kill-Switch Scenario Testing

```python
from datetime import datetime
platform = MockTradingPlatform(
    initial_balance={'FUTURES_USD': 10000.0}
)

# Open position
decision = {
    'id': 'test-001',
    'action': 'BUY',
    'asset_pair': 'BTCUSD',
    'suggested_amount': 5000.0,
    'entry_price': 50000.0,
    'timestamp': datetime.utcnow().isoformat()
}
platform.execute_trade(decision)

# Simulate market crash
platform.update_position_prices({'BTC-USD': 42500.0})  # -15%

# Check if kill-switch should trigger
portfolio = platform.get_portfolio_breakdown()
loss_pct = (portfolio['unrealized_pnl'] / 10000.0) * 100

if loss_pct < -10:  # Stop-loss threshold
    print(f"Kill-switch triggered! Loss: {loss_pct:.2f}%")
```

## Advanced Features

### Position Price Updates

```python
# Update positions with current market prices
platform.update_position_prices({
    'BTC-USD': 55000.0,
    'ETH-USD': 2800.0,
    'SOL-USD': 120.0
})

# Positions now reflect updated prices and P&L
```

### Trade History Analysis

```python
history = platform.get_trade_history()

# Calculate metrics
total_trades = len(history)
buy_trades = sum(1 for t in history if t['action'] == 'BUY')
sell_trades = sum(1 for t in history if t['action'] == 'SELL')

print(f"Total trades: {total_trades}")
print(f"Buy/Sell ratio: {buy_trades}/{sell_trades}")

# Analyze slippage
avg_slippage = sum(t['slippage_pct'] for t in history) / len(history)
print(f"Average slippage: {avg_slippage:.3f}%")
```

### Position Tracking

```python
positions = platform.get_positions()

for asset_pair, position in positions.items():
    print(f"\n{asset_pair}:")
    print(f"  Contracts: {position['contracts']:.4f}")
    print(f"  Entry Price: ${position['entry_price']:.2f}")
    print(f"  Side: {position['side']}")
    print(f"  Unrealized P&L: ${position['unrealized_pnl']:.2f}")
```

## Configuration in YAML

```yaml
# config/config.yaml or config/config.backtest.yaml

trading_platform: mock

# Optional: Configure initial balance in code
# The platform accepts initial_balance in constructor
```

## Comparison with Real Platforms

| Feature | MockPlatform | CoinbasePlatform |
|---------|-------------|------------------|
| API Calls | ❌ None | ✅ Real |
| State Tracking | ✅ Internal | ✅ Exchange |
| Slippage | ✅ Simulated | ✅ Real |
| Fees | ✅ Simulated (0.06%) | ✅ Real |
| Position Mgmt | ✅ Yes | ✅ Yes |
| Portfolio Breakdown | ✅ Same Format | ✅ Real Data |
| Speed | ⚡ Instant | 🐢 Network Latency |
| Cost | 💰 Free | 💰 Trading Fees |

## Best Practices

1. **Use for Development**: Test agent logic without API costs
2. **Backtest First**: Train AI on historical data before live trading
3. **Reset Between Runs**: Call `platform.reset()` for clean state
4. **Update Prices**: Use `update_position_prices()` for realistic P&L
5. **Check Trade History**: Verify all trades executed correctly
6. **Monitor Slippage**: Adjust `slippage_config` for realism

## Troubleshooting

### "Insufficient balance" errors

```python
# Check current balance
balance = platform.get_balance()
print(f"Available: ${balance['FUTURES_USD']:.2f}")

# Ensure suggested_amount + fees <= balance
```

### "No position to sell" errors

```python
# Check existing positions first
positions = platform.get_positions()
if 'BTC-USD' not in positions:
    print("No BTC position to sell")
```

### Rounding issues in contracts

```python
# MockPlatform tracks contracts, not notional
# Small rounding differences are normal due to:
# - Execution price slippage
# - Fee calculations
# - Contract multiplier (0.1 for Coinbase)

# Solution: Use position tracking
positions = platform.get_positions()
contracts_to_close = positions['BTC-USD']['contracts']
```

## Examples

See comprehensive test suite for more examples:
- `tests/trading_platforms/test_mock_platform.py` - Unit tests
- `tests/trading_platforms/test_mock_platform_integration.py` - Integration tests

## Support

For issues or questions:
1. Check test files for usage patterns
2. Review this guide
3. Consult project documentation in `docs/`
