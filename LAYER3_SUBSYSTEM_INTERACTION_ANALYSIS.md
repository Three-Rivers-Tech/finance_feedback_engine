# Layer 3 Analysis: Deep Subsystem Interaction Analysis

**Date:** 2026-01-10
**Scope:** Complex cross-cutting concerns in finance_feedback_engine
**Context:** Building on 47 Layer 2 issues, 5 critical blockers for "First Profitable Trade"

---

## Executive Summary

This Layer 3 analysis identifies **23 complex interaction issues** across 6 critical pathways.
These issues are NOT visible in isolated subsystem testing and represent cascading failure 
scenarios, race conditions, and data consistency problems that emerge only at integration points.

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 4 | Can cause financial loss, data corruption |
| HIGH | 9 | Can cause trade failures, inconsistent state |
| MEDIUM | 7 | Can cause degraded performance, unexpected behavior |
| LOW | 3 | Minor issues, edge cases |

---

## 1. Agent <-> Data Provider <-> Risk Management Chain

### Interaction Pathway Diagram

```
                                    ┌─────────────────┐
                                    │  Data Providers │
                                    │ (Alpha Vantage, │
                                    │  Coinbase, etc) │
                                    └────────┬────────┘
                                             │
                                             ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ TradingLoopAgent│◀───│FinanceFeedback  │◀───│ CircuitBreaker  │
│ (OODA States)   │    │Engine.analyze() │    │ (5 failures=    │
│                 │    │                 │    │  60s timeout)   │
└────────┬────────┘    └────────┬────────┘    └─────────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────┐
│  RiskGatekeeper │    │  Decision Store │
│  .validate_trade│    │  (JSON files)   │
└─────────────────┘    └─────────────────┘
```

### ISSUE L3-001: Race Between State Transition and Data Fetch [CRITICAL]

**Location:** `finance_feedback_engine/agent/trading_loop_agent.py:1262-1430` (handle_reasoning_state)

**Problem:** The agent transitions from PERCEPTION to REASONING before verifying data freshness.
Market data is fetched during REASONING, but the decision to transition happens in PERCEPTION 
based on time elapsed, not data availability.

**Race Condition Scenario:**
1. Agent in PERCEPTION at T=0
2. Data provider (Alpha Vantage) has stale data (59+ minutes old)
3. Agent transitions to REASONING at T=1 (based on analysis_frequency_seconds)
4. REASONING fetches stale data, generates decision
5. RiskGatekeeper.check_market_hours() detects staleness but AFTER decision generation
6. Resources wasted on LLM calls with invalid data

**Code Evidence:**
```python
# trading_loop_agent.py:1162 - PERCEPTION state
async def handle_perception_state(self):
    # ... safety checks only ...
    # NOTE: No data freshness validation here!
    await self._transition_to(AgentState.REASONING)  # Unconditional transition
```

**Impact:** Wasted LLM API calls, potential stale-data decisions if RiskGatekeeper fails

**Fix Required:** Add data freshness pre-check in PERCEPTION before REASONING transition


### ISSUE L3-002: Circuit Breaker State Not Shared Across Subsystems [HIGH]

**Location:** 
- `finance_feedback_engine/utils/circuit_breaker.py:27-340`
- `finance_feedback_engine/core.py:1508-1520`
- `finance_feedback_engine/trading_platforms/unified_platform.py:127-145`

**Problem:** Circuit breakers are instantiated independently in multiple locations:
1. FinanceFeedbackEngine.execute_decision() creates local breaker if platform lacks one
2. UnifiedTradingPlatform.execute_trade() creates local breaker lazily
3. Each data provider may have its own breaker

**Interaction Bug:**
- Data provider circuit breaker OPEN (Alpha Vantage down)
- Agent continues to REASONING state
- LLM generates decision based on cached/stale data
- Execution circuit breaker CLOSED
- Trade executes with outdated market context

**Code Evidence:**
```python
# core.py:1508 - Creates LOCAL breaker, not aware of data provider state
if breaker is None:
    cb_name = f"execute_trade:{self.trading_platform.__class__.__name__}"
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60, name=cb_name)
```

**Impact:** Trades can execute when data layer is degraded

**Fix Required:** Centralized circuit breaker registry with cross-subsystem awareness


