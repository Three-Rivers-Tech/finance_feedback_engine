# Triage: missing `execute_decision_async` execution entrypoint

## Symptom
Live backend logs showed autonomous execution reaching the direct-execution branch and then failing with:

- `'FinanceFeedbackEngine' object has no attribute 'execute_decision_async'`

Observed sequence:
- trade approved by RiskGatekeeper
- autonomous execution enabled
- `trading_loop_agent.handle_execution_state()` attempted `await self.engine.execute_decision_async(decision_id)`
- execution raised `AttributeError`

## Root cause
`finance_feedback_engine/agent/trading_loop_agent.py` still relies on an async engine execution API, but the current `FinanceFeedbackEngine` implementation in `finance_feedback_engine/core.py` only exposes the synchronous `execute_decision(...)` method. The async method is missing from the live class, even though tests and call sites still expect it.

## Fix plan
1. Restore a minimal async `FinanceFeedbackEngine.execute_decision_async(...)` entrypoint in `core.py`.
2. Reuse the same decision loading / preparation / validation semantics as `execute_decision(...)`.
3. Prefer the platform async trade API when available (`aexecute_trade`, with compatibility fallback to `aexecute`), preserving persistence updates.
4. Add a focused regression test that proves `handle_execution_state()` no longer crashes when the engine only provides the restored async entrypoint.
5. Run focused core + agent execution tests.

## Risk notes
- Keep changes surgical and behaviorally aligned with existing sync execution.
- Do not broaden execution semantics beyond restoring the missing async path.
- Rebuild/restart will be required for the running container to pick up the fix after commit.
