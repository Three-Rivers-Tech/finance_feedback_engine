# FFE Stage 46 — Adaptive Control Snapshot Seam

## Why this stage exists

Stage 45 closed the **adaptive control persistence** seam: a normalized, policy-selection-facing summary that adaptive weight-mutation artifacts can progress into persistence-ready / apply-ready control state.

The next careful seam is **adaptive control snapshot**.

This is the first layer where we preserve a normalized, policy-facing record that adaptive control persistence artifacts can progress into serialization-ready / snapshot-ready control artifacts, without collapsing into raw YAML/JSON config serialization, API patch payload schemas, or dashboard/webhook export details.

## Stage 46 scope

### Build from
- Stage 45 adaptive-control-persistence summaries
- existing runtime concepts already present in live code:
  - `base_weights`
  - `provider_weights`
  - enabled-provider state
  - config/load/save pathways touched by adaptive control
  - snapshot-like control state that bridges runtime mutation into durable representation

### Still explicitly NOT this stage
- raw YAML/JSON serialization formats
- gateway/API patch payload contracts
- dashboard / webhook / reporting output schemas
- Thompson posterior math
- Kelly sizing internals
- final migration collapse of adaptive-control implementation details

## Careful seam definition

### adaptive-control-snapshot-ready
A normalized policy-selection layer that says:
- how many comparable adaptive-control-persistence artifacts progressed into snapshot-ready / serialization-ready control artifacts
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those adaptive-control-snapshot summaries for downstream persistence checks

It does **not** yet promise raw config-file-grade or API-payload-grade fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_control_snapshot_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_control_snapshot_summary(...)`
3. **PR-3** — end-to-end adaptive-control-snapshot chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_control_snapshot_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–45:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from adaptive-control persistence into raw config serialization or external export payloads

## Why this is conservative in the right way
Adaptive control persistence answers “did the mutation artifact become a normalized persistence-ready / apply-ready control artifact?”
Adaptive control snapshot answers “did that control artifact become a normalized snapshot-ready / serialization-ready artifact?”

That is the smallest next seam that reflects the live repo shape (`base_weights`, `provider_weights`, enabled-provider state, config/load/save bridges) without prematurely modeling raw config serialization or external payload details.

## Documentation cohesion note
As the stage chain grows, prefer small index-style docs that point at stage plans rather than letting one README absorb every migration detail.
