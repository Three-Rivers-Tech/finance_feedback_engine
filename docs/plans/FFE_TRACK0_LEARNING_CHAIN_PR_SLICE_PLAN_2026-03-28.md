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

---

## Track 0 verification spine — immediate surgical next steps

This section is the operational spine for the next session(s).
It is intentionally narrower than the roadmap language.
Do not start broad PR-4 implementation from vibes.
Use this spine to verify that the recent Track 0 fixes are actually boring under live conditions.

Working rule:
- if any item below fails, treat that failure as the active Track 0 task
- do not advance to adaptation-proof work while a lower-link verification item is still failing
- prefer one sharply-proved seam over three half-proved ones

### Step 1 — Resolve the `pending_outcomes.json` ambiguity

#### Why this is first
The overnight check showed real executions and repeated `Registered executed order ... for outcome tracking` logs, while `data/pending_outcomes.json` was still `{}`.
That is exactly the kind of ambiguity Track 0 is supposed to eliminate.

#### Questions to answer
- What code path emits `Registered executed order ... for outcome tracking`?
- After that log line, what durable artifact is supposed to exist?
- Is `data/pending_outcomes.json` still the canonical queue/state file?
- If not, what replaced it?
- If yes, why can registration be logged while the file remains empty?

#### Surgical inspection plan
1. locate the exact emitter(s) of the registration log line
2. trace the immediate downstream persistence write(s)
3. identify the canonical durable state location for pending/registered outcomes
4. compare implementation reality vs operator assumption
5. classify the empty-file observation as one of:
   - expected queue drain
   - storage location moved
   - stale/misleading log line
   - true persistence failure

#### Required proof artifact
For one real registration event, record:
- timestamp
- asset/product
- order id
- log line text
- code path/module
- canonical durable artifact path
- evidence that the artifact was or was not updated

#### Pass / fail box
- [ ] PASS: one real registration event can be tied to a canonical durable artifact, or the lack of an artifact is explicitly proved to be expected
- [ ] FAIL: registration is logged but durable state is absent, ambiguous, or only inferable from code spelunking

#### If fail
- fix the persistence seam or stale log wording first
- add a focused regression test for "registration claimed but durable pending-state proof missing"
- do not move to PR-4 work until this ambiguity is removed

---

### Step 2 — Re-soak close-path lineage after PR-1b

#### Why this is second
A missing `decision_id` at close time invalidates every downstream learning/adaptation claim.
PR-1b appears to have improved this, but the roadmap explicitly says it still needs soak verification.

#### Questions to answer
- Are any normal closes still producing `Learning handoff SKIPPED ... reason=missing_decision_id`?
- When lineage is recovered, which source actually wins?
- Is the recent decision-store fallback only a rescue path, or is it masking earlier preservation failure?

#### Surgical inspection plan
1. gather a fresh soak window of close events after commit `914371d`
2. search for:
   - `Learning handoff ATTEMPT`
   - `Learning handoff ACCEPTED`
   - `Learning handoff FAILED`
   - `Learning handoff SKIPPED`
   - `reason=missing_decision_id`
3. build a tiny per-close classification table:
   - close timestamp
   - product/asset
   - order id
   - decision id present or absent
   - lineage source used
   - final handoff outcome
4. for any skip, capture attempted lineage sources in order
5. decide whether the failure is:
   - a preservation bug while position is still open
   - a recovery ordering bug
   - an edge case outside the current intended seam

#### Required proof artifact
A small soak summary covering all closes in the window with explicit handoff status and lineage source.

#### Pass / fail box
- [ ] PASS: no fresh normal close in the verification window ends with `missing_decision_id`
- [ ] FAIL: at least one fresh normal close still skips learning because decision lineage was lost

#### If fail
- patch the earliest preservation point possible, not the broadest fallback layer
- add one narrow regression test for the exact failed lifecycle
- repeat Step 2 before touching adaptation proof work

---

### Step 3 — Re-soak portfolio-memory autosave after `115dc12`

#### Why this is third
The autosave serialization failure was explicitly elevated to priority #1 once it was discovered live.
A learning chain that mutates memory but cannot save it durably is not boring enough.

#### Questions to answer
- Did the `'dict' object has no attribute 'to_dict'` warning actually disappear after deploy?
- Do mixed object/dict entries now round-trip through save/load safely?
- Is the persisted memory artifact still readable after fresh learning events?

#### Surgical inspection plan
1. gather logs after commit `115dc12` deploy window
2. search for:
   - `Failed to auto-save portfolio memory`
   - `'dict' object has no attribute 'to_dict'`
   - portfolio memory update success markers
3. correlate a fresh learning event with:
   - handoff accepted
   - memory update logged
   - autosave path completing without warning
4. inspect the resulting durable memory artifact
5. confirm the artifact can be reloaded without compatibility errors

