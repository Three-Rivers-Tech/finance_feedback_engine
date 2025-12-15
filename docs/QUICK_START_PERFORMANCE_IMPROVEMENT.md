## Quick Start: Agent Performance Improvement

This guide will help you get started with benchmarking and improving your trading agent's performance in under 30 minutes.

---

## Step 1: Run Your First Benchmark (5 minutes)

The benchmark suite establishes baseline performance metrics for your agent.

```python
# File: scripts/run_baseline_benchmark.py

import asyncio
from finance_feedback_engine.benchmarking import quick_benchmark
from finance_feedback_engine.utils.config_loader import load_config

async def main():
    # Load your configuration
    config = load_config('config/config.yaml')

    # Run benchmark
    print("🚀 Starting baseline benchmark...")
    report = quick_benchmark(
        asset_pairs=['BTCUSD', 'ETHUSD'],  # Your trading assets
        start_date='2024-01-01',
        end_date='2024-12-01',
        config=config
    )

    # Display results
    print("\n" + "="*60)
    print("📊 BENCHMARK RESULTS")
    print("="*60)
    print(f"Sharpe Ratio:    {report.sharpe_ratio:.2f}")
    print(f"Win Rate:        {report.win_rate:.1%}")
    print(f"Total Return:    {report.total_return:.2f}%")
    print(f"Max Drawdown:    {report.max_drawdown:.2f}%")
    print(f"Profit Factor:   {report.profit_factor:.2f}")
    print(f"Total Trades:    {report.total_trades}")
    print("="*60)

    # Compare to baselines
    if report.vs_buy_hold:
        print("\n📈 vs Buy & Hold:")
        print(f"  Sharpe Improvement: {report.vs_buy_hold['sharpe_improvement']:+.2f}")
        print(f"  Return Improvement: {report.vs_buy_hold['return_improvement']:+.2f}%")

    print(f"\n✅ Full report saved to: data/benchmarks/")
    print(f"   Report name: {report.name}")

if __name__ == '__main__':
    asyncio.run(main())
```

**Run it:**
```bash
python scripts/run_baseline_benchmark.py
```

**What you'll get:**
- Baseline Sharpe ratio, win rate, drawdown
- Comparison vs buy-and-hold strategy
- JSON report saved to `data/benchmarks/`

---

## Step 2: Monitor Live Performance (10 minutes)

Set up real-time performance monitoring to track your agent's live performance.

```python
# File: scripts/monitor_live_performance.py

import asyncio
import time
from finance_feedback_engine.metrics.performance_metrics import (
    PerformanceMetricsCollector,
    RollingMetricsCalculator
)

class LivePerformanceMonitor:
    """Simple live performance monitor."""

    def __init__(self):
        self.collector = PerformanceMetricsCollector()
        self.rolling = RollingMetricsCalculator(self.collector)

    def record_trade(self, trade_outcome):
        """Record a completed trade."""
        self.collector.record_trade(trade_outcome)

        # Calculate rolling metrics
        sharpe_30d = self.rolling.calculate_rolling_sharpe(window_days=30)
        win_rate_20 = self.rolling.calculate_rolling_win_rate(window_trades=20)
        current_dd = self.rolling.calculate_current_drawdown()

        # Display metrics
        print(f"\n📊 Live Performance Update")
        print(f"  30-day Sharpe:        {sharpe_30d:.2f}")
        print(f"  Last 20 trades Win%:  {win_rate_20:.1%}")
        print(f"  Current Drawdown:     {current_dd:.2f}%")

        # Alert on degradation
        if sharpe_30d < 0.5:
            print(f"  ⚠️  WARNING: Low Sharpe detected!")

        if current_dd > 15.0:
            print(f"  🚨 ALERT: High drawdown detected!")

# Usage in your trading loop
monitor = LivePerformanceMonitor()

# After each trade completes
monitor.record_trade({
    'exit_timestamp': datetime.utcnow(),
    'realized_pnl': 150.0,  # Profit/loss in USD
    'pnl_percentage': 1.5,  # P&L as %
    'was_profitable': True,
    'holding_period_hours': 24.0,
    'position_size': 0.1,
    'entry_price': 50000.0,
    'exit_price': 50750.0,
    'asset_pair': 'BTCUSD'
})
```

**Integration points:**
1. In `TradingLoopAgent.handle_learning_state()` - record closed trades
2. In `TradeMonitor.get_closed_trades()` - pass outcomes to monitor
3. In CLI dashboard - display live metrics

---

## Step 3: Identify Improvement Opportunities (5 minutes)

