# Phase 1: Backend Implementation Notes
**Date:** 2026-02-14  
**Developer:** PM Subagent (pm-short-backtesting)  
**Objective:** Fix 3 critical issues preventing SHORT position backtesting

---

## Issues Being Fixed

### Issue #1: Signal Generation Ambiguity ✅ IMPLEMENTING
**Problem:** SELL signal has dual meaning (close LONG vs open SHORT)  
**Root Cause:** Prompt template says "SELL (short signal)" without considering current position  
**Location:** `finance_feedback_engine/decision_engine/engine.py` line 651

### Issue #2: No Position State Awareness ✅ IMPLEMENTING  
**Problem:** AI doesn't know if you currently have a position  
**Root Cause:** Position info is in prompt but signal constraints not enforced  
**Location:** `finance_feedback_engine/decision_engine/engine.py` (prompt template)

### Issue #3: Stop-Loss Edge Case Validation ✅ IMPLEMENTING
**Problem:** Missing validation for edge cases (negative percentages, zero distance)  
**Root Cause:** No bounds checking in position sizing  
**Location:** `finance_feedback_engine/decision_engine/position_sizing.py` lines 234-239

---

## Implementation Plan

### Step 1: Update AI Prompt Template (Issues #1 & #2)

**File:** `finance_feedback_engine/decision_engine/engine.py`

**Changes:**
1. Add position state awareness section after monitoring context
2. Update signal type instructions to clarify BUY/SELL interpretation
3. Add signal constraints based on current position

**New Prompt Section:**
```
POSITION STATE AWARENESS (CRITICAL):
====================================
{position_state_section}

SIGNAL INTERPRETATION RULES:
============================
Your signal MUST respect the current position state:

IF FLAT (no position):
  - BUY signal → Opens LONG position
  - SELL signal → Opens SHORT position
  - HOLD → Stay flat

IF LONG (have long position):
  - BUY signal → NOT ALLOWED (already long)
  - SELL signal → CLOSES the LONG position
  - HOLD → Keep holding long

IF SHORT (have short position):
  - BUY signal → CLOSES the SHORT position
  - SELL signal → NOT ALLOWED (already short)
  - HOLD → Keep holding short

⚠️ CRITICAL: Check "Active Positions" above. If you see a position,
your signal MUST be either HOLD or the CLOSING signal for that position.

EXAMPLES:
- Active Position: "LONG BTC-USD" → Only SELL (to close) or HOLD allowed
- Active Position: "SHORT EUR-USD" → Only BUY (to close) or HOLD allowed
- No Active Positions → BUY (open long), SELL (open short), or HOLD allowed
```

**Implementation Status:** ✅ Ready to implement

---

### Step 2: Add Position State Extraction Helper

**File:** `finance_feedback_engine/decision_engine/engine.py`

**New Method:**
```python
def _extract_position_state(self, context: Dict[str, Any], asset_pair: str) -> Dict[str, Any]:
    """
    Extract current position state for the given asset.
    
    Args:
        context: Decision context with monitoring_context
        asset_pair: Asset pair being analyzed (e.g., "BTC-USD")
    
    Returns:
        {
            "has_position": bool,
            "side": "LONG" | "SHORT" | None,
            "contracts": float,
            "entry_price": float,
            "unrealized_pnl": float,
            "allowed_signals": ["BUY", "SELL", "HOLD"]
        }
    """
    monitoring = context.get("monitoring_context", {})
    active_positions = monitoring.get("active_positions", {})
    futures = active_positions.get("futures", [])
    
    # Find position for this asset
    current_position = None
    for pos in futures:
        if pos.get("product_id") == asset_pair:
            current_position = pos
            break
    
    if not current_position:
        # FLAT - can open either LONG or SHORT
        return {
            "has_position": False,
            "side": None,
            "contracts": 0,
            "entry_price": 0,
            "unrealized_pnl": 0,
            "allowed_signals": ["BUY", "SELL", "HOLD"],
            "state": "FLAT"
        }
    
    side = current_position.get("side", "UNKNOWN").upper()
    
    if side == "LONG":
        # Have LONG - can only SELL (close) or HOLD
        allowed_signals = ["SELL", "HOLD"]
        state = "LONG"
    elif side == "SHORT":
        # Have SHORT - can only BUY (close) or HOLD
        allowed_signals = ["BUY", "HOLD"]
        state = "SHORT"
    else:
        # Unknown side - default to allow all
        logger.warning(f"Unknown position side: {side}")
        allowed_signals = ["BUY", "SELL", "HOLD"]
        state = "UNKNOWN"
    
    return {
        "has_position": True,
        "side": side,
        "contracts": current_position.get("contracts", 0),
        "entry_price": current_position.get("entry_price", 0),
        "unrealized_pnl": current_position.get("unrealized_pnl", 0),
        "allowed_signals": allowed_signals,
        "state": state
    }
```

**Implementation Status:** ✅ Ready to implement

