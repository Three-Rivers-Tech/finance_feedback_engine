# Track SK — Sortino-Gated Adaptive Kelly Position Sizing

## TDD Implementation Plan — April 2026

---

## Executive Summary

Replace FFE's fixed 1% risk position sizing with a sortino-ratio-gated fractional Kelly system that dynamically scales position size based on demonstrated edge quality. The infrastructure already exists — Kelly calculator, sortino computation, multi-window config schema — but the last mile of wiring was never completed. This plan connects those pieces with a TDD approach backed by 96 real trade outcomes.

---

## Research Foundation

### Core Theory

**Kelly Criterion (Kelly 1956):** Maximizes long-term geometric growth rate of capital. The optimal fraction to bet is `f* = (bp - q) / b` where `p` = win probability, `q` = 1-p, `b` = payoff ratio (avg_win / avg_loss). Full Kelly is provably growth-optimal but produces unacceptable drawdowns in practice.

**Fractional Kelly (Thorp 1969, MacLean et al. 2010):** Betting a fraction `λ` of full Kelly (0 < λ ≤ 1) captures `1 - (1-λ)²` of the optimal growth rate while reducing variance by `λ²`. Quarter Kelly (λ=0.25) captures ~44% of optimal growth with only ~6% of the variance. Half Kelly (λ=0.5) captures ~75% of optimal growth with ~25% of the variance. This is the standard practice in quantitative hedge funds.

**Sortino Ratio (Sortino & van der Meer 1991):** Measures risk-adjusted return using only downside deviation, unlike Sharpe which penalizes upside volatility equally. For a system with asymmetric returns (like a trend-following futures strategy), Sortino is a more honest measure of edge quality because profitable volatility is not penalized.

### Key Academic References

1. **Carta & Conversano (2020)** — "Practical Implementation of the Kelly Criterion" (Frontiers in Applied Mathematics). Demonstrates Kelly portfolios outperform Markowitz mean-variance in dynamic settings. Explicitly evaluates fractional Kelly alongside Sortino ratio as risk measures. Key finding: rolling Kelly with 2-year windows outperforms competitors on out-of-sample growth rate.

2. **Hakobyan & Lototsky (2025)** — "Optimal Betting: Beyond the Long-Term Growth" (arXiv:2503.17927). Introduces asymptotic variance analysis for Kelly portfolio fluctuations. Shows every fractional Kelly strategy can be derived from risk estimators, providing theoretical justification for using risk metrics (like Sortino) to modulate Kelly fraction.

3. **Sukhov (2026)** — "Bayesian Kelly Criterion with Parameter Uncertainty" (SSRN:6195358). Uses nearly two decades of live futures data. Demonstrates that when distributional assumptions fail (as they always do in crypto), Bayesian shrinkage toward fractional Kelly provides regime-robust sizing. Key insight: uncertain regime → lower Kelly fraction, confident regime → higher fraction.

4. **Modaffari, Frasca & Barilla (2026)** — "A Gate-Based AI-Driven Decision Framework for Cryptocurrency Derivative Investment" (Management Decision). Implements Kelly criterion with volatility adjustment for crypto derivatives. Demonstrates framework incorporating parameter uncertainty and market regime changes.

5. **Hsieh & Barmish (2015), Busseti et al. (2016)** — Show that unconstrained Kelly produces excessively large drawdowns. Adding drawdown risk constraints (or equivalently, using downside-risk-gated fractional sizing) dramatically improves practical performance.

6. **Rising & Wyner (2012)** — Prove that a fractional Kelly investor is equivalent to a full Kelly investor using shrinkage estimates. This means using Sortino to modulate Kelly fraction is mathematically equivalent to adjusting the model's confidence in its own edge estimate.

### Why Sortino + Kelly Specifically

The combination addresses a fundamental problem: **fixed-fraction sizing treats every trade identically regardless of demonstrated edge quality.**

- When Sortino is high (>1.0), the system has demonstrated it makes more on winners than it loses on losers, with low downside volatility. This is precisely when Kelly says to bet more.
- When Sortino is low (<0.3) or negative, the system is either underperforming or the edge is unproven. This is when Kelly should shrink to minimum or disengage.
- The multi-window approach (7/30/90 day) provides regime detection without explicit regime classification — if the short window tanks while the long window is still positive, the system automatically scales back.

---

## Live System Data Analysis

**From 96 real trade outcomes (Feb-Apr 2026 on Coinbase CFM futures):**

| Metric | Value |
|--------|-------|
| Win rate | 62.9% |
| Avg win | $221.89 |
| Avg loss | -$69.46 |
| Payoff ratio | 3.19 |
| Sortino (trade-level) | 1.118 |
| Total P&L | $3,978.50 |
| Full Kelly fraction | 51.23% |
| Quarter Kelly | 12.81% |
| Half Kelly | 25.61% |

**Interpretation:** The system has a legitimate edge — 62.9% win rate with a 3.19 payoff ratio is excellent. Full Kelly at 51% would be reckless, but quarter Kelly at 12.8% would size positions ~13x larger than the current fixed 1%. Even with conservative capping, this represents a significant capital efficiency improvement.

