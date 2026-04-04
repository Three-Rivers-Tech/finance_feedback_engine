# FFE Efficiency Roadmap — 2026-04-04

## Purpose

Post-1.0-hardening efficiency push across three fronts: trading quality, system performance, and development velocity. The system is stable and reliable. Now make it **smart, fast, and maintainable**.

> **The bot is boring and reliable. Now make it profitable and lean.**

---

## Current Position

FFE is operationally stable:
- Lineage/learning pipeline hardened (linkage fix deployed, stale-reuse guard active)
- Portfolio equity math corrected
- SortinoGate wired end-to-end (auto-activates when edge is positive)
- Data volumes on secondary disk, weekly cleanup cron
- 17 broken tests fixed, CI-ready
- Rebrand complete

Key metrics (Apr 3-4 soak):
- 122 trades/day, 43% win rate, -$165 daily PnL
- SHORT side profitable (+$294), LONG side hemorrhaging (-$459)
- 65% of trades held <10s (churn), best trades are longer holds
- 35/39 futures closes missing decision_id (learning gap still present for pre-patch positions)
- SortinoGate correctly at fixed_risk (negative sortino -0.099)
- Cycle time 35-50s (3 LLM calls dominate)

---

## Track E1 — Pre-Reasoning Layer (Trading Efficiency)

**Goal:** Add a lightweight reasoning step before debate to filter no-ops and produce focused market briefs.

### Phase 1: Market Context Summarizer
- [ ] Single fast LLM call before debate: "Given this market data, what is the key question right now?"
- [ ] Output: structured brief (regime, key levels, momentum summary, open position context)
- [ ] Brief injected into bull/bear/judge prompts (replaces raw data dump)
- [ ] Tests: mock LLM returns structured brief, debate receives it

### Phase 2: No-Op Gate
- [ ] If pre-reasoner determines "no actionable signal" with high confidence AND no open position → skip debate entirely
- [ ] Log the skip decision for audit
- [ ] Configurable: `pre_reasoning.skip_threshold` (default 85% confidence)
- [ ] Reduces wasted LLM calls on dead markets

### Phase 3: Adaptive Cycle Timing
- [ ] When flat + no signal: extend cycle interval (e.g. 10min instead of 5min)
- [ ] When position open: keep tight cycle interval
- [ ] When volatility spike detected: shorten cycle interval
- [ ] Config: `cycle_timing.adaptive_enabled`, `min_interval_s`, `max_interval_s`

**Success:** Fewer wasted cycles, better signal quality, lower inference cost.

---

## Track E2 — Trade Quality (Trading Efficiency)

**Goal:** Reduce churn, improve hold times, and eliminate the rapid-fire loss pattern.

### Phase 1: Minimum Hold Time Gate
- [ ] After opening a position, enforce minimum hold period before considering close
- [ ] Config: `trade_quality.min_hold_seconds` (default 120s)
- [ ] Exception: stop-loss / liquidation-risk overrides the gate
- [ ] Prevents the 14-second round-trips that lose money

### Phase 2: Re-Entry Cooldown
- [ ] After closing a position, enforce cooldown before opening same direction
- [ ] Config: `trade_quality.reentry_cooldown_seconds` (default 300s)
- [ ] Prevents the "close SHORT → immediately open SHORT" churn pattern

### Phase 3: Prompt Engineering
- [ ] Audit current bull/bear/judge prompts for quality
- [ ] Add explicit hold-time awareness ("you are managing a position, not scalping")
- [ ] Include recent trade history in prompt ("last 5 trades: 4 losses, avg hold 12s")
- [ ] Test: compare decision quality before/after prompt changes

**Success:** Average hold time >2min, fewer round-trips/day, higher win rate.

---

## Track E3 — System Performance (Infra Efficiency)

**Goal:** Faster builds, leaner containers, smarter resource usage.

### Phase 1: Docker Build Optimization
- [ ] Pin dependency versions in Dockerfile to maximize layer cache hits
- [ ] Split requirements into base (rarely changes) and app (changes often)
- [ ] Add `.dockerignore` review (exclude tests, docs, scratch from build context)
- [ ] Target: rebuild time <60s for code-only changes (currently ~100s)

### Phase 2: Coinbase After-Hours Awareness
- [ ] Detect CFM restricted hours (~5-6 PM EDT weekdays)
- [ ] Skip execution attempts during restricted windows
- [ ] Log the skip for audit
- [ ] Eliminates `PREVIEW_FUTURES_AFTER_HOUR_INVALID_ORDER_TYPE` errors

### Phase 3: Dashboard Event Queue
- [ ] Fix the 500-event queue overflow (events dropping silently)
- [ ] Either increase queue size, implement drain, or switch to ring buffer
- [ ] Cosmetic but noisy in logs

**Success:** Faster deploys, zero after-hours errors, clean logs.

---

## Track E4 — Development Velocity (Dev Efficiency)

**Goal:** Faster iteration, better safety net, cleaner codebase.

### Phase 1: CI Pipeline
- [ ] GitHub Actions workflow: run test suite on push to main
- [ ] Include the 3 fixed test files + trading_loop_agent tests + order_status_worker tests
- [ ] Fail on new test failures, warn on xfail count increase
- [ ] Target: green CI on every push

### Phase 2: Track B — Shape Normalization
- [ ] Standardize data shapes between components (decision → outcome → learning)
- [ ] Eliminate the class of bugs where P&L is computed differently across layers
- [ ] Define canonical schemas for: decision, trade_outcome, learning_event
- [ ] Validate shapes at component boundaries

### Phase 3: Dual-Recording Dedup
- [ ] Every trade is recorded twice (order_id_tracking + position_polling)
- [ ] Deduplicate at write time using order_id or decision_id as key
- [ ] Prevents inflated trade counts and confused learning attribution

**Success:** CI catches regressions before deploy, consistent data shapes, accurate trade counts.

---

## Priority Order

| Priority | Track | Phase | Effort | Impact |
|----------|-------|-------|--------|--------|
| 1 | E1.1 | Pre-Reasoning Layer | Medium | High — reduces waste, improves signal |
| 2 | E2.1 | Minimum Hold Time Gate | Small | High — stops churn bleeding |
| 3 | E2.2 | Re-Entry Cooldown | Small | Medium — reduces overtrading |
| 4 | E4.1 | CI Pipeline | Small | Medium — safety net |
| 5 | E1.2 | No-Op Gate | Small | Medium — saves LLM calls |
| 6 | E3.2 | After-Hours Awareness | Small | Low — eliminates noise |
| 7 | E2.3 | Prompt Engineering | Medium | High — core signal quality |
| 8 | E1.3 | Adaptive Cycle Timing | Medium | Medium — resource efficiency |
| 9 | E4.2 | Shape Normalization | Large | High — structural debt |
| 10 | E4.3 | Dual-Recording Dedup | Medium | Medium — data accuracy |
| 11 | E3.1 | Docker Build Optimization | Small | Low — convenience |
| 12 | E3.3 | Dashboard Queue Fix | Small | Low — cosmetic |

---

## Dependencies

- E1.1 (Pre-Reasoning) should land before E2.3 (Prompt Engineering) — the pre-reasoner's brief feeds the debate prompts
- E4.2 (Shape Normalization) would make E4.3 (Dedup) cleaner but isn't a hard dependency
- E2.1 (Hold Time Gate) and E2.2 (Cooldown) are independent and can land in any order
- All tracks are independent of each other at the phase level

---

## Revision History

- 2026-04-04: Initial roadmap created