### ISSUE L3-003: Analysis Failure Decay Creates Stale Asset Exclusions [MEDIUM]

**Location:** `finance_feedback_engine/agent/trading_loop_agent.py:1305-1318`

**Problem:** The `analysis_failures` dict uses time-based decay (`reasoning_failure_decay_seconds`)
but the decay check happens at the START of REASONING, not continuously.

**Scenario:**
1. BTCUSD analysis fails 5 times at T=0
2. `analysis_failures["analysis:BTCUSD"] = 5`
3. Agent enters IDLE for 300 seconds
4. At T=300, enters PERCEPTION -> REASONING
5. Decay check at T=300: only 300s passed, decay is 120s default
6. BTCUSD still excluded even though 3 full decay periods passed

**The actual logic:**
```python
# trading_loop_agent.py:1305
if (current_time - last_fail).total_seconds() > self.config.reasoning_failure_decay_seconds:
    # Reset only happens if THIS specific check runs
```

**Impact:** Assets may be excluded for longer than intended

**Severity:** Medium - affects asset coverage, not correctness


### ISSUE L3-004: Cascading Staleness from _multi_timeframe_cache [HIGH]

**Location:** `finance_feedback_engine/monitoring/trade_monitor.py:655-700` (_maybe_execute_market_pulse)

**Problem:** The multi-timeframe cache has a 2x pulse_interval staleness threshold (default 10 min).
If the pulse fails repeatedly, the cache returns None, but callers may not handle this gracefully.

**Cascade Path:**
1. TradeMonitor._maybe_execute_market_pulse() fails for asset
2. _multi_timeframe_cache[asset] not updated
3. get_latest_market_context() returns None after 10 minutes
4. MonitoringContextProvider.get_monitoring_context() gets incomplete data
5. RiskGatekeeper.validate_trade() receives partial context
6. Decision may pass validation that should have failed

**Impact:** Risk validation with incomplete market context


---

## 2. Backtesting <-> Decision Cache <-> Memory System

### Interaction Pathway Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Backtester    │───▶│  DecisionCache  │───▶│ PortfolioMemory │
│   (multiple     │    │  (SQLite WAL)   │    │ Engine (JSON)   │
│   instances?)   │    │                 │    │                 │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         │                      ▼                      ▼
         │             ┌─────────────────┐    ┌─────────────────┐
         └────────────▶│  LLM Providers  │    │  File System    │
                       │  (rate limited) │    │  (atomic write) │
                       └─────────────────┘    └─────────────────┘
```

### ISSUE L3-005: Parallel Backtest Shared Cache Corruption [CRITICAL]

**Location:** `finance_feedback_engine/backtesting/decision_cache.py:20-382`

**Problem:** DecisionCache uses SQLite with WAL mode and connection pooling, BUT:
1. Cache key is `{asset_pair}_{timestamp}_{market_hash}`
2. Two parallel backtests on same asset with different configs will share cache
3. Market hash does NOT include backtest config (slippage, fees, etc.)

**Scenario:**
1. Backtest A: BTCUSD, slippage=0.05%, fees=0.1%
2. Backtest B: BTCUSD, slippage=0.01%, fees=0.05%
3. Both generate same cache key for same timestamp
4. Backtest A stores decision (based on higher costs)
5. Backtest B retrieves A's decision (wrong for lower costs)

**Code Evidence:**
```python
# decision_cache.py:178
def _hash_market_data(self, market_data: Dict[str, Any]) -> str:
    hashable_fields = {
        k: v for k, v in market_data.items()
        if k not in ["timestamp", "historical_data"]  # No backtest config!
    }
