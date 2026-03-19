# FFE Stage 40 — Learning Feedback Seam

## Why this stage exists

Stage 39 closed the **trade outcome** seam: a normalized, policy-selection-facing summary that fill-like execution artifacts can resolve into closed-trade / realized-outcome artifacts.

The next careful seam is **learning feedback**.

This is the first layer where we preserve a normalized, policy-facing record that trade outcomes can progress into feedback-ready / learning-ready artifacts, without collapsing into portfolio-memory storage internals, Thompson-sampling update mechanics, or analytics/export schemas.

## Stage 40 scope

### Build from
- Stage 39 trade-outcome summaries
- existing runtime concepts already present in live code:
  - `handle_learning_state` in `trading_loop_agent`
  - `portfolio_memory` integration in `core.py`
  - trade outcome recording / feedback handling flow
  - learning validation metric entry points

### Still explicitly NOT this stage
- portfolio-memory persistence schema internals
- Thompson-sampling update contracts / beta-distribution math
- Kelly activation contracts
- analytics / CSV / Metabase export schemas
- accounting / webhook delivery payloads
- final migration collapse of learning-system details

## Careful seam definition

### learning-feedback-ready
A normalized policy-selection layer that says:
- how many comparable trade-outcome artifacts progressed into feedback-ready / learning-ready artifacts
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those learning-feedback summaries for downstream persistence checks

It does **not** yet promise portfolio-memory-engine-grade or Thompson-update-grade fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_learning_feedback_set(...)`
2. **PR-2** — `build_policy_selection_learning_feedback_summary(...)`
3. **PR-3** — end-to-end learning-feedback chain hardening
4. **PR-4** — `extract_policy_selection_learning_feedback_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–39:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from trade-outcome normalization into memory-engine internals or learning-math contracts

## Why this is conservative in the right way
Trade outcome answers “did the fill-like artifact resolve into a normalized closed-trade / realized-outcome artifact?”
Learning feedback answers “did that normalized outcome become a feedback-ready / learning-ready artifact?”

That is the smallest next seam that reflects the live repo shape (`handle_learning_state`, `portfolio_memory`, learning-validation entry points) without prematurely modeling portfolio-memory persistence internals, Thompson-sampling math, or analytics/export contracts.
