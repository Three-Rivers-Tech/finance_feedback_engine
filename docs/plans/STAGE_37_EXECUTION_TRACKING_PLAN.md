# FFE Stage 37 — Execution Tracking Seam

## Why this stage exists

Stage 36 closed the **execution receipt** seam: a normalized, policy-selection-facing summary of receipt-like execution artifacts.

The next careful seam is **execution tracking**.

This is the first layer where we preserve a normalized, policy-facing record that a received execution artifact can be tracked through later order-status / fulfillment observation, without collapsing into provider-native status polling payloads or fill-transaction parsing.

## Stage 37 scope

### Build from
- Stage 36 execution-receipt summaries
- existing runtime concepts already present in live code:
  - `order_id`
  - `order_status`
  - `order_status_worker`
  - idempotency / client order identifiers (`clientRequestID`, `client_order_id`)

### Still explicitly NOT this stage
- provider-native transaction-history parsing
- fill/partial-fill settlement modeling
- raw callback/webhook payload modeling
- rollback/reconciliation automation
- final migration collapse of execution lifecycle details

## Careful seam definition

### execution-tracking-ready
A normalized policy-selection layer that says:
- how many comparable execution outcomes progressed into trackable receipt/status artifacts
- how many stayed shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those tracking summaries for downstream persistence checks

It does **not** yet promise provider-native order-status fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_execution_tracking_set(...)`
2. **PR-2** — `build_policy_selection_execution_tracking_summary(...)`
3. **PR-3** — end-to-end execution-tracking chain hardening
4. **PR-4** — `extract_policy_selection_execution_tracking_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are keeping the same pseudocode-roadmap discipline that held across Stages 29–36:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from receipt-level normalization to provider-native status/fill details

## Why this is conservative in the right way
Execution receipt answers “did we get a normalized receipt-like artifact?”
Execution tracking answers “did that artifact enter a normalized trackable lifecycle state?”

That is the smallest next seam that reflects the real repo shape (`order_status_worker`, order status lookup, idempotent identifiers) without prematurely modeling exchange-specific status payloads.
