# FFE Stage 45 — Adaptive Control Persistence Seam

## Why this stage exists

Stage 44 closed the **adaptive weight mutation** seam: a normalized, policy-selection-facing summary that adaptive activation artifacts can progress into provider-weight / provider-control mutation artifacts.

The next careful seam is **adaptive control persistence**.

This is the first layer where we preserve a normalized, policy-facing record that adaptive weight-mutation artifacts can progress into persistence-ready / apply-ready control state, without collapsing into raw config-file serialization, API patch payload schemas, or dashboard/export surfaces.

## Stage 45 scope

### Build from
- Stage 44 adaptive-weight-mutation summaries
- existing runtime concepts already present in live code:
  - persisted provider control state around `base_weights`
  - enabled-provider state mutations
  - config/application hooks in `core.py`
  - failover/apply paths that bridge adaptive control into durable runtime state

### Still explicitly NOT this stage
- raw YAML/JSON config serialization details
- gateway/API patch payload contracts
- dashboard / webhook / reporting export schemas
- Thompson posterior math
- Kelly sizing math
- final migration collapse of adaptive-control plumbing

## Careful seam definition

### adaptive-control-persistence-ready
A normalized policy-selection layer that says:
- how many comparable adaptive weight-mutation artifacts progressed into persistence-ready / apply-ready adaptive control state
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those adaptive-control-persistence summaries for downstream persistence checks

It does **not** yet promise config-serialization-grade or API-payload-grade fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_control_persistence_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_control_persistence_summary(...)`
3. **PR-3** — end-to-end adaptive-control-persistence chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_control_persistence_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–44:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from adaptive-weight-mutation normalization into raw config serialization or external control payloads

## Why this is conservative in the right way
Adaptive weight mutation answers “did the activation-ready artifact become a normalized provider-weight / control mutation artifact?”
Adaptive control persistence answers “did that mutation artifact become a normalized persistence-ready / apply-ready control artifact?”

That is the smallest next seam that reflects the live repo shape (`base_weights`, enabled-provider state, config/apply hooks, failover/apply paths) without prematurely modeling raw config serialization or external control payload details.