#### Required proof artifact
For one fresh learning event, record:
- timestamp
- order id
- decision id
- memory update log evidence
- autosave status evidence
- durable file/store path
- load/read confirmation

#### Pass / fail box
- [ ] PASS: no fresh autosave warning appears and the saved memory artifact remains readable after the learning event
- [ ] FAIL: autosave warnings persist, or save/load compatibility remains uncertain

#### If fail
- patch serialization/load compatibility before any adaptation work
- add a regression test that round-trips mixed dict/object entries through save and load
- repeat Step 3 until the seam is boring

---

### Step 4 — Build a one-trade audit trace record

#### Why this is fourth
This converts the new instrumentation into operator-proof evidence instead of scattered greps.
It is also the seed for PR-5, but should be built now while Track 0 is being soaked.

#### Record template
For one real closed trade, capture in one place:
- close timestamp
- asset / product id
- order id
- decision id
- lineage source used
- durable outcome artifact path and record locator
- learning handoff status
- memory/performance mutation evidence
- pending outcome registration/persistence evidence
- adaptive-state evidence (if any)
- open questions / anomalies

#### Surgical inspection plan
1. pick one clean close from the recent live window
2. trace it forward from close detection to outcome recording
3. trace it through learning handoff
4. trace it into memory/performance mutation
5. note whether adaptation evidence exists yet or remains unproved

#### Required proof artifact
A single compact audit note that proves the chain for one trade without re-reading broad runtime history.

#### Pass / fail box
- [ ] PASS: one real trade can be traced end-to-end through outcome, lineage, handoff, and memory evidence with no ad hoc spelunking
- [ ] FAIL: proving one trade still requires broad manual reconstruction from logs and code

#### If fail
- add the missing instrumentation or documentation at the narrowest missing link
- do not compensate with a bigger runbook yet; fix the missing seam evidence first

---

### Step 5 — Only after Steps 1–4 pass: scope PR-4 narrowly

#### Rule
Do not begin with "prove adaptation" as an abstract goal.
Pick one adaptive mechanism and prove that one mechanism changes because of outcomes and is later used.

#### Candidate mechanisms
- provider weights
- performance tracker
- debate / ensemble selector
- reward / feedback analyzer state

#### Surgical inspection plan
1. identify the single true adaptive state holder to target first
2. map:
   - update trigger
   - durable state location
   - later read/use site
3. instrument before/after state around one learning-triggering event
4. prove the later selector/weighting path actually read the changed state

#### Required proof artifact
A before/after record showing:
- learning-triggering outcome identifiers
- adaptive state before
- adaptive state after
- later runtime read/use evidence
- distinction between runtime learning update vs config normalization

#### Pass / fail box
- [ ] PASS: one adaptive mechanism is shown to change because of a real/near-live outcome and later influence runtime behavior
- [ ] FAIL: only memory/performance stats changed, with no proved downstream adaptive effect

#### If fail
- narrow the mechanism further
- instrument the later read/use site
- do not broaden to multiple adaptive paths until one is fully proved

---

## Session-start execution checklist

Use this as the literal next-session checklist.
Proceed top to bottom.
Do not skip a failing box just because a later item sounds more interesting.

### A. Pending outcome persistence seam
- [ ] locate `Registered executed order ... for outcome tracking` emitter
- [ ] identify canonical pending outcome durable state location
- [ ] verify one real registration event against that state
- [ ] classify `{}` in `data/pending_outcomes.json` as expected or broken
- [ ] if broken, patch seam or log wording and add regression test

### B. Close-path lineage soak
- [ ] collect fresh close events after `914371d`
- [ ] classify each close as ACCEPTED / FAILED / SKIPPED
- [ ] verify no fresh `reason=missing_decision_id` on normal closes
- [ ] capture lineage source for each close in sample window
- [ ] if broken, patch earliest preservation point and retest

### C. Portfolio-memory autosave soak
- [ ] collect fresh post-`115dc12` learning events
- [ ] verify no `'dict' object has no attribute 'to_dict'` warnings
- [ ] verify memory update followed by quiet durable save
- [ ] inspect saved memory artifact
- [ ] confirm load/read compatibility after save

### D. One-trade audit note
- [ ] choose one real closed trade
- [ ] capture outcome artifact evidence
- [ ] capture lineage evidence
- [ ] capture handoff evidence
- [ ] capture memory/performance mutation evidence
- [ ] capture pending-state evidence
- [ ] note whether adaptation evidence exists yet

### E. PR-4 narrow scoping (only if A-D pass)
- [ ] choose exactly one adaptive mechanism
- [ ] map update trigger, durable state, and later read site
- [ ] instrument before/after state
- [ ] prove later runtime use of changed state
- [ ] document result as adaptation proof or not-yet-proved

## Stop conditions