---

### Step 3: Integrate Position State into Prompt

**File:** `finance_feedback_engine/decision_engine/engine.py`  
**Method:** `_create_ai_prompt`

**Changes:**
1. Call `_extract_position_state` to get current position
2. Build position state section for prompt
3. Insert before "ANALYSIS OUTPUT REQUIRED" section

**Code Addition (after line 285 in prompt building):**
```python
# Add position state awareness section
position_state = self._extract_position_state(context, asset_pair)

if position_state["has_position"]:
    state_emoji = "📈" if position_state["side"] == "LONG" else "📉"
    pnl_sign = "+" if position_state["unrealized_pnl"] >= 0 else ""
    
    position_state_section = f"""
=== YOUR CURRENT POSITION STATE ===
Status: {state_emoji} {position_state["state"]} position in {asset_pair}
Side: {position_state["side"]}
Contracts: {position_state["contracts"]:.4f}
Entry Price: ${position_state["entry_price"]:.2f}
Unrealized P&L: {pnl_sign}${position_state["unrealized_pnl"]:.2f}

⚠️ CONSTRAINT: You are currently {position_state["state"]}.
Allowed signals: {", ".join(position_state["allowed_signals"])}

If you recommend {position_state["side"]}-prohibited signals (BUY when LONG, SELL when SHORT),
your decision will be REJECTED as invalid.
"""
else:
    position_state_section = f"""
=== YOUR CURRENT POSITION STATE ===
Status: 📊 FLAT (no active position in {asset_pair})
Allowed signals: BUY (open LONG), SELL (open SHORT), HOLD

You can freely open either a LONG or SHORT position.
"""

market_info += position_state_section
```

**Implementation Status:** ✅ Ready to implement

---

### Step 4: Validate Signal Against Position State

**File:** `finance_feedback_engine/decision_engine/engine.py`  
**Method:** `_create_decision` (or new validation method)

**New Validation Method:**
```python
def _validate_signal_against_position(
    self, 
    action: str, 
    position_state: Dict[str, Any],
    asset_pair: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the signal is allowed given current position state.
    
    Args:
        action: The signal action (BUY, SELL, HOLD)
        position_state: Current position state from _extract_position_state
        asset_pair: Asset pair for logging
    
    Returns:
        (is_valid, error_message)
    """
    allowed = position_state.get("allowed_signals", ["BUY", "SELL", "HOLD"])
    
    if action not in allowed:
        state = position_state.get("state", "UNKNOWN")
        error = (
            f"Signal {action} not allowed when {state}. "
            f"Current position: {position_state.get('side', 'NONE')} {asset_pair}. "
            f"Allowed signals: {', '.join(allowed)}"
        )
        logger.warning(error)
        return False, error
    
    # Additional validation: Don't allow BUY when already LONG
    if action == "BUY" and position_state.get("side") == "LONG":
        error = f"Cannot BUY when already LONG {asset_pair}. Use HOLD to keep position or SELL to close."
        logger.warning(error)
        return False, error
    
    # Additional validation: Don't allow SELL when already SHORT
    if action == "SELL" and position_state.get("side") == "SHORT":
        error = f"Cannot SELL when already SHORT {asset_pair}. Use HOLD to keep position or BUY to close."
        logger.warning(error)
        return False, error
    
    return True, None
```

**Integration Point:** In `generate_decision` method, after AI response but before creating decision:
```python
# Validate AI response action against position state
position_state = self._extract_position_state(context, asset_pair)
is_valid, error_msg = self._validate_signal_against_position(
    ai_response.get("action"), 
    position_state,
    asset_pair
)

if not is_valid:
    logger.warning(
        f"AI generated invalid signal for {asset_pair}: {error_msg}. "
        f"Forcing HOLD."
    )
    ai_response["action"] = "HOLD"
    ai_response["reasoning"] = (
        f"FORCED HOLD: {error_msg}. "
        f"Original reasoning: {ai_response.get('reasoning', 'N/A')}"
    )
    ai_response["confidence"] = 0.0  # Zero confidence for forced HOLD
```

**Implementation Status:** ✅ Ready to implement

---

### Step 5: Add Stop-Loss Validation (Issue #3)

**File:** `finance_feedback_engine/decision_engine/position_sizing.py`  
**Method:** `calculate_position_size` (around line 234-239)

**Current Code (BUGGY):**
```python
# Calculate stop loss price
position_type = self._determine_position_type(action)
stop_loss_price = 0
if position_type == "LONG" and current_price > 0:
    stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
elif position_type == "SHORT" and current_price > 0:
    stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)
```