```

**Impact:** Backtest results contaminated across runs with different configs

**NOT IN LINEAR** - Needs new issue


### ISSUE L3-006: Memory Pollution Between Live and Backtest [HIGH]

**Location:** 
- `finance_feedback_engine/memory/portfolio_memory.py:211-359` (record_trade_outcome)
- Memory uses `self.storage_path` which is NOT guaranteed to be isolated

**Problem:** Documentation mentions `memory_isolation_mode: true` for backtesting, but:
1. PortfolioMemoryEngine.__init__ doesn't enforce isolation
2. If misconfigured, backtest outcomes pollute live memory
3. Provider performance metrics from synthetic backtest trades affect live trading

**Scenario:**
1. Backtest runs with `memory_isolation_mode: false` (misconfiguration)
2. 1000 synthetic trades recorded
3. Provider weights updated based on backtest data
4. Live trading starts, uses polluted provider recommendations

**Impact:** Live trading decisions influenced by non-real-market data


### ISSUE L3-007: Session Metrics Not Thread-Safe [MEDIUM]

**Location:** `finance_feedback_engine/backtesting/decision_cache.py:63-68`

**Problem:** `session_hits` and `session_misses` are simple integer attributes without locking:
```python
self.session_hits = 0
self.session_misses = 0
```

In `get()`:
```python
if result:
    self.session_hits += 1  # Not atomic!
else:
    self.session_misses += 1  # Not atomic!
```

**Impact:** Inaccurate cache statistics under concurrent access


### ISSUE L3-008: Connection Pool Exhaustion Under Parallel Backtests [HIGH]

**Location:** `finance_feedback_engine/backtesting/decision_cache.py:94-133`

**Problem:** Pool has max_connections=5 default. Under heavy parallel backtest load:
1. All 5 connections checked out
2. New requests create "temporary connections" (line 106-108)
3. Temporary connections bypass WAL coordination
4. Potential write conflicts

**Code Evidence:**
```python
except queue.Empty:
    logger.warning("Connection pool exhausted, creating temporary connection")
    conn = self._create_connection()
    conn_from_pool = False  # Temporary, closed after use
```

**Impact:** Database lock contention, potential corruption under high load


---

## 3. API <-> Agent <-> WebSocket Streams

### Interaction Pathway Diagram

```
┌─────────────────┐                    ┌─────────────────┐
│  REST API       │◀──────────────────▶│  WebSocket      │
│  /bot/start     │                    │  /ws            │
│  /bot/stop      │                    │                 │
└────────┬────────┘                    └────────┬────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  _agent_lock    │───▶│  _agent_instance│───▶│  BotState       │
│  (asyncio.Lock) │    │  (global)       │    │  (enum)         │
└─────────────────┘    └────────┬────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ TradingLoopAgent│
                       │ (AgentState)    │
                       └─────────────────┘
```

### ISSUE L3-009: Dual State Representation Inconsistency [CRITICAL]

**Location:**
- `finance_feedback_engine/api/bot_control.py:58` (BotState enum)
- `finance_feedback_engine/agent/trading_loop_agent.py:38` (AgentState enum)

**Problem:** Two independent state enums with no synchronization:

```python
# bot_control.py
class BotState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

# trading_loop_agent.py
class AgentState(Enum):
    IDLE = "idle"
    PERCEPTION = "perception"
    REASONING = "reasoning"
    RISK_CHECK = "risk_check"
    EXECUTION = "execution"
    LEARNING = "learning"
    RECOVERING = "recovering"
```

**Inconsistency Scenario:**
1. API reports BotState.RUNNING
2. Agent internally in AgentState.RECOVERING (after error)
3. API client sees "running" but agent is not processing new trades
4. Client doesn't know recovery is happening

**Code Evidence:**
```python
# bot_control.py:488 - Returns BotState but also includes agent_ooda_state
return AgentStatusResponse(
    state=BotState.RUNNING,
    agent_ooda_state=(_agent_instance.state.name if _agent_instance else None),
    # Two different state views returned!
)
```

**Impact:** Clients may have incorrect understanding of agent operational status


### ISSUE L3-010: WebSocket Client Mid-Cycle Connection [HIGH]

**Location:** `finance_feedback_engine/api/bot_control.py:859-980` (agent_websocket)

**Problem:** When a WebSocket client connects mid-cycle:
1. No initial state dump is sent
2. Client misses all events since agent started
3. `_build_stream_payload` only sends current state, not history

**Code Evidence:**
```python
async def sender() -> None:
    last_status_sent = 0.0
    while not stop_event.is_set():
        payload, last_status_sent = await _build_stream_payload(engine, last_status_sent)
        await websocket.send_json(payload)  # Only current state!
