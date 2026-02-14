# EMERGENCY FIX PLAN - Realign to Project Goals

**Date:** 2026-02-14
**Crisis:** Spot trading added to futures-only project, may have contaminated backtesting
**Goal:** Self-reinforcing long/short LLM council debate local-first trading bot

---

## PROJECT ARCHITECTURE (Correct Understanding)

### Core Design
1. **Debate Council:** Bull (long) vs Bear (short) vs Judge (arbiter)
2. **Local-First:** Ollama models (mistral, llama3.2, deepseek-r1)  
3. **Self-Reinforcing:** Portfolio memory learns from outcomes
4. **Futures Trading:** Coinbase futures + Oanda forex (NO SPOT)
5. **Short-term:** Intraday/swing trading with AI guidance

### Current Config (from config.yaml)
```yaml
ensemble:
  debate_mode: true  # ✅ CORRECT - council debate enabled
  debate_providers:
    bull: "mistral:7b-instruct"           # Long case
    bear: "llama3.2:3b-instruct-fp16"     # Short case  
    judge: "deepseek-r1:8b"               # Arbiter
```

---

## WHAT I BROKE

### 1. ❌ Added Spot Trading to Futures-Only Project
**Files contaminated:**
- `coinbase_platform.py`: Added `_get_spot_positions()` method (147 lines)
- `coinbase_platform.py`: Added `_batch_fetch_prices()` (only needed for spot)
- `cli/main.py`: Added `entry_price=None` handling for spot balances
- `tests/integration/test_coinbase_spot_positions.py`: 309 lines of spot tests

**Impact:** Core trading platform now has spot logic it shouldn't

### 2. ⚠️ Backtesting May Be Contaminated
**Unknown:** Did crypto backtesting use:
- Coinbase sandbox (WRONG - spot data) ❌
- Coinbase production futures (CORRECT) ✅  
- Alpha Vantage (UNKNOWN) ⚠️

**Files at risk:**
- `optuna_results_ethusd.csv` - ETH optimization results
- `data/historical/BTC_USD_M5_5000.parquet` - BTC candles
- `data/historical/ETH_USD_M5_5000.parquet` - ETH candles

**Critical:** If sandbox data was used, all crypto optimization is invalid

### 3. ✅ What's NOT Broken
- THR-237 async outcome recording (unrelated to spot/futures)
- Sandbox URL fix in `_get_client()` (needed)
- Error logging improvements (needed)
- Code cleanup (needed)
- Oanda forex backtesting (correct - Oanda is futures/CFDs)

---

## FIX STRATEGY

### Phase 1: REVERT SPOT CONTAMINATION (30 min)
1. ✅ **Keep:** Sandbox URL fix, error logging, code cleanup, THR-237
2. ❌ **Revert:** All spot position logic
3. 📝 **Document:** Coinbase sandbox limitations

**Actions:**
- Create new branch: `revert/remove-spot-trading`
- Remove `_get_spot_positions()` method
- Remove `_batch_fetch_prices()` (only needed for spot)
- Revert CLI `entry_price=None` handling
- Delete spot integration tests
- Keep futures-only logic
- Update comments to clarify "futures only"

### Phase 2: VERIFY BACKTESTING DATA (15 min)
1. **Check historical data source:**
   - Read `historical_data_provider.py` - where does BTC/ETH data come from?
   - Check if it uses Coinbase API or Alpha Vantage
   - Verify timeframe/candle format matches futures

2. **Validate or invalidate crypto optimization:**
   - If Alpha Vantage → ✅ VALID (crypto spot ≈ futures for backtesting)
   - If Coinbase production futures → ✅ VALID
   - If Coinbase sandbox → ❌ INVALID (re-run needed)

### Phase 3: REALIGN TO DEBATE ARCHITECTURE (30 min)
1. **Verify debate mode works:**
   - Test bull/bear/judge council on GPU laptop Ollama
   - Confirm mistral/llama/deepseek models installed
   - Run single analyze command with debate mode

2. **Validate local-first:**
   - Confirm OLLAMA_HOST=http://192.168.1.75:11434 works
   - Test fallback to cloud providers if Ollama fails
   - Check portfolio memory integration

3. **Document correct usage:**
   - Update README with debate mode examples
   - Clarify futures-only scope
   - Add "Quick Start" for debate council

### Phase 4: PRODUCTION READINESS (15 min)
1. **Fix Coinbase account issue:**
   - Verify production credentials work
   - Check if account needs funding
   - Or switch to Oanda-only for initial testing

2. **Micro trade validation:**
   - Execute 1-2 micro futures trades
   - Verify debate council makes decision
   - Confirm outcome recording works
   - Check portfolio memory updates

---

## EXECUTION ORDER

**Next 90 minutes:**

1. **[10 min]** Revert spot trading contamination
2. **[10 min]** Verify backtesting data sources  
3. **[20 min]** Test debate mode on Ollama
4. **[20 min]** Validate production Coinbase or switch to Oanda
5. **[20 min]** Execute 1-2 micro futures trades
6. **[10 min]** Verify self-reinforcement (memory updates)

**Success criteria:**
- ✅ Spot logic completely removed
- ✅ Backtesting validity confirmed or re-run planned
- ✅ Debate council working (bull/bear/judge)
- ✅ Local Ollama models responding
- ✅ At least 1 futures trade executed successfully
- ✅ Portfolio memory captures outcome

---

## RISK ASSESSMENT

**High Risk:**
- Crypto backtesting may be invalid (if used sandbox data)
- May need to re-run all BTC/ETH optimization

**Medium Risk:**
- Production Coinbase account has $0 balance
- May need to fund account or use Oanda only

**Low Risk:**
- Spot contamination easily reverted (isolated changes)
- Debate mode already configured correctly
- Ollama server operational

---

**STARTING PHASE 1 NOW...**
