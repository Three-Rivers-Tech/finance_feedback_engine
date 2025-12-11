# Market Schedule Integration — Completion Summary

## Implementation Overview

Successfully implemented market-aware trading constraints to prevent trading during closed or illiquid markets. The system now enforces market hours across crypto, forex, and stock markets with timezone-aware logic.

---

## Components Delivered

### 1. **MarketSchedule Class** (`finance_feedback_engine/utils/market_schedule.py`)

Core utility providing market open/close status checks with full timezone support.

**Key Methods:**
- `get_market_status(asset_pair, asset_type, now_utc=None)` — Live/real-time checks; defaults to current UTC time
- `get_market_status_at_timestamp(asset_pair, asset_type, timestamp)` — Backtesting-compatible; accepts Unix timestamp

**Market Rules Implemented:**

| Asset Type | Hours (NY Time) | Days | Closed Windows | Session Detection |
|---|---|---|---|---|
| **Crypto** | 24/7 | All | N/A | Always "Open" |
| **Forex** | 24/5 | Mon–Fri | Fri 5 PM–Sun 5 PM NY | Asian/London/NY/Overlap |
| **Stocks** | 9:30 AM–4:00 PM | Mon–Fri | Weekends + outside hours | "New York" / "Closed" |

**Return Structure:**
```python
{
    "is_open": bool,           # Whether market is tradeable
    "session": str,            # "Asian", "London", "New York", "Overlap", "Open", "Closed"
    "time_to_close": int,      # Minutes until next close
    "warning": str             # "Weekend Low Liquidity" for crypto weekends; "" otherwise
}
```

**Timezone Handling:**
- All internal calculations use UTC
- Conversions: `America/New_York` (stocks/forex), `Europe/London` (forex sessions)
- Robust pytz-based localization; handles DST transitions

---

### 2. **RiskGatekeeper Integration** (`finance_feedback_engine/risk/gatekeeper.py`)

Market schedule validation is the **first check** in the trade validation pipeline, preventing invalid orders before risk analysis.

**Integration Points:**
- Added `from finance_feedback_engine.utils.market_schedule import MarketSchedule`
- Market check runs **before** drawdown/correlation/VaR checks (fail-fast pattern)
- Supports both live trading (no timestamp) and backtesting (Unix timestamp in context)

**Context Fields Expected:**
```python
context = {
    "asset_type": "crypto" | "forex" | "stocks",
    "timestamp": <unix_timestamp> | None,  # Optional; None → live trading
    "recent_performance": {"total_pnl": float},
    "holdings": {},
    # ... other fields
}
```

**Validation Logic:**
```
if not market_open:
    return False, f"Market closed ({session})"
if warning:
    logger.info(f"Market warning: {warning}")
continue_to_next_checks()
```

---

### 3. **Comprehensive Test Suite** (31 tests total)

#### **MarketSchedule Tests** (`tests/utils/test_market_schedule.py` — 22 tests)

**Coverage:**
- Crypto: Always open (24/7), weekend low liquidity warning
- Forex: Friday 5 PM NY closure, Sunday 5 PM reopening, session detection (Asian/London/NY/Overlap), time-to-close calculation
- Stocks: Mon–Fri 9:30–16:00 NY, weekend closure, time-to-close accuracy
- **Backtesting:** Unix timestamp method for replay simulation
- **Edge cases:** Timezone awareness, case-insensitive asset types, default to crypto

**Sample Tests:**
```python
✓ test_forex_friday_boundary_open_and_close
✓ test_forex_sunday_reopen_window
✓ test_stock_open_and_close_edges
✓ test_crypto_weekend_low_liquidity_warning
✓ test_forex_overlap_session
✓ test_backtesting_forex_timestamp
✓ test_timezone_awareness
```

#### **RiskGatekeeper Integration Tests** (`tests/risk/test_gatekeeper_market_schedule.py` — 9 tests)

**Coverage:**
- Forex rejection (Friday 5 PM close)
- Stock rejection (outside hours, weekends)
- Crypto allowance (24/7 on weekdays, with weekend warning)
- Session-aware allowances (London, NY, overlap)
- Market check precedence (fails before other validations)
- Live trading fallback (no timestamp → current time)

