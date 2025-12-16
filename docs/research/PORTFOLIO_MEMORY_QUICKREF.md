# Portfolio Memory Engine - Quick Reference

## Overview

A reinforcement learning-inspired memory system that learns from trade outcomes to improve future decisions.

## Key Capabilities

✅ **Experience Replay** - Stores (decision, outcome) pairs for learning
✅ **Performance Attribution** - Tracks which AI providers generate profitable trades
✅ **Context Generation** - Feeds historical performance into new AI decisions
✅ **Adaptive Learning** - Recommends provider weight adjustments based on results
✅ **Market Regime Detection** - Identifies what works in bullish/bearish/sideways markets
✅ **Risk Metrics** - Sharpe ratio, Sortino ratio, max drawdown, profit factor

## Quick Start

### 1. Enable in Config

```yaml
portfolio_memory:
  enabled: true
  max_memory_size: 1000
  learning_rate: 0.1
  context_window: 20
```

### 2. Record Trade Outcomes

```python
from finance_feedback_engine import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(config)

# Make a decision
decision = engine.analyze_asset('BTCUSD', use_memory_context=True)

# Execute trade
engine.execute_decision(decision['id'])

# Later, when closing position...
outcome = engine.record_trade_outcome(
    decision_id=decision['id'],
    exit_price=52000.0,
    hit_take_profit=True
)
```

### 3. Analyze Performance

```python
# Get performance snapshot
snapshot = engine.get_performance_snapshot()

print(f"Win Rate: {snapshot['win_rate']:.1f}%")
print(f"Total P&L: ${snapshot['total_pnl']:.2f}")
print(f"Sharpe Ratio: {snapshot['sharpe_ratio']:.2f}")
```

### 4. Get Provider Recommendations

```python
# Analyze which providers perform best
recs = engine.get_provider_recommendations()

print(f"Confidence: {recs['confidence']}")
for provider, weight in recs['recommended_weights'].items():
    print(f"{provider}: {weight:.1%}")
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│      PortfolioMemoryEngine                      │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐  ┌──────────────────────┐    │
│  │ Experience   │  │ Performance          │    │
│  │ Replay       │  │ Analysis             │    │
│  │ Buffer       │  │ - Sharpe/Sortino     │    │
│  │              │  │ - Max Drawdown       │    │
│  │ (decision,   │  │ - Win Rate           │    │
│  │  outcome)    │  │ - Profit Factor      │    │
│  └──────────────┘  └──────────────────────┘    │
│                                                 │
│  ┌──────────────┐  ┌──────────────────────┐    │
│  │ Provider     │  │ Market Regime        │    │
│  │ Attribution  │  │ Tracking             │    │
│  │ - Per-prov   │  │ - Bullish/Bearish    │    │
│  │   win rate   │  │ - Trending/Sideways  │    │
│  │ - Confidence │  │ - Sentiment-based    │    │
│  │   calibration│  │                      │    │
│  └──────────────┘  └──────────────────────┘    │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ Context Generation for AI Decisions      │  │
│  │ → Feeds into DecisionEngine prompts      │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Data Structures

### TradeOutcome
Records a completed trade with full context:
- Entry/exit prices and timestamps
- Realized P&L (dollar and percentage)
- Provider attribution
- Market sentiment at entry
- Stop loss/take profit flags

### PerformanceSnapshot
Aggregated metrics at a point in time:
- Win rate, profit factor, Sharpe/Sortino
- Per-provider performance stats
- Market regime breakdowns
- Confidence calibration by bucket

## Best Practices

### Minimum Data Requirements
- **20+ trades**: Basic context generation
- **50+ trades per provider**: Reliable weight recommendations
- **100+ trades**: Accurate confidence calibration

### Sample Workflow

```python
# 1. Enable memory in config
config['portfolio_memory']['enabled'] = True

# 2. Make memory-informed decisions
decision = engine.analyze_asset('BTCUSD', use_memory_context=True)
# AI receives recent performance, win rates, asset-specific history

# 3. Execute and record
engine.execute_decision(decision['id'])
# ... trade runs for X hours/days ...
engine.record_trade_outcome(decision['id'], exit_price=52000)

# 4. Periodic analysis
if trades_count >= 50:
    recs = engine.get_provider_recommendations()
    if recs['confidence'] == 'high':
        # Update ensemble weights
        config['ensemble']['provider_weights'] = recs['recommended_weights']
        # Restart engine with new weights

