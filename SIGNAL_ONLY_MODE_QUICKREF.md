# Signal-Only Mode Quick Reference

## What is Signal-Only Mode?

When portfolio/balance data is **unavailable or invalid**, the engine provides **trading signals only** (no position sizing).

## When Does It Activate?

Signal-only mode activates automatically when:
- ❌ Balance is empty `{}`
- ❌ Balance is zero (all values = 0)
- ❌ Balance is None/null
- ❌ Balance data structure is invalid

## What You Get

### ✅ Provided (Always)
- Trading action: `BUY`, `SELL`, or `HOLD`
- Confidence: `0-100%`
- Reasoning: AI analysis and explanation
- Market data: Full market analysis
- Entry price: Current market price

### ❌ Not Provided (Signal-Only Mode)
- `recommended_position_size` → `null`
- `stop_loss_percentage` → `null`
- `risk_percentage` → `null`

## How to Detect

### In Decision Object
```python
if decision.get('signal_only'):
    print("Signal-only mode: No position sizing")
else:
    print(f"Position size: {decision['recommended_position_size']}")
```

### In CLI Output
```
⚠ Signal-Only Mode: Portfolio data unavailable, no position sizing provided
```

## Example Decision (Signal-Only)

```json
{
  "action": "BUY",
  "confidence": 75,
  "reasoning": "Strong bullish momentum",
  "signal_only": true,
  "recommended_position_size": null,
  "stop_loss_percentage": null,
  "risk_percentage": null,
  "entry_price": 96200.0
}
```

## Example Decision (Normal Mode)

```json
{
  "action": "BUY",
  "confidence": 75,
  "reasoning": "Strong bullish momentum",
  "signal_only": false,
  "recommended_position_size": 0.052,
  "stop_loss_percentage": 2.0,
  "risk_percentage": 1.0,
  "entry_price": 96200.0
}
```

## Testing

```bash
# Unit tests
python test_signal_only_mode.py

# CLI demo
bash demo_signal_only.sh
```

## Common Use Cases

| Scenario | Mode | Position Sizing |
|----------|------|----------------|
| Live account with balance | Normal | ✅ Calculated |
| Mock platform (testing) | Signal-Only | ❌ None |
| Platform API down | Signal-Only | ❌ None |
| Paper trading | Signal-Only | ❌ None |
| Development/testing | Signal-Only | ❌ None |
| Production trading | Normal | ✅ Calculated |

## Benefits

1. **Robust**: Continues working even without portfolio data
2. **Safe**: Prevents incorrect sizing with bad/missing data
3. **Clear**: Transparent indication of mode via `signal_only` flag
4. **Flexible**: Supports both trading and analysis workflows

## Code Example

```python
from finance_feedback_engine.core import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(config)
decision = engine.analyze_asset('BTCUSD')

if decision['signal_only']:
    # Signal-only mode
    print(f"Signal: {decision['action']} (confidence: {decision['confidence']}%)")
    print(f"Reasoning: {decision['reasoning']}")
    print("Note: No position sizing available")
else:
    # Normal mode
    print(f"Action: {decision['action']}")
    print(f"Position Size: {decision['recommended_position_size']:.4f} units")
    print(f"Stop Loss: {decision['stop_loss_percentage']}%")
```

## See Also

- [Full Documentation](SIGNAL_ONLY_MODE.md)
- [Position Sizing](POSITION_SIZING_CHANGES.md)
- [Copilot Instructions](.github/copilot-instructions.md)