Stop forward progress and treat the discovered issue as the active task if any of the following occur:
- a fresh normal close still skips with `missing_decision_id`
- outcome registration still cannot be tied to a durable artifact
- autosave warnings persist or saved memory cannot be read back
- proving one trade still requires broad manual reconstruction

## Advancement rule

PR-4 becomes the active implementation stream only when:
- Step 1 passes
- Step 2 passes
- Step 3 passes
- Step 4 passes

Until then, the correct move is not broader cleverness.
It is making the lower links boring enough to trust.

---

## Deep audit infusion — decision serialization trail (2026-03-29)

This audit should shape all future Track 0 work.
It explains why lineage bugs keep recurring even after targeted read-path fixes.

### Architecture reality

Decisions are still plain dicts with 70+ fields.
There is no dataclass, no Pydantic model for the canonical runtime shape, and no `_schema_version` field.
That means every write path and every recovery/read path must independently tolerate:
- field aliases
- partial shapes
- missing optionals
- format drift across older persisted decisions

### Serialization surfaces to remember

#### Write paths
1. `persistence/decision_store.py` — full decision dict → JSON
2. `backtesting/decision_cache.py` — full decision dict → SQLite JSON
3. `agent/trading_loop_agent.py` recovery synthesis — manually constructed partial decision dict
4. `api/routes.py` — 5-field Pydantic response subset
5. `memory/portfolio_memory.py` — `TradeOutcome` with decision reference only

#### Read / recovery paths
1. decision-store JSON load
2. backtest-cache JSON load
3. recovery decision lookup by product/side/platform/price
4. 6-source lineage recovery fallback chain
5. portfolio-memory load with backward-compat mapping

### Canonical field-drift findings

#### High-risk alias families
- decision id aliases: `id` vs `decision_id` vs legacy `decision`
- traded-asset aliases: `asset_pair` vs `product_id` vs `product` vs `asset`
- semantic action aliases: `action` vs `side` vs `direction`

Normalization helpers exist, but they are not consistently enforced at write boundaries.
That is the root architecture for the recurring lineage bug class.

### Important conclusions for Track 0

1. The recurring bug pattern is still **schema drift + inconsistent normalization boundaries**, not one single read-path mistake.
2. Recovery decisions are structurally smaller than validator-created decisions, so all readers still need to tolerate multiple decision shapes.
3. The 6-source lineage recovery chain is still order-dependent; ephemeral stores can drift before durable lookup rescues the close path.
4. `df791cc` removed two active alias bugs from the close path:
   - canonical `side` now survives pending-order tracking instead of degrading to `action`
   - trade outcomes now normalize `product` and `product_id` both ways before lineage and learning handoff logic

### Audit-informed remediation plan

#### Immediate remediation batch (do now, small + high-signal)
- [x] `order_status_worker.py` canonical side preservation (`df791cc`)
- [x] `trading_loop_agent.py` product/product_id alias normalization (`df791cc`)
- [x] `api/bot_control.py` log degraded status payload when `get_daily_pnl()` fails instead of silently swallowing it (`bbf71b0`)
- [x] `api/bot_control.py` log unexpected primary WebSocket receiver death before stopping the stream (`bbf71b0`)
- [x] `api/bot_control.py` log unexpected portfolio WebSocket sender death before stopping the stream (`bbf71b0`)
- [x] `decision_engine/ensemble_manager.py` raise failover config-sync visibility from debug to error (`bbf71b0`)
- [x] `api/bot_control.py` log unexpected positions WebSocket sender/receiver death before stopping the stream (`027fcfe`)
- [x] `api/bot_control.py` log unexpected decisions WebSocket sender/receiver death before stopping the stream (`027fcfe`)

#### Next structural prevention batch (not same as one-line bugfixes)
- [ ] add `_schema_version` to newly persisted decisions
- [ ] add round-trip serialization tests for canonical decision fields
- [ ] add one single decision-id normalizer for `id` / `decision_id` / `decision`
- [ ] document whether `flake8` is intentionally deferred
- [ ] bound critical runtime dependency majors in `pyproject.toml`

### How this changes PR-4 work

Before claiming provider/model adaptation proof, decision artifacts need to be treated as first-class evidence.
That means PR-4 should now explicitly verify:
- persisted decision shape at write time
- persisted ensemble metadata completeness
- whether adaptation uses a full decision artifact or a degraded/recovery-only subset

If adaptation is unproved, inspect the decision artifact first before adding more downstream fallbacks.

### Latest live verification after remediation deploys

Canonical live host remains `10.130.252.165` (Asus GPU laptop); authoritative runtime artifacts remain Docker-mounted `/app/data` rather than host repo `data/`.

Recent deploy checkpoints:
- `df791cc` — canonical side preservation + product/product_id alias normalization
- `bbf71b0` — serialization-adjacent observability hardening
- `027fcfe` — remaining positions/decisions WebSocket failure visibility

