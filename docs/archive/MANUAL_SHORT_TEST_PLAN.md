# Manual SHORT Position Test Plan

**Date:** 2026-02-14  
**Objective:** Validate SHORT trading pipeline end-to-end on Oanda practice account  
**Priority:** CRITICAL (blocks Phase 3 deployment)

---

## Test Environment

**Platform:** Oanda Practice Account  
**Balance:** $172.77 available  
**Instruments:** EUR/USD, GBP/USD (forex pairs with liquidity)  
**Position size:** Minimum viable (1-10 units)  
**Risk:** ~$10-20 per trade (low-risk validation)

---

## Test Cases

### Test 1: Basic SHORT Entry/Exit
**Objective:** Verify SHORT position opens and closes correctly

**Steps:**
1. Monitor EUR/USD for short signal (price at resistance, downward momentum)
2. Execute SHORT entry (SELL 1 unit EUR/USD)
3. Verify position appears in `ffe positions` with correct direction
4. Set stop-loss ABOVE entry price (e.g., +20 pips)
5. Set take-profit BELOW entry price (e.g., -15 pips)
6. Monitor position
7. Close manually with BUY order
8. Verify P&L calculation: (entry - exit) × units

**Expected:**
- Position tracked as SHORT or negative units
- Stop-loss triggers if price goes UP
- Take-profit triggers if price goes DOWN
- P&L calculated correctly
- Trade outcome recorded

**Success criteria:** All 5 steps work correctly

---

### Test 2: SHORT Stop-Loss Trigger
**Objective:** Verify stop-loss triggers correctly for shorts (price goes UP)

**Steps:**
1. Open SHORT position on EUR/USD
2. Set tight stop-loss ABOVE entry (e.g., +5 pips)
3. Wait for price to move up and trigger SL
4. Verify position closed automatically
5. Verify loss recorded correctly

**Expected:**
- SL triggers when price > entry_price + stop_distance
- Position closed at loss
- Trade outcome shows: entry_price, exit_price, loss amount

**Success criteria:** Stop-loss works in reverse (triggers on upward price movement)

---

### Test 3: SHORT Take-Profit Trigger
**Objective:** Verify take-profit triggers correctly for shorts (price goes DOWN)

**Steps:**
1. Open SHORT position on EUR/USD during downward move
2. Set take-profit BELOW entry (e.g., -10 pips)
3. Wait for price to move down and trigger TP
4. Verify position closed automatically
5. Verify profit recorded correctly

**Expected:**
- TP triggers when price < entry_price - profit_distance
- Position closed at profit
- Trade outcome shows positive P&L

**Success criteria:** Take-profit works in reverse (triggers on downward price movement)

---

### Test 4: Mixed LONG/SHORT Portfolio
**Objective:** Verify system handles both directions simultaneously

**Steps:**
1. Open LONG position on GBP/USD
2. Open SHORT position on EUR/USD
3. Verify both show in `ffe positions` correctly
4. Check portfolio P&L aggregates both
5. Close both positions
6. Verify trade outcomes recorded for both

**Expected:**
- Both positions tracked correctly
- Portfolio breakdown accurate
- No conflicts between LONG and SHORT logic

**Success criteria:** System handles bidirectional trading without errors

---

### Test 5: SHORT Position Sizing
**Objective:** Verify position sizing calculates correctly for shorts

**Steps:**
1. Request SHORT signal from FFE with 2% risk
2. Verify position size calculated correctly
3. Check margin requirements accounted for
4. Execute at calculated size
5. Verify position matches expected units

**Expected:**
- Position sizing same logic as longs
- Margin requirements correct
- Units calculated accurately

**Success criteria:** Position sizing works identically for shorts and longs

---

## Validation Checklist

**Before testing:**
- [ ] Oanda practice account accessible
- [ ] FFE engine can execute trades
- [ ] Position tracking working
- [ ] Trade outcome recorder active

**During testing:**
- [ ] Monitor logs for errors
- [ ] Take screenshots of positions
- [ ] Record entry/exit prices manually
- [ ] Note any unexpected behavior

**After testing:**
- [ ] Review all trade outcomes in data/trade_outcomes/
- [ ] Check P&L calculations manually
- [ ] Document any bugs found
- [ ] Create GitHub issues for fixes needed

---

## Risk Management

**Max loss per test:** $20  
**Total test budget:** $100 (5 tests × $20 max)  
**Account preservation:** Stop if balance drops below $100

**Safety measures:**
- Use minimum position sizes
- Set tight stop-losses
- Test during low-volatility hours
- Monitor all trades manually

---

## Expected Issues (from research)

Based on code audit, likely issues:

1. **SELL signal interpreted as close-only**
   - Symptom: Can't open SHORT, only close LONG
   - Fix: Modify decision engine to allow SHORT entries

2. **Stop-loss in wrong direction**
   - Symptom: SL triggers immediately (placed below entry)
   - Fix: Invert SL logic for shorts

3. **P&L calculation wrong**
   - Symptom: Shows loss when should be profit (formula not inverted)
   - Fix: Change to (entry - exit) × units for shorts

4. **Position tracking missing**
   - Symptom: SHORT positions not visible in CLI
   - Fix: Add support for negative units or SHORT flag

---

## Timeline

**Preparation:** 30 minutes (verify Oanda access, check FFE status)  
**Test execution:** 2-3 hours (5 tests × 20-30 min each)  
**Documentation:** 30 minutes (record results, create issues)

**Total:** 3-4 hours

**Schedule:**
- After sub-agent audit completes (know what to expect)
- Before sub-agent backtesting finishes (validate their work)
- Today if possible, tomorrow morning latest

---

## Success Criteria

**Minimum viable:**
- [ ] 3+ SHORT trades executed successfully
- [ ] Stop-loss triggers correctly (on upward price movement)
- [ ] P&L calculated correctly
- [ ] Trade outcomes recorded

**Ideal:**
- [ ] All 5 test cases pass
- [ ] No critical bugs found
- [ ] SHORT and LONG can coexist
- [ ] Ready for Phase 3 volume execution

**Blocker threshold:**
- If 2+ critical bugs found: Pause Phase 3, fix bugs first
- If 0-1 bugs: Proceed with caution, monitor closely

---

## Next Steps After Testing

**If successful:**
1. Update SHORT_POSITION_TESTING_GAP.md with results
2. Mark SHORT validation complete
3. Proceed with Phase 3 volume targets
4. Monitor first 10 production SHORTs closely

**If issues found:**
1. Create Linear tickets for each bug
2. Prioritize by severity
3. Fix critical bugs before Phase 3
4. Re-test after fixes

---

**Status:** Awaiting sub-agent audit results before execution  
**Owner:** Nyarlathotep (autonomous)  
**Approval:** Christian (informed via progress updates)