```

**Impact:** New clients have incomplete view of agent history


### ISSUE L3-011: Agent Shutdown Race with Active WebSocket [HIGH]

**Location:** `finance_feedback_engine/api/bot_control.py:369-418` (stop_agent)

**Problem:** stop_agent() cancels _agent_task but WebSocket sender loop continues:
1. stop_agent() called
2. _agent_instance.stop() signals agent
3. _agent_task.cancel() issued
4. WebSocket sender still polling for status
5. _agent_instance = None
6. WebSocket sender accesses None, raises exception

**Code Evidence:**
```python
# stop_agent:398
_agent_instance = None  # Set to None immediately
_agent_task = None

# But WebSocket sender (still running) will try:
payload, _ = await _build_stream_payload(engine, last_status_sent)
# _build_stream_payload accesses _agent_instance internally
```

**Impact:** WebSocket connections crash on agent stop


### ISSUE L3-012: Queued Start Request Race [MEDIUM]

**Location:** `finance_feedback_engine/api/bot_control.py:154-182`

**Problem:** `_queued_start_request` is a single slot. If two start requests arrive:
1. First request queued while agent stopping
2. Second request arrives, overwrites first
3. First request's config lost

**Code Evidence:**
```python
# bot_control.py:173
_queued_start_request = (request, engine)  # Overwrites any existing!
```

**Impact:** Start request silently dropped


---

## 4. Risk Gatekeeper <-> Position Sizing <-> Platform Execution

### Interaction Pathway Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  DecisionEngine │───▶│ RiskGatekeeper  │───▶│UnifiedPlatform  │
│  (sizing calc)  │    │ .validate_trade │    │ .execute_trade  │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ recommended_    │    │ monitoring_     │    │ CircuitBreaker  │
│ position_size   │    │ context         │    │ (per platform)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ISSUE L3-013: Position Sizing Calculated BEFORE Risk Check [CRITICAL]

**Location:**
- Decision generation includes `recommended_position_size`
- RiskGatekeeper validates AFTER sizing calculated

**Problem:** The recommended_position_size in the decision is calculated during 
analyze_asset() BEFORE RiskGatekeeper validation. If risk limits change between
analysis and execution:

1. analyze_asset() calculates position_size = 0.5 BTC (based on current risk limits)
2. Risk limits updated (admin action, or market volatility)
3. Decision queued for execution
4. RiskGatekeeper revalidates with NEW limits
5. Position size (0.5 BTC) may now violate new limits

**Impact:** Position size may be stale relative to current risk parameters

**NOT IN LINEAR** - Needs new issue


### ISSUE L3-014: Platform Failure After Risk Approval [HIGH]

**Location:**
- `finance_feedback_engine/core.py:1555-1653` (execute_decision_async)
- `finance_feedback_engine/trading_platforms/unified_platform.py:106-176`

**Problem:** Between RiskGatekeeper approval and platform execution:
1. RiskGatekeeper approves trade at T=0
2. Platform connection drops at T=1ms
3. CircuitBreaker catches failure
4. Decision marked as failed
5. No mechanism to UNDO risk approval

**State Inconsistency:**
- RiskGatekeeper "approved" the trade
- Trade didn't execute
- But approval was recorded (metrics updated)
- Next trade may be rejected due to "concentration" from phantom trade

**Code Evidence:**
```python
# core.py:1499 - Risk approved, metrics updated
update_decision_confidence(asset_pair, decision.get("action"), float(confidence))

# core.py:1619 - But execution can still fail
except Exception as e:
    decision["execution_result"] = {"success": False, "error": str(e)}
