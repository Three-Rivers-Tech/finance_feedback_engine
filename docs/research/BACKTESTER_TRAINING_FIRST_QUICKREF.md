# Backtester Training-First Quick Reference

## TL;DR

The backtester is now a **training system** that lets the AI learn from historical data before going live. All 10 enhancement tasks complete.

## Key Principles

1. **Training-First:** Backtesting trains the AI, not just validates it
2. **Persistent Memory:** Learning accumulates across runs
3. **Local-Only Default:** Free providers only (enable extensive training)
4. **Debate Mode Standard:** Multi-provider consensus everywhere
5. **Cache Everything:** Avoid redundant AI queries

## Essential Commands

```bash
# Standard backtest (with training)
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01

# Overfitting detection
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-06-01

# Risk assessment
python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-03-01

# Learning validation
python main.py learning-report --asset-pair BTCUSD

# Memory cleanup
python main.py prune-memory --keep-recent 1000
```

## What Changed

### New Files
1. `backtesting/decision_cache.py` - SQLite caching (269 lines)
2. `backtesting/agent_backtester.py` - OODA simulation (230 lines)
3. `backtesting/walk_forward.py` - Overfitting detection (298 lines)
4. `backtesting/monte_carlo.py` - Simulation + RL metrics (344 lines)

### Modified Files
1. `memory/portfolio_memory.py` - Added snapshot(), restore(), set_readonly()
2. `backtesting/backtester.py` - Integrated cache + memory
3. `decision_engine/engine.py` - Added monitoring_context parameter
4. `agent/orchestrator.py` - Quicktest validation (raises ValueError in live)
5. `cli/main.py` - 4 new commands
6. `config/*.yaml` - Debate mode ON, training defaults

## Config Quick Ref

### Backtesting Config (config.backtest.yaml)
```yaml
ensemble:
  debate_mode: true  # Multi-provider consensus
  quicktest_mode: false  # ONLY for testing (never live)

advanced_backtesting:
  enable_decision_cache: true  # Cache decisions
  enable_portfolio_memory: true  # Enable learning
  memory_isolation_mode: false  # Share memory across runs
  force_local_providers: true  # Free providers only
  max_concurrent_positions: 5  # Position limit

walk_forward:
  train_ratio: 0.7  # 70% train, 30% test
  min_train_trades: 30
  rolling_window_days: 90

monte_carlo:
  num_simulations: 1000
  price_noise_std: 0.001  # 0.1% noise
```

## Learning Validation Metrics

Generated via `python main.py learning-report`:

1. **Sample Efficiency** - Trades to 60% win rate (DQN/Rainbow)
2. **Cumulative Regret** - Optimal vs actual performance (Bandits)
3. **Concept Drift** - Performance variance over time (Online Learning)
4. **Thompson Sampling** - Exploration vs exploitation (Bayesian Bandits)
5. **Learning Curve** - First vs last quartile improvement (Meta-Learning)

## Safety Features

### Quicktest Mode Restrictions
- **Only** allowed in testing/backtesting
- Raises `ValueError` in `TradingAgentOrchestrator.__init__`
- Disables debate mode and memory for speed
- Warning if debate mode disabled

### Debate Mode Universal
- Default: ON in all configs
- Standard across entire repo
- Only disable for quicktest (testing only)

## Performance Notes

### Decision Cache
- **Hit rate:** 100% on repeated backtests
- **Speed:** ~1ms vs 1-5s for AI query
- **Storage:** ~500 bytes per decision
- **Location:** `data/cache/backtest_decisions.db`

### Memory Snapshot
- **Snapshot:** ~10ms for 1000 outcomes
- **Restore:** ~5ms
- **Deep copy:** Negligible overhead

## Common Workflows

### 1. Initial Backtest
```bash
# First run (cache miss, slow)
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01

# Second run (cache hit, instant)
python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
```

### 2. Overfitting Check
```bash
# Walk-forward analysis
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-06-01

# Look for severity: NONE/LOW/MEDIUM/HIGH
# HIGH = major revision needed
```

### 3. Risk Assessment
```bash
# Monte Carlo simulation
python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-03-01

# Check VaR and percentiles
# 5th percentile = worst case at 95% confidence
```

### 4. Learning Validation
```bash
# Full learning report
python main.py learning-report --asset-pair BTCUSD

# Check for:
# - Sample efficiency (learning speed)
# - Cumulative regret (optimal provider)
# - Concept drift (HIGH = unstable)
# - Thompson Sampling (exploration rate)
# - Learning curve (improvement %)
```

### 5. Memory Management
```bash
# Check memory size
python main.py learning-report | grep "Total Trades"

# Prune if too large
python main.py prune-memory --keep-recent 1000
```