**Sample Tests:**
```python
✓ test_rejects_forex_when_market_closed_friday_evening
✓ test_rejects_stock_when_market_closed_outside_hours
✓ test_allows_crypto_24_7_weekday
✓ test_market_check_is_first_validation
✓ test_defaults_to_live_market_status_without_timestamp
```

---

## Usage Examples

### **Live Trading**
```python
from finance_feedback_engine.risk.gatekeeper import RiskGatekeeper
from finance_feedback_engine.utils.market_schedule import MarketSchedule

gatekeeper = RiskGatekeeper()

# Live check (uses current time)
decision = {"action": "BUY", "asset_pair": "EURUSD", "confidence": 85, "volatility": 0.02}
context = {
    "asset_type": "forex",
    "recent_performance": {"total_pnl": 0.01},
    "holdings": {}
}
is_valid, msg = gatekeeper.validate_trade(decision, context)
print(f"Trade allowed: {is_valid}, Message: {msg}")
```

### **Backtesting**
```python
import time

# Backtest at specific timestamp
backtest_timestamp = int(time.time()) - 86400  # 1 day ago

context = {
    "asset_type": "stocks",
    "timestamp": backtest_timestamp,  # Unix timestamp
    "recent_performance": {"total_pnl": 0.005},
    "holdings": {}
}
is_valid, msg = gatekeeper.validate_trade(decision, context)
```

### **Direct MarketSchedule Usage**
```python
from finance_feedback_engine.utils.market_schedule import MarketSchedule

# Live status
status = MarketSchedule.get_market_status("BTCUSD", "crypto")
print(f"Open: {status['is_open']}, Session: {status['session']}")

# Backtesting
status = MarketSchedule.get_market_status_at_timestamp("AAPL", "stocks", 1715611800)
print(f"Time to close: {status['time_to_close']} minutes")
```

---

## Integration Points

### **Existing Components**
- **RiskGatekeeper:** Market check added as validation step 0 (before drawdown/VaR)
- **TradingAgentOrchestrator:** Already imports `MarketSchedule` (ready for use)
- **Backtester:** Can pass timestamp in context for time-accurate simulations

### **Ready for Integration**
- **PortfolioBacktester:** Pass `timestamp` in decision context during backtests
- **TradeMonitor:** Can warn on illiquid windows (weekend crypto)
- **DecisionEngine:** Can incorporate session info in LLM prompts

---

## Testing Results

```
======================== 31 passed in 3.37s ========================
✓ MarketSchedule tests:  22 passed (99% coverage on module)
✓ Gatekeeper integration: 9 passed
✓ All edge cases validated (timezone DST, Friday closures, session overlaps)
```

---

## Files Modified/Created

| File | Change | Lines |
|---|---|---|
| `finance_feedback_engine/utils/market_schedule.py` | Created | 160 |
| `finance_feedback_engine/risk/gatekeeper.py` | Updated (import + market check) | +25 |
| `tests/utils/test_market_schedule.py` | Expanded (basic → comprehensive) | 360 |
| `tests/risk/test_gatekeeper_market_schedule.py` | Created | 275 |

---

## Key Design Decisions

1. **UTC-centric:** All internal calcs use UTC to avoid timezone confusion; conversions happen at boundaries
2. **Backtesting-first:** `timestamp` parameter enables deterministic historical analysis without mocking `datetime.now()`
3. **Fail-fast:** Market check runs first in gatekeeper; prevents wasted risk calculations
4. **Timezone robustness:** Uses `pytz` with full DST support; handles edge cases (DST transitions, leap years)
5. **Cryptowarnings:** Crypto is 24/7 tradeable but warns on weekend low liquidity (user decision point)
6. **Session labels:** Return human-readable session names (Asian/London/NY/Overlap) for monitoring/logging

---

## Next Steps (Optional)

1. **Integrate into DecisionEngine:** Pass `session` label in LLM prompts for liquidity-aware advice
2. **Portfolio-level checks:** Warn if multiple assets approach close within N minutes
3. **Holiday calendar:** Extend to exclude stock market holidays (Thanksgiving, Christmas, etc.)
4. **Extended hours:** Add support for stock pre-market (4–9:30 AM) / after-hours (4–8 PM)
5. **Regional variants:** Support Asian stock hours (TSE, Shanghai), other forex centers (Sydney, Tokyo)