```

**Impact:** Risk metrics may be inaccurate after execution failures


### ISSUE L3-015: Duplicate RiskGatekeeper Instantiation [MEDIUM]

**Location:**
- `finance_feedback_engine/agent/trading_loop_agent.py:196` (agent creates gatekeeper)
- `finance_feedback_engine/core.py:1487` (engine creates new gatekeeper for execute_decision)

**Problem:** Two different RiskGatekeeper instances with potentially different configs:
1. TradingLoopAgent.risk_gatekeeper (used in RISK_CHECK state)
2. FinanceFeedbackEngine.execute_decision() creates NEW gatekeeper (line 1487)

**Code Evidence:**
```python
# core.py:1487 - Creates fresh gatekeeper with defaults!
from .risk.gatekeeper import RiskGatekeeper
gatekeeper = RiskGatekeeper()  # DEFAULT config, not agent's config!
```

**Impact:** Double validation with potentially inconsistent thresholds


### ISSUE L3-016: Position Tracking Across Platform Reconnects [HIGH]

**Location:**
- `finance_feedback_engine/monitoring/trade_monitor.py:396-445` (_detect_new_trades)

**Problem:** Position detection uses a hash of `product_id:side:entry_price`:
```python
stable_key = f"{product_id}:{side}:{entry_price:.8f}"
trade_id = hashlib.sha256(stable_key.encode()).hexdigest()[:16]
```

After platform reconnect:
1. Existing position still open on exchange
2. TradeMonitor detects it as "new" trade (if not in tracked_trade_ids)
3. Creates duplicate tracker
4. Duplicate feedback recorded

**Impact:** Duplicate trade tracking and memory pollution


---

## 5. Portfolio Memory <-> Trade Monitor <-> Decision Engine

### Interaction Pathway Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ TradingLoopAgent│───▶│  TradeMonitor   │───▶│ PortfolioMemory │
│ LEARNING state  │    │ .get_closed_    │    │ .record_trade_  │
│                 │    │  trades()       │    │  outcome()      │
└────────┬────────┘    └────────┬────────┘    └────────┬────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Decision Queue  │    │ closed_trades_  │    │  File System    │
│ _current_       │    │ queue (Queue)   │    │  (JSON save)    │
│ decisions       │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### ISSUE L3-017: Race Between Decision and Trade Outcome [HIGH]

**Location:**
- `finance_feedback_engine/agent/trading_loop_agent.py:1867-1893` (handle_learning_state)
- `finance_feedback_engine/memory/portfolio_memory.py:211-359` (record_trade_outcome)

**Problem:** The feedback loop has timing ambiguity:
1. Agent in EXECUTION, trade submitted
2. Platform executes trade instantly (T=0)
3. Agent transitions to LEARNING (T=10ms)
4. TradeMonitor hasn't detected closed trade yet (detection_interval=30s)
5. LEARNING state finds no closed trades
6. Agent transitions to PERCEPTION
7. Trade closes at T=100ms
8. TradeMonitor detects at T=30s
9. But agent is now in different cycle

**Impact:** Delayed feedback, potentially missed learning updates


### ISSUE L3-018: Memory Consistency During Agent Restart [HIGH]

**Location:**
- `finance_feedback_engine/memory/portfolio_memory.py:1720-1736` (save_memory)
- Uses `_atomic_write_file` but only for individual files

**Problem:** Memory state is saved across multiple files:
1. `provider_performance.json`
2. `regime_performance.json`
3. Individual trade outcome files

If agent crashes mid-save:
1. `provider_performance.json` written
2. CRASH
3. `regime_performance.json` NOT written
4. Restart loads inconsistent state

**Impact:** Inconsistent memory state after crash


### ISSUE L3-019: Decision History Corruption via Concurrent Updates [MEDIUM]

**Location:** `finance_feedback_engine/persistence/decision_store.py:149-182` (update_decision)

**Problem:** DecisionStore uses file-based storage without locking:
```python
def update_decision(self, decision: Dict[str, Any]) -> None:
    # ... find file ...
    self.file_io.write_json(relative_path, decision, atomic=True, backup=True)
```

If two updates to same decision happen concurrently:
1. Thread A reads decision at T=0
2. Thread B reads decision at T=0
3. Thread A writes update at T=1
4. Thread B writes update at T=2 (overwrites A's changes)

**Impact:** Decision updates may be lost


---

## 6. Observability <-> All Subsystems

### Interaction Pathway Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ OpenTelemetry   │◀───│ All Subsystems  │───▶│ Prometheus      │
│ Tracer          │    │ (spans, metrics)│    │ Metrics         │
└────────┬────────┘    └─────────────────┘    └────────┬────────┘
         │                                             │
         ▼                                             ▼
┌─────────────────┐                           ┌─────────────────┐
│ Jaeger/OTLP     │                           │ /metrics        │
│ Exporter        │                           │ endpoint        │
└─────────────────┘                           └─────────────────┘
```

