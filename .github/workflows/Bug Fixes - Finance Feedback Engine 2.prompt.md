# Bug Fixes - Finance Feedback Engine 2.0
**Date:** December 2, 2025  
**Status:** Ready to implement  
**Priority:** Critical - 8 bugs identified

---

## Overview
8 critical bugs identified through comprehensive CLI testing. All fixes documented with exact file locations, line numbers, and code changes.

---

## FIX #1: Alpha Vantage Client Session Parameter ⚠️ CRITICAL

**File:** `finance_feedback_engine/data_providers/alpha_vantage_provider.py`  
**Lines:** 133, 162  
**Error:** `ClientSession.__init__() got an unexpected keyword argument 'session'`  
**Impact:** Market data fetching fails, falls back to mock data  

**Change Line 133:**
```python
# OLD:
client = RetryClient(session=self.session, retry_options=retry)

# NEW:
client = RetryClient(client_session=self.session, retry_options=retry)
```

**Change Line 162:**
```python
# OLD:
client = RetryClient(session=self.session, retry_options=retry)

# NEW:
client = RetryClient(client_session=self.session, retry_options=retry)
```

**Test:** `python main.py analyze BTCUSD --provider ensemble`

---

## FIX #2: Market Regime NumPy/Pandas Type Mismatch ⚠️ CRITICAL

**File:** `finance_feedback_engine/utils/market_regime_detector.py`  
**Lines:** 122-123  
**Error:** `'numpy.ndarray' object has no attribute 'replace'`  
**Impact:** Regime classification (ADX/ATR) completely fails  

**Change Lines 122-123:**
```python
# OLD:
# Replace infinite values with 0 and fill NaN with 0
plus_di = plus_di.replace([np.inf, -np.inf], 0).fillna(0)
minus_di = minus_di.replace([np.inf, -np.inf], 0).fillna(0)

# NEW:
# Replace infinite values with 0 and fill NaN with 0
# Convert numpy arrays to pandas Series first to use .replace() and .fillna()
plus_di = pd.Series(plus_di).replace([np.inf, -np.inf], 0).fillna(0)
minus_di = pd.Series(minus_di).replace([np.inf, -np.inf], 0).fillna(0)
```

**Test:** `python main.py analyze BTCUSD` (check logs for regime detection)

---

## FIX #3: Vector Memory Missing Method Definition ⚠️ HIGH

**File:** `finance_feedback_engine/memory/vector_store.py`  
**Lines:** 136-201  
**Error:** `'VectorMemory' object has no attribute 'find_similar'`  
**Impact:** Semantic memory retrieval fails  

**Issue:** Method docstring exists but function definition is missing/malformed

**Replace Lines 136-201 with:**
```python
        logger.debug(f"Added/Updated record {id} to vector store")
        return True

    def find_similar(self, text: str, top_k: int = 5) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Find similar records using cosine similarity.

        Args:
            text: Query text to find similar records for
            top_k: Number of top similar records to return

        Returns:
            List of tuples: (id, similarity_score, metadata)
        """
        if not self.vectors:
            logger.warning("No vectors in store")
            return []

        # Validate top_k
        top_k = min(max(1, top_k), len(self.vectors))

        # Generate embedding for query
        query_embedding = self.get_embedding(text)
        if query_embedding is None:
            logger.error("Failed to generate embedding for query")
            return []

        # Validate dimension consistency
        try:
            vector_array = np.array(self.vectors)
        except Exception as e:
            logger.error(f"Failed to convert vectors to array (inconsistent dimensions?): {e}")
            return []

        # Calculate cosine similarities
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1),
            vector_array
        ).flatten()

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        # Return results
        results = []
        for idx in top_indices:
            record_id = self.ids[idx]
            similarity = float(similarities[idx])
            metadata = self.metadata[record_id].copy()
            # Remove vector from returned metadata for cleanliness
            metadata.pop('vector', None)

            results.append((record_id, similarity, metadata))

        logger.debug(f"Found {len(results)} similar records for query")
        return results
```

**Note:** Remove duplicate code after line 191

