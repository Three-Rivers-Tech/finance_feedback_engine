# Stage 64 — Policy-Action Boundary Cleanup Plan

## Goal
Finish the post-Stage-63 migration by removing legacy `BUY` / `SELL` / `HOLD` semantics from operator-facing and control-surface paths wherever policy actions should be the canonical source of truth, while preserving explicit directional compatibility only at true execution-adapter edges.

## Why this stage exists

Stage 63 cleaned up the core live-decision path so policy actions are the canonical language for:
- validation
- ensemble voting
- trading-loop execution intent
- gatekeeper behavior
- adapter-bound normalization

But the repo still has several **boundary leaks** where legacy directional semantics remain the primary language in:
- CLI/operator surfaces
- API request/response shaping
- monitoring/audit helpers
- memory/outcome recording helpers
- documentation/examples that still imply `BUY` / `SELL` are the core contract

Those leaks make the system harder to reason about, especially now that live logs and runtime behavior are becoming more portfolio-aware. The next seam is not “make execution work” — that is already done — but “make the system speak one policy language consistently outside the exchange adapters.”

## Seam boundary

This stage formalizes the boundary between:
- **Canonical internal policy semantics**: `OPEN_*`, `ADD_*`, `REDUCE_*`, `CLOSE_*`, `HOLD`
- **Directional compatibility semantics**: `BUY` / `SELL` / `HOLD` only where a concrete adapter, transport, or legacy backtest interface still truly requires them

It explicitly does **not** aim to:
- rewrite exchange adapters to stop using directional order sides internally where the venue requires them
- rewrite all backtesting abstractions in one giant pass
- change live trading behavior without tests proving semantic equivalence

## Current hotspots

The main remaining hotspots after Stage 63 appear to be:
- `finance_feedback_engine/cli/main.py`
- `finance_feedback_engine/api/bot_control.py`
- `finance_feedback_engine/monitoring/*`
- `finance_feedback_engine/memory/portfolio_memory.py`
- selected docs/examples that still teach `BUY` / `SELL` as the primary contract

Some platform adapters and mock/backtest components also still use directional language, but those need to be split into:
1. **true boundary usage** (allowed)
2. **unnecessary internal leakage** (to be cleaned up)

## Planned slices

### PR-1 — CLI / operator surface normalization
- Audit CLI decision-display and command paths for legacy-first action semantics
- Make policy action the primary displayed/actioned field where available
- Preserve compatibility labels only as explicit secondary metadata
- Add focused tests proving operator-visible output prefers policy-action semantics

### PR-2 — API / control-surface normalization
- Audit request/response schemas and manual control endpoints
- Ensure policy-action-aware normalization at API boundaries
- Preserve legacy directional aliases only where explicitly accepted for compatibility
- Add tests proving policy actions round-trip canonically through API control flows

### PR-3 — Monitoring / memory / audit normalization
- Audit monitoring context, order outcome recording, and portfolio-memory helpers
- Ensure audit trails preserve canonical `policy_action` and `policy_action_family`
- Reduce implicit inference from raw `BUY` / `SELL` when policy metadata is present
- Add tests proving persisted/operator-facing audit records preserve policy semantics

### PR-4 — Boundary allowlist + helper consolidation
- Consolidate repeated policy→direction compatibility conversions behind explicit helpers
- Document and enforce the small allowlist of places where `BUY` / `SELL` remain legitimate
- Add regression tests so new internal legacy leaks are harder to reintroduce

### PR-5 — Closeout validation
- Run focused suites for the touched CLI/API/monitoring/memory seams
- Re-run the broader policy-actions / trading-loop / decision-store suites
- Confirm no regression in live operator/audit behavior

## Test strategy

Use the same discipline as recent stages:
- write a failing test first for each hotspot
- patch the narrowest seam necessary
- keep compatibility behavior explicit and localized
- prefer proof via persistence / operator-facing assertions over broad refactors

Likely test files/surfaces:
- `tests/test_trading_loop_agent.py`
- `tests/test_decision_store_policy_trace.py`
- `tests/decision_engine/test_policy_actions.py`
- new focused CLI/API/monitoring tests as needed

## Success criteria

Stage 64 is done when:
- policy actions are the primary operator-visible action language across CLI/API/audit paths
- legacy directional labels survive only as explicit compatibility metadata or true venue-boundary fields
- monitoring and memory outputs preserve canonical policy semantics when available
- no live-trading regression is introduced
- the codebase has a clearer documented rule for where `BUY` / `SELL` are still allowed

## Relation to live trading

This stage improves **operator trust** and **auditability** more than execution capability.

Now that the live runtime is more transparent about:
- recovered positions
- margin usage
- portfolio state
- decision/risk context

…the next logical step is to make the **action language** equally consistent everywhere humans inspect or control the system.