The Sortino of 1.118 places the system in the "proven edge" zone — comfortably above 0.5 (marginal) and approaching 1.5 (strong). This supports activation of adaptive Kelly rather than staying on fixed sizing.

**Critically:** These numbers include the early learning period when the system was making worse decisions. The recent 30-day window would likely show even stronger metrics.

---

## Architecture: What Exists vs What's Needed

### Already Built ✅
- `KellyCriterionCalculator` in `decision_engine/kelly_criterion.py` — full implementation, quarter Kelly default
- `position_sizing.py` integration point — `use_kelly_criterion` flag, `_get_kelly_parameters()` method
- `_kelly_activated` flag in `trading_loop_agent.py` — checks profit factor stability after 50 trades
- Sortino calculation in `portfolio_memory.py` — computes from trade P&L, fed to AI prompts
- `SortinoConfig` with multi-window schema — 7/30/90 day weights defined in `agent/config.py`
- 96 durable outcome files for backtesting/TDD

### The Gap ❌
1. `_kelly_activated` is tracked but never passed to `position_sizing.py`
2. Sortino is calculated but only shown to models, not used for sizing decisions
3. Multi-window sortino is configured but never implemented
4. No bridge between sortino quality and Kelly fraction multiplier
5. No tests for the sortino→kelly sizing pathway

---

## TDD Implementation Plan

### Phase 0 — Test Infrastructure (write tests first, all fail)

**File: `tests/test_sortino_kelly_sizing.py`**

Tests to write before any implementation:

```
test_sortino_below_threshold_uses_fixed_risk()
  → Sortino < 0.3 → position_sizing_method == "risk_based", fraction == 0.01

test_sortino_marginal_uses_quarter_kelly()
  → Sortino 0.3-0.8 → method == "kelly_criterion", multiplier == 0.25

test_sortino_good_uses_half_kelly()
  → Sortino 0.8-1.5 → method == "kelly_criterion", multiplier == 0.50

test_sortino_excellent_caps_at_half_kelly()
  → Sortino > 1.5 → still capped at 0.50 (never go above half Kelly)

test_sortino_negative_forces_fixed_risk()
  → Sortino < 0 → fixed risk, log warning about negative risk-adjusted returns

test_multi_window_sortino_weighted_average()
  → 7d=0.8, 30d=1.2, 90d=0.5 → weighted = 0.8*0.5 + 1.2*0.3 + 0.5*0.2 = 0.86

test_multi_window_sortino_short_window_veto()
  → 7d=-0.5, 30d=1.0, 90d=1.0 → short window negative vetoes kelly activation

test_kelly_fraction_respects_max_cap()
  → Full Kelly > kelly_fraction_cap → capped at 0.25 (configurable)

test_kelly_sizing_with_real_outcome_data()
  → Load actual outcome files, compute Kelly params, verify sizing is sane

test_transition_logged_on_mode_change()
  → Fixed→Kelly: log "Kelly ACTIVATED", Kelly→Fixed: log "Kelly DEACTIVATED"

test_insufficient_trades_stays_on_fixed()
  → <30 trades with P&L → stays on fixed risk regardless of sortino

test_position_size_never_exceeds_max_pct()
  → Even with excellent sortino + kelly → max_position_size_pct (5%) never exceeded

test_sortino_gate_updates_every_cycle()
  → Sortino recalculated from latest window, not stale cached value
```

### Phase 1 — Multi-Window Sortino Calculator

**File: `finance_feedback_engine/decision_engine/sortino_gate.py`** (new)

Implement the multi-window sortino calculator that produces a single gating score.

```python
class SortinoGate:
    """Compute multi-window sortino and determine Kelly activation level."""
    
    def __init__(self, windows=[7, 30, 90], weights=[0.5, 0.3, 0.2], 
                 min_trades=30, veto_threshold=-0.1):
        ...
    
    def compute(self, trade_outcomes: list[dict]) -> SortinoGateResult:
        """Returns activation level and recommended kelly multiplier."""
        ...
    
    def _calculate_window_sortino(self, pnls: list[float]) -> float:
        """Sortino for a single window of P&L values."""
        ...
```

**SortinoGateResult:**
```python
@dataclass
class SortinoGateResult:
    weighted_sortino: float
    window_sortinos: dict[int, float]  # {7: 0.8, 30: 1.2, 90: 0.5}
    kelly_multiplier: float            # 0.0 (disabled) to 0.50
    sizing_mode: str                   # "fixed_risk" | "quarter_kelly" | "half_kelly"
    reason: str                        # human-readable explanation
    trade_count: int
    short_window_veto: bool
```

**Mapping logic:**
- Sortino < 0 → `multiplier=0.0`, mode="fixed_risk" (negative edge, safety mode)
- Sortino 0-0.3 → `multiplier=0.0`, mode="fixed_risk" (unproven edge)
- Sortino 0.3-0.8 → `multiplier=0.25`, mode="quarter_kelly"
- Sortino 0.8-1.5 → `multiplier=0.50`, mode="half_kelly"
- Sortino > 1.5 → `multiplier=0.50`, mode="half_kelly" (capped, never go higher)
- 7-day window < `veto_threshold` → override to fixed_risk regardless of long windows

