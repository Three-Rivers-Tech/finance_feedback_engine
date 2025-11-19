# Portfolio Tracking Feature

## Overview

The Finance Feedback Engine now supports **real portfolio tracking** from Coinbase Advanced, enabling the AI to make context-aware trading recommendations based on your actual holdings.

**Status: Signal-Only Mode** - Portfolio tracking is active, but trade execution is disabled. The system provides intelligent signals while learning from your real portfolio.

## Features

### 📊 Real Portfolio Data
- Live account balances from Coinbase Advanced API
- Holdings breakdown with USD valuations
- Allocation percentages across all assets
- Total portfolio value calculation

### 🤖 AI Portfolio Awareness
The AI decision engine now receives:
- Your current holdings and amounts
- USD value of each position
- Allocation percentages
- Whether you already hold the asset being analyzed

This enables recommendations like:
- "You already hold 15% in BTC - consider rebalancing" 
- "Portfolio is 80% USD - opportunity to deploy capital"
- "ETH allocation is only 5% - bullish signals suggest increasing"

### 🔒 Safety First
- **No execution enabled** - signals only
- Read-only API access to portfolio data
- Learning mode for AI training
- Manual execution of trades (you remain in control)

## Setup

### 1. Install Dependencies

```bash
pip install coinbase-advanced-py
```

### 2. Get Coinbase API Credentials

