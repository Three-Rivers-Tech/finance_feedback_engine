# FFE Stage 43 — Adaptive Activation Seam

## Why this stage exists

Stage 42 closed the **adaptive recommendation** seam: a normalized, policy-selection-facing summary that learning-analytics artifacts can progress into adaptive provider/sizing recommendation artifacts.

The next careful seam is **adaptive activation**.

This is the first layer where we preserve a normalized, policy-facing record that adaptive recommendation artifacts can progress into activation-ready / control-ready adaptive decisions, without collapsing into Thompson posterior math, Kelly sizing internals, or direct ensemble failover/base-weight mutation mechanics.

## Stage 43 scope

### Build from
- Stage 42 adaptive-recommendation summaries
- existing runtime concepts already present in live code:
  - `check_kelly_activation_criteria`
  - `update_base_weights`
  - `apply_failover`
  - `register_thompson_callback` / `register_thompson_sampling_callback`
  - adaptive-learning control hooks in `core.py` and `ensemble_manager.py`

### Still explicitly NOT this stage
- Thompson posterior update math / regime update internals
- Kelly fraction calculation and sizing formulas
- direct provider-weight mutation semantics as a first-class policy contract
- external export / dashboard / webhook schemas
- final migration collapse of adaptive control behavior

## Careful seam definition

### adaptive-activation-ready
A normalized policy-selection layer that says:
- how many comparable adaptive recommendation artifacts progressed into activation-ready / control-ready adaptive decisions
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those adaptive-activation summaries for downstream persistence checks

It does **not** yet promise Thompson/Kelly-engine-grade or ensemble-mutation-grade fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_adaptive_activation_set(...)`
2. **PR-2** — `build_policy_selection_adaptive_activation_summary(...)`
3. **PR-3** — end-to-end adaptive-activation chain hardening
4. **PR-4** — `extract_policy_selection_adaptive_activation_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–42:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from adaptive-recommendation normalization into Kelly/Thompson internals or direct mutation mechanics

## Why this is conservative in the right way
Adaptive recommendation answers “did the analytics-ready artifact become a normalized adaptive recommendation artifact?”
Adaptive activation answers “did that recommendation become a normalized activation-ready adaptive control artifact?”

That is the smallest next seam that reflects the live repo shape (`check_kelly_activation_criteria`, `update_base_weights`, failover hooks, Thompson callbacks) without prematurely modeling posterior math, Kelly internals, or direct mutation semantics as the policy contract.
