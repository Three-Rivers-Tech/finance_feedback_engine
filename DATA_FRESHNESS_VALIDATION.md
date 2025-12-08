# Data Freshness Validation — Implementation Summary

## Overview

Implemented `validate_data_freshness()` function to prevent AI trading decisions based on stale market data. The system monitors API response times and connectivity issues, automatically rejecting or warning on data older than asset-specific thresholds.

---

## Implementation Details

### Function Signature

```python
def validate_data_freshness(
    data_timestamp: str,
    asset_type: str = "crypto",
    timeframe: str = "intraday"
) -> Tuple[bool, str, str]:
```

**Parameters:**
- `data_timestamp` (str): ISO 8601 UTC timestamp (e.g., `"2024-12-08T14:30:00Z"` or `"2024-12-08T14:30:00+00:00"`)
- `asset_type` (str): Asset class — `"crypto"`, `"forex"`, or `"stocks"` (case-insensitive; default: `"crypto"`)
- `timeframe` (str): For stocks only — `"daily"` or `"intraday"` (default: `"intraday"`; ignored for crypto/forex)

**Return Value:**
```python
(is_fresh: bool, age_str: str, warning_message: str)
```
- `is_fresh`: True if data is within acceptable freshness threshold
- `age_str`: Human-readable age (e.g., "2.5 minutes", "45 seconds", "1.23 hours")
- `warning_message`: Descriptive message; empty string if data is fresh

---

## Freshness Thresholds

### Crypto & Forex

| Age | Status | Action |
|---|---|---|
| < 5 minutes | ✅ Fresh | Trade allowed; no warning |
| 5–15 minutes | ⚠️ Stale | Trade allowed; warning logged |
| > 15 minutes | ❌ Critical | Trade rejected; error logged |

**Examples:**
```python
# Fresh (2 minutes old)
is_fresh, age, msg = validate_data_freshness("2024-12-08T14:30:00Z", "crypto")
# is_fresh = True, age = "2.0 minutes", msg = ""

# Warning (7 minutes old)
is_fresh, age, msg = validate_data_freshness("2024-12-08T14:23:00Z", "crypto")
# is_fresh = True, age = "7.0 minutes", msg = "WARNING: Crypto data is 7.0 minutes old..."

# Critical (20 minutes old)
is_fresh, age, msg = validate_data_freshness("2024-12-08T14:10:00Z", "crypto")
# is_fresh = False, age = "20.0 minutes", msg = "CRITICAL: Crypto data is 20.0 minutes old..."
```

### Stocks (Intraday)

| Age | Status | Action |
|---|---|---|
| < 5 minutes | ✅ Fresh | Trade allowed; no warning |
| 5–15 minutes | ⚠️ Stale | Trade allowed; warning logged |
| > 15 minutes | ❌ Critical | Trade rejected; error logged |

### Stocks (Daily Timeframe)

| Age | Status | Action |
|---|---|---|
| < 24 hours | ✅ Fresh | Trade allowed; no warning |
| > 24 hours | ⚠️ Stale | Trade allowed; warning logged (daily data ages slower) |

**Daily Example:**
```python
# Fresh daily data (12 hours old)
is_fresh, age, msg = validate_data_freshness(
    "2024-12-07T14:30:00Z", "stocks", timeframe="daily"
)
# is_fresh = True, age = "12.00 hours", msg = ""

# Warning (26 hours old)
is_fresh, age, msg = validate_data_freshness(
    "2024-12-06T12:30:00Z", "stocks", timeframe="daily"
)
# is_fresh = True, age = "26.00 hours", msg = "WARNING: Stock daily data is 26.00 hours old..."
```

---

## Key Features

### 1. **ISO 8601 UTC Parsing**
- Handles `"Z"` suffix (UTC indicator) and `"+00:00"` offset format
- Raises `ValueError` for invalid timestamps with helpful error messages

### 2. **Human-Readable Age Formatting**
- < 1 minute: `"45.3 seconds"`
- 1–60 minutes: `"7.5 minutes"`
- ≥ 60 minutes: `"2.15 hours"`

### 3. **Defensive Defaults**
- `asset_type=None` → defaults to crypto thresholds (5/15 min)
- `timeframe=None` → defaults to intraday (5/15 min for stocks)
- Unknown asset types → crypto thresholds

### 4. **Case-Insensitive Inputs**
```python
validate_data_freshness(ts, "CRYPTO")      # ✓ Works
validate_data_freshness(ts, "crypto")      # ✓ Works
validate_data_freshness(ts, "CrYpTo")      # ✓ Works
validate_data_freshness(ts, "stocks", "DAILY")  # ✓ Works
```

### 5. **Logging Integration**
- DEBUG: Data freshness checks logged with age and status
- WARNING: Threshold warnings (age > warning threshold)
- ERROR: Critical rejections (age > error threshold)

---

## Usage Examples

### **Live Trading Pre-Check**

Guard against stale market data before sending to decision engine:

```python
from finance_feedback_engine.utils.validation import validate_data_freshness

def get_market_data_with_freshness_check(asset_pair, asset_type):
    """Fetch market data and validate freshness."""
    market_data = fetch_from_api(asset_pair)  # Your API call
    
    is_fresh, age, warning = validate_data_freshness(
        market_data["timestamp"],
        asset_type=asset_type,
        timeframe="intraday" if asset_type == "stocks" else None
    )
    
    if not is_fresh:
        logger.error(f"Rejecting stale data: {warning}")
        return None  # Skip decision
    
    if warning:
        logger.warning(warning)  # Log but continue
    
    logger.info(f"Data age: {age}")
    return market_data
```