### Phase 2 — Wire SortinoGate into Position Sizing

**File: `finance_feedback_engine/decision_engine/position_sizing.py`** (modify)

1. Accept `SortinoGateResult` in the sizing context
2. When `sizing_mode != "fixed_risk"`, use Kelly with the recommended multiplier
3. Override `kelly_fraction_multiplier` dynamically instead of reading from static config
4. Log the transition clearly

Key change in `calculate_position_size_with_risk`:
```python
# Replace static use_kelly_criterion flag:
sortino_gate_result = context.get("sortino_gate_result")
if sortino_gate_result and sortino_gate_result.sizing_mode != "fixed_risk":
    # Dynamic Kelly with sortino-determined multiplier
    self.kelly_calculator.kelly_fraction_multiplier = sortino_gate_result.kelly_multiplier
    # ... use kelly sizing path
else:
    # Fixed risk sizing (current behavior)
    # ... existing code
```

### Phase 3 — Wire SortinoGate into Trading Loop

**File: `finance_feedback_engine/agent/trading_loop_agent.py`** (modify)

1. Instantiate `SortinoGate` in agent init
2. Compute sortino gate result at start of each reasoning cycle
3. Pass result through to position sizing via decision context
4. Replace the disconnected `_kelly_activated` flag with sortino gate
5. Log sortino gate status in cycle summary

### Phase 4 — Config + Safety Rails

**File: `config/config.yaml`** and **`agent/config.py`** (modify)

Add to config:
```yaml
agent:
  position_sizing:
    sortino_kelly:
      enabled: true
      windows_days: [7, 30, 90]
      weights: [0.5, 0.3, 0.2]
      min_trades: 30
      short_window_veto_threshold: -0.1
      max_kelly_multiplier: 0.50
      max_position_size_pct: 0.05
```

Safety rails:
- `enabled: false` by default (opt-in)
- Hard cap at half Kelly (never 75% or full)
- `max_position_size_pct` = 5% of account (already exists)
- Short-window veto: if 7-day sortino goes negative, revert to fixed immediately
- Minimum 30 non-zero-PnL trades before Kelly can activate
- All transitions logged at INFO level

### Phase 5 — Backtest Validation

**File: `tests/test_sortino_kelly_backtest.py`** (new)

Using the 96 real outcome files:
1. Replay trade history through the SortinoGate
2. Compare theoretical sizing (fixed 1% vs sortino-kelly) at each trade
3. Verify the system would have activated Kelly at the right time
4. Verify short-window veto fires during losing streaks
5. Compute theoretical equity curve comparison

---

## Sequencing & Dependencies

```
Phase 0 (tests)     → no dependencies, write first
Phase 1 (SortinoGate) → depends on Phase 0 tests
Phase 2 (position_sizing wiring) → depends on Phase 1
Phase 3 (trading_loop wiring) → depends on Phase 2
Phase 4 (config) → can parallel with Phase 2-3
Phase 5 (backtest) → depends on all above
```

**Estimated scope:** ~300 lines new code, ~50 lines modified, ~400 lines tests. 1 new file, 3 modified files, 2 new test files.

**Risk level:** LOW if `enabled: false` by default. The system continues on fixed 1% risk until explicitly activated. When activated, it's bounded by half Kelly cap + 5% position max + short-window veto.

---

## Success Criteria

1. All Phase 0 tests pass
2. Backtest on real data shows sortino gate correctly identifies regime changes
3. Quarter Kelly positions during sortino 0.3-0.8 produce better risk-adjusted returns than fixed 1%
4. Half Kelly positions during sortino >0.8 produce significantly better growth without worse drawdowns
5. Short-window veto fires within 1-2 cycles of a regime deterioration
6. Zero regressions in existing position sizing tests
7. The system can be toggled off with a single config change

---

## What This Does NOT Do (Post-1.0)

- Per-asset sortino gating (future: BTC might warrant Kelly while ETH stays fixed)
- Regime-specific Kelly multipliers beyond sortino threshold bands
- Integration with Thompson sampling for provider-specific sizing
- Sortino-weighted adaptive learning (using sortino to weight learning rate, not just sizing)
- Real-time sortino from streaming P&L (currently uses trade-close P&L only)

---

## Appendix: FFE Live Data Summary (as of 2026-04-03)

```
96 total outcome records
35 non-zero P&L trades
22 wins / 13 losses (62.9% win rate)
Avg win: $221.89 / Avg loss: -$69.46
Payoff ratio: 3.19
Sortino: 1.118
Full Kelly: 51.23%
Quarter Kelly: 12.81%  ← conservative entry point
Half Kelly: 25.61%     ← maximum with proven edge
Total P&L: $3,978.50
Provider: ensemble (87 trades, $5,703 cumulative)
```
