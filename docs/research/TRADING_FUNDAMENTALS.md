# Trading Fundamentals: Long/Short Positions & Risk Management

This document explains the core trading concepts implemented in the Finance Feedback Engine's decision-making system.

## Table of Contents
- [Long vs Short Positions](#long-vs-short-positions)
- [Position Sizing](#position-sizing)
- [Profit & Loss Calculation](#profit--loss-calculation)
- [Risk Management Principles](#risk-management-principles)
- [Code Examples](#code-examples)

---

## Long vs Short Positions

### Long Positions (Bullish Strategy)

A **LONG position** is opened when you believe an asset's price will **RISE**.

**Mechanics:**
- **Enter:** BUY action to open the position
- **Exit:** SELL action to close the position
- **Profit:** When current price > entry price
- **Loss:** When current price < entry price

**P&L Formula:**
```
P&L = (Exit Price - Entry Price) × Position Size
P&L % = ((Current Price - Entry Price) / Entry Price) × 100
```

**Example:**
```
Entry: BUY 0.1 BTC at $50,000
Exit: SELL 0.1 BTC at $55,000
P&L: ($55,000 - $50,000) × 0.1 = $500 profit (+10%)
```

### Short Positions (Bearish Strategy)

A **SHORT position** is opened when you believe an asset's price will **FALL**.

**Mechanics:**
- **Enter:** SELL action to open the short position (borrowing asset)
- **Exit:** BUY action to close/cover the position
- **Profit:** When current price < entry price
- **Loss:** When current price > entry price

**P&L Formula:**
```
P&L = (Entry Price - Exit Price) × Position Size
P&L % = ((Entry Price - Current Price) / Entry Price) × 100
```

**Example:**
```
Entry: SELL (short) 0.1 BTC at $50,000
Exit: BUY (cover) 0.1 BTC at $45,000
P&L: ($50,000 - $45,000) × 0.1 = $500 profit (+10%)
```

**⚠️ Key Difference:**
- **LONG:** Profit when price goes UP ⬆️
- **SHORT:** Profit when price goes DOWN ⬇️

---

## Position Sizing

Position sizing determines **how much capital** to allocate to a trade. Proper sizing is critical for risk management and long-term survival.

### Factors to Consider

1. **Account Balance:** Total capital available
2. **Risk Tolerance:** Percentage you're willing to lose (typically 1-2%)
3. **Stop Loss Distance:** How far price can move against you before exiting
4. **Volatility:** Higher volatility = smaller positions

### Position Sizing Formula

```
Position Size = (Account Balance × Risk %) / (Entry Price × Stop Loss %)
```

### Examples

**Conservative Approach (1% risk, 2% stop loss):**
```
Account: $10,000
Risk: 1% = $100
Asset: BTC at $50,000
Stop Loss: 2% = $1,000 per BTC

Position Size = ($10,000 × 0.01) / ($50,000 × 0.02)
             = $100 / $1,000
             = 0.1 BTC

Total Position Value: $5,000
Maximum Loss if Stop Hit: $100 (1% of account)
```

**Aggressive Approach (2% risk, 5% stop loss):**
```
Account: $10,000
Risk: 2% = $200
Asset: BTC at $50,000
Stop Loss: 5% = $2,500 per BTC

Position Size = ($10,000 × 0.02) / ($50,000 × 0.05)
             = $200 / $2,500
             = 0.08 BTC

Total Position Value: $4,000
Maximum Loss if Stop Hit: $200 (2% of account)
```

### Why Position Sizing Matters

- **Prevents catastrophic losses:** Never lose entire account on one trade
- **Consistent risk:** Each trade risks same % regardless of asset price
- **Psychological benefit:** Smaller positions = less emotional stress
- **Longevity:** Stay in the game even after losing streaks

---

## Profit & Loss Calculation

### Types of P&L

1. **Unrealized P&L:** Open positions (mark-to-market, not yet locked in)
2. **Realized P&L:** Closed positions (actual profit/loss in your account)

### Long Position P&L

```python
# For LONG positions
pnl_dollars = (current_price - entry_price) × position_size
pnl_percentage = ((current_price - entry_price) / entry_price) × 100
```

**Example Scenarios:**
```
Entry: $50,000 | Position: 0.1 BTC

Price at $55,000 → +$500 (+10%) ✅ PROFIT
Price at $50,000 → $0 (0%) ➖ BREAK-EVEN
Price at $45,000 → -$500 (-10%) ❌ LOSS
```

### Short Position P&L

```python
# For SHORT positions
pnl_dollars = (entry_price - current_price) × position_size
pnl_percentage = ((entry_price - current_price) / entry_price) × 100
```

**Example Scenarios:**
```
Entry: $50,000 | Position: 0.1 BTC (short)

Price at $45,000 → +$500 (+10%) ✅ PROFIT
Price at $50,000 → $0 (0%) ➖ BREAK-EVEN
Price at $55,000 → -$500 (-10%) ❌ LOSS
```

### Quick Comparison

| Price Move | Long P&L | Short P&L |
|------------|----------|-----------|
| +10% UP    | +10% ✅  | -10% ❌   |
| 0% FLAT    | 0% ➖    | 0% ➖     |
| -10% DOWN  | -10% ❌  | +10% ✅   |

---

## Risk Management Principles

### 1. Always Use Stop Losses
- Define exit point **before** entering trade
- Limits maximum loss per trade
- Removes emotion from decision

### 2. Risk 1-2% Per Trade
- Standard institutional approach
- Allows for 50+ consecutive losses before account wipeout
- Enables recovery from drawdowns

### 3. Position Sizing is Non-Negotiable
- Calculate before every trade
- Adjust for volatility
- Smaller positions in uncertain conditions

### 4. Diversification
- Don't put all capital in one asset
- Spread across different markets/strategies
- Reduces correlation risk

### 5. Never Risk More Than You Can Afford to Lose
- Only trade with risk capital
- Don't use rent/bill money
- Emotional stability = better decisions

---

## Code Examples

### Using the DecisionEngine

```python
from finance_feedback_engine.decision_engine.engine import DecisionEngine

# Initialize engine
config = {
    'ai_provider': 'local',
    'model_name': 'default',
    'decision_threshold': 0.7
}
engine = DecisionEngine(config)

# Calculate position size
position_size = engine.calculate_position_size(
    account_balance=10000.00,    # $10,000 account
    risk_percentage=1.0,          # Risk 1%
    entry_price=50000.00,         # BTC at $50,000
    stop_loss_fraction=0.02      # 2% stop loss (as decimal)
)
# Result: 0.1 BTC

# Calculate P&L for long position
long_pnl = engine.calculate_pnl(
    entry_price=50000.00,
    current_price=55000.00,
    position_size=0.1,
    position_type='LONG',
    unrealized=True
)
# Result: {'pnl_dollars': 500.0, 'pnl_percentage': 10.0, 'unrealized': True}

# Calculate P&L for short position
short_pnl = engine.calculate_pnl(
    entry_price=50000.00,
    current_price=45000.00,
    position_size=0.1,
    position_type='SHORT',
    unrealized=True
)
# Result: {'pnl_dollars': 500.0, 'pnl_percentage': 10.0, 'unrealized': True}
```

### Running the Example

```bash
# See complete demonstration of concepts
python examples/position_sizing_example.py
```

### CLI Integration

When generating decisions, the engine automatically calculates recommended position sizes:

```bash
# Analyze an asset
python main.py analyze BTCUSD

# Output includes:
# - Position type (LONG/SHORT based on BUY/SELL)
# - Entry price
# - Recommended position size
# - Risk percentage (default 1%)
# - Stop loss percentage (default 2%)
```

---

## Decision Object Schema

Generated decisions include these position-related fields:

```json
{
  "action": "BUY|SELL|HOLD",
  "position_type": "LONG|SHORT|null",
  "entry_price": 50000.00,
  "recommended_position_size": 0.1,
  "risk_percentage": 1.0,
  "stop_loss_fraction": 0.02,
  "confidence": 75,
  "reasoning": "..."
}
```

---

## Resources & Further Reading

- **Position Sizing:** "Trade Your Way to Financial Freedom" by Van K. Tharp
- **Risk Management:** "The New Trading for a Living" by Dr. Alexander Elder
- **Short Selling:** "The Art of Short Selling" by Kathryn F. Staley

---

## Summary

**Remember:**
1. **LONG** = Buy low, sell high (profit from price increases)
2. **SHORT** = Sell high, buy low (profit from price decreases)
3. **Position Sizing** = Calculate every trade to limit risk
4. **Stop Losses** = Non-negotiable risk management tool
5. **1-2% Risk Rule** = Path to long-term survival and success

The Finance Feedback Engine implements these principles automatically in its decision-making process, providing position sizing recommendations and tracking P&L for both long and short strategies.
