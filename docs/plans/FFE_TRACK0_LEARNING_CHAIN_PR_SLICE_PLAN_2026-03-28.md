# FFE Track 0 — Learning-Chain Integrity PR-Slice Plan

Date: 2026-03-28
Status: active
Source of truth for live/dev verification: `asus-rog-old-laptop:/home/cmp6510/finance_feedback_engine`
Roadmap anchor: `docs/plans/FFE_1_0_HARDENING_ROADMAP_2026-03-27.md` → Track 0

## Objective

Turn Track 0 from a thesis into an auditable delivery sequence.

The goal is not just to "improve learning."
It is to prove the end-to-end chain:

1. execution occurs
2. durable outcome artifact lands
3. decision lineage survives
4. learning ingests the outcome
5. memory/performance state changes durably
6. provider/model weighting or later decision behavior reflects the update

## Operating stance

- Work from the authoritative FFE repo on the gpu laptop / `asus-rog-old-laptop`
- Prefer small TDD-first slices
- No large refactors without a specific live or auditability symptom attached
- Each PR slice should create new proof artifacts, not just move code around
- "Recorded" is not enough; each slice must tighten evidence of "used"

---

## PR-1 — Preserve decision lineage while positions are still open

### Goal
Reduce or eliminate learning skips caused by missing `decision_id` at close time.

### Scope
- preserve/enrich `decision_id` on active position snapshots before they enter recorder state
- prefer existing recorder state, then trade-monitor associations, then other already-existing low-risk lookups
- make close-time lineage recovery a fallback, not the primary strategy

### Why first
This is the first semantic link in the chain that is still visibly breaking.
If lineage is lost, every downstream learning or weight-adaptation claim is compromised.

### Required artifacts
- focused regression coverage for active-position decision-id enrichment
- focused regression coverage for close-time lineage recovery fallback
- explicit logs showing lineage source / attempted sources when recovery is needed

### Acceptance
- `missing decision_id; durable artifact recorded but learning update skipped` drops materially or is eliminated for the covered path
- recorder state preserves decision lineage for normal open→close lifecycle

### Status notes
- Initial seam patch started 2026-03-28 on `trading_loop_agent.py`
- Focused test coverage added for trade-monitor fallback enrichment

---

## PR-2 — Make learning ingestion explicit and non-silent

### Goal
No closed trade should quietly disappear between durable outcome recording and learning ingestion.

### Scope
- create explicit event/log markers for:
  - durable outcome saved
  - learning handoff attempted
  - learning handoff accepted
  - learning handoff skipped
  - learning handoff failed
- ensure every skip/failure includes reason and identifiers sufficient for audit
- normalize distinction between:
  - pending queue state
  - durable outcome artifact
  - learning ingestion event

### Why second
Before changing adaptation behavior, we need trustworthy observability for whether learning actually happened.

### Required artifacts
- structured or high-signal log lines with order id / decision id / product / lineage source
- test coverage for skip/failure reason paths
- operator-facing log trail for one closed trade

### Acceptance
- for every recorded close, an operator can answer whether it was ingested, skipped, or failed
- no ambiguous "recorded but maybe used" path remains in the critical seam

---

## PR-3 — Durable before/after memory/performance state proof

### Goal
Prove that ingested outcomes mutate durable performance/memory state in a way we can inspect later.

### Scope
- identify canonical durable state artifacts for learning effects
- add explicit before/after snapshots or deltas for the learning update path
- make it possible to tie one outcome to one durable state change

### Why third
Learning that only exists in transient logs is not trustworthy.
We need durable evidence that a specific outcome changed memory/performance state.

### Required artifacts
- canonical file(s) or store entry points documented for:
  - outcome persistence
  - memory/performance persistence
- audit fields linking:
  - order id
  - decision id
  - outcome record
  - memory/performance update id or timestamp
- tests for persistence/update behavior where practical

### Acceptance
- one real or near-live closed trade can be traced to a durable state mutation
- operators can inspect the state change without reconstructing everything from logs

---

## PR-4 — Provider/model adaptation proof path

### Goal
Prove that learning-state updates can affect provider/model weighting or selection behavior.

### Scope
- isolate the actual adaptation mechanism(s):
  - provider weights
  - performance tracker
  - debate/ensemble selection logic
  - any reward/feedback analyzer path
- instrument before/after state around adaptation
- separate config normalization from true learning-driven change

### Why fourth
This is the dividing line between a system that records outcomes and a system that adapts.

### Required artifacts
- explicit evidence of weight/selection state before and after a learning-triggering event
- tests proving outcome-driven updates hit the intended adaptation path
- clear logs distinguishing:
  - config merge normalization
  - runtime adaptive update

### Acceptance
- outcome-driven adaptation can be demonstrated with before/after evidence
- no operator needs to guess whether a weight change was learned or merely normalized from config

---

## PR-5 — End-to-end audit harness and live verification runbook

### Goal
Make Track 0 repeatably verifiable by operators, not just developers with context in their heads.

### Scope
- create a compact audit/runbook for proving the chain end to end
- define the exact artifacts/logs/files to inspect
- add a near-live or fixture-driven verification path for regression checks
- update roadmap audit notes with completion evidence per slice

### Why fifth
The last mile is not code; it is trust and repeatability.
The system is only "special" if the learning chain can be demonstrated on demand.

### Required artifacts
- runbook/checklist for:
  - execution → outcome → lineage → learning → state update → adaptation
- operator summary template for future overnight checks
- roadmap updates marking what is proved vs merely suspected

### Acceptance
- an operator can verify the learning chain without deep code spelunking
- Track 0 status can be reported in roadmap terms with evidence, not vibes

---

## Slice ordering rationale

This sequence is intentionally narrow:

- **PR-1** fixes the first broken semantic link
- **PR-2** makes ingestion observable
- **PR-3** proves durable memory/performance mutation
- **PR-4** proves adaptation rather than mere recording
- **PR-5** makes the whole thing auditable and repeatable

Each slice should leave the system better instrumented than before.
If a slice cannot produce new proof artifacts, it is probably too fuzzy and needs to be narrowed.

---

## Audit checklist to update as work lands

- [x] PR-1 landed
- [x] PR-1 live-verified enough to move out of immediate fire-fighting, while still deserving ongoing soak observation
- [x] PR-2 landed
- [x] PR-2 live-verified
- [x] PR-3 landed
- [x] PR-3 live-verified (after surfacing and then resolving autosave/load compatibility regressions under live conditions)
- [ ] PR-4 landed
- [ ] PR-4 live-verified
- [ ] PR-5 landed
- [ ] PR-5 live-verified

## Notes

- Track 0 is now the immediate top-priority roadmap item because reliable learning/adaptation is the differentiator.
- A boring runtime is now a feature; the next work is about subtlety, lineage, memory, and proof.
- If the chain cannot be proved, FFE remains a competent but expensive state-processing machine rather than an adaptive system.
