# FFE Stage 41 — Learning Analytics Seam

## Why this stage exists

Stage 40 closed the **learning feedback** seam: a normalized, policy-selection-facing summary that trade outcomes can progress into feedback-ready / learning-ready artifacts.

The next careful seam is **learning analytics**.

This is the first layer where we preserve a normalized, policy-facing record that learning-feedback artifacts can progress into analytics-ready / reporting-ready artifacts, without collapsing into Thompson-sampling internals, Kelly activation contracts, or external export/dashboard schemas.

## Stage 41 scope

### Build from
- Stage 40 learning-feedback summaries
- existing runtime concepts already present in live code:
  - `generate_learning_validation_metrics`
  - `learning_report` CLI flow
  - `PerformanceAnalyzer` / portfolio-memory coordinator summaries
  - provider recommendation and validation metric entry points

### Still explicitly NOT this stage
- Thompson-sampling update math / beta-distribution internals
- Kelly activation criteria contracts
- CSV / Metabase / dashboard export schemas
- external webhook/accounting payloads
- final migration collapse of adaptive-learning system details

## Careful seam definition

### learning-analytics-ready
A normalized policy-selection layer that says:
- how many comparable learning-feedback artifacts progressed into analytics-ready / reporting-ready artifacts
- how many remained shadow / primary-cutover / manual-hold / deferred shaped
- and that the chain can safely export those learning-analytics summaries for downstream persistence checks

It does **not** yet promise Thompson/Kelly-engine-grade or dashboard/export-grade fidelity.

## PR-sized breakdown
1. **PR-1** — `build_policy_selection_learning_analytics_set(...)`
2. **PR-2** — `build_policy_selection_learning_analytics_summary(...)`
3. **PR-3** — end-to-end learning-analytics chain hardening
4. **PR-4** — `extract_policy_selection_learning_analytics_summaries(...)`
5. **PR-5** — persistence-backed closeout hardening

## Mapping rule used for this draft
We are continuing the same pseudocode-roadmap discipline used across Stages 29–40:
- one narrow seam at a time
- summary-oriented policy-selection abstractions
- no skipping directly from learning-feedback normalization into Thompson/Kelly internals or external analytics/export schemas

## Why this is conservative in the right way
Learning feedback answers “did the normalized outcome become a feedback-ready / learning-ready artifact?”
Learning analytics answers “did that learning-ready artifact become an analytics-ready / reporting-ready artifact?”

That is the smallest next seam that reflects the live repo shape (`generate_learning_validation_metrics`, `learning_report`, performance-analyzer summaries, provider recommendations) without prematurely modeling Thompson/Kelly internals or external export/dashboard schemas.