**Fixed Code with Validation:**
```python
# Validate stop-loss percentage
MIN_STOP_LOSS_PCT = 0.005  # 0.5% minimum
MAX_STOP_LOSS_PCT = 0.50   # 50% maximum (sanity check)

if sizing_stop_loss_percentage < MIN_STOP_LOSS_PCT:
    logger.warning(
        f"Stop-loss percentage {sizing_stop_loss_percentage:.3%} below minimum {MIN_STOP_LOSS_PCT:.3%}. "
        f"Adjusting to minimum."
    )
    sizing_stop_loss_percentage = MIN_STOP_LOSS_PCT

if sizing_stop_loss_percentage > MAX_STOP_LOSS_PCT:
    logger.warning(
        f"Stop-loss percentage {sizing_stop_loss_percentage:.3%} above maximum {MAX_STOP_LOSS_PCT:.3%}. "
        f"Capping to maximum."
    )
    sizing_stop_loss_percentage = MAX_STOP_LOSS_PCT

# Validate current price
if current_price <= 0:
    logger.error(
        f"Invalid current_price: {current_price}. Cannot calculate stop-loss. "
        f"Defaulting to 0."
    )
    stop_loss_price = 0
else:
    # Calculate stop loss price
    position_type = self._determine_position_type(action)
    
    if position_type == "LONG":
        stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
        # Validate: LONG stop-loss must be below entry
        if stop_loss_price >= current_price:
            logger.error(
                f"LONG stop-loss {stop_loss_price:.2f} >= entry {current_price:.2f}. "
                f"This should never happen. Setting to entry * 0.98"
            )
            stop_loss_price = current_price * 0.98
    elif position_type == "SHORT":
        stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)
        # Validate: SHORT stop-loss must be above entry
        if stop_loss_price <= current_price:
            logger.error(
                f"SHORT stop-loss {stop_loss_price:.2f} <= entry {current_price:.2f}. "
                f"This should never happen. Setting to entry * 1.02"
            )
            stop_loss_price = current_price * 1.02
    else:
        logger.warning(f"Unknown position type: {position_type}. Cannot calculate stop-loss.")
        stop_loss_price = 0

    # Final validation: Ensure minimum distance between entry and stop-loss
    min_distance = current_price * MIN_STOP_LOSS_PCT
    actual_distance = abs(stop_loss_price - current_price)
    
    if actual_distance < min_distance:
        logger.warning(
            f"Stop-loss distance {actual_distance:.2f} too close to entry {current_price:.2f}. "
            f"Minimum distance: {min_distance:.2f}. Adjusting."
        )
        if position_type == "LONG":
            stop_loss_price = current_price * (1 - MIN_STOP_LOSS_PCT)
        elif position_type == "SHORT":
            stop_loss_price = current_price * (1 + MIN_STOP_LOSS_PCT)
```

**Implementation Status:** ✅ Ready to implement

---

## Testing Strategy

### Unit Tests (to be added)
1. **test_position_state_extraction.py:**
   - Test extracting FLAT state (no position)
   - Test extracting LONG state (has long position)
   - Test extracting SHORT state (has short position)
   - Test allowed signals for each state

2. **test_signal_validation.py:**
   - Test BUY when FLAT (should pass)
   - Test SELL when FLAT (should pass)
   - Test BUY when LONG (should fail)
   - Test SELL when SHORT (should fail)
   - Test SELL when LONG (should pass - closes position)
   - Test BUY when SHORT (should pass - closes position)

3. **test_stop_loss_validation.py:**
   - Test negative stop-loss percentage (should be rejected)
   - Test zero stop-loss percentage (should be adjusted to minimum)
   - Test stop-loss too close to entry (should be adjusted)
   - Test LONG stop-loss above entry (should be rejected)
   - Test SHORT stop-loss below entry (should be rejected)

### Integration Tests
1. Run backtest on downtrending market (EUR/USD or BTC 2022 crash)
2. Verify SHORT positions open when AI says SELL (and no existing position)
3. Verify SHORT positions close when AI says BUY (and have SHORT position)
4. Verify no SELL signals generated when already SHORT

---

## Migration Impact

### Breaking Changes
**None** - This is additive functionality. Existing LONG-only behavior remains unchanged.

### Behavior Changes
1. **NEW:** AI prompt now includes current position state
2. **NEW:** Signals validated against position state (invalid signals forced to HOLD)
3. **NEW:** Stop-loss validation prevents edge cases

### Performance Impact
- Minimal: One additional dict lookup for position state
- Validation adds ~0.1ms per decision

---

## Deployment Checklist
- [ ] Implement position state extraction helper
- [ ] Update AI prompt template with position state section
- [ ] Add signal validation logic
- [ ] Add stop-loss validation in position_sizing.py
- [ ] Write unit tests for all new functions
- [ ] Run regression tests (ensure LONGs still work)
- [ ] Run integration test on SHORT-favorable data
- [ ] Update documentation

---

## Next Steps
1. Implement all code changes (estimated 4-6 hours)
2. Write comprehensive unit tests (estimated 2-3 hours)
3. Run integration tests and backtest validation (estimated 1-2 hours)
4. Request Gemini code review
5. Create final completion report

---

**Status:** Planning complete, ready to implement...