# 5. Regular snapshots
snapshot = engine.get_performance_snapshot(window_days=30)
engine.save_memory()  # Persist to disk
```

## Performance Metrics Explained

### Win Rate
```
Winning Trades / Total Trades × 100%
```

### Profit Factor
```
Gross Profit / Gross Loss
> 1.0 = profitable, > 2.0 = excellent
```

### Sharpe Ratio
```
(Mean Return - Risk Free Rate) / Std Deviation × √252
> 1.0 = good, > 2.0 = very good, > 3.0 = excellent
```

### Sortino Ratio
```
(Mean Return - Risk Free Rate) / Downside Std × √252
Like Sharpe but only penalizes downside volatility
```

### Max Drawdown
```
(Peak - Trough) / Peak × 100%
Largest peak-to-trough decline
```

## Integration Points

### With DecisionEngine
- Memory context automatically added to AI prompts
- Recent performance, win rates, streaks included
- Asset-specific historical data highlighted

### With EnsembleManager
- Complements ensemble provider tracking
- Adds realized P&L attribution
- Confidence calibration by bucket
- Market regime analysis

### With Backtester
- Can analyze backtest results
- Compare simulated vs live performance
- Validate strategies before deployment

## File Storage

```
data/
└── memory/
    ├── outcome_{decision_id}.json      # Individual trade outcomes
    ├── snapshot_{timestamp}.json       # Performance snapshots
    ├── provider_performance.json       # Provider stats summary
    └── regime_performance.json         # Market regime summary
```

## Comparing to Industry Standards

| Feature | Traditional | HF Trading | Portfolio Memory |
|---------|-------------|------------|------------------|
| Outcome tracking | Manual | Automated | ✅ Automated |
| Attribution | None | Per-strategy | ✅ Per-provider |
| Learning | None | RL agents | ✅ Heuristic RL |
| Risk metrics | Basic P&L | Full suite | ✅ Sharpe, Sortino, DD |
| Regime detection | None | ML-based | ✅ Sentiment/trend |
| Confidence calibration | None | Bayesian | ✅ By bucket |
| Feedback loop | None | Online learning | ✅ Context in prompts |

## Advanced Usage

### Custom Metrics

```python
# Extend with custom analysis
class CustomMemory(PortfolioMemoryEngine):
    def analyze_performance(self, window_days=None):
        snapshot = super().analyze_performance(window_days)

        # Add custom metric: average holding period
        outcomes = self.trade_outcomes
        holding_periods = [
            o.holding_period_hours
            for o in outcomes if o.holding_period_hours
        ]
        snapshot.avg_holding_period = (
            sum(holding_periods) / len(holding_periods)
            if holding_periods else 0
        )

        return snapshot
```

### Regime-Based Strategy Selection

```python
snapshot = engine.get_performance_snapshot()
regimes = snapshot['regime_performance']

# Check performance in bullish markets
if regimes.get('bullish', {}).get('win_rate', 0) > 70:
    # Strategy works well in bull markets
    decision = engine.analyze_asset('BTCUSD')
else:
    # Consider alternative strategy or HOLD
    pass
```

## Troubleshooting

**No context showing up?**
- Enable: `portfolio_memory.enabled: true`
- Record outcomes: `engine.record_trade_outcome(...)`

**Low recommendation confidence?**
- Need 20+ trades minimum
- Check `sample_sizes` in recommendations

**Memory not persisting?**
- Call `engine.save_memory()` periodically
- Check file permissions in `data/memory/`

## References

- Experience Replay: Mnih et al., Nature 2015 (DQN)
- Thompson Sampling: Agrawal & Goyal, COLT 2012
- Meta-Learning: Finn et al., ICML 2017 (MAML)
- Ensemble Methods: Mungoli, arXiv 2023
- Risk Metrics: Sharpe, Journal of Portfolio Management 1994

## Demo

Run the demo to see all features:

```bash
python demo_portfolio_memory.py
```

Output shows:
- Recording 5 sample trades
- Performance metrics (win rate, Sharpe, etc.)
- Provider recommendations
- Context generation
- Memory persistence

---

For full documentation, see: `PORTFOLIO_MEMORY_ENGINE.md`
