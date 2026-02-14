# Balance Troubleshooting & Testing Gap - Status Report

**Date:** 2026-02-14 13:25 PM EST  
**Issues:** (1) Can't see Coinbase production balance, (2) SHORT position logic untested

---

## Issue #1: Coinbase Balance Visibility

**Christian's feedback:** "it has funds, troubleshoot why you can't see them"

### Troubleshooting Steps Taken:
1. ✅ Verified production mode: `COINBASE_USE_SANDBOX="false"` in .env
2. ✅ Confirmed API credentials present (organizations/.../apiKeys/...)
3. ❌ Unable to query API directly (dependency/environment issues)
4. 🔄 Starting Docker backend to use proper SDK environment

### Current Blockers:
- Python environment on Mac lacks required dependencies (pandas, aiohttp, coinbase SDK)
- Can't use pip3 install (system packages locked)
- Docker backend wasn't running
- Need to use containerized environment for API calls

### Next Steps:
1. Start Docker backend service (in progress)
2. Query Coinbase API via backend container
3. Check all account types:
   - Brokerage accounts (`/api/v3/brokerage/accounts`)
   - Futures positions (`/api/v3/brokerage/cfm/positions`)
   - Portfolios (`/api/v3/brokerage/portfolios`)
4. Identify which account type holds the funds

### Hypotheses:
- **Most likely:** Funds are in futures trading account, not spot account
- **Possible:** API permissions issue (read-only vs trade permissions)
- **Less likely:** Wrong API endpoint (sandbox vs production URL)

---

## Issue #2: SHORT Position Testing Gap

**Christian's feedback:** "if we were only testing long (spot) we were not effectively capturing what the bot is doing/capable of"

### The Real Problem:
**Backtesting validated:** LONG positions only (buy → hold → sell)  
**Never tested:** SHORT positions (sell → hold → buy)

**Impact:**
- Futures trading enables both LONG and SHORT
- ~50% of Phase 3 trades will be SHORT
- SHORT logic has ZERO validation
- Different risk profile (unlimited loss potential)
- Stop-loss/take-profit math is inverted for shorts

### Critical Gaps:
❌ SHORT signal generation untested  
❌ SHORT position sizing untested  
❌ SHORT stop-loss placement untested (above entry, not below)  
❌ SHORT take-profit untested (below entry, not above)  
❌ SHORT P&L calculation untested  
❌ SHORT margin requirements untested  

### Risk Level: **HIGH**
If we execute 75 SHORT trades (50% of 150) with zero validation, we're flying blind.

---

## Recommended Action Plan

### Immediate (Today):
1. **Fix balance visibility** (1 hour)
   - Use Docker backend to query Coinbase API
   - Document which account type holds funds
   - Update UnifiedPlatform if needed

2. **Audit SHORT decision logic** (2-3 hours)
   - Review decision_engine/*.py for SHORT signal generation
   - Verify stop-loss/take-profit math for shorts
   - Check position sizing for short positions
   - Identify any LONG-only assumptions in code

3. **Execute manual SHORT test trades** (1 hour)
   - Test on Oanda practice account (low risk)
   - 3-5 SHORT positions on EUR/USD or GBP/USD
   - Verify: entry, tracking, P&L, stop-loss triggers, exit
   - Document any issues

### Short-term (Next 2-3 Days):
4. **Add SHORT backtesting** (3-4 hours)
   - Modify backtester.py to handle SELL signals as short entries
   - Run SHORT-only strategy backtest
   - Compare SHORT vs LONG performance metrics
   - Measure mixed (50/50) portfolio performance

5. **Paper trade SHORT positions** (ongoing)
   - Execute 10-20 SHORTs on practice account
   - Build confidence before production deployment

### Decision Point:
**Option A (Conservative):** Complete SHORT validation before Phase 3 scaling  
- Time: 2-3 days delay  
- Risk: Low  
- Confidence: High  

**Option B (Aggressive):** Manual SHORT tests only, proceed with caution  
- Time: Today  
- Risk: Medium  
- Confidence: Moderate  

**Option C (Reckless):** Proceed with Phase 3 as-is  
- Time: No delay  
- Risk: High  
- Confidence: Unknown  

---

## Documents Created:
- `SHORT_POSITION_TESTING_GAP.md` - Detailed analysis of SHORT testing gap
- `BALANCE_AND_TESTING_STATUS.md` - This file (status summary)

---

## Awaiting Christian's Direction:
1. **Balance issue:** Continue troubleshooting via Docker? Or is there a specific account type I should check?
2. **Testing approach:** Which option (A/B/C) for SHORT validation?
3. **Phase 3 timeline:** Pause volume targets until validation complete? Or proceed with manual monitoring?
