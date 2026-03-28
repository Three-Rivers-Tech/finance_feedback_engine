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

### Audit notes / execution plan
Track 0 is being executed as a phased five-PR slice plan documented here:
- `docs/plans/FFE_TRACK0_LEARNING_CHAIN_PR_SLICE_PLAN_2026-03-28.md`

Current intended slice order:
1. preserve decision lineage while positions are still open
2. make learning ingestion explicit and non-silent
3. prove durable before/after memory/performance mutation
4. prove provider/model adaptation from outcomes rather than config normalization
5. ship an end-to-end audit harness / live verification runbook

Audit rule:
- do not mark Track 0 complete based on logs that merely show outcome recording
- completion requires evidence for the full chain from execution through adaptive effect

### Live audit notes — 2026-03-28
Track 0 now has real live evidence after backend redeploy on `asus-rog-old-laptop`.

#### What is now proved live
- durable outcome recording is real (`data/trade_outcomes/2026-03-28.jsonl`)
- learning handoff instrumentation is live and firing
- durable portfolio-memory mutation is live and firing
- at least one close path successfully completed:
  - outcome saved
  - learning handoff ATTEMPT logged
  - portfolio memory updated
  - learning handoff ACCEPTED logged
  - learning outcome recorded

Concrete observed success case:
- `2026-03-28 13:06:51 UTC`
- closed position: `BIP-20DEC30-CDE`
- order id: `be381020-a9ff-433f-a804-146604601a9f`
- decision id: `45cffede-96a6-42db-b9f9-ed3ca65f2b20`
- provider memory update logged with:
  - `provider=recovery`
  - `provider_total_trades=1`
  - `provider_total_pnl=-95.0`

#### What was failing live
A later close initially skipped learning because decision lineage was missing:
- `2026-03-28 14:32:14 UTC`
- closed position: `BIP-20DEC30-CDE`
- order id: `0736f0b7-c7a7-4c75-a866-1d0bd5dc0bbd`
- `Learning handoff SKIPPED ... reason=missing_decision_id`
- attempted sources logged:
  - `recorder.open_positions`
  - `trade_monitor.expected_trades`
  - `trade_monitor.active_trackers`
  - `trade_monitor.get_decision_id_by_asset`
  - `trade_monitor.closed_trades_queue`

A `PR-1b` fix was then implemented to add a durable fallback via recent decisions keyed by `recovery_metadata.product_id`.
- commit: `914371d` — `fix: recover close lineage from decision store`

#### New live evidence after PR-1b
After redeploy, a fresh BIP close no longer skipped:
- `2026-03-28 15:48:57 UTC`
- closed position: `BIP-20DEC30-CDE`
- order id: `d48977f2-1bee-43e0-8fa4-c2f3c948e1e6`
- `Learning handoff ATTEMPT ...`
- `Learning handoff ACCEPTED ...`
- `Recorded learning outcome ...`

This is strong evidence that the lineage regression improved materially, but it should still be treated as recently-fixed until more live runtime confirms the skip pattern is gone.

#### Newly exposed live regression
Once the chain progressed farther, a new reliability failure surfaced in durable memory autosave:
- `Failed to auto-save portfolio memory: 'dict' object has no attribute 'to_dict'`
- observed live at least at:
  - `2026-03-28 15:22:43 UTC`
  - `2026-03-28 15:48:57 UTC`

Root cause:
- `PortfolioMemoryEngine.save_to_disk()` assumed every entry in `trade_outcomes` and `experience_buffer` had `.to_dict()`
- live runtime can contain mixed `TradeOutcome` objects and plain `dict` entries

Fix applied:
- tolerant mixed-entry serialization for portfolio memory saves
- regression coverage added for dict-backed entries in memory buffers
- commit: `115dc12` — `fix: tolerate dict entries in portfolio memory saves`
- deployed live after tests passed; awaiting live post-fix confirmation that the warning is gone

#### Sequencing correction from live evidence
The roadmap still conceptually points next to **PR-4** (prove adaptation), but live evidence continues to show that Track 0 must follow a regression-first discipline before deeper feature proof.

