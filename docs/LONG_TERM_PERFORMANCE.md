# Long-Term Portfolio Performance Integration

## Overview

The Finance Feedback Engine now automatically includes **long-term portfolio performance metrics** in AI decision-making context. This gives AI models a comprehensive view of portfolio health over an extended period (default: 90 days) rather than just recent trades.

## What's New

### Key Metrics Now Available to AI

When making trading decisions, AI models now receive:

1. **Realized P&L** (90 days) - Total profit/loss from completed trades
2. **Win Rate** - Percentage of profitable trades over the period
3. **Profit Factor** - Ratio of gross profit to gross loss
4. **ROI Percentage** - Return on investment over the period
5. **Average Win/Loss** - Mean profit from winning vs losing trades
6. **Best/Worst Trades** - Largest gains and losses in the period
7. **Performance Momentum** - Trend indicator (improving/declining/stable)
8. **Sharpe Ratio** - Risk-adjusted returns (if enough data)
9. **Average Holding Period** - Typical trade duration

### Why This Matters

**Before:** AI models only saw ~20 recent trades
- Limited historical context
- Vulnerable to recent volatility
- No long-term trend awareness

**After:** AI models see both recent trades AND 90-day performance
- Better understanding of strategy effectiveness
- Can detect performance degradation
- More informed risk management
- Performance-based decision guidance

## Architecture

### New Method: `get_performance_over_period()`

Added to `PortfolioMemoryEngine` in `finance_feedback_engine/memory/portfolio_memory.py`:

```python
def get_performance_over_period(
    self,
    days: int = 90,
    asset_pair: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate portfolio performance metrics over a specified time period.
    
    Args:
        days: Number of days to look back (default 90)
        asset_pair: Optionally filter to specific asset
    
    Returns:
        Dict with comprehensive performance metrics
    """
```

**Returns:**
```python
{
    'has_data': True,
    'period_days': 90,
    'realized_pnl': 1250.50,        # Total P&L
    'total_trades': 45,
    'win_rate': 62.2,                # Percentage
    'profit_factor': 2.1,            # Wins/losses ratio
    'roi_percentage': 12.5,          # ROI
    'avg_win': 85.30,                # Average winning trade
    'avg_loss': -40.20,              # Average losing trade
    'best_trade': 350.00,            # Largest win
    'worst_trade': -125.00,          # Largest loss
    'recent_momentum': 'improving',  # Trend direction
    'sharpe_ratio': 1.85,            # Risk-adjusted return
    'average_holding_hours': 36.5,  # Typical hold time
}
```

### Enhanced Context Generation

Updated `generate_context()` method to include long-term metrics:

```python
def generate_context(
    self,
    asset_pair: Optional[str] = None,
    max_recent: Optional[int] = None,
    include_long_term: bool = True,     # NEW
    long_term_days: int = 90            # NEW
) -> Dict[str, Any]:
```

### AI Prompt Integration

Enhanced `_format_memory_context()` in `DecisionEngine` to present long-term performance in AI prompts with:

- Formatted performance metrics
- Conditional guidance based on performance
- Warning indicators for poor performance
- Momentum indicators for trend awareness

## Usage

### Automatic Integration

**No code changes required!** Long-term performance is automatically included:

```python
from finance_feedback_engine import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(config_path="config/config.yaml")

# Long-term performance automatically included in AI context
decision = engine.analyze_asset("BTCUSD")
```

### Configuration Options

#### Option 1: YAML Configuration

Add to your `config.yaml`:

```yaml
portfolio_memory:
  max_memory_size: 1000
  learning_rate: 0.1
  context_window: 20      # Recent trades to analyze
  long_term_days: 90      # Days for long-term metrics (default: 90)
```

#### Option 2: Programmatic Control

