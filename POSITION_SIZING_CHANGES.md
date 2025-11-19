# Long/Short Position Context Enhancement

## Summary

Enhanced the Finance Feedback Engine to provide comprehensive context about long/short trading positions, position sizing, and profit/loss calculations. These fundamental trading concepts are now integrated throughout the decision-making system.

## Changes Made

### 1. Enhanced DecisionEngine (`finance_feedback_engine/decision_engine/engine.py`)

#### Added Class Documentation
- Comprehensive docstring explaining long/short fundamentals
- Position sizing principles and formulas
- P&L calculation methods for both position types
- Risk management guidelines

#### New Methods

**`calculate_position_size()`**
- Calculates appropriate position size based on risk management
- Parameters: account balance, risk %, entry price, stop loss %
- Returns: Position size in units of asset
- Formula: `(Account Balance × Risk%) / (Entry Price × Stop Loss%)`

**`calculate_pnl()`**
- Calculates profit/loss for open or closed positions
- Supports both LONG and SHORT position types
- Parameters: entry price, current price, position size, position type
- Returns: P&L in dollars and percentage, plus unrealized flag

#### Enhanced AI Prompt
- Added extensive context about long vs short positions
- Explains profit/loss mechanics for each type
- Includes position sizing principles
- Provides P&L formulas in the prompt

#### Updated Decision Object Schema
Added new fields to decisions:
- `position_type`: 'LONG', 'SHORT', or None (for HOLD)
- `recommended_position_size`: Calculated using risk management
- `entry_price`: Current market price at decision time
- `stop_loss_percentage`: Default 2%
- `risk_percentage`: Default 1%

### 2. Updated CLI Display (`finance_feedback_engine/cli/main.py`)

Enhanced the `analyze` command output to show:
- Position type (LONG/SHORT)
- Entry price
- Recommended position size
- Risk percentage
- Stop loss percentage

Example output:
```
Position Details:
  Type: LONG
  Entry Price: $50,000.00
  Recommended Size: 0.100000 units
  Risk: 1% of account
  Stop Loss: 2% from entry
```

### 3. Created Example Script (`examples/position_sizing_example.py`)

Comprehensive demonstration script showing:
- Position sizing calculations (conservative vs aggressive)
- Long position P&L scenarios
- Short position P&L scenarios
- Side-by-side comparison of long vs short
- Real-world examples with Bitcoin

Run with: `python examples/position_sizing_example.py`

### 4. Created Documentation (`TRADING_FUNDAMENTALS.md`)

Complete reference guide covering:
- Long vs short position mechanics
- Entry/exit strategies for each
- Position sizing formulas with examples
- P&L calculation methods
- Risk management principles (1-2% rule, stop losses, diversification)
- Code examples and CLI usage
- Decision object schema reference

## Key Concepts Implemented

### Long Positions (Bullish)
- **Action**: BUY to enter, SELL to exit
- **Profit**: When price rises above entry
- **Formula**: P&L = (Exit Price - Entry Price) × Size

### Short Positions (Bearish)
- **Action**: SELL to enter, BUY to cover
- **Profit**: When price falls below entry
- **Formula**: P&L = (Entry Price - Exit Price) × Size

### Position Sizing
- Based on account balance, risk tolerance, and stop loss distance
- Default: 1% risk with 2% stop loss (conservative)
- Prevents catastrophic losses
- Ensures consistent risk per trade

### Risk Management
- 1-2% risk per trade (industry standard)
- Always use stop losses
- Position sizing is non-negotiable
- Diversification across assets

## Usage Examples

### Generate a Decision
```bash
python main.py analyze BTCUSD
```

Output now includes position sizing and type information automatically.

### Run Position Sizing Demo
```bash
python examples/position_sizing_example.py
```

Shows calculations for:
- Conservative vs aggressive sizing
- Long position scenarios
- Short position scenarios
- Side-by-side comparisons

### Access Methods Programmatically
```python
from finance_feedback_engine.decision_engine.engine import DecisionEngine

engine = DecisionEngine(config)

# Calculate position size
size = engine.calculate_position_size(
    account_balance=10000,
    risk_percentage=1.0,
    entry_price=50000,
    stop_loss_percentage=2.0
)

# Calculate P&L
pnl = engine.calculate_pnl(
    entry_price=50000,
    current_price=55000,
    position_size=0.1,
    position_type='LONG'
)
```

## Benefits

1. **Educational**: Clear explanation of fundamental trading concepts
2. **Practical**: Automated position sizing calculations
3. **Risk-Aware**: Built-in risk management principles
4. **Transparent**: Shows reasoning behind recommendations
5. **Comprehensive**: Covers both bullish (long) and bearish (short) strategies

## Testing

All changes tested and verified:
- ✅ Position sizing calculations correct
- ✅ P&L formulas accurate for long/short
- ✅ CLI displays new fields properly
- ✅ Example script runs successfully
- ✅ Decision objects include new fields

## Backward Compatibility

All changes are backward compatible:
- New fields have defaults
- Existing decision files still work
- Optional position details only shown when applicable
- No breaking changes to existing APIs

## Next Steps (Future Enhancements)

Potential additions:
- Backtesting with position sizing
- Custom risk percentages per asset
- Dynamic stop loss based on volatility
- Portfolio-level risk management
- Historical P&L tracking and reporting
