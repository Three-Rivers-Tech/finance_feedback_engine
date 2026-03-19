# FFE Stage 39 — Trade Outcome Seam

## Why this stage exists

Stage 38 closed the **execution fill** seam: a normalized, policy-selection-facing summary that tracked execution artifacts can resolve into fill-like outcomes.

The next careful seam is **trade outcome**.

This is the first layer where we preserve a normalized, policy-facing record that fill-like execution artifacts can resolve into closed-trade / realized-outcome artifacts, without collapsing into accounting ledgers, webhook payloads, or portfolio-memory learning internals.

## Stage 39 scope

### Build from
- Stage 38 execution-fill summaries
- existing runtime concepts already present in live code:
  - `trade_outcome_recorder`
  - closed-trade processing in `trading_loop_agent`
  - trade outcome recording / retrieval interfaces
  - realized trade outcome artifacts used by monitoring and learning flows

### Still explicitly NOT this stage
- accounting / CFO webhook payload modeling
- portfolio-memory storage schema internals
- Thompson-sampling / learning-update contracts
- P&L analytics export schemas
- reconciliation / ledger rollups
- final migration collapse of execution-to-learning lifecycle details

## Careful seam definition

### trade-outcome-ready
A normalized policy-selection layer that says:
- how many comparable execution-fill outcomes progressed into closed-trade / outcome-like artifacts
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those trade-outcome summaries for downstream persistence checks

It does **not** yet promise accounting-grade or learning-engine-grade outcome fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_trade_outcome_set(...)`
2. **PR-2** — `build_policy_selection_trade_outcome_summary(...)`
3. **PR-3** — end-to-end trade-outcome chain hardening
4. **PR-4** — `extract_policy_selection_trade_outcome_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–38:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from fill-level normalization into accounting, webhook, or learning-specific data contracts

## Why this is conservative in the right way
Execution fill answers “did the tracked execution artifact resolve into a normalized fill-like outcome?”
Trade outcome answers “did that fill-like outcome resolve into a normalized closed-trade / realized-outcome artifact?”

That is the smallest next seam that reflects the live repo shape (`trade_outcome_recorder`, closed-trade processing, trade outcome recording interfaces) without prematurely modeling accounting/webhook payloads or portfolio-memory learning internals.
