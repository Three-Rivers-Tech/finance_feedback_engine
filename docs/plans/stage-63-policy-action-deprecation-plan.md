# Stage 63 — Policy Action Deprecation Cleanup Plan

## Goal
Remove legacy `BUY` / `SELL` / `HOLD` semantics from live decision and execution paths, while preserving explicit compatibility metadata only where required for migration safety.

## Current status
- PR-1 (`ad4c749`): policy-aware validation and fallback cleanup
- PR-2 (`33f7098`): policy-aware ensemble voting cleanup
- PR-2.5 (`84433b2`): trading-loop execution intent derives actionability from policy semantics
- PR-3 (current draft): engine prompt/validation/forced-hold path migrated to policy-action semantics
- Gemini review completed against PR-1 + PR-2 patch set

## Gemini review integration

### Must fix before broad PR-3 engine cleanup
1. **Trading loop execution gating must stop relying on brittle manual policy-action mappings.**
   - Risk: valid policy actions can be silently treated as non-actionable.
   - Required change: centralize execution intent derivation around policy-action family semantics and bounded compatibility fields.
   - Required tests: prove `REDUCE_*` / `CLOSE_*` actions can flow through reasoning when structurally valid.

### Should fix during/after PR-3
2. **Deduplicate normalization logic** between:
   - `decision_validation.normalize_decision_action_payload`
   - `ensemble_manager._normalize_ensemble_decision_payload`
3. **Audit completeness of policy-action compatibility mappings** in `policy_actions.py`.
   - Explicitly verify every supported policy action has the expected execution intent / compatibility semantics.

## Planned slices

### PR-2.5 — Gemini must-fix gate
- Fix `TradingLoopAgent` execution-intent derivation
- Replace brittle hardcoded actionability mapping with policy-family-aware execution intent
- Add regression tests for valid close/reduce actions and directional entry actions

### PR-3 — `decision_engine/engine.py` migration slice
- [x] Rewrite prompt position-state guidance around canonical policy actions
- [x] Make forced-HOLD handling policy-aware
- [x] Tighten validation around legal policy actions and position-state constraints
- [ ] Preserve compatibility only at integration boundaries across remaining legacy educational text and adapters

### PR-4 — downstream execution / adapters
- Audit execution interfaces, platform adapters, monitoring, and alerting for legacy-only assumptions
- Continue reducing legacy directional labels to explicit compatibility metadata only

## Exit criteria
- Decision generation uses policy actions canonically
- Ensemble and validation layers preserve policy actions canonically
- Trading loop and execution gating operate on policy-action semantics directly
- Legacy directional labels exist only as explicit compatibility fields, not as the core source of truth
