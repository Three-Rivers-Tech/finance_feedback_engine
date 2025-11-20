# Oanda Forex Trading Integration

## Overview

The Finance Feedback Engine integrates with **Oanda** to provide real-time forex trading capabilities with comprehensive portfolio tracking, margin management, and automated trade execution.

## Features

### ✅ Real-time Portfolio Tracking
- **Open Positions**: View all long/short positions across currency pairs
- **Unrealized P&L**: Track profit/loss for each position
- **Margin Management**: Monitor margin used, available margin, and leverage
- **Currency Exposure**: Breakdown of net exposure by currency
- **NAV Tracking**: Real-time Net Asset Value calculation

### ✅ Trade Execution
- **Market Orders**: Execute BUY/SELL orders with automatic position sizing
- **Stop Loss**: Automatic stop loss placement based on risk percentage
- **Position Fill**: FOK (Fill or Kill) orders for immediate execution
- **Order Tracking**: Complete order history with timestamps and prices

### ✅ Account Management
- **Multi-Currency**: Support for all major, cross, and exotic forex pairs
- **Practice/Live**: Seamless switching between practice and live environments
- **Balance Tracking**: Real-time account balance in base currency

## Setup

### 1. Install Dependencies

```bash
pip install oandapyV20
```

The library is already included in `requirements.txt`:
```
oandapyV20>=0.7.2
```

### 2. Get Oanda API Credentials