### ISSUE L3-020: OpenTelemetry Context Not Propagated Across Threads [HIGH]

**Location:**
- `finance_feedback_engine/monitoring/trade_monitor.py:78-81` (ThreadPoolExecutor)
- `finance_feedback_engine/observability/context.py:42-66` (with_span)

**Problem:** TradeMonitor spawns threads via ThreadPoolExecutor:
```python
self.executor = ThreadPoolExecutor(
    max_workers=self.MAX_CONCURRENT_TRADES, thread_name_prefix="TradeMonitor"
)
```

OpenTelemetry context is thread-local and NOT propagated:
```python
# Span in main thread
with with_span(tracer, "trade_execution"):
    self.executor.submit(tracker.run)  # Child thread has NO span context!
```

**Impact:** Traces broken across thread boundaries, incomplete observability


### ISSUE L3-021: Metrics Recording Blocking Critical Paths [MEDIUM]

**Location:** Multiple locations where metrics are recorded synchronously:
- `finance_feedback_engine/monitoring/prometheus.py` (all update_* functions)
- `finance_feedback_engine/risk/gatekeeper.py:288` (metrics recording)

**Problem:** Prometheus metrics are recorded in-line on the critical path:
```python
# gatekeeper.py:288
self._metrics["ffe_risk_blocks_total"].add(1, {"reason": "max_drawdown", ...})
```

If Prometheus client has issues:
1. Exception from metrics library
2. Caught by outer try-except
3. But adds latency to critical path

**Impact:** Observability failures can slow trading decisions


### ISSUE L3-022: Log Aggregation Missing Correlation ID [MEDIUM]

**Location:** `finance_feedback_engine/observability/context.py:69-95`

**Problem:** `_correlation_id_var` uses ContextVar but:
1. Not consistently set at entry points
2. WebSocket handlers don't set correlation ID
3. Background threads (TradeMonitor) don't inherit

**Code Evidence:**
```python
# context.py:73
_correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)

# But in bot_control.py:859 (agent_websocket):
# No call to set_correlation_id()!
```

**Impact:** Log correlation broken for WebSocket and background operations


### ISSUE L3-023: Async Boundary Trace Correlation Failures [LOW]

**Location:**
- `finance_feedback_engine/observability/tracer.py:124-139` (get_tracer)
- Multiple async/await boundaries in agent code

**Problem:** When crossing async boundaries (await points), span context may not 
propagate correctly if using sync tracer operations inside async functions.

**Impact:** Some spans may be orphaned or incorrectly parented


---

## Full Trade Execution Path - Failure Points

```
Market Data Fetch ──────────────────────────────────────────────────────────────────
     │ [L3-001] Stale data can bypass freshness check
     │ [L3-004] Multi-timeframe cache may return None
     ▼
Decision Generation ────────────────────────────────────────────────────────────────
     │ [L3-002] Circuit breaker state not shared
     │ [L3-005] Backtest cache contamination
     ▼
Risk Check ─────────────────────────────────────────────────────────────────────────
     │ [L3-013] Position sizing calculated before risk check
     │ [L3-015] Duplicate gatekeeper instances
     │ [L3-009] Dual state representation
     ▼
Execution ──────────────────────────────────────────────────────────────────────────
     │ [L3-014] Platform failure after risk approval
     │ [L3-016] Position tracking across reconnects
     ▼
Outcome Recording ──────────────────────────────────────────────────────────────────
     │ [L3-017] Race between decision and outcome
     │ [L3-018] Memory consistency during restart
     │ [L3-019] Decision history corruption
     ▼
Learning/Feedback ──────────────────────────────────────────────────────────────────
     │ [L3-006] Memory pollution live/backtest
     │ [L3-020] OTel context not propagated
```

---

## Deadlock Scenarios Identified

### Scenario 1: _agent_lock + _asset_pairs_lock

**Location:**
- `finance_feedback_engine/api/bot_control.py:89` (_agent_lock)
- `finance_feedback_engine/agent/trading_loop_agent.py:1269` (_asset_pairs_lock)

**Potential Deadlock:**
```
Thread A (API): acquire _agent_lock -> call agent method -> need _asset_pairs_lock
Thread B (Agent): acquire _asset_pairs_lock -> call API callback -> need _agent_lock
```