Operationally:
- PR-2 is live-proved
- PR-3 is live-proved in the sense that durable memory mutation is observable
- PR-1b improved the lineage path and may have resolved the observed skip, but it remains under live verification
- the autosave serialization regression is now the newest **priority #1** blocker until verified fixed in production behavior

#### Audit interpretation
As of 2026-03-28:
- PR-2 = live-proved
- PR-3 = live-proved, but exposed an autosave reliability bug under live conditions
- PR-1 = substantially improved; PR-1b deployed; awaiting more live confirmation that missing-lineage skips have stopped
- PR-4 = still the next conceptual section, but blocked in practice by newly surfaced live regressions on the same seam

#### Immediate next focus
Before treating PR-4 as the active implementation section, keep boring-ifying the learning chain under live conditions:
- confirm the `missing_decision_id` regression stays gone after PR-1b
- confirm the portfolio-memory autosave warning disappears after `115dc12`
- keep using the new attempted-source / handoff / memory-update logs as the audit spine
- only then treat adaptation proof as a clean next-stage target

#### Regression classification
Live reliability regressions on the learning chain are explicit **Track 0 regressions**.

Regression rule for Track 0 and future feature work:
- when a new feature or verification effort exposes a live regression, that regression becomes **priority #1** ahead of further feature expansion on that seam
- do not continue deeper into a new feature section while a newly exposed live regression undermines the reliability of the chain being proved
- for this Track 0 phase, lineage-loss regressions, skipped learning updates, and broken durable-state saves all outrank adaptation-proof feature work until the chain is boring and dependable

Working interpretation:
- PR-4 remains the next conceptual feature section
- but any live regression uncovered while pursuing PR-4 (especially lineage drops, skipped learning updates, or broken durable-state mutations) should preempt feature progress and be handled first

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

## Track G — Repository hygiene and architecture debt reduction
**Priority:** High when Track 0 is in a waiting/verification posture; subordinate to live Track 0 regressions

### Why
A broader repository audit on 2026-03-28 found that FFE’s root layout and module boundaries have accumulated a meaningful amount of clutter and duplication. This is not the same problem as Track 0, but it does affect maintainability, auditability, and the ability to reason clearly about which code paths are active vs stale.

### Audit reference
Detailed audit notes now live here:
- `docs/audits/FFE_REPO_AUDIT_2026-03-28.md`

### Working interpretation
Track 0 asks:
- is the learning chain real, boring, and dependable?

Track G asks:
- is the repo legible enough that we can trust what code, docs, and modules are actually active?

These are related, but not identical.

### Initial prioritized remediation
#### P0 / safe-and-small
- align mypy `python_version` with the actual required Python version (`3.13`)
- extend `.gitignore` for result/report artifacts
- clarify test-coverage / CI-gate semantics instead of leaving the 42%-vs-70% mismatch implicit

#### P1 / likely-safe cleanup after verification
- move orphan root `test_*.py` files into `tests/`
- verify whether root `core.py` is stale and remove it if confirmed dead
- delete/archive stale `.pre-commit-config-*.yaml` variants if not referenced
- relocate/archive root conversation-artifact markdown files into a dedicated archival docs area

#### P2 / deeper architecture consolidation
- consolidate or clearly delineate:
  - `backtest/` vs `backtesting/`
  - `monitoring/` vs `observability/`
- resolve incomplete/deprecated duplicate module pairs
- revisit dependency bounding strategy
- enable or intentionally defer flake8/pre-commit expansion with an explicit reason

### Guardrails
- do not let repo hygiene work outrank a newly exposed **live learning-chain regression**
- do not delete duplicate-looking files/modules without verifying import reachability and runtime/reference status
- prefer archival moves over destructive deletion until provenance is clear
- use this track to reduce ambiguity, not to create cleanup theater

### Working priority rule
- live Track 0 regressions remain priority #1
- Track G becomes the default cleanup stream when Track 0 is in a waiting/verification posture

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

