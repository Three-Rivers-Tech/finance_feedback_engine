# FFE 1.0 Hardening Roadmap — 2026-03-27

## Purpose

This roadmap resets the near-term direction for Finance Feedback Engine around a simple 1.0 principle:

> **Boring and reliable beats clever and fragile.**

FFE does **not** need more architecture ambition right now.
It needs to become:
- operationally stable
- legible in logs
- consistent in state handling
- test-backed around its fragile seams
- trustworthy enough that a quiet runtime feels reassuring, not suspicious

This roadmap supersedes the more exploratory tone of earlier hardening notes.
The current phase is not “invent the future.”
It is:

> route out bugs, tighten observability, and reduce surprise until the system is boring.

---

## Current position

FFE is in a much healthier place than it was a few days ago.
Recent work materially improved:
- pending-order lifecycle handling
- Coinbase client/path shape handling
- decision lineage recovery for closes
- monitoring/position seam coverage
- disk-pressure and Ollama storage hygiene
- operator visibility on machine health

The system is no longer dominated by “why is prod on fire?” problems.
The remaining work is more interesting and more 1.0-shaped:
- seam hardening
- observability clarity
- state/recovery consistency
- ongoing regression coverage

That is progress.

---

## Non-goals for 1.0

To keep the roadmap honest, these are **not** current 1.0 priorities:

- judge-first AI escalation policy
- inference cost optimization as a top-line goal
- major architecture rewrites
- broad feature expansion
- clever routing layers that introduce new failure modes
- large refactors with no live symptom attached

Why:
- each new layer creates more bug surface
- expensive reasoning is part of the product thesis anyway
- the system still gets more value from reliability than from sophistication

Those ideas may be high-value later.
They are not the right center of gravity for 1.0.

---

## 1.0 success definition

FFE 1.0 should feel like this:

### Runtime
- stays up
- recovers cleanly
- does not lose state for dumb reasons
- does not silently degrade around order tracking or lineage

### Decisions
- decisions are consistent and traceable
- active-position state is reflected accurately
- close/open lineage is recoverable and auditable

### Observability
- logs are explicit, not misleading
- operators can tell global vs asset-scoped state apart
- warnings mean something actionable
- healthy quiet loops look healthy, not ambiguous

### Operations
- machine pressure is controlled
- storage layout is sane
- health monitoring exists
- operator access/tooling is not the bottleneck

### Development discipline
- new bug classes get regression coverage quickly
- fixes are small, targeted, and validated
- test fixtures reflect real payload shapes instead of idealized shapes

If those are true, FFE is much closer to a real 1.0 than any policy-layer enhancement can make it.

---

## Current highest-value tracks

## Track 0 — Learning-chain integrity and adaptive-memory proof
**Priority:** Immediate / highest

### Why
FFE is now healthy enough that the next important question is no longer:
- does the loop stay up?
- does execution plumbing basically work?

Those are becoming boring in the good sense.

The next threshold is whether FFE is actually **learning**.
Without a trustworthy learning chain, FFE is still mostly an expensive state-processing and execution machine.
What makes it special is the closed loop from:
- execution
- outcome capture
- lineage recovery
- learning ingestion
- memory/performance update
- provider/model weight adaptation
- later decision behavior

If that chain is partial, silent, or unverifiable, the system is not yet delivering on the real thesis.

### Focus
- eliminate silent learning skips for closed trades
- harden decision-lineage recovery so durable outcome artifacts reliably retain `decision_id`
- make every closed-trade outcome either:
  - successfully enter learning, or
  - emit a loud, explicit, actionable failure artifact
- prove that durable outcomes update memory/performance state
- prove that updated memory/performance state can affect provider/model weighting or later decision behavior
- distinguish clearly between:
  - outcome recorded
  - outcome ingested
  - weights updated
  - later behavior changed

### Deliverables
- explicit end-to-end learning-chain instrumentation
- durable proof artifacts linking:
  - execution/order
  - outcome record
  - decision lineage
  - learning update
  - memory/performance state change
  - provider/model weight change (when applicable)
- regression coverage around closed-trade lineage recovery and learning handoff
- removal or explanation of `missing decision_id; durable artifact recorded but learning update skipped` cases
- operator-facing verification path for proving that learning is real, not implied