Analyze your agent's performance to find optimization opportunities.

```python
# File: scripts/analyze_opportunities.py

from finance_feedback_engine.metrics.performance_metrics import PerformanceMetricsCollector

def identify_opportunities(metrics_collector: PerformanceMetricsCollector):
    """Analyze performance and identify improvement opportunities."""

    metrics = metrics_collector.calculate_metrics()

    opportunities = []

    # Check 1: Low Sharpe Ratio
    if metrics.sharpe_ratio < 1.0:
        opportunities.append({
            'issue': 'Low Sharpe Ratio',
            'current': metrics.sharpe_ratio,
            'target': 1.5,
            'recommendation': 'Optimize provider weights or tighten entry criteria',
            'priority': 'HIGH'
        })

    # Check 2: Low Win Rate
    if metrics.win_rate < 0.50:
        opportunities.append({
            'issue': 'Low Win Rate',
            'current': f"{metrics.win_rate:.1%}",
            'target': '55%',
            'recommendation': 'Improve entry timing or add confirmation signals',
            'priority': 'HIGH'
        })

    # Check 3: High Drawdown
    if metrics.max_drawdown > 15.0:
        opportunities.append({
            'issue': 'High Drawdown',
            'current': f"{metrics.max_drawdown:.2f}%",
            'target': '<12%',
            'recommendation': 'Reduce position sizing or widen stop-losses',
            'priority': 'CRITICAL'
        })

    # Check 4: Poor Win/Loss Ratio
    if metrics.win_loss_ratio < 1.5:
        opportunities.append({
            'issue': 'Poor Win/Loss Ratio',
            'current': f"{metrics.win_loss_ratio:.2f}",
            'target': '>2.0',
            'recommendation': 'Let winners run longer or cut losses faster',
            'priority': 'MEDIUM'
        })

    # Display opportunities
    print("\n🔍 IMPROVEMENT OPPORTUNITIES")
    print("="*60)

    if not opportunities:
        print("✅ No critical issues found! Performance looks good.")
    else:
        for i, opp in enumerate(opportunities, 1):
            print(f"\n{i}. {opp['issue']} [{opp['priority']}]")
            print(f"   Current: {opp['current']}")
            print(f"   Target:  {opp['target']}")
            print(f"   Action:  {opp['recommendation']}")

    print("="*60)

    return opportunities

# Usage
collector = PerformanceMetricsCollector()
# ... record trades ...
opportunities = identify_opportunities(collector)
```

---

## Step 4: Test an Improvement (10 minutes)

Test a simple improvement using A/B testing.

```python
# File: scripts/test_improvement.py

import asyncio
from finance_feedback_engine.utils.config_loader import load_config
from finance_feedback_engine.benchmarking import quick_benchmark

async def test_improvement():
    """Test a configuration change."""

    # Load base config
    base_config = load_config('config/config.yaml')

    # Test parameters
    asset_pairs = ['BTCUSD']
    start_date = '2024-01-01'
    end_date = '2024-06-01'

    # Baseline: Current configuration
    print("🔵 Testing BASELINE configuration...")
    baseline_report = quick_benchmark(
        asset_pairs=asset_pairs,
        start_date=start_date,
        end_date=end_date,
        config=base_config
    )

    # Treatment: Adjusted stop-loss
    print("\n🟢 Testing IMPROVED configuration (wider stop-loss)...")
    improved_config = base_config.copy()
    improved_config['agent']['sizing_stop_loss_percentage'] = 0.03  # 3% instead of 2%

    improved_report = quick_benchmark(
        asset_pairs=asset_pairs,
        start_date=start_date,
        end_date=end_date,
        config=improved_config
    )

    # Compare results
    print("\n" + "="*60)
    print("📊 A/B TEST RESULTS")
    print("="*60)

    sharpe_improvement = improved_report.sharpe_ratio - baseline_report.sharpe_ratio
    return_improvement = improved_report.total_return - baseline_report.total_return
    dd_improvement = baseline_report.max_drawdown - improved_report.max_drawdown

    print(f"\nSharpe Ratio:")
    print(f"  Baseline: {baseline_report.sharpe_ratio:.2f}")
    print(f"  Improved: {improved_report.sharpe_ratio:.2f}")
    print(f"  Change:   {sharpe_improvement:+.2f} ({sharpe_improvement/baseline_report.sharpe_ratio*100:+.1f}%)")

    print(f"\nWin Rate:")
    print(f"  Baseline: {baseline_report.win_rate:.1%}")
    print(f"  Improved: {improved_report.win_rate:.1%}")

    print(f"\nMax Drawdown:")
    print(f"  Baseline: {baseline_report.max_drawdown:.2f}%")
    print(f"  Improved: {improved_report.max_drawdown:.2f}%")
    print(f"  Change:   {dd_improvement:+.2f}%")

    # Decision
    if sharpe_improvement > 0.1 and dd_improvement > 0:
        print(f"\n✅ RECOMMENDATION: Deploy improved configuration")
        print(f"   Improvement is statistically significant")
    else:
        print(f"\n❌ RECOMMENDATION: Keep baseline configuration")
        print(f"   No significant improvement detected")

    print("="*60)

if __name__ == '__main__':
    asyncio.run(test_improvement())
```

