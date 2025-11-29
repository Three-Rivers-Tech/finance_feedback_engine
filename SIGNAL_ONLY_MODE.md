# Signal-Only Mode Implementation

## Overview

The Finance Feedback Engine now includes a **signal-only mode** that gracefully handles scenarios where portfolio or balance data is unavailable. Instead of failing or providing incorrect position sizing, the engine provides trading signals (action, confidence, reasoning) without position sizing recommendations.

## Key Features

### 1. **Smart Detection**

The engine automatically detects when portfolio/balance data is unavailable or invalid:

- Empty balance dictionary (`{}`)
- Zero balance (all values = 0)
- None/null balance
- Invalid balance data structure

### 2. **Graceful Fallback**

When balance is unavailable, the decision includes:

✅ **Provided:**
- Trading action (BUY/SELL/HOLD)
- Confidence score (0-100%)
- Reasoning and analysis
- Market data analysis
- Entry price

❌ **Not Provided (set to null):**
- `recommended_position_size`
- `stop_loss_fraction`
- `risk_percentage`

### 3. **Clear Indication**

The decision object includes a `signal_only` flag:
```json
{
  "action": "BUY",
  "confidence": 75,
  "reasoning": "Strong bullish momentum with healthy RSI",
  "signal_only": true,
  "recommended_position_size": null,
  "stop_loss_percentage": null,
  "risk_percentage": null
}
```

### 4. **User-Friendly CLI**

The CLI displays a clear warning when in signal-only mode:

```
⚠ Signal-Only Mode: Portfolio data unavailable, no position sizing provided
```

## Implementation Details

### Logic Gate in `DecisionEngine._create_decision()`

```python
# Check if balance data is available and valid
has_valid_balance = (
    balance and 
    isinstance(balance, dict) and 
    len(balance) > 0 and 
    sum(balance.values()) > 0
)

# Calculate position sizing only if balance is available
if has_valid_balance:
    # Normal mode: calculate position sizing
    recommended_position_size = self.calculate_position_size(...)
    stop_loss_percentage = 2.0
    risk_percentage = 1.0
    signal_only = False
else:
    # Signal-only mode: no position sizing
    recommended_position_size = None
    stop_loss_percentage = None
    risk_percentage = None
    signal_only = True
```

## Use Cases

### 1. **Testing & Development**
- Test trading strategies without risking capital
- Validate AI decisions before connecting real accounts
- Learn platform behavior with mock data

### 2. **Platform Failures**
- Continue operating when trading platform APIs are down
- Graceful degradation when balance endpoint fails
- Maintain signal generation even without portfolio access

### 3. **Paper Trading**
- Generate trading signals for manual execution
- Learn market patterns without automated position sizing
- Educational use for understanding AI recommendations

### 4. **Multi-Platform Scenarios**
- Some platforms may not support balance queries
- Async portfolio updates may not be available
- Partial data availability from different sources

## Testing

Run the test suite to verify signal-only mode:

```bash
# Unit test for signal-only logic
python test_signal_only_mode.py

# Integration demo with CLI
bash demo_signal_only.sh
```

## Configuration

No additional configuration required. The feature automatically activates when:
- Trading platform returns empty balance
- Platform doesn't support `get_balance()` properly
- Network issues prevent balance retrieval
- Mock platform is used (typically returns empty balance)

## Benefits

1. **Robustness**: System continues working even when portfolio data unavailable
2. **Clarity**: Clear indication when position sizing is not provided
3. **Safety**: Prevents incorrect position sizing based on bad/missing data
4. **Flexibility**: Supports both full trading and signal-only workflows
5. **User Experience**: Transparent operation with clear warnings

## Technical Notes

### Decision Object Schema

The decision object always includes the `signal_only` field:
- `signal_only: false` → Position sizing calculated (normal mode)
- `signal_only: true` → Position sizing unavailable (signal-only mode)

### Backward Compatibility

Existing code that expects position sizing fields should check:
```python
if decision.get('signal_only'):
    # Signal-only mode: no position sizing
    print("Trading signal only")
else:
    # Normal mode: use position sizing
    position_size = decision['recommended_position_size']
```

## Related Documentation

- [Position Sizing](POSITION_SIZING_CHANGES.md)
- [Trading Fundamentals](TRADING_FUNDAMENTALS.md)
- [Copilot Instructions](.github/copilot-instructions.md)

## Future Enhancements

Potential improvements for signal-only mode:

1. **Manual Position Entry**: Allow users to specify position size manually when in signal-only mode
2. **Risk Parameters**: Provide suggested risk parameters even without balance data
3. **Historical Balance**: Use cached/historical balance data as fallback
4. **Confidence Adjustment**: Reduce confidence score when operating in signal-only mode
5. **Multi-Tier Fallback**: Progressive degradation with partial data availability

---

**Status**: ✅ Implemented and tested (November 2025)
