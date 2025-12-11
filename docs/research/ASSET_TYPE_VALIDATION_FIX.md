# Asset Type Validation Fix

## Problem Summary

Repeated `Invalid asset_type 'unknown'` errors were occurring during Phase 2 premium provider escalation in the two-phase ensemble decision system. The errors appeared in training logs and indicated that the `asset_type` was not being validated or normalized before being passed to `get_premium_provider_for_asset()`.

**Error Pattern from Training Logs:**
```
ERROR - Invalid asset_type 'unknown' passed to get_premium_provider_for_asset. Expected 'crypto', 'forex', or 'stock'.
ERROR - Escalation failed: Invalid asset_type 'unknown'. Expected 'crypto', 'forex', or 'stock'. Falling back to Phase 1 result
```

## Root Cause

In `finance_feedback_engine/decision_engine/ensemble_manager.py`, the `aggregate_decisions_two_phase()` method was extracting the asset type from `market_data` **without any validation or normalization**:

```python
# OLD CODE (line 689)
asset_type = market_data.get('type', 'unknown')
primary_provider = get_premium_provider_for_asset(asset_type)
```

This meant:
- If `market_data['type']` was missing, it defaulted to `'unknown'`
- If `market_data['type']` had a variation (e.g., `'cryptocurrency'`, `'fx'`), it was passed as-is
- No validation ensured the value was in the canonical set `{'crypto', 'forex', 'stock'}`
- The invalid/unknown value would cascade to `get_premium_provider_for_asset()`, causing escalation failures

## Solution Implemented

Added **early validation and normalization** of `asset_type` at the start of `aggregate_decisions_two_phase()` (before any escalation logic):

### 1. Canonical Asset Types
Defined the canonical set of asset types expected by the system:
```python
CANONICAL_ASSET_TYPES = {'crypto', 'forex', 'stock'}
```

### 2. Normalization Mapping
Created a mapping to handle common variations:
```python
ASSET_TYPE_NORMALIZATION = {
    'cryptocurrency': 'crypto',
    'cryptocurrencies': 'crypto',
    'digital_currency': 'crypto',
    'digital': 'crypto',
    'btc': 'crypto',
    'eth': 'crypto',
    'foreign_exchange': 'forex',
    'fx': 'forex',
    'currency': 'forex',
    'currency_pair': 'forex',
    'equities': 'stock',
    'equity': 'stock',
    'shares': 'stock',
    'stocks': 'stock',
}
```

### 3. Validation and Normalization Logic
```python
# Extract raw asset_type from market_data
raw_asset_type = market_data.get('type', None)

# Normalize asset_type
if raw_asset_type is None:
    logger.warning(
        f"Asset type missing in market_data for {asset_pair}. "
        "Defaulting to 'crypto' for safe escalation."
    )
    normalized_asset_type = 'crypto'  # Safe default
elif isinstance(raw_asset_type, str):
    raw_lower = raw_asset_type.lower().strip()
    
    # Check if already canonical
    if raw_lower in CANONICAL_ASSET_TYPES:
        normalized_asset_type = raw_lower
    # Check if it's a known variation
    elif raw_lower in ASSET_TYPE_NORMALIZATION:
        normalized_asset_type = ASSET_TYPE_NORMALIZATION[raw_lower]
        logger.info(
            f"Asset type normalized: '{raw_asset_type}' -> '{normalized_asset_type}' "
            f"for {asset_pair}"
        )
    # Handle unknown/invalid asset types
    else:
        logger.error(
            f"Invalid asset_type '{raw_asset_type}' for {asset_pair}. "
            f"Expected one of {CANONICAL_ASSET_TYPES} or variations. "
            "Defaulting to 'crypto' for safe escalation."
        )
        normalized_asset_type = 'crypto'  # Safe default
else:
    logger.error(
        f"Asset type is not a string (type: {type(raw_asset_type)}) for {asset_pair}. "
        "Defaulting to 'crypto' for safe escalation."
    )
    normalized_asset_type = 'crypto'  # Safe default

# Final validation: ensure normalized type is in canonical set
if normalized_asset_type not in CANONICAL_ASSET_TYPES:
    logger.error(
        f"CRITICAL: Normalized asset_type '{normalized_asset_type}' is not canonical! "
        f"This should never happen. Aborting escalation for {asset_pair}."
    )
    raise ValueError(
        f"Asset type validation failed: '{normalized_asset_type}' is not in {CANONICAL_ASSET_TYPES}. "
        "Cannot proceed with premium escalation."
    )

logger.info(f"Asset type validated for {asset_pair}: '{normalized_asset_type}'")

# Update market_data with normalized type for downstream use
market_data = market_data.copy()  # Avoid mutating caller's dict
market_data['type'] = normalized_asset_type
```