1. **Create Account**: Sign up at [Oanda](https://www.oanda.com/)
2. **Practice or Live**: Choose practice for demo trading or live for real money
3. **Generate Token**: 
   - Log into your account
   - Go to **Manage API Access**
   - Click **Generate** to create a Personal Access Token
   - Copy and save the token (shown only once!)
4. **Find Account ID**:
   - Located in account dashboard
   - Format: `001-XXX-XXXXXXX-XXX`

### 3. Configure Platform

Create `config/config.local.yaml` (gitignored):

```yaml
alpha_vantage_api_key: "YOUR_ALPHA_VANTAGE_API_KEY"

trading_platform: "oanda"

platform_credentials:
  api_key: "YOUR_OANDA_API_TOKEN"
  account_id: "001-XXX-XXXXXXX-XXX"
  environment: "practice"  # or "live"
```

Or use the example config:
```bash
cp config/examples/oanda.yaml config/config.local.yaml
# Edit config.local.yaml with your credentials
```

## Usage

### Check Account Status

```bash
python main.py status
```

**Output:**
```
Platform: oanda
Account ID: 001-XXX-XXXXXXX-XXX
Environment: practice
Currency: USD
Balance: 50,000.00 USD
NAV: 50,234.56 USD
Unrealized P&L: +234.56 USD
```

### View Portfolio Breakdown

```bash
python main.py portfolio
```

**Output:**
```
╭─────────────────────────────────────────────────╮
│           Oanda Forex Portfolio                 │
├─────────────────────────────────────────────────┤
│ Total NAV:              $50,234.56              │
│ Balance:                $50,000.00              │
│ Unrealized P&L:         +$234.56                │
│ Margin Used:            $1,250.00               │
│ Margin Available:       $48,750.00              │
│ Open Positions:         3                       │
├─────────────────────────────────────────────────┤
│                Open Positions                   │
├──────────┬─────────┬──────────┬─────────────────┤
│ Pair     │ Type    │ Units    │ Unrealized P&L  │
├──────────┼─────────┼──────────┼─────────────────┤
│ EUR_USD  │ LONG    │ 10,000   │ +$156.20        │
│ GBP_USD  │ SHORT   │ 5,000    │ +$89.34         │
│ USD_JPY  │ LONG    │ 15,000   │ -$10.98         │
╰──────────┴─────────┴──────────┴─────────────────╯
```

### Analyze Currency Pair

```bash
python main.py analyze EUR_USD
```

**AI analyzes** market data, portfolio context, and generates decision:
- Considers current EUR exposure
- Evaluates margin availability
- Calculates optimal position size
- Determines stop loss levels

### Execute Trade

```bash
python main.py execute <decision_id>
```

Executes the trade on Oanda with:
- Market order placement
- Automatic stop loss
- Position fill confirmation
- Order ID tracking

### View History

```bash
python main.py history --limit 20
python main.py history --asset EUR_USD
```

## Portfolio Breakdown Schema

The `get_portfolio_breakdown()` method returns:

```python
{
    'total_value_usd': float,      # Total NAV
    'num_assets': int,              # Number of currencies
    'base_currency': str,           # Account currency (e.g., 'USD')
    'balance': float,               # Account balance
    'unrealized_pl': float,         # Unrealized P&L
    'margin_used': float,           # Margin in use
    'margin_available': float,      # Available margin
    'nav': float,                   # Net Asset Value
    
    'positions': [                  # Open positions
        {
            'instrument': str,      # e.g., 'EUR_USD'
            'position_type': str,   # 'LONG' or 'SHORT'
            'units': float,         # Position size
            'unrealized_pl': float, # Position P&L
            'long_units': float,    # Long exposure
            'short_units': float,   # Short exposure
            'long_pl': float,       # Long P&L
            'short_pl': float       # Short P&L
        }
    ],
    
    'holdings': [                   # Currency exposures
        {
            'asset': str,           # Currency code
            'amount': float,        # Net exposure
            'value_usd': float,     # USD value
            'allocation_pct': float # % of total
        }
    ],
    
    'platform': 'oanda',
    'account_id': str,
    'environment': str              # 'practice' or 'live'
}
```

## Supported Currency Pairs

### Major Pairs
- EUR_USD, GBP_USD, USD_JPY, USD_CHF
- AUD_USD, USD_CAD, NZD_USD

### Cross Pairs
- EUR_GBP, EUR_JPY, GBP_JPY, EUR_CHF
- AUD_JPY, CAD_JPY, NZD_JPY

### Exotic Pairs
- USD_TRY, USD_ZAR, USD_MXN, USD_SGD
- EUR_TRY, GBP_TRY

**Note**: Use Oanda format with underscore (e.g., `EUR_USD` not `EURUSD`)

## AI Integration with Portfolio Context

When analyzing forex pairs, the AI receives:

1. **Current Positions**: Existing long/short positions
2. **Currency Exposure**: Net exposure by currency
3. **Margin Status**: Available margin for new trades
4. **P&L Context**: Current profitability of positions
5. **Risk Metrics**: Portfolio risk concentration

This enables **context-aware decisions**:
- Avoid over-concentration in single currency
- Balance long/short exposure
- Manage margin utilization
- Consider correlated pairs

## Trade Execution Flow

1. **Analysis Phase**:
   ```python
   decision = engine.analyze_asset('EUR_USD')
   ```
   - Fetches market data (OHLC, sentiment, macro)
   - Loads portfolio context
   - AI generates recommendation
   - Calculates position sizing

2. **Execution Phase**:
   ```python
   result = engine.execute_decision(decision['id'])
   ```
   - Creates market order on Oanda
   - Applies stop loss
   - Confirms fill
   - Updates decision record

3. **Tracking Phase**:
   - Decision saved with `executed: true`
   - Order details stored
   - Portfolio refreshed
   - P&L tracked

## Environment Switching

### Practice Environment
```yaml
platform_credentials:
  environment: "practice"
```
- Risk-free demo trading
- $100,000 virtual capital
- Real market data
- No financial risk

### Live Environment
```yaml
platform_credentials:
  environment: "live"
```
- Real money trading
- Actual account balance
- Live order execution
- ⚠️ Financial risk applies

## Error Handling

The integration handles common errors gracefully:

### Missing Library
```
ValueError: Oanda library not available. Install oandapyV20
```
**Solution**: `pip install oandapyV20`

### Authentication Error
```
Error fetching Oanda balances: 401 Unauthorized
```
**Solution**: Verify API token and account ID

### Invalid Instrument
```
Error: Instrument 'INVALID' not found
```
**Solution**: Use proper format (e.g., `EUR_USD`)

### Insufficient Margin
```
Error: Insufficient margin for order
```
**Solution**: Reduce position size or close positions

## Advanced Features

### Position Sizing
Automatic calculation using:
- **Risk Percentage**: Default 1% of account
- **Stop Loss**: Default 2% from entry
- **Formula**: `(balance × risk%) / (entry_price × stop_loss%)`

### Stop Loss Placement
- **Long Position**: Entry price × (1 - stop_loss%)
- **Short Position**: Entry price × (1 + stop_loss%)

### Margin Management
Tracks:
- Margin used by open positions
- Available margin for new trades
- Margin call risk levels

## Integration with Decision Engine

The Oanda platform integrates seamlessly with:

- ✅ **Local LLM** (Llama-3.2-3B)
- ✅ **Copilot CLI**
- ✅ **Codex CLI**
- ✅ **Qwen CLI**
- ✅ **Ensemble Mode**

All providers receive portfolio context for informed decisions.

## Best Practices

### 1. Start with Practice
Always test strategies in practice environment before live trading.

### 2. Monitor Margin
Keep margin usage below 50% to avoid margin calls.

### 3. Diversify Exposure
Avoid over-concentration in single currency or correlated pairs.

### 4. Use Stop Losses
Always set stop losses to limit downside risk.

### 5. Track Performance
Review decision history regularly to evaluate strategy.

## Example Workflow

```bash
# 1. Check account status
python main.py status

# 2. View current portfolio
python main.py portfolio

# 3. Analyze opportunity
python main.py analyze EUR_USD

# 4. Execute if confident
python main.py execute <decision_id>

# 5. Monitor results
python main.py portfolio
python main.py history --limit 5
```

## Troubleshooting

### Portfolio Not Loading
- Verify API credentials
- Check account ID format
- Ensure oandapyV20 installed

### Trade Execution Fails
- Verify sufficient margin
- Check instrument format
- Confirm practice/live environment matches intent

### Incorrect Balance
- Refresh account: `python main.py status`
- Verify correct account ID
- Check environment (practice vs live)

## API Rate Limits

Oanda enforces rate limits:
- **Practice**: 100 requests/second
- **Live**: 100 requests/second

The integration automatically handles rate limiting with exponential backoff.

## Security Best Practices

1. **Never commit** API tokens to version control
2. **Use** `config.local.yaml` (gitignored)
3. **Rotate** API tokens periodically
4. **Restrict** API token permissions if possible
5. **Monitor** account activity regularly

## Support

For issues specific to:
- **Oanda API**: [Oanda Developer Docs](https://developer.oanda.com/)
- **This Integration**: Open GitHub issue
- **Trading Strategy**: Consult with financial advisor

---

**⚠️ Trading Risk Disclaimer**: Forex trading involves substantial risk of loss. Past performance is not indicative of future results. Always consult with a qualified financial advisor before trading.
