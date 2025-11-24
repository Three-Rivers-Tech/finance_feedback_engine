# Portfolio Tracking Feature

## Overview

The Finance Feedback Engine supports **real-time futures trading portfolio tracking** from Coinbase Advanced, enabling the AI to make context-aware trading recommendations based on your active long/short positions.

**Status: Signal-Only Mode** - Portfolio tracking is active, but trade execution is disabled. The system provides intelligent signals for perpetual futures and forex long/short positions.

**Strategy Focus**: This is a **perpetual futures long/short trading strategy** (forex support planned) - no spot holdings or position accumulation logic.

## Features

### 📊 Real Futures Trading Data
- Live futures account balance and margin from Coinbase Advanced API
- Active long/short positions with entry/current prices
- Unrealized and realized PnL tracking
- Buying power and margin requirements

### 🤖 AI Portfolio Awareness
The AI decision engine now receives:
- Your current long/short positions
- Position sizes and leverage
- Unrealized PnL on open positions
- Available buying power and margin status

This enables recommendations like:
- "You have a LONG position in BTC-PERP at $42,000 - consider closing on resistance"
- "Current SHORT in ETH shows +$150 unrealized PnL - trail stop loss"
- "Buying power at $1,200 - opportunity for new position"

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
python main.py dashboard
```

**Output:**

```text
Futures Trading Account
Account Balance: $217.70

Account Metrics
  Unrealized PnL: $17.70
  Daily Realized PnL: $10.75
  Buying Power: $123.13
  Initial Margin: $233.83

                         Active Positions (Long/Short)
┏━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Product         ┃ Side ┃ Contracts ┃     Entry ┃   Current ┃ Unrealized PnL ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ ETP-20DEC30-CDE │ LONG │         3 │ $2,920.00 │ $2,978.00 │         $12.60 │
└─────────────────┴──────┴───────────┴───────────┴───────────┴────────────────┘
```

### Get AI Signal with Futures Position Context

```bash
python main.py analyze BTCUSD
```

The AI will see:

```text
CURRENT FUTURES ACCOUNT:
------------------------
Futures Balance: $217.70
Unrealized PnL: $17.70
Daily Realized PnL: $10.75
Buying Power: $123.13
Initial Margin: $233.83

ACTIVE POSITIONS:
  ETP-20DEC30-CDE LONG: 3 contracts
    Entry: $2,920.00
    Current: $2,978.00
    Unrealized PnL: $12.60
```

**The AI uses this to provide context-aware recommendations:**

- Considers your existing long/short positions
- Suggests position sizing based on available buying power
- Factors in current margin requirements
- Advises on risk management based on unrealized PnL

### Check Account Info

```bash
python main.py status
```

Shows:

- Platform: coinbase_advanced
- Mode: signal_only (futures trading)
- Execution enabled: false
- Futures account balance and active positions

## API Reference

### CoinbaseAdvancedPlatform Methods

```python
# Get futures account balance
balances = platform.get_balance()
# Returns: {'FUTURES_USD': 217.70}

# Get detailed futures portfolio breakdown
portfolio = platform.get_portfolio_breakdown()
# Returns: {
#     'futures_positions': [
#         {
#             'product_id': 'ETP-20DEC30-CDE',
#             'side': 'LONG',
#             'contracts': 3.0,
#             'entry_price': 2920.0,
#             'current_price': 2978.0,
#             'unrealized_pnl': 12.60,
#             'daily_pnl': 5.25
#         }
#     ],
#     'futures_summary': {
#         'total_balance_usd': 217.70,
#         'unrealized_pnl': 17.70,
#         'daily_realized_pnl': 10.75,
#         'buying_power': 123.13,
#         'initial_margin': 233.83
#     },
#     'total_value_usd': 217.70,
#     'futures_value_usd': 217.70,
#     'spot_value_usd': 0.0,
#     'holdings': [],
#     'num_assets': 0
# }

# Get account info with futures portfolio
account_info = platform.get_account_info()
# Returns: {
#     'platform': 'coinbase_advanced',
#     'mode': 'signal_only',
#     'execution_enabled': False,
#     'balances': {'FUTURES_USD': 217.70},
#     'portfolio': {
#         'futures_positions': [...],
#         'futures_summary': {...},
#         'total_value_usd': 217.70
#     }
# }
```

## How It Works

### 1. Futures Portfolio Data Flow

```text
Coinbase Advanced API (Futures)
    ↓
CoinbaseAdvancedPlatform.get_portfolio_breakdown()
    ↓
FinanceFeedbackEngine.analyze_asset()
    ↓
DecisionEngine.generate_decision() [includes futures portfolio context]
    ↓
AI Provider receives futures positions and margin data in prompt
    ↓
Context-aware long/short trading signal generated
```

### 2. Decision Engine Integration

The `DecisionEngine` now accepts an optional `portfolio` parameter:

```python
decision = decision_engine.generate_decision(
    asset_pair="BTCUSD",
    market_data={...},
    balance={...},
    portfolio={...}  # NEW: Futures portfolio breakdown
)
```

### 3. AI Prompt Enhancement

The AI prompt now includes:

```text
CURRENT FUTURES ACCOUNT:
------------------------
Futures Balance: $XXX.XX
Unrealized PnL: $XX.XX
Daily Realized PnL: $XX.XX
Buying Power: $XXX.XX
Initial Margin: $XXX.XX

ACTIVE POSITIONS:
  PRODUCT LONG/SHORT: N contracts
    Entry: $X,XXX.XX
    Current: $X,XXX.XX
    Unrealized PnL: $XX.XX
```

## Limitations & Future Enhancements

### Current Limitations

- **Signal-only mode**: No automatic trade execution
- **Coinbase futures only**: Spot trading and other platforms not supported
- **Perpetual futures focus**: Strategy is long/short trading only (no position accumulation)
- **Limited to active positions**: Only shows currently open long/short positions

### Planned Enhancements

1. **Forex Integration**
   - Oanda API for forex long/short positions
   - Multi-platform futures/forex aggregation
   - Unified position tracking

2. **Advanced Risk Management**
   - Position size recommendations based on margin
   - Stop-loss suggestions for open positions
   - Leverage and margin utilization alerts

3. **Performance Analytics**
   - Win rate and profit factor by position type
   - Risk-adjusted returns for long/short strategies
   - Correlation analysis between positions
   - Maximum drawdown tracking

4. **Position History**
   - Historical long/short position tracking
   - Trade journal for closed positions
   - Performance attribution by instrument

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

### "No futures positions found"

- Check Coinbase account has active perpetual futures positions
- Verify using correct API environment (sandbox vs production)
- Check API key permissions include futures read access
- Ensure you have opened futures positions (this is not for spot balances)

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

**Ready to start?** Run `python main.py dashboard` to see your live holdings! 🚀