```python
# Custom lookback period
memory_context = portfolio_memory.generate_context(
    asset_pair="BTCUSD",
    include_long_term=True,
    long_term_days=60  # Use 60 days instead of 90
)

# Disable long-term context if needed
memory_context = portfolio_memory.generate_context(
    include_long_term=False  # Only recent trades
)
```

#### Option 3: Direct Performance Queries

```python
# Get 90-day performance for all assets
perf_90 = portfolio_memory.get_performance_over_period(days=90)

# Get 30-day performance for specific asset
perf_btc = portfolio_memory.get_performance_over_period(
    days=30,
    asset_pair="BTCUSD"
)

# Access metrics
print(f"Total P&L: ${perf_90['realized_pnl']:.2f}")
print(f"Win Rate: {perf_90['win_rate']:.1f}%")
print(f"Momentum: {perf_90['recent_momentum']}")
```

## AI Prompt Example

When the AI makes a decision, it now sees:

```
============================================================
PORTFOLIO MEMORY & LEARNING CONTEXT
============================================================
Historical Trades: 156
Recent Trades Analyzed: 20

LONG-TERM PERFORMANCE (90 days):
------------------------------------------------------------
  Total Realized P&L: $1,250.50
  Total Trades: 45
  Win Rate: 62.2%
  Profit Factor: 2.10
  ROI: 12.5%

  Average Win: $85.30
  Average Loss: $-40.20
  Best Trade: $350.00
  Worst Trade: $-125.00

  Recent Momentum: improving
  Sharpe Ratio: 1.85
  Average Holding Period: 36.5 hours

Recent Performance:
  Win Rate: 65.0%
  Total P&L: $420.50
  Wins: 13, Losses: 7
  Current Streak: 3 winning trades

============================================================

PERFORMANCE GUIDANCE FOR DECISION:
✓ Long-term performance is strong. Current strategy is working well.
✓ Performance momentum is IMPROVING. Recent trades performing better.

IMPORTANT: Consider this historical performance when making
your recommendation. If recent performance is poor, consider
being more conservative.
```

## Performance Indicators

### Momentum Calculation

The system automatically calculates **performance momentum** by comparing first half vs second half of the period:

- **Improving**: Recent trades performing 10%+ better
- **Declining**: Recent trades performing 10%+ worse
- **Stable**: Performance relatively consistent

### AI Guidance Logic

The AI receives conditional warnings based on performance:

```python
# Poor Performance Warning
if total_pnl < 0 and win_rate < 45:
    "⚠ CAUTION: Long-term performance is negative. 
     Consider being more conservative."

# Strong Performance Confirmation
if total_pnl > 0 and win_rate > 60:
    "✓ Long-term performance is strong. 
     Current strategy is working well."

# Declining Momentum Warning
if momentum == 'declining':
    "⚠ Performance momentum is DECLINING. 
     Recent trades performing worse than earlier ones."
```

## Testing

Run the included test scripts:

```bash
# Test long-term performance calculation
python test_long_term_performance.py

# See demonstration of AI context
python demo_long_term_performance.py
```

**Expected Output:**
```
✅ All tests passed!

Your AI models now have access to:
  • 90-day realized P&L
  • Long-term win rate
  • Profit factor & ROI
  • Performance momentum
  • Risk-adjusted returns (Sharpe ratio)
```

## Technical Details

### Data Source

Long-term metrics are calculated from:
- **Trade outcomes** stored in `PortfolioMemoryEngine.trade_outcomes`
- Filtered by exit timestamp within the lookback period
- Optional filtering by asset pair

### Calculations

**Win Rate:**
```python
win_rate = (winning_trades / total_trades) * 100
```

**Profit Factor:**
```python
profit_factor = gross_profit / abs(gross_loss)
```

**ROI Percentage:**
```python
roi = (total_pnl / avg_position_value) * 100
```

**Sharpe Ratio** (annualized, risk-free rate = 0):
```python
sharpe = (mean_return / std_deviation) * sqrt(252)
```