### Track 0 runs above the rest
Track 0 is the immediate top-priority stream and runs **ahead of / in parallel with** the rest of the roadmap.

Working rule:
- do not treat Phases 1–4 below as permission to ignore a newly exposed live Track 0 regression
- when Track 0 is in active regression-fix mode, it outranks all other tracks
- when Track 0 is in a waiting/verification posture, Track G and the remaining structural tracks become the default next work

### Phase 0 — Make the learning chain boring
1. finish live verification of Track 0 regression fixes
2. eliminate newly exposed live learning-chain regressions before deeper feature proof
3. only treat PR-4 / adaptation proof as active once lineage, handoff, and durable saves are dependable

### Phase 1 — Make the system legible
4. Observability clarity
5. Warning/log taxonomy
6. Shared fixture realism for known bad seams

### Phase 2 — Remove repeated shape bugs
7. Wrapper/shape normalization helpers
8. Canonical Coinbase product-ID handling

### Phase 3 — Tighten delicate state seams
9. Incremental recovery-path cleanup outside Track 0’s immediate learning-chain seam
10. Additional regression coverage around pending orders / closes / lineage

### Phase 4 — Lock down operator confidence
11. Ops hygiene documentation
12. Maintenance checklist
13. Clean-loop evidence spec for release confidence
14. Repository hygiene / architecture debt reduction work from Track G when Track 0 is quiet

This order is intentional:
- first make the learning chain trustworthy
- then make behavior easier to see
- then reduce repeated data-shape brittleness
- then simplify the hardest remaining seams on top of that

---

## Milestone gates / re-evaluation markers

These are intentionally rough gates, not fake-precise deadlines.

### Gate 1 — Track 0 boring-enough threshold
Treat this as the first major gate before resuming deeper adaptation-proof work:
- no fresh live lineage-loss regressions in normal closes over a meaningful soak window
- no fresh live durable-memory save regressions in the same window
- live handoff logs remain explicit and interpretable
- operators can verify the learning chain from runtime evidence without ad hoc spelunking

### Gate 2 — Structural hardening window
Once Gate 1 is satisfied, active work can expand across Tracks A–F/G more normally:
- observability wording/log taxonomy becomes cleaner
- repeated shape bugs continue shrinking
- recovery seams outside Track 0’s immediate learning chain get simplified
- repo hygiene work can proceed without competing with urgent live learning regressions

### Gate 3 — 1.0 release-candidate judgment
A 1.0 call should only be considered when:
- Track 0 acceptance criteria are satisfied
- the system survives longer quiet/healthy soak windows without mystery regressions
- operators can explain runtime state from logs and artifacts quickly
- rollback / halt posture is documented and usable

## Rollback / incident posture

A trading system roadmap should say what happens when a good-looking deploy is wrong.

Minimum 1.0 operational posture should include:
- a documented rollback path for backend deploys
- a documented trading halt / safe-stop procedure
- explicit note on which circuit breakers or flags can disable harmful behavior quickly
- operator guidance for when to stop proving adaptation and revert to safety-first runtime posture

This does not need to become a giant incident-management program now, but it must stop being implicit.

## Coverage / CI-gate note

The broader repo audit reported approximately 42% line coverage against an apparent 70% gate.
That mismatch needed explicit interpretation rather than hand-waving.

Clarification from repo inspection on 2026-03-28:
- the 70% threshold is **real and enforced in CI**
- `.github/workflows/ci.yml` runs:
  - `pytest --full-suite ... --cov=finance_feedback_engine --cov-fail-under=70`
- CI uses Python 3.13 in the `backend-quality` job
- local audit measurements therefore likely differ because of scope, marker selection, environment, or run-shape differences rather than because the threshold is imaginary

Open follow-up under Track G:
- explain why the audit saw ~42% while CI claims a passing 70%-gated run
- document whether that is due to:
  - different selected tests,
  - different measured subset,
  - different coverage configuration,
  - or some other reporting mismatch

Do not use coverage theater as a success signal.
Use this note to force clarity on what the gate actually means in practice.

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