Post-deploy live verification on the Asus showed:
- backend and postgres both returned healthy after each redeploy
- a fresh ETH execution completed end-to-end through:
  - decision persistence
  - trade execution
  - pending-order registration
  - pending-order sweep
  - outcome recording
- a fresh close after the last redeploy completed end-to-end through:
  - decision-id recovery via `decision_store.recovery_metadata_product`
  - `Learning handoff ATTEMPT`
  - `Learning handoff ACCEPTED`
  - portfolio memory save/update
  - recorded learning outcome
- `pending_outcomes.json` draining back to `{}` remained consistent with healthy worker sweep behavior, not a fresh failure signal
- no fresh `missing_decision_id` and no fresh portfolio-memory autosave warning were seen in the sampled window
- logs remain noisy on startup because historical `recovery` trades are replayed into memory/Thompson integration, but this did not present as a runtime failure in the sampled window

### Soak conclusion

The post-remediation soak window is now good enough to stop treating PR-1/PR-3 fixes as fragile.

Working conclusion:
- the live chain from execution -> durable outcome -> lineage recovery -> learning handoff -> portfolio-memory persistence is now boring enough to move out of immediate fire-fighting
- the next Track 0 bottleneck is no longer close-path survival; it is **adaptation proof clarity**
- the next work should therefore be PR-4 evidence work, not more generic stability poking

This does **not** mean the system is finished.
It means the burden of proof has moved up-stack.

### Updated medium-risk operational focus

The remaining medium-risk class is now less about silent WebSocket death and more about broader runtime-noise / replay / adaptation-proof clarity:
- startup replay noise around `recovery` trade recording and Thompson updates
- repeated ensemble provider-weight normalization logs after config merge
- structural serialization prevention work (`_schema_version`, round-trip tests, single decision-id normalizer)
- ambiguity about what "adaptation evidence" should look like under debate mode vs weighted mode

These are still worth doing, but they are no longer in the same immediate class as the now-remediated silent-failure surfaces.

### PR-4 clarification after live inspection

A key clarification from the latest live inspection:
- recent persisted ensemble decisions were **not** missing ensemble metadata entirely
- instead, the rich fields were nested under `ensemble_metadata`
- the recent live runtime was producing **debate-mode** decisions, not plain weighted-voting decisions

That distinction matters.
The wrong question is:
- "why are top-level `original_weights` / `adjusted_weights` / `provider_decisions` empty?"

The more correct questions are:
- what is the canonical persisted contract for a **debate-mode** decision?
- what is the canonical persisted contract for a **weighted-mode** decision?
- in each mode, what exact artifact is supposed to change when learning/adaptation occurs?

### Mode-aware PR-4 proof spine

#### Debate-mode reality (current live shape)
Recent live decision artifacts show:
- `ai_provider = "ensemble"`
- `ensemble_metadata.voting_strategy = "debate"`
- `ensemble_metadata.role_decisions` populated
- `ensemble_metadata.debate_seats` populated
- `ensemble_metadata.provider_decisions` carrying a legacy/minimal judge-centric view
- `ensemble_metadata.original_weights = {}`
- `ensemble_metadata.adjusted_weights = {}`

That means empty weight dictionaries are **not automatically a serialization bug** in debate mode.
They may simply be the current debate contract.

#### Weighted-mode expectation (still must be proved)
For non-debate weighted ensemble decisions, the persisted artifact should still explicitly preserve:
- `ensemble_metadata.original_weights`
- `ensemble_metadata.adjusted_weights`
- `ensemble_metadata.provider_decisions`
- enough provider-level detail to connect a later learning update back to the decision that generated it

If weighted-mode persistence drops those fields, that is a real PR-4 seam.
If it preserves them, the remaining seam moves downstream into adaptation-state mutation and operator-facing proof.

### PR-4 test plan to land before broad adaptation claims

#### 1. Persistence contract tests
Add focused tests for two distinct decision shapes:
- debate-mode persisted decision contract
- weighted-mode persisted decision contract

The point is to stop treating all ensemble decisions as if they share one evidence shape.

#### 2. DecisionStore round-trip test
Persist a decision with rich nested `ensemble_metadata`, then reload it and assert full round-trip preservation of:
- `original_weights`
- `adjusted_weights`
- `provider_decisions`
- `role_decisions`
- `debate_seats`

This removes the store layer from suspicion.

#### 3. Engine propagation tests
Prove ensemble metadata survives from aggregator/debate manager -> validator -> final decision -> persistence.

This should explicitly cover:
- debate-mode metadata propagation
- weighted-mode metadata propagation