**Momentum:**
```python
first_half_pnl = sum(first_half_trades)
second_half_pnl = sum(second_half_trades)

if second_half_pnl > first_half_pnl * 1.1:
    momentum = 'improving'
elif second_half_pnl < first_half_pnl * 0.9:
    momentum = 'declining'
else:
    momentum = 'stable'
```

### Performance Considerations

- **Memory efficient**: Only processes outcomes within time window
- **Fast calculation**: O(n) where n = trades in period
- **Cached**: Results stored in context dict, regenerated on each decision
- **Minimal overhead**: ~1-2ms for 100 trades

## Limitations

1. **Requires trade history**: Needs completed trades with exit data
2. **Approximate ROI**: Uses average position value (not actual capital allocation)
3. **Sharpe ratio**: Requires ≥10 trades for calculation
4. **Time-based filtering**: Only includes trades with exit timestamps

## Migration Notes

### Existing Deployments

**No breaking changes!** The feature is:
- ✅ Backward compatible
- ✅ Enabled by default
- ✅ Configurable via YAML or code
- ✅ Gracefully handles missing data

### Disabling Long-Term Metrics

If you prefer the old behavior (recent trades only):

```python
# In generate_context call
context = memory.generate_context(
    include_long_term=False
)
```

## Examples

### Example 1: Performance-Aware Trading

```python
# AI sees that 90-day performance is declining
# → Recommends more conservative position sizing

decision = engine.analyze_asset("BTCUSD")

# Decision includes:
# - Lower confidence due to poor historical performance
# - Smaller position size recommendation
# - More conservative entry/exit levels
```

### Example 2: Asset-Specific Analysis

```python
# Compare long-term performance across assets
btc_perf = memory.get_performance_over_period(
    days=90,
    asset_pair="BTCUSD"
)

eth_perf = memory.get_performance_over_period(
    days=90,
    asset_pair="ETHUSD"
)

# Make decisions based on which asset performs better
if btc_perf['win_rate'] > eth_perf['win_rate']:
    decision = engine.analyze_asset("BTCUSD")
else:
    decision = engine.analyze_asset("ETHUSD")
```

### Example 3: Custom Time Periods

```python
# Shorter term (30 days) for fast markets
context_30 = memory.generate_context(
    long_term_days=30
)

# Longer term (180 days) for conservative approach
context_180 = memory.generate_context(
    long_term_days=180
)
```

## Benefits

### For AI Models

1. **Better context**: Understands portfolio health beyond recent trades
2. **Risk awareness**: Can adjust recommendations based on historical success
3. **Trend detection**: Recognizes improving/declining performance
4. **Confidence calibration**: More accurate confidence based on track record

### For Traders

1. **Performance tracking**: Built-in 90-day performance metrics
2. **Risk management**: AI adjusts to portfolio performance
3. **Strategy validation**: See if your strategy works long-term
4. **Decision quality**: Better-informed AI recommendations

## Future Enhancements

Potential additions (not yet implemented):

- [ ] Rolling Sharpe/Sortino ratios over time
- [ ] Drawdown analysis and recovery metrics
- [ ] Correlation analysis across assets
- [ ] Market regime classification (bull/bear/sideways)
- [ ] Multi-timeframe performance (30/60/90/180 days)
- [ ] Performance attribution by provider (ensemble mode)

## See Also

- **Portfolio Memory**: `docs/PORTFOLIO_MEMORY_IMPLEMENTATION.md`
- **Trade Monitoring**: `docs/LIVE_TRADE_MONITORING.md`
- **Decision Engine**: `finance_feedback_engine/decision_engine/engine.py`
- **Test Scripts**: `test_long_term_performance.py`, `demo_long_term_performance.py`

---

**Questions?** Check the test scripts or review the implementation in:
- `finance_feedback_engine/memory/portfolio_memory.py` (line ~600)
- `finance_feedback_engine/decision_engine/engine.py` (line ~545)