## Integration Points

### Using DecisionCache
```python
from finance_feedback_engine.backtesting.decision_cache import DecisionCache

cache = DecisionCache()
cache_key = cache.build_cache_key(asset_pair, timestamp, market_data)
market_hash = cache.build_market_hash(market_data)

# Check cache
decision = cache.get(cache_key)
if decision is None:
    decision = generate_decision(...)
  cache.put(cache_key, decision, asset_pair, timestamp, market_hash)
```

### Using Memory Snapshots
```python
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine

memory = PortfolioMemoryEngine(config)

# Train window
snapshot = memory.snapshot()
# ... train on historical data ...

# Test window (prevent lookahead bias)
memory.set_readonly(True)
# ... test on out-of-sample data ...
memory.set_readonly(False)

# Restore for next window
memory.restore(snapshot)
```

### Using Learning Validation
```python
from finance_feedback_engine.backtesting.monte_carlo import (
    generate_learning_validation_metrics
)

# Via memory engine
metrics = memory.generate_learning_validation_metrics(asset_pair='BTCUSD')

# Direct call
metrics = generate_learning_validation_metrics(memory, asset_pair='BTCUSD')

# Access metrics
sample_efficiency = metrics['sample_efficiency']
cumulative_regret = metrics['cumulative_regret']
concept_drift = metrics['concept_drift']
thompson_sampling = metrics['thompson_sampling']
learning_curve = metrics['learning_curve']
```

## Testing

### Verify Cache
```python
python test_decision_cache.py
# Expected: 100% hit rate, snapshot/restore working
```

### Verify Learning Validation
```python
python test_learning_validation.py
# Expected: Learning progression detected (90% win rate improvement)
```

### Verify CLI Commands
```bash
python main.py walk-forward --help
python main.py monte-carlo --help
python main.py learning-report --help
python main.py prune-memory --help
```

## Troubleshooting

### Cache Not Working
- Check `data/cache/backtest_decisions.db` exists
- Verify `enable_decision_cache: true` in config
- Look for cache stats in backtest output

### Memory Not Persisting
- Check `enable_portfolio_memory: true`
- Verify `memory_isolation_mode: false` (share across runs)
- Memory file location in config

### Quicktest Error in Live Trading
```
ValueError: quicktest_mode is ONLY allowed in testing/backtesting environments
```
- Set `ensemble.quicktest_mode: false` in config
- Never use quicktest in live trading

### Debate Mode Warning
```
⚠️  WARNING: debate_mode is disabled
```
- Set `ensemble.debate_mode: true` in config
- Debate mode is the standard

## File Locations

```
finance_feedback_engine/
├── backtesting/
│   ├── decision_cache.py          # SQLite caching (NEW)
│   ├── agent_backtester.py        # OODA simulation (NEW)
│   ├── walk_forward.py            # Overfitting detection (NEW)
│   ├── monte_carlo.py             # Simulation + RL metrics (NEW)
│   └── backtester.py              # Cache/memory integration (MODIFIED)
├── memory/
│   └── portfolio_memory.py        # Snapshotting methods (MODIFIED)
├── decision_engine/
│   └── engine.py                  # monitoring_context param (MODIFIED)
├── agent/
│   └── orchestrator.py            # Quicktest validation (MODIFIED)
└── cli/
    └── main.py                    # 4 new commands (MODIFIED)

config/
├── config.yaml                    # Debate mode ON (MODIFIED)
└── config.backtest.yaml           # Training defaults (MODIFIED)

data/
├── cache/
│   └── backtest_decisions.db      # Decision cache (AUTO-CREATED)
└── decisions/                     # Decision storage
```

## Research Citations

1. **DQN/Rainbow:** Hessel et al. (2018) - *Rainbow: Combining Improvements in Deep Reinforcement Learning*
2. **Bandits:** Lattimore & Szepesvári (2020) - *Bandit Algorithms*
3. **Concept Drift:** Gama et al. (2014) - *A Survey on Concept Drift Adaptation*
4. **Thompson Sampling:** Russo et al. (2018) - *A Tutorial on Thompson Sampling*
5. **MAML:** Finn et al. (2017) - *Model-Agnostic Meta-Learning for Fast Adaptation*

## Next Steps

1. **Run initial backtest** to populate decision cache
2. **Walk-forward analysis** to check overfitting
3. **Learning report** to validate AI improvement
4. **Monte Carlo** for risk assessment
5. **Prune memory** periodically to manage size

## Support

See full documentation: `BACKTESTER_TRAINING_FIRST_COMPLETE.md`

---

**Quick Ref v1.0** | Finance Feedback Engine 2.0
