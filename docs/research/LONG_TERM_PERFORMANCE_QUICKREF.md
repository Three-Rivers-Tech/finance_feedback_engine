# Long-Term Performance Quick Reference

## TL;DR

AI models now see **90-day portfolio performance** automatically when making decisions. No code changes required!

## What You Get

```
✓ 90-day realized P&L
✓ Long-term win rate
✓ Profit factor (wins/losses ratio)
✓ ROI percentage
✓ Performance momentum (improving/declining/stable)
✓ Sharpe ratio (risk-adjusted returns)
✓ Best/worst trades
✓ Average holding period
```

## Zero-Config Usage

```python
from finance_feedback_engine import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(config_path="config/config.yaml")
decision = engine.analyze_asset("BTCUSD")
# ✅ Long-term performance automatically included!
```

## Quick Commands

```bash
# Test the feature
python test_long_term_performance.py

# See demo
python demo_long_term_performance.py
```

## Custom Period

```python
# Use 60 days instead of 90
context = memory.generate_context(
    asset_pair="BTCUSD",
    long_term_days=60
)
```

## Query Performance Directly

```python
# Get 90-day metrics
perf = portfolio_memory.get_performance_over_period(days=90)

print(f"Total P&L: ${perf['realized_pnl']:.2f}")
print(f"Win Rate: {perf['win_rate']:.1f}%")
print(f"Momentum: {perf['recent_momentum']}")
```

## Configuration (Optional)

```yaml
# config.yaml
portfolio_memory:
  long_term_days: 120  # Use 120 days instead of default 90
```

## AI Context Example

AI sees this when making decisions:

```
LONG-TERM PERFORMANCE (90 days):
  Total Realized P&L: $1,250.50
  Win Rate: 62.2%
  Profit Factor: 2.10
  ROI: 12.5%
  Recent Momentum: improving

PERFORMANCE GUIDANCE:
✓ Long-term performance is strong.
✓ Performance momentum is IMPROVING.
```

## Returned Metrics

```python
{
    'has_data': True,
    'period_days': 90,
    'realized_pnl': float,           # Total profit/loss
    'total_trades': int,
    'win_rate': float,               # Percentage
    'profit_factor': float,          # Gross profit / gross loss
    'roi_percentage': float,
    'avg_win': float,
    'avg_loss': float,
    'best_trade': float,
    'worst_trade': float,
    'recent_momentum': str,          # 'improving'|'declining'|'stable'
    'sharpe_ratio': float|None,      # If ≥10 trades
    'average_holding_hours': float|None
}
```

## Performance Momentum

- **Improving**: Recent performance 10%+ better than early period
- **Declining**: Recent performance 10%+ worse than early period
- **Stable**: Performance relatively consistent

## Benefits

1. **Better AI decisions**: Models understand long-term strategy effectiveness
2. **Risk awareness**: AI adjusts based on historical performance
3. **Trend detection**: Recognizes improving/declining patterns
4. **Built-in tracking**: No need for external performance analytics

## Files Changed

- `finance_feedback_engine/memory/portfolio_memory.py`
  - Added: `get_performance_over_period()` method
  - Enhanced: `generate_context()` with long-term metrics

- `finance_feedback_engine/decision_engine/engine.py`
  - Enhanced: `_format_memory_context()` to include long-term data
  - Added: Performance-based guidance for AI

## Testing

```bash
# Run tests
python test_long_term_performance.py

# Expected output:
# ✅ All tests passed!
# Your AI models now have access to:
#   • 90-day realized P&L
#   • Long-term win rate
#   • Profit factor & ROI
#   • Performance momentum
#   • Risk-adjusted returns (Sharpe ratio)
```

## Disable If Needed

```python
# Disable long-term context
context = memory.generate_context(include_long_term=False)
```

---

**Full docs**: `docs/LONG_TERM_PERFORMANCE.md`