### Success criteria
- no closed trade can silently disappear from the learning path
- durable trade outcomes are consistently linked back to originating decisions
- learning updates are observable and auditable end to end
- provider/model adaptation can be shown with before/after evidence when outcomes should affect weights
- operators can prove the chain:
  - execution → durable outcome → decision-linked learning event → memory/performance update → observable adaptive effect

### Acceptance bar
Do not treat FFE as meaningfully adaptive until we can demonstrate, on live or near-live evidence, that:
1. a real executed trade closes
2. the outcome lands durably
3. the originating decision lineage survives
4. learning ingests that outcome without skip
5. durable memory/performance state changes
6. a later weight/config/selection behavior reflects the update

---

## Track A — Observability clarity
**Priority:** Very high

### Why
Misleading logs waste time and destroy trust.
A technically true but operationally confusing log line is still a product bug.

### Focus
- make monitoring logs explicitly asset-scoped vs global
- make recovery logs show lineage source and attempted sources
- distinguish completed/removed vs stale/orphaned pending orders
- make per-cycle summaries clearer and easier to scan
- reduce stale wording that implies older runtime assumptions

### Deliverables
- clearer log wording in monitoring / recovery / pending-order paths
- tests around wording/summary helpers where practical
- operator glossary for high-frequency runtime messages

### Success criteria
- an operator can read 1–2 minutes of logs and correctly answer:
  - what positions exist globally
  - what positions exist for the asset under analysis
  - why a close lineage was recovered or missed
  - whether a pending order was completed or aged out

---

## Track B — Wrapper / shape normalization
**Priority:** Very high

### Why
Recent bugs keep rhyming:
- direct vs nested clients
- top-level vs nested payloads
- flat portfolio vs `platform_breakdowns`
- string vs tuple-shaped IDs
- futures product IDs vs normalized asset pairs

This is not random.
It is a codebase pattern.

### Focus
- centralize helper logic for common payload/client/shape normalization
- stop re-implementing similar extraction rules in multiple seams
- reduce silent mismatch behavior

### Deliverables
- small helper layer for common shape normalization
- fewer ad-hoc per-call shape fixes
- explicit use sites for unified Coinbase / monitoring / recovery flows

### Success criteria
- new bugfixes stop taking the form “support one more weird shape in one more random place”
- common wrapper/payload variants are handled by a small number of reusable helpers

---

## Track C — Shared test fixture realism
**Priority:** High

### Why
Some recent test friction came from fixtures that were too idealized compared to production.
That slows bug routing and lets real-world payload weirdness slip through.

### Focus
- canonical Coinbase futures fixtures
- unified-platform nested fixtures
- pending-order payload variants
- tracker/lineage fixtures with real tuple/string/missing-ID variants
- realistic portfolio shapes with nested `platform_breakdowns`

### Deliverables
- reusable shared fixtures/builders for known-real payload classes
- reduced one-off fixture invention inside test files

### Success criteria
- adding a new regression test becomes easier
- test failures point at real behavior, not unrealistic fixture assumptions

---

## Track D — Incremental recovery-path cleanup
**Priority:** High

### Why
Recovery is one of the most delicate parts of the system.
It touches:
- open position discovery
- close detection
- pending/outcome sync
- lineage recovery
- decision persistence
- trade-monitor expectations

It is now healthier, but still a seam worth simplifying carefully.

### Focus
- make lineage resolution order explicit
- reduce duplicated lookup logic
- clarify recovery summaries
- avoid large rewrites

### Deliverables
- small recovery seam cleanups
- clearer recovery logs
- regression tests around lineage-source priority and close sync behavior

### Success criteria
- recovery becomes easier to reason about from logs + tests
- fewer one-off fallback paths exist for lineage resolution

---

## Track E — Canonical Coinbase product-ID handling
**Priority:** High

### Why
Mapping between product IDs and canonical asset pairs is still spread around too much.
Examples:
- `BIP-*` → `BTCUSD`
- `ETP-*` → `ETHUSD`
- platform-specific futures IDs vs spot-style asset keys

This has already caused bugs in:
- monitoring
- tracker lookup
- recovery
- active-position visibility

### Focus
- centralize canonical mapping rules
- ensure all monitoring/tracking/recovery paths use the same interpretation

### Deliverables
- one canonical mapping strategy
- tests for BTC/ETH and known product-prefix cases

### Success criteria
- asset-scoped logic agrees across monitoring, recovery, and trade tracking
- fewer bugs caused by product-ID ambiguity