#### 4. Learning-to-adaptation tests
For a weighted-mode decision with provider decisions attached:
- record a trade outcome
- assert the adaptive update path actually mutates canonical learning/adaptation state
- assert a later decision or weight calculation can observe that change

If debate mode is the production runtime, add a non-lying test that states what debate mode does **not** currently prove.
That is better than pretending weighted-weight evidence exists where it does not.

#### 5. One live proof packet
For one fresh live decision/outcome pair, capture:
- persisted decision artifact
- voting mode (`debate` vs `weighted`)
- outcome artifact
- learning handoff acceptance evidence
- canonical post-learning state artifact (`ensemble_history.json`, provider stats, or some stronger adaptation ledger)

The operator goal is simple:
- no more "I think it adapted"
- one compact before/after packet that proves whether it did

### PR-4 immediate working question

The next coding/testing pass should answer this before adding more fallbacks:

> In the mode the live system is actually using, what is the canonical adaptation signal that should change after learning?

If the answer is "weights," then debate mode is not yet surfacing enough evidence.
If the answer is "provider performance state" or some other tracker, then that state must become the explicit proof target.

### PR-4 ordered implementation checklist

This is the next-session execution order.
Do not skip ahead unless an earlier step proves irrelevant.

#### Step A — Lock the persistence contract before changing behavior

##### Goal
Remove ambiguity about whether ensemble evidence is being lost vs merely nested or mode-shaped differently.

##### Suggested test targets
- `tests/persistence/test_decision_store_ensemble_metadata.py`
- or an equivalent focused addition near existing persistence coverage

##### Test cases
1. **DecisionStore round-trip preserves nested debate metadata**
   - save decision with `ensemble_metadata.role_decisions`, `debate_seats`, legacy `provider_decisions`
   - reload and assert exact preservation
2. **DecisionStore round-trip preserves nested weighted metadata**
   - save decision with `ensemble_metadata.original_weights`, `adjusted_weights`, `provider_decisions`
   - reload and assert exact preservation
3. **No accidental top-level alias expectation**
   - assert tests read from `ensemble_metadata`, not nonexistent top-level shadow fields, unless the code intentionally writes both

##### Exit criteria
- store layer is proved innocent or guilty with a tiny, durable test surface
- future debugging can stop hand-waving about JSON persistence

#### Step B — Lock the decision-shape contract per ensemble mode

##### Goal
Make debate-mode and weighted-mode evidence shapes explicit so operators and tests stop conflating them.

##### Suggested test targets
- `tests/decision_engine/test_ensemble_metadata_contracts.py`
- or additions adjacent to existing ensemble/debate coverage

##### Test cases
1. **Debate-mode contract**
   - persisted/returned decision includes:
     - `ai_provider = "ensemble"`
     - `ensemble_metadata.voting_strategy = "debate"`
     - `role_decisions`
     - `debate_seats`
     - judge-centric legacy `provider_decisions`
   - explicitly assert `{}` for `original_weights` and `adjusted_weights` if that is the intended current contract
2. **Weighted-mode contract**
   - persisted/returned decision includes:
     - populated `original_weights`
     - populated `adjusted_weights`
     - populated `provider_decisions`
     - any vote-summary metadata expected by the aggregator
3. **Contract mismatch test**
   - if a debate decision is inspected as though it were weighted, the test/doc should make that category error obvious

##### Exit criteria
- one can look at a persisted decision and classify it as debate vs weighted without guesswork
- empty weights in debate mode are no longer misdiagnosed as generic serialization failure

#### Step C — Prove metadata survives engine propagation

##### Goal
Verify the metadata survives aggregator/debate manager -> decision validator -> final decision object -> persistence call.

##### Suggested code seams
- `finance_feedback_engine/decision_engine/ensemble_manager.py`
- `finance_feedback_engine/decision_engine/debate_manager.py`
- `finance_feedback_engine/decision_engine/engine.py`
- `finance_feedback_engine/decision_engine/decision_validator.py`

##### Suggested test targets
- extend existing decision-engine tests rather than writing giant new end-to-end cases

##### Test cases
1. **Weighted metadata propagation**
   - mock aggregator result with rich `ensemble_metadata`
   - pass through engine/validator path
   - assert metadata survives into saved decision
2. **Debate metadata propagation**
   - mock debate result with `role_decisions` / `debate_seats`
   - assert same end-to-end preservation
3. **No silent contraction**
   - ensure helper/validator layers do not strip unknown-but-important nested ensemble fields

##### Exit criteria
- if metadata disappears, the exact shrinking seam is identified
- if metadata survives, PR-4 focus moves downstream into adaptation-state proof

#### Step D — Prove learning mutates canonical adaptation state

##### Goal
Show that outcome ingestion changes something durable and inspectable in the adaptation path.

##### Suggested code seams
- `finance_feedback_engine/core.py::record_trade_outcome`
- `finance_feedback_engine/decision_engine/performance_tracker.py`
- `finance_feedback_engine/decision_engine/ensemble_manager.py`

