# FFE Roadmap

Purpose: keep the roadmap readable without destroying the raw audit trail.

The canonical history stays in:
- `memory/2026-04-06.md`
- `memory/2026-04-06-ffe-handoff.md`
- `memory/2026-04-08.md`

This file is the cleaned structure, not the full narrative log.

## 1. Core trading correctness and audit spine

Status: complete for the core roadmap track, and strong enough to justify performance work proceeding on top of it.

Completed:
- fixed collapse of judged/debate outputs into hollow persisted artifacts
- preserved `decision_origin`, `market_regime`, and debate metadata through engine, AI manager, debate manager, ensemble wrapper, and persistence
- added focused regression coverage at seam level
- added core smoke coverage for both live lanes:
  - judged debate persistence
  - pre-reason skip persistence
- hardened `scripts/verify-deployment.sh` to require fresh spine-valid outputs and reject fresh hollow outputs

Exit criteria met:
- live judge lane healthy
- live pre-reason lane healthy
- persistence fidelity covered
- deploy verifier checks spine truth, not just process liveness

Release/readiness note:
- this section is considered complete for roadmap sequencing purposes, but any actual version bump still depends on ordinary soak, deploy verification, and the current known-good runtime state

Primary audit references:
- `memory/2026-04-08.md`

## 2. System performance

Status: decision-complete for the current runtime-model slice, with low-touch soak still appropriate.

Goal:
- reduce cycle latency and reasoning cost without changing trading intent

Baseline that started this section:
- pre-reason skip cycles: about 10-14s
- judged debate cycles: about 40-60s
- dominant cost is reasoning/debate time, not perception/risk/execution/learning

Measured progress so far:
- normal-case debate timing is materially below the original baseline after judge compaction, role compaction, compact shared debate context, and role-output trimming
- catastrophic single-seat stalls are materially better contained than before due to bounded retry/timeout behavior
- current accepted seat retry policy remains the known live `30s` per attempt / `45s` total budget unless explicitly changed and re-verified later
- provider execution time, not Python-side queue wait, is the leading remaining outlier source from the latest attribution work
- the controlled same-model `gemma4:e2b` bakeoff has now produced a strong enough live sample to accept Gemma as the current debate-seat baseline on the one-GPU box

Completed in this section so far:
1. instrumented reasoning-path timings in detail
   - pre-reason raw call
   - prompt build/compression
   - bull seat
   - bear seat
   - judge seat
   - debate synthesis
2. identified the main live cost centers
   - pre-reason raw call for skip lane
   - bull/bear parallel model time plus judge time for debate lane
3. reduced judge-path latency with compact judge context under regression guard
4. reduced bull/bear latency with more compact role prompts under regression guard
5. introduced compact shared debate context, then corrected a real regime-preservation regression with TDD and added permanent regression coverage for compact-context behavior
6. rejected role-only generation-option tuning on the current one-GPU setup after live variance worsened and rolled it back
7. investigated catastrophic stalls, fixed pre-provider instrumentation bugs, and added bounded retry/timeout containment without allowing single-sided debates through to judge
8. added provider-phase attribution in the local provider path to separate connection/preflight time from generate-call time for the next runtime slice

Current decision rule for this section:
- keep taking System Performance slices only while they improve latency variance or reduce catastrophic-stall damage without weakening the audit spine or debate contract
- do not switch to Trading Performance until the remaining System Performance work is either low-yield or clearly blocked on runtime/provider limits rather than prompt or orchestration issues

Section exit gate:
- the current provider-runtime outlier investigation is complete enough to say whether the remaining debate variance is primarily connection/preflight, retry waiting, or generate-call execution
- fresh live measurements show the bounded-retry baseline is stable enough that new System Performance slices would be low-yield compared with Trading Performance work
- judged debate and pre-reason skip lanes both remain spine-clean under the accepted bounded-retry policy

Exit metrics to fill before closing this section:
- sample size: enough fresh live cycles to judge both judged-debate and pre-reason skip lanes without leaning on one-off wins
- judged debate latency: record current p50 and p95 from the accepted bounded-retry baseline, then decide whether the remaining gap is worth more system work
- pre-reason skip latency: record current p50 and p95 from the same measurement window to verify skip-lane regressions were not introduced while optimizing debate
- stall / timeout rate: record the share of fresh cycles that hit bounded retry, seat timeout, or clean debate abort
- provider-phase attribution: classify the dominant remaining outlier source as connection/preflight, retry wait, or generate-call execution before declaring the section low-yield
- audit integrity: confirm zero fresh single-sided debates reaching judge and zero fresh audit-spine regressions in the measurement window

Likely next slices:
1. enter Trading Performance milestone 1 and establish the lane/regime quality baseline before touching decision policy
2. keep passive Gemma soak monitoring in the background, and only reopen System Performance if the longer window reveals a new tail, retry cluster, or audit regression
3. investigate one-GPU provider-runtime hygiene and serialization only if the background soak produces fresh attribution evidence that the new baseline is still materially unstable
4. continue refining shared context/prompt shaping only if it directly helps runtime variance from here
5. avoid the rejected role-only generation-option tuning path on the current one-GPU setup, since live variance got worse after that experiment and it was rolled back
6. re-measure against the original baseline after each accepted slice when future system work resumes