1. Go to [Coinbase Settings → API](https://www.coinbase.com/settings/api)
2. Create a new API key with **View permissions only**
3. Save your API Key and API Secret securely
4. Enable **Advanced Trade API** access

### 3. Configure

Copy the example configuration:

```bash
cp config/examples/coinbase.portfolio.yaml config/config.local.yaml
```

Edit `config/config.local.yaml`:

```yaml
trading_platform: "coinbase_advanced"

platform_credentials:
  api_key: "YOUR_COINBASE_API_KEY"
  api_secret: "YOUR_COINBASE_API_SECRET"
  use_sandbox: false  # true for testing, false for production
```

### 4. Test Connection

```bash
# View your portfolio
python main.py -c config/config.local.yaml portfolio

# Check balances
python main.py -c config/config.local.yaml balance
```

## Usage

### View Portfolio

```bash
python main.py portfolio
```

**Output:**
```
Portfolio Summary
Total Value: $12,345.67
Number of Assets: 4

Portfolio Holdings
┌────────┬──────────────┬──────────────┬────────────┐
│ Asset  │ Amount       │ Value (USD)  │ Allocation │
├────────┼──────────────┼──────────────┼────────────┤
│ USD    │ $8,500.00    │ $8,500.00    │ 68.85%     │
│ BTC    │ 0.125000     │ $2,500.00    │ 20.25%     │
│ ETH    │ 2.500000     │ $1,250.00    │ 10.12%     │
│ SOL    │ 5.000000     │ $95.67       │ 0.77%      │
└────────┴──────────────┴──────────────┴────────────┘
```

### Get AI Signal with Portfolio Context

```bash
python main.py analyze BTCUSD
```

The AI will see:
```
CURRENT PORTFOLIO:
------------------
Total Portfolio Value: $12,345.67
Number of Assets: 4

Holdings:
  USD: 8500.000000 ($8,500.00 - 68.8%)
  BTC: 0.125000 ($2,500.00 - 20.2%)
  ETH: 2.500000 ($1,250.00 - 10.1%)
  SOL: 5.000000 ($95.67 - 0.8%)

EXISTING POSITION IN BTC:
Amount: 0.125000
Current Value: $2,500.00
Allocation: 20.2%
```

**The AI uses this to provide context-aware recommendations:**
- Considers your existing exposure
- Suggests position sizing relative to portfolio
- Factors in diversification
- Advises on rebalancing opportunities

### Check Account Info

```bash
python main.py status
```

Shows:
- Platform: coinbase_advanced
- Mode: signal_only
- Execution enabled: false
- Portfolio value and asset count

## API Reference

### CoinbaseAdvancedPlatform Methods

```python
# Get simple balances
balances = platform.get_balance()
# Returns: {'USD': 8500.0, 'BTC': 0.125, 'ETH': 2.5, 'SOL': 5.0}

# Get detailed portfolio breakdown
portfolio = platform.get_portfolio_breakdown()
# Returns: {
#     'holdings': [
#         {
#             'currency': 'USD',
#             'amount': 8500.0,
#             'value_usd': 8500.0,
#             'allocation_pct': 68.85
#         },
#         ...
#     ],
#     'total_value_usd': 12345.67,
#     'num_assets': 4
# }

# Get account info with portfolio
account_info = platform.get_account_info()
# Returns: {
#     'platform': 'coinbase_advanced',
#     'mode': 'signal_only',
#     'execution_enabled': False,
#     'balances': {...},
#     'portfolio': {...}
# }
```

## How It Works

### 1. Portfolio Data Flow

```
Coinbase Advanced API 
    ↓
CoinbaseAdvancedPlatform.get_portfolio_breakdown()
    ↓
FinanceFeedbackEngine.analyze_asset()
    ↓
DecisionEngine.generate_decision() [includes portfolio context]
    ↓
AI Provider receives portfolio data in prompt
    ↓
Context-aware trading signal generated
```

### 2. Decision Engine Integration

The `DecisionEngine` now accepts an optional `portfolio` parameter:

```python
decision = decision_engine.generate_decision(
    asset_pair="BTCUSD",
    market_data={...},
    balance={...},
    portfolio={...}  # NEW: Portfolio breakdown
)
```

### 3. AI Prompt Enhancement

The AI prompt now includes:

```text
CURRENT PORTFOLIO:
------------------
Total Portfolio Value: $X,XXX.XX
Number of Assets: N

Holdings:
  ASSET: amount (value - allocation%)
  ...

EXISTING POSITION IN [ASSET]:
Amount: X.XXXXXX
Current Value: $X,XXX.XX
Allocation: XX.X%
```

## Limitations & Future Enhancements

### Current Limitations

- **Signal-only mode**: No automatic trade execution
- **Coinbase only**: Other platforms not yet supported
- **No P&L tracking**: Doesn't track entry prices/gains yet
- **No historical positions**: Only current holdings

### Planned Enhancements

1. **P&L Tracking**
   - Entry price recording
   - Realized/unrealized gains
   - Performance metrics

2. **Multi-Platform Support**
   - Oanda portfolio integration
   - Binance support
   - Multi-platform aggregation

3. **Advanced Analytics**
   - Sharpe ratio calculation
   - Risk-adjusted returns
   - Correlation analysis
   - Diversification score

4. **Position Management**
   - Historical position tracking
   - Trade journal integration
   - Performance attribution

## Security Best Practices

1. **API Key Permissions**
   - Use **view-only** permissions for portfolio tracking
   - Never share API keys in code or config files
   - Use environment variables for production

2. **Configuration Files**
   - Add `config.local.yaml` to `.gitignore`
   - Never commit real credentials
   - Use separate keys for sandbox/production

3. **Sandbox Testing**
   - Test with `use_sandbox: true` first
   - Verify portfolio data accuracy
   - Test error handling

## Troubleshooting

### "coinbase-advanced-py not installed"
```bash
pip install coinbase-advanced-py
```

### "Portfolio breakdown not supported"
- Ensure using `coinbase_advanced` platform (not legacy `coinbase`)
- Check API credentials are correct
- Verify API key has required permissions

### "No holdings found"
- Check Coinbase account actually has assets
- Verify using correct API environment (sandbox vs production)
- Check API key permissions include portfolio read access

### Connection errors
- Verify internet connection
- Check Coinbase API status
- Ensure API key is not expired
- Try sandbox mode first for testing

## Examples

See working examples in:
- `config/config.coinbase.portfolio.yaml` - Full configuration
- `examples/portfolio_tracking_example.py` - Python API usage (coming soon)
- `demo.sh` - CLI demonstration

## Support

For issues or questions:
1. Check logs with `-v` flag: `python main.py -v portfolio`
2. Review [Coinbase Advanced Trade API docs](https://docs.cloud.coinbase.com/advanced-trade-api)
3. Open an issue on GitHub

---

**Ready to start?** Run `python main.py portfolio` to see your live holdings! 🚀
