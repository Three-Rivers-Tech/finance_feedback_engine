# FFE Stage 38 — Execution Fill Seam

## Why this stage exists

Stage 37 closed the **execution tracking** seam: a normalized, policy-selection-facing summary that execution artifacts have entered a trackable lifecycle state.

The next careful seam is **execution fill**.

This is the first layer where we preserve a normalized, policy-facing record that tracked execution artifacts can resolve into fill-like outcomes, without collapsing into provider-native transaction-history payloads, reconciliation ledgers, or webhook/callback delivery details.

## Stage 38 scope

### Build from
- Stage 37 execution-tracking summaries
- existing runtime concepts already present in live code:
  - `order_status_worker`
  - extracted fill information
  - `filled_size`
  - order-status-derived completion / settlement hints

### Still explicitly NOT this stage
- provider-native transaction history payload modeling
- exchange-specific fill / partial-fill schemas
- accounting / reconciliation ledgers
- trade-close webhook payloads
- rollback or compensating action machinery
- final migration collapse of end-to-end execution lifecycle details

## Careful seam definition

### execution-fill-ready
A normalized policy-selection layer that says:
- how many comparable execution outcomes progressed into fill-like/settlement-like artifacts
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those fill summaries for downstream persistence checks

It does **not** yet promise provider-native fill fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_execution_fill_set(...)`
2. **PR-2** — `build_policy_selection_execution_fill_summary(...)`
3. **PR-3** — end-to-end execution-fill chain hardening
4. **PR-4** — `extract_policy_selection_execution_fill_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–37:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from tracking-level normalization to raw transaction payloads or reconciliation plumbing

## Why this is conservative in the right way
Execution tracking answers “did the execution artifact enter a normalized trackable state?”
Execution fill answers “did that tracked artifact resolve into a normalized fill-like outcome?”

That is the smallest next seam that reflects the live repo shape (`order_status_worker`, extracted `filled_size`, order-status-derived fill information) without prematurely modeling exchange-native transaction payloads or downstream accounting/reconciliation machinery.
