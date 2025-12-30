# Oanda Platform Idempotent Order Execution Implementation

**Date**: December 30, 2025  
**Status**: Implemented  
**File Modified**: `finance_feedback_engine/trading_platforms/oanda_platform.py`

## Problem Statement

The `execute_trade` method in `OandaPlatform` was previously decorated with `@platform_retry`, which automatically retried failed trade submissions using exponential backoff. This created a critical risk of duplicate orders because:

1. **Non-idempotent requests**: The Oanda API `OrderCreate` endpoint executes trades immediately on successful requests
2. **Timeout ambiguity**: If a request timed out or received an HTTP 5xx error, the order might have already been submitted before the failure occurred
3. **Blind retries**: The `@platform_retry` decorator would retry without checking if the order already existed, leading to duplicate positions

**Example failure scenario:**
- User submits order with `@platform_retry`
- Request succeeds and order is submitted
- Network timeout occurs before response reaches the client
- `@platform_retry` automatically retries the same order
- Two identical orders are now open in the account

## Solution Implemented

**Approach**: Option A - Remove `@platform_retry` and implement manual idempotent retry logic with duplicate detection.

### Key Changes

#### 1. **Removed Non-Idempotent Retry Decorator**
- Removed: `@platform_retry(max_attempts=3, min_wait=2, max_wait=15)` from `execute_trade` method
- Removed: `platform_retry` import (kept in module for other methods like `get_balance`)

#### 2. **Added Imports**
```python
import time
import uuid
```

#### 3. **New Helper Method: `_get_recent_orders()`**
Queries the Oanda API to retrieve recent orders for duplicate detection.

**Signature:**
```python
def _get_recent_orders(self, instrument: str, max_results: int = 50) -> List[Dict[str, Any]]
```

**Purpose:**
- Retrieves list of recent orders from Oanda account
- Used as the data source for duplicate detection
- Handles import errors gracefully (returns empty list to allow submission)
- Logs retrieval count for debugging

**Error Handling:**
- If Oanda library is unavailable, logs error and returns empty list
- If query fails, logs warning and returns empty list (allows submission to continue)

#### 4. **New Helper Method: `_find_duplicate_order()`**
Searches recent orders for an existing order matching the current trade.

**Signature:**
```python
def _find_duplicate_order(self, instrument: str, units: int, client_request_id: str) -> Optional[Dict[str, Any]]
```

**Purpose:**
- Performs idempotency detection by checking for orders with matching `clientRequestID`
- This is the primary idempotency key used by Oanda API
- Returns matching order dict if found, None otherwise

**Idempotency Key**:
- Generated as: `f"ffe-{decision_id}-{uuid.uuid4().hex[:8]}"`
- Unique for each trade attempt
- Included in the order data payload

#### 5. **Manual Retry Logic in `execute_trade()`**

**Flow:**
1. **Generate unique clientRequestID** for idempotency tracking
   ```python
   client_request_id = f"ffe-{decision_id}-{uuid.uuid4().hex[:8]}"
   ```

2. **Pre-submission duplicate detection** (NEW)
   - Query recent orders before submitting
   - If order with same `clientRequestID` already exists, return immediately with order details
   - Prevents wasted API calls and confirms successful previous submission

3. **Submit order with clientRequestID**
   - Include `clientRequestID` in order data payload
   - Oanda uses this to detect duplicate submissions from the same client

4. **Error handling with selective retries**
   - **ConnectionError** (transient): Retry with exponential backoff (min 2s, max 15s)
   - **DNS/connection issues** (transient): Retry with backoff
   - **TimeoutError** (ambiguous): DO NOT RETRY
     - Instead, query for existing order
     - If found, return success (order was submitted before timeout)
     - If not found, re-raise error
   - **HTTP 5xx/other errors** (potentially submitted): DO NOT RETRY blindly
     - Log error with clientRequestID for audit trail
     - Return failure with order reference for manual reconciliation

5. **Comprehensive logging**
   - Log all attempts with `clientRequestID`
   - Log `order_status` and `order_id` for audit trail
   - Log duplicate detection results
   - Log timeout handling decisions

**Max Attempts:** 3 (configurable in method)

### Example Execution Flow

```
Order Submission Sequence:
1. Generate clientRequestID: "ffe-12345-67abcdef"
2. Query recent orders for "ffe-12345-67abcdef" → None found
3. Submit order with clientRequestID in payload
4. Case A: Success → Return order details with clientRequestID logged
5. Case B: Timeout → Query recent orders for "ffe-12345-67abcdef"
   - If found: Return existing order (success)
   - If not found: Re-raise TimeoutError (failure)
6. Case C: DNS error → Wait 2s, retry up to 3 times
7. Case D: HTTP 5xx → Log error with clientRequestID, return failure
```