### 4. Updated Escalation Logic
Changed the Phase 2 escalation to use the validated `normalized_asset_type`:
```python
# Use the normalized asset_type (already validated above)
asset_type = normalized_asset_type
primary_provider = get_premium_provider_for_asset(asset_type)
```

## Key Features of the Fix

1. **Early Validation**: Asset type is validated immediately upon entry to `aggregate_decisions_two_phase()`, before any provider queries or escalation decisions.

2. **Normalization Mapping**: Common variations (e.g., `'cryptocurrency'`, `'fx'`) are automatically mapped to canonical types.

3. **Explicit Logging**:
   - `logger.info()` when normalization occurs
   - `logger.warning()` when asset type is missing
   - `logger.error()` when invalid/unknown types are encountered
   - `logger.info()` after successful validation

4. **Safe Default**: Unknown or invalid asset types default to `'crypto'` (logged as error), preventing escalation failures.

5. **Final Safety Check**: A final validation ensures `normalized_asset_type` is in `CANONICAL_ASSET_TYPES` before use; raises `ValueError` if not (defensive programming).

6. **No Mutation**: Creates a copy of `market_data` before updating, avoiding side effects on caller's dict.

## Expected Behavior After Fix

- **Valid canonical type** (e.g., `'crypto'`): Passes through unchanged, logged as validated
- **Known variation** (e.g., `'cryptocurrency'`): Normalized to `'crypto'`, logged with normalization message
- **Missing type** (`None`): Defaults to `'crypto'`, logged as warning
- **Invalid/unknown type** (e.g., `'unknown'`, `'mystery'`): Defaults to `'crypto'`, logged as error
- **Non-string type**: Defaults to `'crypto'`, logged as error

**The value `'unknown'` will NEVER reach `get_premium_provider_for_asset()`** because it will be caught by the validation logic and defaulted to `'crypto'` with an error log.

## Files Modified

- `finance_feedback_engine/decision_engine/ensemble_manager.py`
  - Added asset type validation/normalization section at start of `aggregate_decisions_two_phase()`
  - Updated Phase 2 escalation to use `normalized_asset_type` instead of raw `market_data.get('type', 'unknown')`

## Testing Recommendations

1. **Unit Test**: Create test cases for `aggregate_decisions_two_phase()` with various asset type inputs:
   - `None` (missing)
   - `'unknown'` (invalid)
   - `'cryptocurrency'` (variation)
   - `'crypto'` (canonical)
   - Non-string types (e.g., `123`, `[]`)

2. **Integration Test**: Run backtesting with the fix and verify:
   - No more `'unknown'` errors in logs
   - Normalization messages appear when expected
   - Phase 2 escalation works correctly

3. **Log Analysis**: Monitor training logs for:
   - Presence of normalization messages
   - Absence of `'unknown'` errors
   - Correct provider selection based on normalized types

## Related Files

- `finance_feedback_engine/decision_engine/provider_tiers.py`: Defines `get_premium_provider_for_asset()` which expects canonical types
- `finance_feedback_engine/decision_engine/engine.py`: Calls `aggregate_decisions_two_phase()` with `market_data`
- `data/training_logs/training_log_20251208_151035.txt`: Source of error reports

## Completion Date

December 8, 2025