**Mitigation:** Lock ordering is NOT documented or enforced.


### Scenario 2: SQLite WAL + Connection Pool

**Location:** `finance_feedback_engine/backtesting/decision_cache.py`

**Potential Deadlock:**
```
Thread A: Pool connection 1 -> BEGIN IMMEDIATE transaction -> waiting for lock
Thread B: Pool connection 2 -> BEGIN IMMEDIATE transaction -> waiting for lock
Thread C: Needs Pool connection -> Pool exhausted -> creates temp connection -> lock conflict
```

**Mitigation:** WAL mode helps but pool exhaustion creates risk.


---

## Data Consistency Guarantees Assessment

| Subsystem | Consistency Model | Transaction Boundary | Rollback Support |
|-----------|-------------------|---------------------|------------------|
| DecisionCache | Eventual (WAL) | Per-query | SQLite auto |
| DecisionStore | None (files) | Per-file | No |
| PortfolioMemory | None (files) | Per-file | No |
| TradeMonitor | In-memory | None | No |
| Agent State | In-memory | None | RECOVERING state |

**Critical Gap:** No cross-subsystem transaction support. A decision can be:
- Saved to DecisionStore
- Executed on platform
- But NOT recorded in PortfolioMemory (if crash between)


---

## Timing Assumptions and Race Windows

| Assumption | Location | Race Window | Impact |
|------------|----------|-------------|--------|
| Data fresh within 5 min | RiskGatekeeper | 0-5 min | Stale data trades |
| Trade executes < 90s | REASONING timeout | 0-90s | Timeout false positive |
| Closed trade detected < 30s | TradeMonitor | 0-30s | Delayed feedback |
| Cache valid 2x pulse interval | get_latest_market_context | 0-10 min | Stale context |
| Decision valid until execution | execute_decision_async | 0-∞ | Market moved |


---

## Issues Verification Against Linear

Checked all 23 issues against THR-* issues in Linear. The following are NOT covered:

| Issue | Description | Recommended Action |
|-------|-------------|-------------------|
| L3-001 | State transition before data validation | Create new ticket |
| L3-005 | Parallel backtest cache contamination | Create new ticket |
| L3-009 | Dual state representation | Create new ticket |
| L3-013 | Position sizing before risk check | Create new ticket |
| L3-014 | Platform failure after risk approval | Create new ticket |
| L3-017 | Race between decision and outcome | Create new ticket |
| L3-018 | Memory consistency during restart | Create new ticket |
| L3-020 | OTel context not propagated | Create new ticket |


---

## Recommendations by Priority

### Immediate (Block First Profitable Trade)

1. **L3-009:** Unify BotState and AgentState - clients need accurate status
2. **L3-013:** Recalculate position size at execution time, not analysis time
3. **L3-014:** Implement risk approval rollback on execution failure

### High Priority (Production Stability)

4. **L3-001:** Add data freshness pre-check in PERCEPTION state
5. **L3-002:** Centralized circuit breaker registry
6. **L3-005:** Add backtest config to cache key hash
7. **L3-011:** Graceful WebSocket shutdown on agent stop
8. **L3-017:** Synchronize feedback timing with trade execution

### Medium Priority (Reliability)

9. **L3-018:** Atomic multi-file memory save
10. **L3-020:** Propagate OTel context to child threads
11. **L3-015:** Single RiskGatekeeper instance throughout flow
12. **L3-016:** Idempotent position detection

### Lower Priority (Polish)

13. **L3-007:** Atomic session metrics
14. **L3-012:** Queued request queue (not single slot)
15. **L3-022:** Consistent correlation ID setting


---

## Summary

This Layer 3 analysis reveals that while individual subsystems are well-implemented,
their integration points have significant issues that could cause:

1. **Financial Risk:** Trades executing with stale data or incorrect sizing
2. **Data Corruption:** Memory pollution between live/backtest, decision history loss
3. **Operational Blindness:** Broken traces, inconsistent state reporting
4. **Reliability Degradation:** Cascading failures from circuit breaker gaps

The 4 CRITICAL issues (L3-001, L3-005, L3-009, L3-013) should be addressed before
production deployment or the "First Profitable Trade" milestone can be considered secure.