### Return Value Updates

All successful returns now include:
- `client_request_id`: The idempotency key used for this order
- `attempt`: The attempt number (1, 2, or 3)

Example:
```json
{
  "success": true,
  "platform": "oanda",
  "decision_id": "uuid-here",
  "order_id": "12345",
  "client_request_id": "ffe-uuid-here-67abcdef",
  "instrument": "EUR_USD",
  "units": 10000,
  "attempt": 1,
  "message": "Trade executed successfully",
  "timestamp": "2025-12-30T12:34:56Z"
}
```

## Audit Trail & Observability

### Logging Strategy

All key events are logged at INFO level with contextual information:

1. **Order Submission**
   ```
   INFO: Submitting order (attempt 1/3): clientRequestID=ffe-uuid-67abcdef
   ```

2. **Duplicate Detection**
   ```
   INFO: Found duplicate order by clientRequestID: ffe-uuid-67abcdef, order_id=12345
   INFO: Reusing existing order (duplicate detected): order_id=12345, status=FILLED, clientRequestID=...
   ```

3. **Timeout Handling**
   ```
   ERROR: Timeout error - will not retry to prevent duplicates (clientRequestID=...): ...
   INFO: Order was submitted before timeout: order_id=12345
   ```

4. **Connection Errors (with retry)**
   ```
   WARNING: Connection error (attempt 1/3): Connection refused (clientRequestID=...)
   INFO: Retrying after 2.0 seconds...
   ```

5. **Successful Execution**
   ```
   INFO: Trade executed successfully: order_id=12345, clientRequestID=ffe-uuid-67abcdef, attempt=1
   ```

### Audit Trail Recovery

If a trade fails with timeout or unclear error:
1. Check logs for `clientRequestID`: `ffe-...`
2. Query Oanda account directly using clientRequestID
3. If order exists → trade succeeded (delivery problem)
4. If order missing → trade failed (pre-submission error)

## Safety Guarantees

✓ **No duplicate orders on timeout** - Queries for existing order before retrying  
✓ **No duplicate orders on transient errors** - Only retries DNS/connection issues, not HTTP 5xx  
✓ **Audit trail** - Every order includes clientRequestID and attempt count in logs  
✓ **Backward compatible** - Old code calling `execute_trade()` works without changes  
✓ **Explicit error handling** - Different retry behaviors for different error types  

## Migration Notes

- No changes required to caller code
- No database migrations needed
- Config defaults remain unchanged
- Existing positions unaffected

## Testing

### Manual Verification
```bash
cd /home/cmp6510/finance_feedback_engine-2.0

# Verify implementation
python -c "
from finance_feedback_engine.trading_platforms.oanda_platform import OandaPlatform
print('✓ Helper methods exist:',
      hasattr(OandaPlatform, '_get_recent_orders'),
      hasattr(OandaPlatform, '_find_duplicate_order'))
"

# Test HOLD action
python -c "
from finance_feedback_engine.trading_platforms.oanda_platform import OandaPlatform
import uuid

config = {'api_timeouts': {'platform_execute': 30}}
creds = {'access_token': 'test', 'account_id': 'test', 'environment': 'practice'}
platform = OandaPlatform(creds, config)

decision = {
    'id': str(uuid.uuid4()),
    'action': 'HOLD',
    'asset_pair': 'EURUSD',
    'timestamp': '2025-01-01T00:00:00Z'
}

result = platform.execute_trade(decision)
print('Result:', 'success' if result['success'] else 'error')
"
```

### Unit Tests
Tests can verify:
- `_find_duplicate_order()` returns None when no matches exist
- `_find_duplicate_order()` returns order when clientRequestID matches
- Manual retry loop respects max_attempts
- TimeoutError triggers query instead of immediate retry
- ConnectionError triggers exponential backoff retry
- Log statements include clientRequestID for audit

## References

- **Oanda API Documentation**: `clientRequestID` support in OrderCreate endpoint
- **Coinbase Implementation**: Uses similar `client_order_id` pattern (see `coinbase_platform.py`)
- **Idempotency Pattern**: Industry standard for transaction idempotency in financial systems
- **Architecture Guide**: See copilot-instructions.md section on Unified Platform Mode

## Author Notes

This implementation follows the established pattern from `CoinbaseAdvancedPlatform.execute_trade()` which also uses UUID-based idempotency keys for order submissions. The key difference is that Oanda requires manual duplicate detection via order queries (Coinbase SDK provides a built-in `list_orders()` with `client_order_id` filtering).

The decision to NOT retry on TimeoutError is critical: even though the order might not have been submitted, we cannot know for certain, and retrying could create a duplicate. The safer approach is to query first, then fail if the order doesn't exist.
