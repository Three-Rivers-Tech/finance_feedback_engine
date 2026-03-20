# FFE Stage 50 — Adaptive Control Config Update Transport Contract Seam

## Why this stage exists

Stage 49 closed the **adaptive control runtime config materialization** seam: a normalized, policy-selection-facing summary that adaptive-control-config-patch-contract artifacts can progress into runtime-config-materialization-ready updates, grounded in the repo's real runtime-config file pathways and file I/O semantics.

The next careful seam in the live repo is **adaptive control config update transport contract**.

This is the layer where the repo turns internal adaptive-control update intent into a concrete authenticated control-plane exchange around the `/config` update path, including request validation, status shaping, and returned update payloads, without yet collapsing into websocket/dashboard streaming or broader agent lifecycle/restart orchestration.

## Live repo evidence used for this draft

### `/config` control-plane endpoint already exists
- `finance_feedback_engine/api/bot_control.py`
  - `@bot_control_router.patch("/config")`
  - `request: ConfigUpdateRequest`
  - `_api_user: str = Depends(verify_api_key_or_dev)`
  - `config_snapshot = copy.deepcopy(engine.config)`
  - `updates_for_agent`
  - `updates_for_ensemble`
  - `response_updates`
  - `engine.config.clear()`
  - `engine.config.update(config_snapshot)`
  - return payload:
    - `"status": "updated"`
    - `"updates": response_updates`
    - `"timestamp": datetime.now(UTC).isoformat()`

### Transport-contract / error-shaping evidence already visible
- `finance_feedback_engine/api/bot_control.py`
  - `HTTPException`
  - `status.HTTP_400_BAD_REQUEST`
  - `status.HTTP_500_INTERNAL_SERVER_ERROR`
  - numeric / mapping validation for:
    - `stop_loss_pct`
    - `position_size_pct`
    - `confidence_threshold`
    - `max_concurrent_trades`
    - `provider_weights`
- authenticated control dependency already explicit:
  - `verify_api_key_or_dev`

## Why this is the next honest seam

The live repo still separates at least three nearby concerns:
1. runtime config materialization / runtime-local config persistence semantics
2. authenticated config update transport contract (`PATCH /config` request/response/error behavior)
3. broader operational behavior such as restart/reload propagation, websocket/dashboard fanout, and cross-process rollout guarantees

Stage 49 covered the first.
Stage 50 should cover the second.
A later stage can decide whether restart/reload propagation deserves its own seam.

## Stage 50 scope

### Build from
- Stage 49 adaptive-control-runtime-config-materialization summaries
- live repo evidence around the authenticated `/config` control path:
  - `ConfigUpdateRequest`
  - `verify_api_key_or_dev`
  - `HTTPException`
  - `status.HTTP_*`
  - `response_updates`
  - atomic `engine.config` replacement

### Stage 50 should preserve as policy-facing signals
- how many comparable adaptive-control-runtime-config-materialization artifacts progressed into config-update-transport-contract-ready updates
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- that downstream transport-facing summaries can still be exported and persisted without turning into an opaque “API call happened” blob

## Still explicitly NOT this stage
- websocket / dashboard / SSE payload schemas
- manual-trade transport behavior
- agent stop/start/pause/resume lifecycle semantics
- restart / reload / hot-reconfigure propagation across processes
- health/readiness endpoint aggregation
- infra deployment orchestration
- Thompson posterior math
- Kelly sizing internals

## Careful seam definition

### adaptive-control-config-update-transport-contract-ready
A normalized policy-selection layer that says:
- adaptive-control-runtime-config-materialization artifacts were eligible to progress into an authenticated config-update transport exchange
- the transport-facing summary preserves request/response contract shape discipline
- validation/error/result semantics remain representable as auditable control outcomes

It does **not** yet promise websocket fanout, process restart semantics, or full operational rollout guarantees.

## Why not jump straight to restart / lifecycle behavior
The repo evidence for restart / lifecycle behavior is broader and less narrowly coupled to adaptive-control config updates than the `/config` transport contract itself. Right now the smallest, most legible next seam is still the authenticated control-plane boundary where materialized runtime config intent becomes a concrete update request/response contract.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_control_config_update_transport_contract_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_control_config_update_transport_contract_summary(...)`
3. **PR-3** — end-to-end adaptive-control-config-update-transport-contract chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_control_config_update_transport_contract_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are still following the same seam discipline used across the prior stages:
- derive from live repo evidence, not stale intention alone
- keep one narrow abstraction layer at a time
- prefer policy-facing summaries before broader operational side effects
- keep the system auditable, understandable, and re-derivable later

## Documentation cohesion note
Keep the seam trail in `docs/plans/` instead of bloating root docs with migration-by-migration detail.