##### Suggested test targets
- focused unit/integration tests near existing Thompson/performance tests

##### Test cases
1. **Weighted-mode learning updates provider performance state**
   - start with known provider decisions
   - record positive/negative outcome
   - assert `ensemble_history.json` or in-memory performance history changes
2. **Weighted-mode learning changes derived adaptive weights**
   - call weight calculation before/after outcome ingestion
   - assert change is attributable to the recorded outcome, not config normalization
3. **Debate-mode honesty test**
   - assert what debate mode currently updates and what it does not
   - if debate mode only updates provider stats but not weights, say so in test names and assertions

##### Exit criteria
- adaptation evidence is reduced to one or two canonical state artifacts
- no one needs to infer adaptation indirectly from vague logs

#### Step E — Build one operator-facing live proof packet

##### Goal
Turn code-level proof into a compact field runbook artifact.

##### Contents of the packet
For one fresh live decision/outcome pair, capture:
1. persisted decision JSON path
2. mode classification (`debate` or `weighted`)
3. critical ensemble metadata snapshot
4. outcome artifact path
5. learning handoff log lines
6. post-learning adaptation-state artifact path/value

##### Suggested artifact location
- append to this spine or create a small sibling runbook under `docs/plans/` or `docs/runbooks/`

##### Exit criteria
- an operator can prove or disprove adaptation from a bounded packet of evidence
- Track 0 status can be reported from artifacts instead of intuition

### First live proof packet (captured 2026-03-29 after soak)

#### Packet summary
A bounded live packet now exists, but it proves an asymmetric result:
- **proved live:** close-path lineage recovery -> learning handoff acceptance -> durable outcome artifact -> portfolio-memory persistence
- **not proved live:** provider/model adaptation on the ensemble path

That is not a contradiction.
It is a mode/artifact mismatch.

#### Packet A — accepted live learning handoff on recovery decision

Latest clean sampled close:
- close timestamp in logs: `2026-03-29 17:04:24 UTC`
- closed product: `ETP-20DEC30-CDE`
- recovered decision id: `94b02477-7d42-4a9a-aed6-2646f8b71f1a`
- lineage source: `decision_store.recovery_metadata_product`
- handoff result: `Learning handoff ACCEPTED`
- realized pnl in acceptance line: `7.5`

Observed log chain:
- `Recovered decision_id 94b02477-7d42-4a9a-aed6-2646f8b71f1a ... lineage_source=decision_store.recovery_metadata_product`
- `Learning handoff ATTEMPT ... decision_id=94b02477-7d42-4a9a-aed6-2646f8b71f1a`
- `Learning handoff ACCEPTED ... decision_id=94b02477-7d42-4a9a-aed6-2646f8b71f1a | realized_pnl=7.5`

Correlated durable artifacts:
- decision artifact: `/app/data/decisions/2026-03-29_94b02477-7d42-4a9a-aed6-2646f8b71f1a.json`
- outcome artifact: `/app/data/memory/outcome_94b02477-7d42-4a9a-aed6-2646f8b71f1a.json`
- portfolio memory file: `/app/data/memory/portfolio_memory.json`

Decision artifact facts:
- `ai_provider = "recovery"`
- `action = "SELL"`
- `asset_pair = "ETP20DEC30CDE"`
- recovery metadata present for Coinbase product aliasing
- no ensemble metadata / provider decisions / adaptation-weight evidence on this artifact

Outcome artifact facts:
- `decision_id = 94b02477-7d42-4a9a-aed6-2646f8b71f1a`
- `realized_pnl = 7.5`
- timestamp aligns with handoff acceptance window

Portfolio-memory persistence facts:
- `/app/data/memory/portfolio_memory.json` mtime moved to `2026-03-29 17:04:24 UTC`
- `/app/data/pending_outcomes.json` then drained back to `{}` (size `2` bytes) by `2026-03-29 17:04:46 UTC`

#### What Packet A proves

Packet A is sufficient to prove:
1. durable decision lookup rescued the close path
2. accepted learning handoff occurred for the closed trade
3. outcome artifact was written durably
4. portfolio memory was updated durably
5. pending outcome drain behavior remained healthy after processing

#### What Packet A does *not* prove

Packet A does **not** prove provider/model adaptation because the accepted close is tied to a `recovery` decision artifact, not an ensemble decision artifact.

That means there is no provider-level attribution on the packet’s decision itself:
- no `ensemble_metadata`
- no `provider_decisions`
- no debate-role evidence
- no weighted adaptation fields

So this packet proves lower-chain learning durability, but not PR-4 provider adaptation.

### Key live contradiction resolved

At the same time the accepted closes are landing on `recovery` decisions, the recent BTC/ETH live decision artifacts are clearly **ensemble debate-mode** decisions.

