# FFE Performance/Bottleneck Baseline (2026-02-23)

## Scope & Method
Quick baseline focused on:
- Main trading driver (`TradingLoopAgent` + core decision/execution path)
- Test suite pain points and runtime hotspots

Commands run (local venv):
- `pytest -q tests/test_autonomous_bot_integration.py tests/integration/test_order_execution.py tests/data_providers/test_alpha_vantage_coinbase_routing.py tests/test_backtester_execution.py --durations=20 --durations-min=0.05`
- `pytest -q tests/agent tests/backtesting tests/memory tests/monitoring/test_process_monitor.py --durations=20 --durations-min=0.05`

Note: a full-suite run was attempted but did not complete in practical time for this quick baseline; results below combine fresh targeted runs + existing historical full-run artifact (`qa_reports/test_results_full.txt`) for context.

---

## 1) Current pytest status summary

### A. Trading/integration-focused run (fresh)
- **Result:** `35 passed, 2 xfailed, 9 errors, 13 warnings in 55.07s`
- **Exit code:** failed (errors + coverage gate)
- **Pain point:** all 9 errors came from `tests/integration/test_order_execution.py` (Coinbase order execution class + cross-platform cases), indicating fixture/env/integration setup fragility.
- **Coverage gate impact:** session fails with `Required test coverage of 70% not reached` (subset run measured 13.65%).

### B. Agent/backtesting/memory/monitoring run (fresh)
- **Result:** `420 passed, 1 skipped, 410 warnings in 32.33s`
- **Exit code:** failed only because coverage threshold (subset measured 16.21%).
- **Interpretation:** these areas are generally fast/stable in isolation; failure mode is mostly policy/coverage rather than test correctness.

### C. Historical full-suite context (artifact)
From `qa_reports/test_results_full.txt`:
- **Result:** `79 failed, 870 passed, 98 skipped, 3 errors in 141.19s`
- Indicates broader correctness debt beyond performance, but also useful for identifying recurring high-friction modules (data providers, ensemble logic, platform error handling, trading loop agent).

---

## 2) Slowest tests (top 20)

Top 20 from fresh broader run (`tests/agent tests/backtesting tests/memory tests/monitoring/test_process_monitor.py`):

1. 2.11s `tests/agent/test_agent_recovery.py::test_recovery_api_timeout_retry`
2. 2.01s `tests/agent/test_agent_recovery.py::test_recovery_api_failure_all_retries_exhausted`
3. 1.11s `tests/agent/test_agent_recovery.py::test_run_transitions_to_recovering`
4. 0.67s `tests/memory/test_consistency.py::TestTransactionIdGeneration::test_transaction_ids_are_unique`
5. 0.44s `tests/monitoring/test_process_monitor.py::TestProcessOutputCapture::test_timeout_handling`
6. 0.27s `tests/memory/test_memory_persistence.py::TestListSnapshots::test_list_snapshots_sorted_by_time`
7. 0.25s `tests/monitoring/test_process_monitor.py::TestAgentProcessMonitor::test_monitor_cycle_captures_duration`
8. 0.21s `tests/monitoring/test_process_monitor.py::TestAgentProcessMonitor::test_monitor_multiple_cycles`
9. 0.12s teardown `tests/memory/test_memory_persistence.py::TestListSnapshots::test_list_snapshots_sorted_by_time`
10. 0.12s teardown `tests/monitoring/test_process_monitor.py::TestAgentProcessMonitor::test_monitor_cycle_captures_duration`
11. 0.12s teardown `tests/monitoring/test_process_monitor.py::TestAgentProcessMonitor::test_monitor_multiple_cycles`
12. 0.12s teardown `tests/agent/test_agent_recovery.py::test_recovery_api_timeout_retry`
13. 0.12s teardown `tests/memory/test_consistency.py::TestTransactionIdGeneration::test_transaction_ids_are_unique`
14. 0.12s teardown `tests/agent/test_agent_recovery.py::test_run_transitions_to_recovering`
15. 0.12s teardown `tests/monitoring/test_process_monitor.py::TestProcessOutputCapture::test_timeout_handling`
16. 0.12s teardown `tests/agent/test_agent_recovery.py::test_recovery_api_failure_all_retries_exhausted`
17. 0.07s teardown `tests/memory/test_trade_recorder.py::TestUtilityMethods::test_get_summary`
18. 0.06s teardown `tests/monitoring/test_process_monitor.py::TestProcessOutputCapture::test_thread_safety`
19. 0.06s teardown `tests/monitoring/test_process_monitor.py::TestProcessOutputCapture::test_capture_with_correlation_id`
20. 0.06s teardown `tests/monitoring/test_process_monitor.py::TestIntegration::test_capture_with_structured_logging`

Additional notable slow tests from trading-focused run:
- 30.13s `tests/test_autonomous_bot_integration.py::...::test_bot_runs_autonomously_and_executes_profitable_trade` (xfail timeout-driven)
- 20.12s `tests/test_autonomous_bot_integration.py::...::test_bot_autonomous_state_transitions` (xfail timeout-driven)

