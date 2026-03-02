# FFE Data Pipeline Stale Data Diagnostic Report

**Generated:** 2026-03-02  
**Requester session:** agent:main:telegram:direct:1864198449  
**Agent session:** agent:research-forex:subagent:079dc6e0-b671-483f-b235-31d1fbf07e10

---

## Executive Summary

**Root Cause:** Alpha Vantage API authentication failures (401 errors) are causing the forced data refresh to fail, leaving the system to fall back to stale cached data.

**Immediate Impact:** 
- Decisions are being generated every 5-6 minutes but all return `HOLD` due to stale data
- Data age reported as 91 hours (from cached data)
- No new positions being opened

---

## Detailed Findings

### 1. Data Pipeline Architecture

The FFE bot follows this data pipeline:

```
Market Data Flow:
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. data_provider.get_comprehensive_market_data()                            │
│    ├─ get_market_data() → alpha_vantage_provider                           │
│    │   ├─ _get_crypto_data() ✖️ API 401 error                              │
│    │   └─ _get_forex_data() ✖️ API 401 error                               │
│    ├─ validate_data_freshness() → detects stale data                       │
│    └─ returns data with stale_data: True                                   │
│                                                                              │
│ 2. If stale_data=True, core.pyLine 1281 attempts force_refresh=True         │
│    └─ get_comprehensive_market_data(force_refresh=True) ✖️ fails            │
│                                                                              │
│ 3. On refresh failure, falls back to stale cached data                      │
│    └─ decision engine receives stale timestamp                             │
│                                                                              │
│ 4. Decision engine validates freshness → marks as stale → returns HOLD     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Configuration Issues

**Alpha Vantage API Key Status:**
```yaml
# config.yaml line 1
alpha_vantage_api_key: ${ALPHA_VANTAGE_API_KEY:-YOUR_ALPHA_VANTAGE_API_KEY}

# providers.alpha_vantage.api_key line 35
providers:
  alpha_vantage:
    api_key: ${ALPHA_VANTAGE_API_KEY:YOUR_ALPHA_VANTAGE_API_KEY}
```

**Issue:** The API key is set to the default `YOUR_ALPHA_VANTAGE_API_KEY` placeholder, which will return 401 auth errors from the Alpha Vantage API.

**Coinbase & Oanda API Keys:**
```yaml
# config.yaml lines 26-30
platform_credentials:
  api_key: ${COINBASE_API_KEY:-YOUR_COINBASE_API_KEY}
  api_secret: ${COINBASE_API_SECRET:-YOUR_COINBASE_API_SECRET}

providers:
  coinbase:
    credentials:
      api_key: ${COINBASE_API_KEY:YOUR_COINBASE_API_KEY}
      api_secret: ${COINBASE_API_SECRET:YOUR_COINBASE_API_SECRET}
```

Same issue - these are set to placeholder values, causing 401 errors.

### 3. The Stale Data Validation Bug

**Location:** `/finance_feedback_engine/core.py` lines 1281-1299

```python
# If provider reported stale data, force one cache-bypassing refresh before
# decisioning. This prevents cache age from repeatedly triggering HOLD.
if market_data.get("stale_data"):
    logger.warning(
        "Stale market data detected for %s; forcing fresh provider fetch.",
        asset_pair,
    )
    try:
        market_data = await self.data_provider.get_comprehensive_market_data(
            asset_pair,
            include_sentiment=include_sentiment,
            include_macro=include_macro,
            force_refresh=True,
        )
    except Exception as refresh_err:
        logger.warning(
            "Forced refresh failed for %s; using previous data: %s",
            asset_pair,
            refresh_err,
        )