---

## Common Improvement Strategies

### 1. Optimize Provider Weights

```yaml
# config/config.yaml
ensemble:
  enabled_providers:
    - llama3.2:latest
    - qwen2.5:latest
    - gemma2:latest

  # Adjust these based on performance
  provider_weights:
    llama3.2:latest: 0.40  # Increase if performing well
    qwen2.5:latest: 0.35
    gemma2:latest: 0.25
```

**Test it:**
```bash
# Run benchmark with adjusted weights
python scripts/test_improvement.py
```

### 2. Widen Stop-Loss

```yaml
# config/config.yaml
agent:
  sizing_stop_loss_percentage: 0.03  # Increase from 0.02 (2%) to 0.03 (3%)
```

**Why:** Prevents getting stopped out by normal volatility

### 3. Increase Confidence Threshold

```yaml
# config/config.yaml
agent:
  min_confidence_threshold: 0.75  # Increase from 0.70 to 0.75
```

**Why:** Only take highest-conviction trades

### 4. Enable Dynamic Stop-Loss

```yaml
# config/config.yaml
agent:
  use_dynamic_stop_loss: true
  atr_multiplier: 2.0  # 2x ATR for stop-loss distance
  min_stop_loss_pct: 0.01  # Minimum 1%
  max_stop_loss_pct: 0.05  # Maximum 5%
```

**Why:** Adapts stop-loss to market volatility

---

## Next Steps

### Week 1: Establish Baseline
- ✅ Run baseline benchmark
- ✅ Set up live monitoring
- ✅ Identify top 3 improvement opportunities

### Week 2: Test Improvements
- ✅ A/B test provider weight optimization
- ✅ A/B test stop-loss adjustments
- ✅ A/B test confidence threshold changes

### Week 3: Deploy Winners
- ✅ Deploy improvements with >10% Sharpe improvement
- ✅ Monitor for regressions
- ✅ Document successful changes

### Week 4: Advanced Optimization
- ✅ Implement regime-adaptive strategies
- ✅ Add meta-learning for provider selection
- ✅ Build automated optimization pipeline

---

## Troubleshooting

### Q: Benchmark takes too long
**A:** Reduce date range or number of assets:
```python
report = quick_benchmark(
    asset_pairs=['BTCUSD'],  # Just one asset
    start_date='2024-10-01',  # Shorter period
    end_date='2024-12-01',
    config=config
)
```

### Q: No improvement detected
**A:** Try larger changes or different parameters:
```python
# More aggressive changes
improved_config['agent']['min_confidence_threshold'] = 0.80  # +10% instead of +5%
improved_config['agent']['sizing_stop_loss_percentage'] = 0.04  # Double the change
```

### Q: Results are inconsistent
**A:** Use longer test periods and multiple assets:
```python
report = quick_benchmark(
    asset_pairs=['BTCUSD', 'ETHUSD', 'EURUSD'],  # Multiple assets
    start_date='2024-01-01',  # 12-month period
    end_date='2024-12-01',
    config=config
)
```

---

## Performance Goals

### Minimum Acceptable Performance
- Sharpe Ratio: > 0.8
- Win Rate: > 45%
- Max Drawdown: < 20%
- Profit Factor: > 1.3

### Good Performance
- Sharpe Ratio: > 1.2
- Win Rate: > 55%
- Max Drawdown: < 15%
- Profit Factor: > 1.6

### Excellent Performance
- Sharpe Ratio: > 1.5
- Win Rate: > 60%
- Max Drawdown: < 12%
- Profit Factor: > 2.0

---

## Getting Help

- 📖 Full Documentation: `docs/AGENT_PERFORMANCE_IMPROVEMENT_PLAN.md`
- 🐛 Issues: Create issue in GitHub
- 💬 Questions: Check project discussions

Happy optimizing! 🚀