These two are the dominant runtime pain points in the trading-driver area.

---

## 3) Obvious hot paths (I/O, API calls, model calls)

## A) Main trading driver (`finance_feedback_engine/agent/trading_loop_agent.py`)

### I/O / blocking patterns
- Frequent `logger.info` in tight state transitions and per-asset loops (high log volume under multi-asset configs).
- Dashboard event queue operations every state transition/decision (`_emit_dashboard_event`) with queue contention/drop behavior.
- Recovery path reads/writes decision memory and may close excess positions serially.

### API/network-heavy paths
- `_update_position_mtm()`
  - Pulls portfolio via blocking call wrapped in executor + retry.
  - Per-position price fetches (`_fetch_current_price`) and platform price updates with retries.
- `_fetch_current_price()`
  - Monitoring context call first, then fallback provider API call.
- `handle_reasoning_state()`
  - One analysis call per asset (`analyze_asset_async`), each with up to **90s timeout**.
  - Hard-coded `await asyncio.sleep(15)` between assets (rate-limit guard) multiplies cycle time linearly with asset count.
- `_send_signals_to_telegram()` / `_deliver_webhook()`
  - External delivery with retry/backoff can add user-visible delay.

### Model/decision-heavy paths
- `self.engine.analyze_asset_async(...)` in reasoning loop is the dominant compute/latency contributor.
- `DecisionEngine.generate_decision(...)` (in core/decision stack) may involve ensemble/local model/provider fallbacks.

## B) Monitoring worker (`monitoring/order_status_worker.py`)
- Thread polling loop (`poll_interval` default 30s) repeatedly locks/reads/writes `pending_outcomes.json`.
- File-lock + JSON read/modify/write for each update can become a bottleneck under many pending orders.
- Stale-order timeout only after 100 checks (~50 min), potentially retaining noisy backlog.

## C) Test suite pain-point characteristics
- Integration order execution tests fail in bulk when fixtures/environment are unavailable (high red-noise, low signal).
- Autonomous bot integration tests intentionally timeout/xfail at 20-30s, creating slow unavoidable floor.
- Coverage threshold is enforced on partial runs, making quick feedback loops fail even when assertions pass.

---

## 4) 5 prioritized optimizations (impact/risk)

## 1) Parallelize per-asset reasoning (bounded concurrency) + remove fixed inter-asset sleep
- **What:** Replace serial per-asset `analyze_asset_async` + `sleep(15)` with bounded concurrency (e.g., semaphore) and provider-aware rate limiter/jitter.
- **Expected impact:** **High** (cycle latency reduction 2-5x on multi-asset configs).
- **Risk:** **Medium** (rate-limit behavior and ordering semantics must be preserved).

## 2) Add strict test-mode fast path for autonomous integration tests
- **What:** In tests, stub or compress long waits/timeouts (analysis frequency, polling intervals, timeout decorators) to sub-second simulated time.
- **Expected impact:** **High** (cuts 20-30s tests to low seconds, faster CI feedback).
- **Risk:** **Low-Medium** (must avoid masking true async/state bugs; keep one realistic end-to-end canary).

## 3) Decouple coverage gate from targeted/PR smoke runs
- **What:** Keep coverage enforcement in full nightly/mainline jobs; allow targeted runs to pass without 70% global gate.
- **Expected impact:** **High** developer throughput (large reduction in false-fail loops).
- **Risk:** **Low** (if full-suite coverage gate remains mandatory elsewhere).

## 4) Reduce file-lock churn in `OrderStatusWorker`
- **What:** Batch pending-order updates in memory and flush periodically; use append-log or lightweight DB (SQLite) instead of full JSON rewrite per mutation.
- **Expected impact:** **Medium** (improves scalability under many pending orders; lowers lock contention and I/O).
- **Risk:** **Medium** (migration and failure-recovery semantics need care).

## 5) Add deterministic fixture guards for integration order tests
- **What:** Mark/env-gate true integration tests; ensure fixture contract is explicit (skip fast when creds/services absent), and separate mocked-integration from external-integration.
- **Expected impact:** **Medium-High** (removes 9-error bursts, improves signal-to-noise).
- **Risk:** **Low** (mostly test harness hygiene).

---

## 5) Key actions to execute next (short list)
1. Implement bounded-concurrency reasoning path and replace fixed 15s inter-asset sleep with rate-limiter tokens.
2. Introduce `TEST_FAST_MODE` for autonomous integration tests (short sleeps/timeouts) and keep one real-time canary.
3. Split CI jobs: smoke/targeted (no global coverage gate) vs full/nightly (strict coverage gate).
4. Refactor `pending_outcomes` persistence away from full-file JSON rewrite per event.
5. Harden integration test fixture gating so missing env/services produce skip, not error storms.

---

## Bottom line
The biggest performance drag in trading-driver behavior is serial reasoning with fixed inter-asset sleeps and long per-asset timeouts; the biggest test-suite drag is slow autonomous integration tests plus fragile integration environment assumptions. Addressing those two areas should materially improve both runtime responsiveness and CI feedback speed with moderate implementation risk.
