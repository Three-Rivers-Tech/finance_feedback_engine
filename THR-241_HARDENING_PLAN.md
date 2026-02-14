# THR-241 Hardening Plan

**Goal:** Address Gemini P1 issues before merge (6/10 → 9/10 rating)

---

## Task Breakdown (by difficulty)

### 🟢 Easy (Difficulty 2-3, ~15-30 min total)

**Task 1: Fix entry_price for settled balances**
- **Difficulty:** 2/10
- **Time:** 10 min
- **What:** Change `entry_price: current_price` → `entry_price: None` for account balances
- **Why:** Current approach shows fake $0.00 P&L (misleading)
- **Impact:** Accurate data representation
- **File:** `coinbase_platform.py` line 1221

**Task 2: Improve error logging**
- **Difficulty:** 2/10
- **Time:** 10 min
- **What:** Replace `except Exception as e:` with `logger.exception()` for stack traces
- **Why:** Better debugging in production
- **Impact:** Easier troubleshooting
- **Files:** Lines 1219, 1265, 1312

**Task 3: Clean up getattr redundancy**
- **Difficulty:** 3/10
- **Time:** 15 min
- **What:** Remove redundant `or ""` clauses after getattr with default
- **Example:** `getattr(account, "currency", "") or ""` → `getattr(account, "currency", "")`
- **Why:** Code clarity, no functional change
- **Impact:** Maintainability
- **Files:** Lines 1201, 1213, etc.

---

### 🟡 Medium (Difficulty 5-6, ~45-60 min)

**Task 4: Batch price fetches (single-call optimization)**
- **Difficulty:** 5/10
- **Time:** 45 min
- **What:** Replace per-asset `get_product()` calls with single batch ticker endpoint
- **API:** Check if `client.get_product_book()` or similar supports multi-product
- **Fallback:** If no batch endpoint, cache prices for 30s to reduce duplicate calls
- **Why:** Avoid rate limits with 10+ holdings
- **Impact:** 10-20x fewer API calls
- **Files:** Lines 1210, 1262

**Current flow:**
```python
for account in accounts:
    product = client.get_product(f"{currency}-USD")  # 1 call per asset
    price = product.price
```

**Target flow:**
```python
# Collect all product_ids first
product_ids = [f"{currency}-USD" for currency in currencies]

# Single batch call
tickers = client.get_all_tickers(product_ids)  # 1 call total
prices = {t.product_id: t.price for t in tickers}
```

---

### 🔴 Hard (Difficulty 7, ~60-90 min)

**Task 5: Handle None in downstream consumers**
- **Difficulty:** 7/10
- **Time:** 60-90 min
- **What:** Update CLI + other consumers to handle `entry_price: None`
- **Why:** Changing data model impacts display logic
- **Impact:** Breaking change if not done carefully
- **Files:** 
  - `cli/main.py` positions command (handle None gracefully)
  - Any other code that assumes entry_price is always float

**Changes needed:**
1. CLI: Skip P&L calculation if entry_price is None
2. Display: Show "Unknown" instead of "$0.00 (0.00%)"
3. Tests: Update assertions to expect None for settled balances

---

## Execution Order

1. **Easy tasks first (Tasks 1-3):** 35 min → Quick wins, low risk
2. **Medium task (Task 4):** 45 min → Research batch API, implement caching fallback
3. **Hard task (Task 5):** 60-90 min → Test downstream impacts thoroughly

**Total time:** 2.5-3 hours

---

## Alternative: Phased Approach

**Phase 1 (30 min):** Tasks 1-3 only → Rating 7/10 (acceptable for staging)  
**Phase 2 (45 min):** Task 4 → Rating 8/10 (production-ready for <10 assets)  
**Phase 3 (60 min):** Task 5 → Rating 9/10 (fully hardened)

**Recommendation:** Do all 5 tasks now while context is fresh (2.5-3 hours total).

---

## Risk Assessment

**If we skip hardening:**
- ✅ Works for current use case (1-2 assets)
- ⚠️ Will hit rate limits at scale (20+ holdings)
- ⚠️ Misleading P&L data (shows $0.00 instead of "Unknown")
- ⚠️ Harder to debug production issues (no exception traces)

**If we harden now:**
- ✅ Production-ready for scale
- ✅ Accurate data representation
- ✅ Better monitoring/debugging
- ⏱️ Delays other tickets by ~3 hours

---

**Next:** Awaiting go/no-go on full hardening plan.
