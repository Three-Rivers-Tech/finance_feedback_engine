# Portfolio Dashboard

## Overview

The Portfolio Dashboard feature aggregates portfolio metrics from multiple trading platforms and compiles them into a unified view. This allows you to see your entire portfolio across different platforms (Coinbase, Oanda, etc.) in one place.

## Features

- **Multi-Platform Aggregation**: Combines portfolio data from all configured trading platforms
- **Comprehensive Metrics**: Shows total portfolio value, asset count, holdings, and allocations
- **Rich CLI Display**: Uses Rich library for beautiful table formatting and colors
- **Real-time Data**: Fetches live portfolio breakdowns from each platform
- **Extensible Design**: Easy to add new metrics (risk, PnL, performance, etc.) in the future

## Architecture

### Components

1. **PortfolioDashboardAggregator** (`finance_feedback_engine/dashboard/portfolio_dashboard.py`)
   - Accepts a list of platform instances
   - Calls `get_portfolio_breakdown()` on each platform
   - Aggregates totals across all platforms
   - Handles errors gracefully (warns if a platform fails)

2. **display_portfolio_dashboard()** (`finance_feedback_engine/dashboard/portfolio_dashboard.py`)
   - Renders the aggregated data using Rich library
   - Shows summary panel with total value and asset count
   - Displays per-platform breakdown with holdings table
   - Formats currency, percentages, and decimals

3. **CLI Integration** (`finance_feedback_engine/cli/main.py`)
   - New `dashboard` command for direct invocation
   - Accessible in interactive mode (`--interactive`)
   - Auto-listed in command menu

### Data Flow

```
Platform 1 (Coinbase)  ─┐
Platform 2 (Oanda)     ─┤──> PortfolioDashboardAggregator ──> display_portfolio_dashboard()
Platform N (Custom)    ─┘
```

## Usage

### CLI Command

```bash
# Direct command
python main.py dashboard

# With specific config
python main.py -c config/my-config.yaml dashboard
```

### Interactive Mode

```bash
# Start interactive mode
python main.py --interactive

# At the prompt
finance-cli> dashboard
```

### Demo Script

```bash
# Run standalone demo with mock data
python demo_dashboard.py
```

## Example Output

```
╭─────────────────────── Multi-Platform Portfolio Dashboard ───────────────────────╮
│ Total Portfolio Value: $25,000.00                                                │
│ Assets Across Platforms: 3                                                       │
╰──────────────────────────────────────────────────────────────────────────────────╯

MockPlatform - $25,000.00 (3 assets)
 Asset  Amount  Value (USD)  Allocation 
 BTC       0.5   $20,000.00      80.00% 
 ETH         2    $4,000.00      16.00% 
 USD     1,000    $1,000.00       4.00% 
```

## Platform Requirements

Each trading platform must implement the `get_portfolio_breakdown()` method to return:

```python
{
    'total_value_usd': float,       # Total portfolio value in USD
    'num_assets': int,              # Number of unique assets
    'holdings': [                   # List of holdings
        {
            'asset': str,           # Asset symbol (e.g., 'BTC')
            'amount': float,        # Amount held
            'value_usd': float,     # USD value
            'allocation_pct': float # Portfolio allocation %
        }
    ]
}
```

### Supported Platforms

- ✅ **MockPlatform**: For testing and demos
- ✅ **CoinbaseAdvancedPlatform**: Crypto futures (requires `coinbase-advanced-py`)
- ✅ **OandaPlatform**: Forex positions (requires `oandapyV20`)
- ✅ **UnifiedTradingPlatform**: Aggregates Coinbase + Oanda

### Custom Platforms

To add dashboard support to a custom platform:

```python
from finance_feedback_engine.trading_platforms import BaseTradingPlatform

class MyCustomPlatform(BaseTradingPlatform):
    # ... implement required methods ...
    
    def get_portfolio_breakdown(self) -> dict:
        """Return portfolio breakdown for dashboard."""
        # Fetch your platform's portfolio data
        holdings = self._fetch_holdings()
        
        return {
            'total_value_usd': sum(h['value_usd'] for h in holdings),
            'num_assets': len(holdings),
            'holdings': holdings
        }
```

## Future Enhancements

The dashboard is designed to be extensible. Planned features include:

- **Risk Metrics**: Add volatility, Sharpe ratio, max drawdown
- **Performance Tracking**: Show daily/weekly/monthly returns
- **Asset Deduplication**: Combine same assets across platforms
- **Global Allocation**: Show allocation across all platforms, not just per-platform
- **Filtering**: Filter by asset type, platform, or value threshold
- **Export**: Export dashboard data to JSON, CSV, or PDF
- **Historical View**: Show portfolio value over time with charts
- **Alerts**: Notify when portfolio metrics cross thresholds

## Implementation Notes

- **Error Handling**: If a platform fails to return portfolio data, a warning is displayed but aggregation continues
- **Mock Data**: The MockPlatform returns demo data for testing; actual platforms fetch live data
- **Single Platform**: Currently, the CLI initializes one platform per engine instance; future versions may support multiple platforms from config
- **Backward Compatibility**: Platforms without `get_portfolio_breakdown()` are handled gracefully (fall back to simple balance)

## Developer Guide

### Adding New Metrics

To add a new metric to the dashboard:

1. **Update Platform Method**: Add the metric to `get_portfolio_breakdown()` return dict
2. **Update Aggregator**: Handle the new metric in `PortfolioDashboardAggregator.aggregate()`
3. **Update Display**: Show the metric in `display_portfolio_dashboard()`

Example: Adding PnL

```python
# In platform
def get_portfolio_breakdown(self):
    return {
        # ... existing fields ...
        'total_pnl': 1234.56,  # New field
        'daily_pnl': 45.67
    }

# In aggregator
def aggregate(self):
    aggregated = {
        # ... existing fields ...
        'total_pnl': 0.0
    }
    for platform in self.platforms:
        breakdown = platform.get_portfolio_breakdown()
        aggregated['total_pnl'] += breakdown.get('total_pnl', 0.0)
    return aggregated

# In display
def display_portfolio_dashboard(aggregated_data):
    total_pnl = aggregated_data.get('total_pnl', 0.0)
    console.print(f"Total PnL: ${total_pnl:,.2f}")
```

### Testing

Test the dashboard with different configurations:

```bash
# Mock platform (for testing)
python main.py -c config/config.test.mock.yaml dashboard

# Coinbase platform (requires credentials)
python main.py -c config/examples/coinbase.portfolio.yaml dashboard

# Oanda platform (requires credentials)
python main.py -c config/examples/oanda.yaml dashboard

# Unified platform (Coinbase + Oanda)
python main.py -c config/config.local.yaml dashboard
```

## Related Documentation

- [PORTFOLIO_TRACKING.md](PORTFOLIO_TRACKING.md) - Platform-specific portfolio tracking
- [PLATFORM_SWITCHING.md](PLATFORM_SWITCHING.md) - Platform configuration guide
- [Trading Platforms](../finance_feedback_engine/trading_platforms/) - Platform implementations