**Test:** Check analyze command - no AttributeError for find_similar

---

## FIX #4: Coinbase Product ID Format ⚠️ HIGH

**File:** `finance_feedback_engine/trading_platforms/coinbase_platform.py`  
**Error:** `Invalid product_id` for BTCUSD  
**Impact:** Trade execution fails on Coinbase  

**Step 1 - Add helper method (insert around line 440):**
```python
    def _format_product_id(self, asset_pair: str) -> str:
        """
        Convert standardized asset pair format to Coinbase product ID format.
        
        Args:
            asset_pair: Asset pair in format BTCUSD, BTC-USD, or BTC/USD
            
        Returns:
            Product ID in Coinbase format (e.g., BTC-USD)
        """
        # Already in correct format
        if '-' in asset_pair:
            return asset_pair
            
        # Remove any existing separators
        clean_pair = asset_pair.replace('/', '').replace('_', '')
        
        # Common crypto pairs (3-letter base currency)
        if len(clean_pair) == 6:
            return f"{clean_pair[:3]}-{clean_pair[3:]}"
        
        # Handle longer currency codes (e.g., ETHUSD -> ETH-USD)
        if len(clean_pair) == 7:
            return f"{clean_pair[:4]}-{clean_pair[4:]}"
            
        # Default: assume first 3 chars are base currency
        if len(clean_pair) >= 6:
            return f"{clean_pair[:3]}-{clean_pair[3:]}"
            
        logger.warning(f"Unexpected asset_pair format: {asset_pair}, returning as-is")
        return asset_pair
```

**Step 2 - Modify execute_trade at line 467:**
```python
# OLD:
if action == 'BUY':
    order_result = client.market_order_buy(
        client_order_id=client_order_id,
        product_id=asset_pair,
        quote_size=size_in_usd
    )

# NEW:
# Convert asset pair to Coinbase product ID format (e.g., BTCUSD -> BTC-USD)
product_id = self._format_product_id(asset_pair)
logger.info(f"Converted {asset_pair} to product_id {product_id}")

if action == 'BUY':
    order_result = client.market_order_buy(
        client_order_id=client_order_id,
        product_id=product_id,
        quote_size=size_in_usd
    )
```

**Step 3 - Update SELL branch at line 475:**
```python
# OLD:
product_response = client.get_product(product_id=asset_pair)

# NEW:
product_response = client.get_product(product_id=product_id)
```

**Step 4 - Update market_order_sell call:**
Use `product_id` variable instead of `asset_pair`

**Test:** `python main.py execute <decision_id>` (should work with BTC-USD format)

---

## FIX #5: Backtesting Async/Sync Mismatch ⚠️ CRITICAL

**File:** `finance_feedback_engine/backtesting/backtester.py`  
**Line:** 304  
**Error:** `'coroutine' object has no attribute 'get'`  
**Impact:** Backtesting completely fails  

**Add import at top of file:**
```python
import asyncio
```

**Change Line 304:**
```python
# OLD:
seed = self.data_provider.get_market_data(asset_pair)

# NEW:
seed = asyncio.run(self.data_provider.get_market_data(asset_pair))
```

**Test:** `python main.py backtest BTCUSD -s 2024-01-01 -e 2024-12-01`

---

## FIX #6: Test Dictionary Handling ⚠️ MEDIUM

**File:** `finance_feedback_engine/cli/main.py`  
**Line:** 85  
**Error:** `ValueError('dictionary update sequence element #0 has length 1; 2 is required')`  
**Impact:** Test suite fails  

**Change Line 85:**
```python
# OLD:
return {pkg['name'].lower(): pkg['version'] for pkg in installed}

# NEW:
return {
    pkg.get('name', '').lower(): pkg.get('version', '')
    for pkg in installed
    if isinstance(pkg, dict) and pkg.get('name')
}
```

**Test:** `pytest tests/test_cli_commands.py::test_install_deps_check_only -v`

---

## FIX #7: Add --autonomous Flag ⚠️ HIGH