Recent sampled live BTC/ETH decisions show:
- `ai_provider = "ensemble"`
- `ensemble_metadata.voting_strategy = "debate"`
- `providers_used = ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"]`
- judge-centric legacy `provider_decisions`
- full `role_decisions` and `debate_seats`

So the runtime currently has both:
- ensemble debate decisions being generated on BTC/ETH
- recovery decisions being used as the authoritative lineage anchor for accepted closes on the sampled ETP/BIP path

This explains why live lower-chain learning can be healthy while live provider adaptation remains unproved.

### Current best adaptation-state artifact check

The most obvious durable adaptation ledger currently available is:
- `/app/data/ensemble_history.json`

Latest inspection showed:
- file exists
- mtime: `2026-01-06 15:06:34 UTC`
- contents remain stale/minimal (`local` provider only)

That matters.
If March 29 handoffs had produced durable ensemble/provider adaptation on the currently sampled live path, this file would be a natural place to expect change.
It did **not** move during the verified March 29 handoff packet.

#### Practical conclusion from Packet A + adaptation-state check

Current live evidence supports this narrower claim:
- Track 0 learning durability is real
- PR-4 provider adaptation is still **not proved live**

Stronger interpretation:
- the live accepted-close path is still dominated by `recovery` decision artifacts for the audited closes
- therefore provider-attributed adaptation state is not getting an auditable proof packet from those closes
- until a fresh accepted close can be tied back to a true ensemble-originated decision artifact (or a separate provider-state ledger clearly changes), PR-4 should remain open

### Revised live-proof packet requirement for PR-4 closure

A closing packet should now require **all** of the following in one chain:
1. persisted decision artifact with `ai_provider = "ensemble"`
2. visible mode classification (`debate` or `weighted`)
3. provider-attribution evidence on that decision artifact (`provider_decisions` and/or `role_decisions`)
4. accepted close/outcome linked back to that same decision id
5. post-learning durable provider/adaptation state mutation

Until that packet exists, do not overclaim adaptation.

### Latest live finding — sticky recovery anchors still dominate BIP/ETP closes

Recent overnight/live verification produced an important narrowing result:

- the runtime is healthy and actively trading
- fresh BTC/ETH decisions are still being persisted as clean `ai_provider = "ensemble"` debate-mode artifacts
- but accepted BIP/ETP closes are still repeatedly resolving to the same old recovery decision ids:
  - `60f440ea-ce91-4169-bdf9-f54fed37dacb` (BIP)
  - `f8320792-0301-47c7-bcb7-59f8d684e386` (ETP)
- those accepted closes still use:
  - `lineage_source = decision_store.recovery_metadata_product`
  - `provider = recovery`
- the persisted recovery decision files for those ids still lacked:
  - `shadowed_from_decision_id`
  - `shadowed_from_provider`
  - preserved `ensemble_metadata`
  - preserved `policy_trace`

That means the lower learning chain is still healthy, but the live adaptation path is still blocked by **sticky reused recovery anchors**.

### Attribution-preservation work completed but narrowed by live evidence

Two recovery-preservation slices are now in code:

1. **new recovery wrapper preservation**
   - newly created synthetic recovery decisions can inherit source attribution fields
2. **existing recovery upgrade path**
   - reused recovery decisions can now be upgraded in place with preserved attribution if a matching source decision is found

However, live evidence showed that this still did not fire for the BIP/ETP anchors above.

### What the live data proved about the current matcher

The current source-decision matcher was originally too literal for the live futures path.

The failing real-world shape looked like:

- source decision:
  - `asset_pair = BTCUSD / ETHUSD`
  - `action = OPEN_SMALL_SHORT`
  - fractional `recommended_position_size`
- recovered futures anchor:
  - `asset_pair = BIP20DEC30CDE / ETP20DEC30CDE`
  - `action = SELL`
  - `position_size = 1.0` contract

So the live miss was a three-part domain mismatch:

1. **asset namespace mismatch**
   - underlying pair vs futures product alias
2. **action-family mismatch**
   - canonical policy action vs execution-side adapter action
3. **size-domain mismatch**
   - fractional asset sizing vs whole futures contract count

### New next slice drafted from data — cross-domain attribution matcher

The next slice is no longer generic recovery work.
It is specifically:

#### Goal
Teach recovery-source matching to bridge underlying-asset ensemble decisions to reused futures recovery anchors.

#### Required bridges
- `BTCUSD` <-> `BIP20DEC30CDE`
- `ETHUSD` <-> `ETP20DEC30CDE`
- `OPEN_SMALL_SHORT` <-> `SELL`
- fractional source sizing <-> `1.0` contract recovery sizing