### **Backtesting with Historical Data**

```python
def backtest_with_data_validation(historical_bars):
    """Validate historical data freshness for replay."""
    for bar in historical_bars:
        is_fresh, age, warning = validate_data_freshness(
            bar["timestamp"],
            asset_type="stocks",
            timeframe="daily"
        )
        
        if not is_fresh:
            print(f"Warning: {bar['timestamp']} data exceeds threshold. {warning}")
        
        process_bar(bar)
```

### **Integration with RiskGatekeeper**

```python
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.utils.validation import validate_data_freshness

def validate_trade_with_freshness(decision, context, market_data):
    """Multi-layer validation: freshness → risk → execution."""
    # Step 1: Check data freshness
    is_fresh, age, msg = validate_data_freshness(
        market_data["timestamp"],
        asset_type=context.get("asset_type", "crypto")
    )
    
    if not is_fresh:
        logger.error(f"Trade blocked: {msg}")
        return False, msg
    
    # Step 2: Check risk constraints
    gatekeeper = RiskGatekeeper()
    is_valid, risk_msg = gatekeeper.validate_trade(decision, context)
    
    return is_valid, risk_msg if is_valid else msg
```

---

## Test Coverage

**25 comprehensive tests** in `tests/utils/test_data_freshness.py`:

✅ **Threshold Tests** (10):
- Crypto/Forex: 5 min warning, 15 min critical
- Stock intraday: 5 min warning, 15 min critical
- Stock daily: 24 hour warning
- Edge cases: exactly at thresholds

✅ **Format Tests** (6):
- ISO 8601 with `Z` suffix
- ISO 8601 with `+00:00` offset
- Age formatting: seconds, minutes, hours

✅ **Robustness Tests** (6):
- Case-insensitive asset types & timeframes
- Unknown asset types default to crypto
- Invalid timestamps raise `ValueError`
- Defaults: `asset_type=crypto`, `timeframe=intraday`

✅ **Integration Tests** (3):
- Live trading (no timestamp override)
- Multiple asset types
- Multiple timeframes

---

## Error Handling

### **Invalid Inputs**

```python
# Empty timestamp
validate_data_freshness("", "crypto")
# Raises: ValueError: "data_timestamp must be a non-empty ISO 8601 string"

# Non-ISO format
validate_data_freshness("Dec 8 2024", "crypto")
# Raises: ValueError: "Invalid data_timestamp 'Dec 8 2024': must be ISO 8601 UTC format..."

# None
validate_data_freshness(None, "crypto")
# Raises: ValueError: "data_timestamp must be a non-empty ISO 8601 string"
```

### **Graceful Defaults**

```python
# Missing asset_type → crypto thresholds
validate_data_freshness("2024-12-08T14:30:00Z")  # ✓ Uses crypto (5/15 min)

# Missing timeframe for stocks → intraday
validate_data_freshness("2024-12-08T14:30:00Z", "stocks")  # ✓ Uses intraday (5/15 min)

# Unknown asset_type → crypto thresholds
validate_data_freshness("2024-12-08T14:30:00Z", "commodities")  # ✓ Uses crypto (5/15 min)
```

---

## Files Modified/Created

| File | Change | Lines |
|---|---|---|
| `finance_feedback_engine/utils/validation.py` | Added `validate_data_freshness()` | +130 (208 total) |
| `tests/utils/test_data_freshness.py` | Created comprehensive test suite | 252 |

---

## Integration Roadmap

### **Phase 1: Immediate** ✅
- Function implemented and tested
- Ready for integration into data providers

### **Phase 2: Data Providers**
Integrate into data fetching pipelines:
```python
# In AlphaVantageProvider.get_market_data()
market_data = fetch_data()
is_fresh, age, warning = validate_data_freshness(market_data["timestamp"], "crypto")
if not is_fresh:
    raise StaleDataError(warning)
market_data["_freshness"] = {"is_fresh": is_fresh, "age": age}
return market_data
```

### **Phase 3: DecisionEngine**
Guard AI decisions:
```python
# In DecisionEngine.query_ai_provider()
if not market_data["_freshness"]["is_fresh"]:
    logger.warning("Skipping AI decision: stale data")
    return {"action": "HOLD", "reasoning": "Stale data"}
```

### **Phase 4: Monitoring**
Dashboard alerts on data age:
```python
# In TradeMonitor
freshness = validate_data_freshness(last_tick["timestamp"], asset_type)
if freshness[2]:  # warning_message
    alert_user(f"Market data warning: {freshness[2]}")
```

---

## Performance Notes

- **Time Complexity**: O(1) — simple timestamp parsing and arithmetic
- **Memory**: Negligible — creates 2 datetime objects per call
- **Recommended**: Call once per market data fetch, not per decision

---

## Related Components

- **MarketSchedule**: Complements with open/closed market awareness (e.g., prevents trading when markets closed AND data is stale)
- **RiskGatekeeper**: Can integrate freshness check as validation step 0
- **DecisionEngine**: Guards AI prompts with fresh data requirement
- **TradeMonitor**: Logs data freshness in P&L tracking