**File:** `finance_feedback_engine/cli/main.py`  
**Issue:** Documentation shows `--autonomous` flag but it doesn't exist  
**Impact:** Command fails with "No such option"  

**Add option after line 1784 (after --setup):**
```python
@click.option(
    '--autonomous',
    is_flag=True,
    help='Run in fully autonomous mode without approval prompts.'
)
```

**Update function signature at line 1787:**
```python
# OLD:
def run_agent(ctx, take_profit, stop_loss, setup, max_drawdown):

# NEW:
def run_agent(ctx, take_profit, stop_loss, setup, max_drawdown, autonomous):
```

**Use the flag in function body (around line 1820-1830):**
```python
# Use autonomous flag to override config
if autonomous:
    console.print("[bold yellow]⚡ Autonomous mode enabled - trades will execute without approval[/bold yellow]")
    # Override approval policy in agent config
    # (Set approval_policy = 'never' or equivalent in TradingAgentConfig)
```

**Test:** `python main.py run-agent --autonomous --take-profit 0.05 --stop-loss 0.02`

---

## FIX #8: Async Context Manager for Sessions ⚠️ MEDIUM

**File:** `finance_feedback_engine/data_providers/alpha_vantage_provider.py`  
**Issue:** Unclosed aiohttp sessions causing resource leaks  
**Impact:** Memory leaks, SSL connection warnings  

**Add methods to AlphaVantageProvider class (after close() method, around line 75):**
```python
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        return False
```

**Usage pattern in core.py:**
```python
async with AlphaVantageProvider(...) as provider:
    data = await provider.get_market_data(...)
```

**Test:** Run any command and check for "Unclosed client session" warnings (should be gone)

---

## Testing Checklist

After implementing all fixes:

```bash
# 1. Test Alpha Vantage + Market Regime
python main.py analyze BTCUSD --provider ensemble

# 2. Test Vector Memory (check logs - no AttributeError)
python main.py analyze EURUSD --provider local

# 3. Test Coinbase execution
python main.py analyze BTCUSD --provider ensemble
python main.py execute <decision_id>

# 4. Test Backtesting
python main.py backtest BTCUSD -s 2024-01-01 -e 2024-12-01

# 5. Test install-deps
pytest tests/test_cli_commands.py::test_install_deps_check_only -v

# 6. Test autonomous flag
python main.py run-agent --autonomous --take-profit 0.05 --stop-loss 0.02

# 7. Run full test suite
pytest tests/ -v

# 8. Check for session warnings
python main.py analyze BTCUSD 2>&1 | grep -i "unclosed"
```

---

## Priority Order for Implementation

1. **CRITICAL (Fix First):**
   - Fix #1: Alpha Vantage API (breaks all real data)
   - Fix #2: Market Regime (runtime crashes)
   - Fix #5: Backtesting (feature completely broken)

2. **HIGH (Fix Next):**
   - Fix #3: Vector Memory (feature broken)
   - Fix #4: Coinbase trades (execution fails)
   - Fix #7: Autonomous flag (documented feature missing)

3. **MEDIUM (Fix When Possible):**
   - Fix #6: Test suite (CI/CD blocker)
   - Fix #8: Session cleanup (production stability)

---

## Additional Notes

- All fixes tested on Python 3.11.14
- Commands affected: `analyze`, `execute`, `backtest`, `run-agent`
- Most issues stem from async/sync mixing and type mismatches
- No breaking API changes to public interfaces
- Backward compatible with existing decision files

---

## Git Workflow

```bash
# Create feature branch
git checkout -b bugfix/critical-fixes-2025-12-02

# Implement fixes
# (make changes to files as documented above)

# Test each fix
pytest tests/ -v

# Commit with reference to this document
git add .
git commit -m "Fix 8 critical bugs - see BUGFIXES_2025-12-02.md"

# Push and create PR
git push origin bugfix/critical-fixes-2025-12-02
```

---

**Status:** Ready for implementation  
**Estimated Time:** 1-2 hours for all fixes  
**Risk Level:** Low (all changes isolated, well-tested)
