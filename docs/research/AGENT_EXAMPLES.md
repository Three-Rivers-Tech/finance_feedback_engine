# AI Agent Examples - Coinbase Balance Tracking

This document shows concrete examples of how AI agents can now work with your Coinbase balances thanks to the updated `.github/copilot-instructions.md`.

## Example 1: View Your Portfolio

The agent knows about the `portfolio` command and can run it:

```bash
python main.py portfolio
```

**What the agent sees:**
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

## Example 2: Context-Aware Trading Decisions

When you ask the agent to analyze BTC, it now knows your current position:

```bash
python main.py analyze BTCUSD
```

**Before portfolio tracking:**
```json
{
  "action": "BUY",
  "confidence": 75,
  "reasoning": "Bitcoin showing bullish signals with RSI at 45..."
}
```

**After portfolio tracking (agent sees you already hold 20% BTC):**
```json
{
  "action": "HOLD",
  "confidence": 65,
  "reasoning": "Bitcoin showing bullish signals, BUT you already hold 20.25% of portfolio in BTC. Current allocation is appropriate given risk tolerance. Consider rebalancing if BTC exceeds 25% allocation..."
}
```

## Example 3: Agent Writing Code to Check Balances

If you ask: *"Write code to check if I have enough USD to buy $500 of BTC"*

The agent knows to use:

```python
from finance_feedback_engine.core import FinanceFeedbackEngine
import yaml

# Load config
with open('config/config.local.yaml') as f:
    config = yaml.safe_load(f)

# Initialize engine
engine = FinanceFeedbackEngine(config)

# Get portfolio breakdown
portfolio = engine.trading_platform.get_portfolio_breakdown()

# Find USD balance
usd_holding = next(
    (h for h in portfolio['holdings'] if h['asset'] == 'USD'),
    None
)

if usd_holding:
    usd_balance = usd_holding['amount']
    if usd_balance >= 500:
        print(f"✓ You have ${usd_balance:,.2f} USD available")
        print(f"  You can buy $500 of BTC")
    else:
        print(f"✗ Insufficient funds: ${usd_balance:,.2f} USD available")
        print(f"  Need $500.00")
else:
    print("No USD holdings found")
```

## Example 4: Agent Implementing a Rebalancing Check

If you ask: *"Alert me if any asset exceeds 30% of my portfolio"*

The agent knows the portfolio structure and can write:

```python
from finance_feedback_engine.core import FinanceFeedbackEngine
import yaml

with open('config/config.local.yaml') as f:
    config = yaml.safe_load(f)

engine = FinanceFeedbackEngine(config)
portfolio = engine.trading_platform.get_portfolio_breakdown()

ALERT_THRESHOLD = 30.0  # 30%

print(f"Portfolio Concentration Check (>{ALERT_THRESHOLD}% threshold)\n")

alerts = []
for holding in portfolio['holdings']:
    asset = holding['asset']
    allocation = holding['allocation_pct']

    if allocation > ALERT_THRESHOLD:
        alerts.append({
            'asset': asset,
            'allocation': allocation,
            'value': holding['value_usd']
        })

if alerts:
    print("⚠️  CONCENTRATION ALERTS:")
    for alert in alerts:
        print(f"  • {alert['asset']}: {alert['allocation']:.2f}% "
              f"(${alert['value']:,.2f})")
    print(f"\nConsider rebalancing to maintain diversification")
else:
    print("✓ Portfolio is well-diversified")
    print(f"  All positions under {ALERT_THRESHOLD}% allocation")
```

## Example 5: Agent Analyzing Your Actual Holdings

If you ask: *"What's my crypto exposure vs fiat?"*

The agent can analyze your portfolio:

```python
portfolio = engine.trading_platform.get_portfolio_breakdown()

crypto_value = 0
fiat_value = 0

for holding in portfolio['holdings']:
    asset = holding['asset']
    value = holding['value_usd']

    if asset in ['USD', 'USDC', 'USDT']:
        fiat_value += value
    else:
        crypto_value += value

total = portfolio['total_value_usd']

print(f"Asset Allocation Analysis\n")
print(f"Total Portfolio: ${total:,.2f}\n")
print(f"Crypto Exposure:  ${crypto_value:,.2f} ({crypto_value/total*100:.1f}%)")
print(f"Fiat Exposure:    ${fiat_value:,.2f} ({fiat_value/total*100:.1f}%)")
```

**Output:**
```
Asset Allocation Analysis

Total Portfolio: $12,345.67

Crypto Exposure:  $3,845.67 (31.1%)
Fiat Exposure:    $8,500.00 (68.9%)
```

## Example 6: Agent Modifying the Platform Code

If you ask: *"Add a method to get only crypto holdings"*

The agent knows to edit `finance_feedback_engine/trading_platforms/coinbase_platform.py`:

```python
def get_crypto_holdings(self) -> List[Dict[str, Any]]:
    """
    Get only cryptocurrency holdings (excludes fiat like USD, USDC).

    Returns:
        List of crypto holdings with amount, value, allocation
    """
    portfolio = self.get_portfolio_breakdown()

    FIAT_CURRENCIES = {'USD', 'USDC', 'USDT', 'DAI', 'EUR', 'GBP'}

    return [
        h for h in portfolio['holdings']
        if h['asset'] not in FIAT_CURRENCIES
    ]
```

## What the Agent Now Knows

From `.github/copilot-instructions.md`, the agent understands:

1. ✅ **Portfolio Method Signature**
   ```python
   def get_portfolio_breakdown(self) -> Dict[str, Any]:
       return {
           'total_value_usd': float,
           'num_assets': int,
           'holdings': [
               {
                   'asset': str,
                   'amount': float,
                   'value_usd': float,
                   'allocation_pct': float
               }
           ]
       }
   ```

2. ✅ **When Portfolio Context is Available**
   - AI receives portfolio in decision prompts
   - Enables context-aware recommendations
   - Only available for platforms implementing `get_portfolio_breakdown()`

3. ✅ **CLI Commands**
   - `python main.py dashboard` - unified comprehensive dashboard
   - `python main.py balance` - simple balances
   - Both work with Coinbase Advanced platform

4. ✅ **Platform Support**
   - `CoinbaseAdvancedPlatform` implements portfolio tracking
   - Uses Coinbase Advanced Trade API
   - Read-only access (signal-only mode)

## Try It Yourself

Ask the agent questions like:

- *"Show me my current Coinbase balances"*
- *"What percentage of my portfolio is in Bitcoin?"*
- *"Write code to check if ETH is over 15% of my portfolio"*
- *"Generate a trading decision for BTCUSD considering my current holdings"*
- *"Create a function to find my largest crypto position"*

The agent will know exactly how to access your portfolio data!
