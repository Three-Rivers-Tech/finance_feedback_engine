# FFE Roadmap

Purpose: keep the roadmap readable without destroying the raw audit trail.

The canonical history stays in:
- `memory/2026-04-06.md`
- `memory/2026-04-06-ffe-handoff.md`
- `memory/2026-04-08.md`

This file is the cleaned structure, not the full narrative log.

## 1. Core trading correctness and audit spine

Status: complete, version-bump worthy before performance work.

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

Primary audit references:
- `memory/2026-04-08.md`

## 2. System performance

Status: next active roadmap section.

Goal:
- reduce cycle latency and reasoning cost without changing trading intent

Current baseline:
- pre-reason skip cycles: about 10-14s
- judged debate cycles: about 40-60s
- dominant cost is reasoning/debate time, not perception/risk/execution/learning

Next slices:
1. instrument reasoning-path timings in more detail
   - pre-reason raw call
   - prompt build/compression
   - bull seat
   - bear seat
   - judge seat
   - portfolio/context fetch overhead
2. identify the worst contributor in live runs
3. reduce debate-path latency with the smallest safe changes first
4. re-measure and compare against baseline

Primary audit references:
- `memory/2026-04-08.md`

## 3. Trading performance

Status: separate roadmap section, not the same thing as system performance.

Goal:
- improve decision quality and trading outcomes after correctness and system-latency work are on stable footing

Likely topics:
- HOLD-heavy behavior and calibration
- regime handling quality
- decision quality by lane and by market condition
- execution quality and expectancy
- PnL, drawdown, win-rate, and risk-adjusted outcomes

Known clue from earlier notes:
- HOLD-heavy behavior was already called out as a follow-up track, distinct from runtime fixes and smoke coverage

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

This should not be mixed into core trading correctness or system performance decisions.

## Working rule

When we say:
- "correctness" -> Section 1
- "performance" -> Section 2 unless explicitly stated otherwise
- "trading performance" -> Section 3
- "platform / 1.0" -> Section 4