Accepted `gemma4:e2b` bakeoff decision:
- experiment is live on Asus after upgrading Ollama to `0.20.5`; bull, bear, and judge all moved together to `gemma4:e2b`
- accepted live sample at decision time: 108 judged cycles in the window, 18 seat-labeled Gemma debate samples, 0 observed debate timeouts, 0 observed provider/fallback failures, 0 clean debate aborts
- accepted Gemma debate-seat timings from that window:
  - bull: p50 about `8.456s`, p95 about `11.079s`
  - bear: p50 about `10.640s`, p95 about `11.647s`
  - judge: p50 about `4.247s`, p95 about `4.832s`
- comparison against the earlier DeepSeek same-model sample is strong enough to keep Gemma as the current debate-seat baseline, especially because judge latency is materially lower, bull improved, bear stayed within an acceptable band, and no new audit, timeout, or fallback regressions appeared in the soak window
- decision: keep `gemma4:e2b` as the accepted current debate-seat model on the one-GPU box, and treat further System Performance work as background-only unless the longer soak produces contradictory evidence

Next concrete slice:
- move into Trading Performance milestone 1: establish the current quality baseline by lane, regime, and market condition before changing policy
- deliverable: a baseline read covering HOLD rate by lane, action distribution by lane and regime, realized outcome or expectancy by action family, and headline drawdown/win-rate/risk-adjusted returns on the current strategy window
- guardrail: keep lane attribution and audit-spine integrity explicit so later trading-quality slices can be compared without reopening correctness questions

Next major milestone after this section:
- once the Trading Performance baseline exists, choose one narrow quality slice, likely HOLD-heavy behavior or confidence calibration, and measure it against that baseline rather than against runtime anecdotes

Primary audit references:
- `memory/2026-04-08.md`
- `memory/2026-04-09.md`

## 3. Trading performance

Status: sequenced next section after System Performance, not the same thing as system performance.

Goal:
- improve decision quality and trading outcomes after correctness and system-latency work are on stable footing

Trading milestone 1: establish the quality baseline
- hypothesis: trading-quality work will thrash unless lane-level and regime-level behavior are measured first
- deliverable: a baseline read for decision mix and outcome quality broken down by lane, regime, and market condition
- metrics to capture:
  - HOLD rate by lane
  - action distribution by lane and regime
  - realized outcome / expectancy by action family
  - drawdown, win-rate, and risk-adjusted returns on the current strategy window
- rollback / stop rule:
  - do not change decision policy until this baseline exists and is credible enough to compare later slices against

Trading milestone 2: address HOLD-heavy behavior and calibration
- hypothesis: a meaningful part of current trading underperformance may come from over-conservative action selection or poor confidence calibration rather than raw runtime
- deliverable: one narrow calibration slice that adjusts decision thresholds or confidence use without changing multiple policy levers at once
- success criteria:
  - HOLD rate moves in the intended direction without a corresponding degradation in risk-adjusted outcomes
  - judged and skip lanes remain audit-clean
- rollback / stop rule:
  - revert if action-rate changes increase drawdown, reduce expectancy, or blur lane attribution

Trading milestone 3: improve regime handling quality
- hypothesis: some decision-quality loss is likely coming from weak regime-specific behavior rather than from the global policy shape
- deliverable: one regime-aware quality slice at a time, measured against the baseline by market condition
- success criteria:
  - improved outcome quality in the targeted regime bucket without degrading other regime buckets beyond an agreed tolerance
- rollback / stop rule:
  - revert if improvements are regime-local but net-negative across the broader evaluation window

Trading milestone 4: execution quality and expectancy
- hypothesis: some performance loss may sit downstream of the decision itself in sizing, execution timing, or expectancy capture
- deliverable: a focused execution-quality pass after decision-policy slices are measured
- metrics to capture:
  - slippage / fill quality where available
  - expectancy by execution path
  - PnL and drawdown impact after execution adjustments
- rollback / stop rule:
  - revert if execution tweaks improve one metric while worsening net expectancy or risk materially

Known clue from earlier notes:
- HOLD-heavy behavior was already called out as a follow-up track, distinct from runtime fixes and smoke coverage

Section entry gate:
- System Performance has reached a stable enough state that further latency work is lower-value than decision-quality work
- current live system still preserves audit-spine correctness across judged and skip lanes

Primary audit references:
- `memory/2026-04-06.md`
- `memory/2026-04-08.md`

## 4. Platform-wide / 1.0 surface area

Status: separate from the core trading roadmap.

Examples:
- frontend completeness
- broader observability surfaces
- non-core deployment checks
- full platform polish

Explicitly out of scope for the current core roadmap unless they block Sections 1-3 directly:
- UI polish or feature completeness
- non-core observability surfaces that do not change trading correctness or trading-quality decisions
- deployment/process improvements that do not materially affect the core trading lanes
- broad 1.0 packaging work

Preemption rule:
- Section 4 work should not interrupt Sections 2-3 unless it is blocking live verification, safe deployment of the core trading system, or interpretation of core trading outcomes

## Glossary

- audit spine: the persisted fields, behaviors, and checks that make judged and skip-lane outputs trustworthy and traceable end to end
- spine-clean: a live run preserves the required audit-spine fields and does not regress persistence truth
- no-single-sided-debate contract: the judge must never decide a debate when only one advocate seat completed successfully
- bounded retry baseline: the currently accepted debate-seat retry policy with one retry max, `30s` per-attempt timeout, and `45s` total seat cap

## Working rule

When we say:
- "correctness" -> Section 1
- "performance" -> Section 2 unless explicitly stated otherwise
- "trading performance" -> Section 3
- "platform / 1.0" -> Section 4