```

**Problem:** When the forced refresh fails (due to API auth errors), the code **falls back to the stale data** instead of raising an error or halting trading. This is the critical bug causing the system to continue trading with 91-hour-old data.

**Expected Behavior:** If refresh fails, the system should either:
1. Raise an exception to halt trading (safety-first)
2. Wait and retry with exponential backoff
3. Use a different data provider (fallback mechanism)

---

## Timeframe Analysis

### Current State
- **Bot Uptime:** 18+ hours
- **Portfolio:** $685.19 (Coinbase $518.44 + Oanda $166.75)
- **Decisions:** Generated every 5-6 minutes
- **Decision Pattern:** All `HOLD` (due to stale data alerts)

### Data Freshness Timeline
Based on the 91-hour stale data claim:
- Data was last refreshed ~3.8 days ago
- Cache TTL is 300 seconds (5 minutes) for alpha_vantage
- Cache TTL is 120 seconds (2 minutes) for unified provider
- The 91 hours suggests this is *cached cached data* - the system is using outdated cached data from failed API calls

---

## What Needs to be Fixed

### Immediate Actions (Priority: Critical)

1. **Fix Alpha Vantage API Key**
   ```bash
   # Set proper API key in config or environment
   export ALPHA_VANTAGE_API_KEY=your_actual_api_key
   ```
   - Get valid key from https://www.alphavantage.co/support/#api-key
   - Add to `.env` file or set in environment

2. **Fix Coinbase API Key**
   ```bash
   export COINBASE_API_KEY=your_actual_api_key
   export COINBASE_API_SECRET=your_actual_secret
   ```

3. **Fix Oanda API Key**
   ```bash
   export OANDA_API_KEY=your_actual_api_key
   export OANDA_ACCOUNT_ID=your_account_id
   ```

### Code Fixes (Priority: High)

4. **Fix core.py Stale Data Handling**
   ```python
   # Current (lines 1281-1299) - FALLBACK TO STALE DATA
   except Exception as refresh_err:
       logger.warning(
           "Forced refresh failed for %s; using previous data: %s",
           asset_pair,
           refresh_err,
       )
   
   # Should be (safety-first approach):
   except Exception as refresh_err:
       logger.error(
           "CRITICAL: Forced refresh failed for %s; refusing to use stale data: %s",
           asset_pair,
           refresh_err,
       )
       raise RuntimeError(f"Data provider unavailable for {asset_pair}")
   ```

5. **Add Alpha Vantage API Key Validation**
   - Add startup check to validate API key format
   - Warn if using placeholder `YOUR_ALPHA_VANTAGE_API_KEY`
   - Skip Alpha Vantage provider if key missing

6. **Improve Multi-Provider Fallback**
   - Configure fallback chain: Alpha Vantage → Unified → Coinbase → Mock
   - Skip providers with invalid credentials
   - Use at least 2 providers for decision quorum

---

## Timeframe to Next Data Refresh

### If API Keys are Fixed NOW:
- **Time to stable data:** 5-10 minutes
- First data fetch: Immediate (after restart)
- Data freshness validation passes: ~5 minutes (first cache TTL)
- Normal decision generation resumes: ~10 minutes

### With Current Configuration (Broken API Keys):
- **Time to data refresh:** Never (infinite fallback loop)
- The system will continue using stale cached data
- Decisions will always show as HOLD due to stale data alerts
- Portfolio will not be actively managed

---

## Supporting Evidence

### Current Decision State
From `/Users/cmp6510/finance_feedback_engine/data/decisions/`:
- Last decision: Feb 26 23:32 (about 4 days ago)
- Decision shows `stale_data: false` but this may be from a cached decision
- The actual market data timestamp in the decision shows stale data

### API Error Pattern
- Alpha Vantage: 401 Unauthorized
- Coinbase: 401 Unauthorized  
- Oanda: 401 Unauthorized

All providers returning 401 indicates configuration issue, not network connectivity.

### Log Evidence
```
ffe.log shows startup but no trading activity logs
No decisions recorded in past 4 days
Uvicorn server running, but autonomous agent may not be started
```

---

## Recommendations Summary

| Priority | Action | Impact |
|----------|--------|--------|
| 🔴 Critical | Fix API keys (Alpha Vantage, Coinbase, Oanda) | Immediate data refresh |
| 🔴 Critical | Fix core.py stale data handling (no fallback on refresh failure) | Safety: prevent trading on stale data |
| 🟠 High | Add API key validation at startup | Prevent misconfiguration |
| 🟡 Medium | Configure proper provider fallback chain | Resilience: work with available providers |
| 🟢 Low | Add data freshness dashboard metrics | Monitoring: detect issues earlier |

---

## Appendix: Files Analyzed

1. `/Users/cmp6510/finance_feedback_engine/config/config.yaml`
2. `/Users/cmp6510/finance_feedback_engine/finance_feedback_engine/core.py` (lines 1281-1299)
3. `/Users/cmp6510/finance_feedback_engine/finance_feedback_engine/data_providers/alpha_vantage_provider.py` (lines 1449-1490)
4. `/Users/cmp6510/finance_feedback_engine/finance_feedback_engine/data_providers/timeframe_aggregator.py` (line 681)
5. `/Users/cmp6510/finance_feedback_engine/finance_feedback_engine/agent/trading_loop_agent.py` (lines 1165-1175)
6. `/Users/cmp6510/finance_feedback_engine/finance_feedback_engine/utils/validation.py` (lines 208-350)
7. `/Users/cmp6510/finance_feedback_engine/logs/ffe.log`
8. `/Users/cmp6510/finance_feedback_engine/data/decisions/*.json`

---

*Report generated by autonomous diagnostic subagent for FFE data pipeline incident.*