#### Narrow implementation plan
1. use asset alias candidates rather than exact `asset_pair` equality
2. match on directional position side rather than literal action string
3. use tolerant entry-price matching instead of exact float equality
4. allow a cross-domain size bridge for the common futures case (`1.0` contract vs fractional underlying size)
5. once matched, upgrade reused recovery decisions in place with:
   - `ai_provider`
   - `ensemble_metadata`
   - `policy_trace`
   - `decision_source`
   - `shadowed_from_decision_id`
   - `shadowed_from_provider`

#### Tests to pin this slice
- matcher-level regression for BTCUSD -> BIP contract bridging
- matcher-level regression for ETHUSD -> ETP contract bridging
- recovery-agent regression showing an existing plain BIP recovery anchor upgraded from an underlying BTC ensemble source

#### Exit criterion for this slice
After deploy, reused BIP/ETP recovery anchors should be able to carry preserved ensemble provenance on disk.
Only then does the adaptive proof packet have a realistic chance of firing live.

### Recommended coding order if time is tight

If only one narrow pass fits in the next session, do this exact order:
1. Step A1/A2 — DecisionStore round-trip tests
2. Step B1/B2 — debate vs weighted contract tests
3. Step D1 — prove learning mutates canonical performance state
4. only then decide whether PR-4 needs code changes or just stronger observability/runbook work

### Anti-drift rules for the next pass

- do not add more lineage fallbacks unless a lower-link regression reappears
- do not claim serialization failure until nested `ensemble_metadata` is inspected
- do not claim adaptation proof from debate-mode artifacts using weighted-mode expectations
- do not broaden into Telegram / ops UX work while PR-4 proof remains unresolved
- prefer one sharp failing test over a broad speculative refactor

---

## Ops front-end audit infusion — Telegram as control interface (2026-03-29)

### Verdict

Telegram is a **high-viability** front-end control surface for FFE.
The backend is already ready; the gap is mostly in the command layer.

### Current state

FFE already has a Telegram approval bot with:
- `/start`
- approval queue / pending approval flow
- inline approve / reject / modify controls
- allowed-user whitelist security
- FastAPI webhook integration
- Redis-backed approval queue with in-memory fallback

What it does **not** currently expose in Telegram:
- agent lifecycle control
- balance / portfolio queries
- positions listing / closing
- decision summaries
- config changes
- health/readiness checks
- P&L reporting

### Why this is viable

The existing REST/API layer already supports almost everything needed for Telegram operator control.
The Telegram layer can remain thin:
- parse command
- call existing API endpoint or engine surface
- format response for Telegram

This avoids new trading logic and avoids backend architectural churn.

### Backend/API readiness summary

The current API surface already supports:
- start / stop / pause / resume / emergency-stop
- bot status
- open positions
- close position
- portfolio / balance status
- recent decisions
- config patching
- manual trade
- health check

So this is fundamentally a **front-end command wiring task**, not a backend capability project.

### Recommended implementation slice

#### Tier 1 — operator essentials (highest-value first)
- `/status`
- `/balance`
- `/positions`
- `/decisions [n]`
- `/start [pairs]`
- `/stop`
- `/emergency` (with confirmation)

#### Tier 2 — active management
- `/pause`
- `/resume`
- `/close <id>`
- `/pnl`
- `/health`

#### Tier 3 — careful configuration
- `/config`
- `/set <param> <value>` with explicit confirmation

### Architecture recommendation

Preferred path: extend the existing `integrations/telegram_bot.py` rather than create a separate control bot.

Reasons:
- auth/whitelist is already implemented
- webhook flow already exists
- approval UX patterns already exist
- the additive work is straightforward command-handler wiring

Only split into a second module/bot if operator trust separation is needed.

### Risk notes

#### Real risks
- destructive commands from chat (`/emergency`, `/close`) need two-step confirmation
- sensitive operational data will exist in Telegram history if sent there
- Telegram webhook delivery is best-effort, so command UX should stay pull-based

#### Recommended mitigations
- require inline confirmation for destructive actions
- never send secrets/tokens/config secrets via Telegram
- accept Telegram for operator visibility/control, not as the only critical alerting path

### What not to overbuild in Telegram
- charts/graphs
- real-time streaming dashboards
- multi-step config wizards
- full trade-history browsing

Telegram should be treated as a **mobile operator control surface**, not a replacement for the web dashboard.

### Sequencing relative to Track 0

This is **post-Track-0** work.
It should not compete with boring reliability work.

Recommended trigger:
- implement Tier 1 once Track 0 Gate 1 is satisfied and no fresh lineage regressions appear across a meaningful soak window

### Practical roadmap consequence

This is a strong candidate for an FFE 1.0 / ops-hygiene slice because:
- value is high for single-operator mobile control
- effort is comparatively low
- backend risk is low
- it reuses existing Telegram + API infrastructure instead of creating a second control plane