---

## Track F — Ops hygiene and maintenance discipline
**Priority:** Medium-high

### Why
Operational sloppiness can still undo good code.
The recent disk-pressure incident proved that.

### Current good state
- Ollama moved off root onto `/mnt/ffe-data`
- root disk pressure resolved
- hourly health snapshot installed
- `btop` / `sysmon` available on host

### Focus
- document the actual storage layout and maintenance expectations
- document health-check commands and known-good indicators
- define recurring low-risk cleanup posture for Docker/log pressure

### Deliverables
- short operator hygiene doc
- explicit “what lives where” note
- minimal maintenance checklist

### Success criteria
- future disk-pressure or operator-access surprises become less likely
- healthy machine state is easy to verify quickly

---

## Suggested sequencing

### Phase 1 — Make the system legible
1. Observability clarity
2. Warning/log taxonomy
3. Shared fixture realism for known bad seams

### Phase 2 — Remove repeated shape bugs
4. Wrapper/shape normalization helpers
5. Canonical Coinbase product-ID handling

### Phase 3 — Tighten delicate state seams
6. Incremental recovery-path cleanup
7. Additional regression coverage around pending orders / closes / lineage

### Phase 4 — Lock down operator confidence
8. Ops hygiene documentation
9. Maintenance checklist
10. Clean-loop evidence spec for release confidence

This order is intentional:
- first make behavior easier to see
- then reduce repeated data-shape brittleness
- then simplify the hardest seam on top of that

---

## What to defer until after 1.0 hardening

These are worth keeping, but should remain explicitly deferred:
- AI-owned escalation policy
- judge-first prechecks
- inference routing optimization
- broader debate architecture changes
- cost/latency-focused policy redesign

**Plain statement:** AI escalation is a **post-1.0** effort. It is intentionally out of scope for the current hardening track and should not compete with boring reliability work until the base system is stable, legible, and trusted.

Reason:
- these are multipliers
- multipliers should come after the base system is trustworthy

Right now the right job is still:
- reduce bug surface
- increase trust
- increase clarity

### Deferred post-1.0 version-bump outline

When the base system is boring enough to trust, the next major roadmap branch should be framed as a **version-bump-worthy architecture/observability release**, not as a casual performance tweak.

#### Why it merits a version bump
- it changes inference architecture
- it changes policy ownership
- it expands the auditability surface
- it changes runtime cost/latency profile
- it changes operational observability and decision-path semantics

#### Recommended release framing
- **minor version bump with major release-note weight** for the first safe release
- preserve backward-compatible behavior first through:
  - instrumentation baseline
  - shadow-mode policy judge
  - feature-flagged live gating only later

#### Deferred release phases
1. **Instrumentation baseline**
   - per-asset debate cost visibility
   - cycle latency decomposition
   - audit schema for pre-debate policy decisions
2. **Shadow-mode policy judge**
   - judge-first precheck runs
   - full debate still runs normally
   - disagreement / false-skip analysis collected
3. **Conservative live gating**
   - only in narrow low-risk scenarios
   - explicit force-full-debate overrides remain
4. **Broader policy ownership**
   - only after audit confidence and soak evidence exist

#### Deferred success criteria
Any future policy-escalation release should only be considered successful if it is:
- **auditable**
  - every judged/gated asset has a valid audit record
- **safe**
  - no regressions in active-position, pending-order, or recovery flows
- **operationally legible**
  - operators can explain any asset’s path from logs/records alone
- **actually beneficial**
  - measurable reduction in low-value full-debate spend without a pattern of obvious missed opportunities

#### Deferred rollout rule
Do not turn this on broadly just because it is clever.
Turn it on only after:
- regression coverage is strong
- shadow-mode evidence is clean
- rollback controls exist
- operators can understand what happened after the fact

---

## Definition of roadmap success over the next stretch

We are on track if, after a few more sessions:
- recent logs stay clean for longer soak windows
- warning volume drops and warning meaning improves
- new bug discoveries are smaller and more localized
- regression coverage keeps growing around real seams
- operators can explain the system’s current state quickly from logs
- no new flashy feature layers are required to feel progress

That is what 1.0 progress should look like.

---

## Final guidance

If there is tension between:
- adding a clever new capability
and
- making a confusing seam boring,

choose boring.

That is the correct 1.0 trade.
