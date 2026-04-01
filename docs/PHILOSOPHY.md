# FFE Philosophy & North Star

## The One Metric: Sortino Ratio

Everything the Finance Feedback Engine does — every decision, every trade, every line of code — exists to **maximize the Sortino ratio**.

Not Sharpe. **Sortino.** The distinction matters: we don't penalize upside volatility. We welcome asymmetric wins. We brutally punish downside risk.

```
Sortino = (Portfolio Return - Risk-Free Rate) / Downside Deviation
```

Every feature, every parameter, every architectural decision should be evaluated against this: **does it improve the Sortino ratio?** If it doesn't, it's noise.

---

## What This Means in Practice

### 1. Asymmetric Risk is the Whole Game

The bot should be pathologically allergic to drawdowns and completely comfortable with volatile gains. Concretely:

- **Cut losers fast.** Stop-losses are non-negotiable. A position that's moving against you is information — act on it.
- **Let winners run.** Don't take profits early out of fear. Upside volatility is *good* — it's the numerator.
- **Size positions to survive.** Position sizing should ensure no single trade can create meaningful downside deviation. The Kelly criterion (fractional) is the right instinct — quarter-Kelly is conservative but keeps you in the game.

### 2. The Bot Must Be a Coward First

The most dominant bots are the ones that survive. Capital preservation isn't a defensive posture — it's the prerequisite for compounding.

- **HOLD is the default.** Trading for the sake of trading is the enemy. Every trade has friction (fees, slippage, spread). A HOLD with conviction beats a trade with uncertainty.
- **Genuine conviction or nothing.** The debate engine should produce *real* disagreement. When bull, bear, and judge all see the same thing with high confidence, act. When they don't, sit on your hands.
- **Circuit breakers are sacred.** They're not safety theater — they're the system acknowledging it doesn't know everything.

### 3. Downside Deviation is the Enemy

The denominator of the Sortino ratio is downside deviation — the volatility of *negative* returns only. Minimizing this means:

- **Drawdown limits are hard ceilings, not guidelines.** If the portfolio hits a drawdown threshold, the system should derisk aggressively — close positions, reduce size, go flat. No "waiting for recovery."
- **Correlation kills.** Two correlated positions are one position with double the risk. The correlation monitoring isn't optional — it's core risk infrastructure.
- **Time kills too.** Holding a position that's going nowhere still exposes you to tail risk. Stale positions should have time-based review triggers.

### 4. The Ensemble Must Earn Its Keep

Debate mode is powerful, but only if it produces *better risk-adjusted returns* than a simpler approach. The ensemble's job:

- **Reduce false signals** — the value of multiple models isn't being right more often, it's being wrong less catastrophically.
- **Adaptive weights must reflect Sortino contribution** — a model that catches upside but also produces big losers should be downweighted vs. one that produces fewer but cleaner trades.
- **Unanimous HOLD > split-decision trade.** When the ensemble can't agree, that *is* the signal: do nothing.

---

## SaaS North Star

FFE is open-source now and eventually becomes a SaaS product. The philosophy shapes the product:

### Open Source Value Prop
- **Transparent risk engine.** Users can audit every decision, every override, every weight adjustment. Trust through transparency.
- **Pluggable AI providers.** Bring your own models, your own data, your own risk parameters. The framework is the value — not the locked-in provider.
- **Self-hostable.** The open-source version should be fully functional for individual traders. No crippled free tier.

### SaaS Differentiation
- **Managed infrastructure** — multi-asset, multi-exchange, always-on monitoring without running your own servers.
- **Aggregate learning** — the SaaS version can learn from aggregate (anonymized) performance data across users. More data → better adaptive weights → better Sortino.
- **Portfolio-level optimization** — individual traders optimize per-pair. The SaaS can optimize across the entire portfolio: correlation management, sector exposure, tail risk hedging across all user positions.
- **Risk dashboards** — real-time Sortino tracking, drawdown alerts, regime detection visualizations. Make the abstract concrete.
- **Strategy marketplace** — users can share (or sell) ensemble configurations, debate prompts, risk parameter sets that have demonstrated high Sortino in live trading.

### Pricing Philosophy
- Open-source core is always free and fully functional.
- SaaS charges for convenience, infrastructure, and aggregate intelligence.
- Never charge for features that are about *safety* (circuit breakers, stop-losses, risk limits). Those should be available to everyone.

---

## What Dominant Looks Like

A dominant FFE doesn't trade the most. It doesn't have the highest win rate. It doesn't catch every move.

A dominant FFE:

1. **Compounds relentlessly** because it avoids catastrophic losses.
2. **Trades only when the edge is clear** — high-conviction, asymmetric setups.
3. **Adapts** — weights shift, regimes are detected, parameters evolve. But the north star (Sortino) never changes.
4. **Survives everything** — flash crashes, exchange outages, bad data, model hallucinations. The system degrades gracefully; it never blows up.
5. **Gets better with time** — every trade outcome feeds back into the system. Every closed position makes the next decision smarter.

The measure of success isn't "did we make money today?" It's: **over a rolling window, is our Sortino ratio increasing?**

---

## Anti-Patterns (Things We Don't Do)

- **Chase returns.** We optimize risk-adjusted returns, not raw PnL.
- **Over-trade.** Fees and slippage compound against you. Every trade needs to justify its friction.
- **Trust one model.** Single points of failure are unacceptable in decisions *or* infrastructure.
- **Ignore regime changes.** A strategy that worked in a bull market will kill you in a crash. Regime detection isn't optional.
- **Optimize for backtest performance.** Backtests are hypothesis generators, not truth. Live performance with real slippage and latency is the only scoreboard.
- **Ship safety features behind a paywall.** Risk management is a public good.

---

*This document is the soul of the project. Code changes come and go. This stays.*
