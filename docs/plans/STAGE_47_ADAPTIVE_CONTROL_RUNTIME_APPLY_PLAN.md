# FFE Stage 47 — Adaptive Control Runtime Apply Seam

## Why this stage exists

Stage 46 closed the **adaptive control snapshot** seam: a normalized, policy-selection-facing summary that adaptive-control-persistence artifacts can progress into snapshot-ready / serialization-ready control artifacts.

The next careful seam in the live repo is **adaptive control runtime apply**.

This is the first layer where we preserve a normalized, policy-facing record that adaptive-control-snapshot artifacts can progress into **runtime-applied control updates**, grounded in the repo's real config mutation and apply pathways, without collapsing into raw HTTP request/response payload contracts or final YAML file serialization details.

## Live repo evidence used for this draft

### Runtime mutation / apply hooks already present
- `finance_feedback_engine/api/bot_control.py`
  - `ConfigUpdateRequest`
  - `@bot_control_router.patch("/config")`
  - `updates_for_ensemble`
  - `response_updates`
  - atomic mutation via copied `config_snapshot`
  - commit via `engine.config.clear()` / `engine.config.update(config_snapshot)`
- `finance_feedback_engine/core.py`
  - `_trigger_ollama_failover(...)`
  - mutation of `enabled_providers`
  - mutation of `provider_weights`
  - runtime application through `ensemble_manager.apply_failover(...)`
- config normalization / merge pathways in:
  - `finance_feedback_engine/utils/config_loader.py`
  - `finance_feedback_engine/utils/config_validator.py`
  - `finance_feedback_engine/utils/config_schema_validator.py`

### Runtime control concepts still clearly in play
- `enabled_providers`
- `provider_weights`
- `base_weights`
- failover / fallback application
- atomic config snapshot / replace semantics

## Stage 47 scope

### Build from
- Stage 46 adaptive-control-snapshot summaries
- real runtime apply semantics already visible in the repo:
  - config snapshot mutation
  - ensemble update collection
  - atomic config replacement
  - failover / enabled-provider mutation

### Still explicitly NOT this stage
- raw FastAPI request/response schemas as the main abstraction target
- YAML file write format / disk serialization details
- dashboard / websocket / webhook payloads
- external control-plane auth / transport concerns
- Thompson posterior math
- Kelly sizing internals

## Careful seam definition

### adaptive-control-runtime-apply-ready
A normalized policy-selection layer that says:
- how many comparable adaptive-control-snapshot artifacts progressed into runtime-apply-ready control updates
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely summarize those apply-ready control updates for downstream persistence / transport layers

It does **not** yet promise concrete HTTP payload shape, endpoint semantics, or file-on-disk serialization fidelity.

## Why this is the smallest honest next seam

The repo now clearly contains two kinds of state movement after snapshot formation:
1. **runtime application** (`bot_control.py`, `core.py`, failover hooks, config snapshot replacement)
2. **serialization / transport detail** (request/response contracts, YAML/runtime-file specifics)

Those are not the same thing.

A good seam keeps them separate.

So Stage 47 should model the **runtime apply** concept first:
- a control snapshot becomes an apply-ready / runtime-applied control artifact
- later stages can decide whether to break out HTTP/control-plane contract shape, file serialization, or durable runtime config materialization separately

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_control_runtime_apply_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_control_runtime_apply_summary(...)`
3. **PR-3** — end-to-end adaptive-control-runtime-apply chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_control_runtime_apply_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are still following the same seam discipline used across the prior stages:
- derive from live repo evidence, not stale intention alone
- keep one narrow abstraction layer at a time
- prefer policy-facing summaries before raw transport or persistence payloads
- keep the system re-derivable, auditable, and understandable

## Documentation cohesion note
This stage continues the policy of keeping roadmap growth in `docs/plans/` rather than inflating the root README with every migration seam.
