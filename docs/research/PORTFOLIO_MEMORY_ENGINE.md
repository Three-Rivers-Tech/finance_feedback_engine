# Portfolio Memory Engine - Documentation

## Overview

The **Portfolio Memory Engine** is a reinforcement learning-inspired system that learns from trading outcomes to improve future decisions. It implements experience replay, performance attribution, and adaptive learning strategies commonly found in state-of-the-art RL trading systems.

## Key Features

### 1. **Experience Replay**
- Stores historical (decision, outcome) pairs
- Maintains a replay buffer of configurable size (default: 1000 experiences)
- Enables learning from past successes and failures

### 2. **Performance Attribution**
- Tracks which AI providers make profitable decisions
- Analyzes provider performance by confidence level
- Identifies which actions (BUY/SELL/HOLD) work best in different market regimes

### 3. **Context Generation**
- Generates performance summaries for AI decision-making
- Feeds recent win rate, P&L, and action performance into prompts
- Provides asset-specific historical context

### 4. **Adaptive Learning**
- Recommends provider weight adjustments based on realized performance
- Calculates confidence-calibrated statistics
- Supports market regime detection (bullish/bearish/sideways)

### 5. **Comprehensive Metrics**
- Win rate, profit factor, Sharpe/Sortino ratios
- Maximum drawdown tracking
- Provider-specific performance stats
- Confidence calibration analysis

## Architecture

```
PortfolioMemoryEngine
├── TradeOutcome Recording
│   ├── record_trade_outcome()      # Record completed trade results
│   ├── _update_provider_performance()
│   └── _update_regime_performance()
├── Performance Analysis
│   ├── analyze_performance()        # Generate performance snapshot
│   ├── _calculate_provider_stats()
│   ├── _calculate_sharpe_ratio()
│   └── _calculate_sortino_ratio()
├── Context Generation
│   ├── generate_context()           # Create AI prompt context
│   ├── format_context_for_prompt()  # Human-readable formatting
│   └── get_provider_recommendations() # Suggest weight adjustments
└── Persistence
    ├── _save_outcome()              # Save individual outcomes
    ├── _save_snapshot()             # Save performance snapshots
    └── _load_memory()               # Load from disk on init
```

## Data Structures

### TradeOutcome
```python
@dataclass
class TradeOutcome:
    decision_id: str
    asset_pair: str
    action: str  # BUY/SELL/HOLD
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    position_size: float
    realized_pnl: float
    pnl_percentage: float
    holding_period_hours: float

    # Provider attribution
    ai_provider: str
    ensemble_providers: List[str]
    decision_confidence: int

    # Market context
    market_sentiment: str
    volatility: float
    price_trend: str

    # Outcome classification
    was_profitable: bool
    hit_stop_loss: bool
    hit_take_profit: bool
```

### PerformanceSnapshot
```python
@dataclass
class PerformanceSnapshot:
    timestamp: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float

    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float

    provider_stats: Dict[str, Dict[str, float]]
    regime_performance: Dict[str, Dict[str, float]]
```

## Configuration

Add to your `config.yaml`:

```yaml
portfolio_memory:
  enabled: true
  max_memory_size: 1000       # Max experiences to retain
  learning_rate: 0.1          # Provider weight update rate
  context_window: 20          # Recent trades for context
```

## Usage Examples

### 1. Basic Setup

```python
from finance_feedback_engine import FinanceFeedbackEngine

# Enable memory in config
config = {
    'alpha_vantage_api_key': 'YOUR_KEY',
    'trading_platform': 'coinbase',
    'platform_credentials': {...},
    'decision_engine': {
        'ai_provider': 'ensemble'
    },
    'portfolio_memory': {
        'enabled': True,
        'max_memory_size': 1000,
        'context_window': 20
    }
}

engine = FinanceFeedbackEngine(config)
```

### 2. Making Memory-Informed Decisions

```python
# Generate decision with memory context
decision = engine.analyze_asset(
    'BTCUSD',
    include_sentiment=True,
    use_memory_context=True  # Include historical performance
)

print(f"Action: {decision['action']}")
print(f"Confidence: {decision['confidence']}%")
print(f"Reasoning: {decision['reasoning']}")
```

### 3. Recording Trade Outcomes

```python
# Execute a trade
decision = engine.analyze_asset('BTCUSD')
engine.execute_decision(decision['id'])

# Later, when closing the position...
outcome = engine.record_trade_outcome(
    decision_id=decision['id'],
    exit_price=52000.0,
    exit_timestamp='2025-01-15T10:30:00Z',
    hit_stop_loss=False,
    hit_take_profit=True
)

print(f"P&L: ${outcome['realized_pnl']:.2f}")
print(f"Win Rate: {outcome['pnl_percentage']:.2f}%")
```

### 4. Analyzing Performance

```python
# Get all-time performance
snapshot = engine.get_performance_snapshot()

print(f"Total Trades: {snapshot['total_trades']}")
print(f"Win Rate: {snapshot['win_rate']:.1f}%")
print(f"Total P&L: ${snapshot['total_pnl']:.2f}")
print(f"Sharpe Ratio: {snapshot['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {snapshot['max_drawdown']:.2f}%")

# Get recent performance (last 30 days)
recent = engine.get_performance_snapshot(window_days=30)
```

### 5. Getting Provider Recommendations

```python
# Analyze which AI providers are performing best
recommendations = engine.get_provider_recommendations()

print(f"Confidence: {recommendations['confidence']}")
print("Recommended Weights:")
for provider, weight in recommendations['recommended_weights'].items():
    stats = recommendations['provider_stats'][provider]
    print(f"  {provider}: {weight:.2%}")
    print(f"    Win Rate: {stats['win_rate']:.1f}%")
    print(f"    Total Trades: {stats['total_trades']}")
    print(f"    Avg P&L: ${stats['avg_pnl_per_trade']:.2f}")
```

### 6. Viewing Memory Context

```python
# Get context for specific asset
context = engine.get_memory_context(asset_pair='BTCUSD')

if context['has_history']:
    print(f"Historical Trades: {context['total_historical_trades']}")
    print(f"Recent Win Rate: {context['recent_performance']['win_rate']:.1f}%")

    # Asset-specific stats
    if 'asset_specific' in context:
        asset_stats = context['asset_specific']
        print(f"BTCUSD Historical: {asset_stats['win_rate']:.1f}% win rate")
```

## Best Practices

### 1. **Minimum Data Requirements**
- Start recording outcomes after at least 20 trades
- Provider recommendations become reliable after 50+ trades per provider
- Confidence calibration requires 100+ samples for accuracy

### 2. **Regular Snapshots**
```python
# Take periodic snapshots for tracking
import schedule

def take_snapshot():
    engine.get_performance_snapshot()
    engine.save_memory()

schedule.every().day.at("23:59").do(take_snapshot)
```

### 3. **Weight Adaptation Strategy**
```python
# Update ensemble weights based on memory recommendations
recommendations = engine.get_provider_recommendations()

if recommendations['confidence'] == 'high':
    # Apply recommended weights to ensemble config
    config['ensemble']['provider_weights'] = (
        recommendations['recommended_weights']
    )
    # Restart engine with new weights
```

### 4. **Market Regime Awareness**
The engine automatically tracks performance in different market regimes:
- **Bullish sentiment**: Performance when news is positive
- **Bearish sentiment**: Performance when news is negative
- **Trend_bullish**: Performance in uptrending markets
- **Trend_bearish**: Performance in downtrending markets

Access regime stats:
```python
snapshot = engine.get_performance_snapshot()
for regime, stats in snapshot['regime_performance'].items():
    print(f"{regime}: {stats['win_rate']:.1f}% ({stats['total_trades']} trades)")
```

## RL/Trading Best Practices Implemented

### 1. **Experience Replay (DeepMind DQN)**
- Maintains replay buffer of (state, action, reward) tuples
- Allows learning from past experiences
- Prevents catastrophic forgetting

### 2. **Thompson Sampling**
- Confidence-based weight allocation
- Balances exploration vs exploitation
- Adapts to changing market conditions

### 3. **Meta-Learning**
- Learns which providers work best in which conditions
- Market regime detection
- Confidence calibration by bucket

### 4. **Risk-Adjusted Metrics**
- Sharpe ratio (risk-adjusted returns)
- Sortino ratio (downside-adjusted returns)
- Maximum drawdown tracking
- Profit factor (gross profit / gross loss)

### 5. **Adaptive Weighting**
- Dynamic weight updates based on realized performance
- Combination of win rate (60%) and avg P&L (40%)
- Sample size-based confidence levels

## Integration with Ensemble Manager

The Portfolio Memory Engine integrates seamlessly with the Ensemble Decision Manager:

```python
# Ensemble already tracks basic stats
# Memory engine adds:
# 1. Realized P&L attribution
# 2. Confidence calibration
# 3. Market regime analysis
# 4. Context for future decisions

# Example: Compare ensemble stats vs memory stats
ensemble_stats = engine.decision_engine.ensemble_manager.get_provider_stats()
memory_stats = engine.get_provider_recommendations()

# Ensemble stats: prediction accuracy
# Memory stats: realized P&L performance
```

## File Structure

```
data/
└── memory/
    ├── outcome_{decision_id}.json         # Individual outcomes
    ├── snapshot_{timestamp}.json          # Performance snapshots
    ├── provider_performance.json          # Provider stats summary
    └── regime_performance.json            # Regime performance summary
```

## Performance Considerations

- **Memory Usage**: Configurable `max_memory_size` (default 1000 outcomes)
- **Disk I/O**: Outcomes saved incrementally, snapshots on-demand
- **Computation**: Lightweight statistical calculations
- **Scalability**: Can handle 10,000+ historical trades efficiently

## Limitations & Future Work

### Current Limitations
1. **No true RL agent**: Uses heuristic-based weight updates, not gradient descent
2. **Simplified reward**: Binary win/loss, doesn't account for risk-adjusted returns
3. **No state representation**: Doesn't model market state explicitly
4. **Manual outcome recording**: Requires explicit `record_trade_outcome()` call

### Planned Enhancements
1. **Automatic outcome tracking**: Hook into platform trade notifications
2. **Deep RL integration**: Q-learning or policy gradient methods
3. **State representation**: LSTM/Transformer-based market state encoding
4. **Multi-objective optimization**: Pareto-optimal risk/return balancing
5. **Online learning**: Real-time weight updates after each trade

## Advanced: Custom Metrics

You can extend the memory engine with custom metrics:

```python
class CustomMemoryEngine(PortfolioMemoryEngine):
    def analyze_performance(self, window_days=None):
        snapshot = super().analyze_performance(window_days)

        # Add custom metrics
        outcomes = self.trade_outcomes

        # Calculate custom metric: average holding period
        holding_periods = [
            o.holding_period_hours for o in outcomes
            if o.holding_period_hours
        ]
        snapshot.avg_holding_period = (
            sum(holding_periods) / len(holding_periods)
            if holding_periods else 0
        )

        return snapshot
```

## Comparison to Traditional Systems

| Feature | Traditional | Portfolio Memory Engine |
|---------|-------------|------------------------|
| Historical tracking | Manual spreadsheet | Automated JSON storage |
| Performance attribution | None | Per-provider, per-action |
| Learning feedback | None | Context in AI prompts |
| Risk metrics | Basic P&L | Sharpe, Sortino, drawdown |
| Regime awareness | None | Sentiment/trend tracking |
| Confidence calibration | None | By confidence bucket |
| Provider adaptation | Static | Dynamic weight updates |

## Troubleshooting

### No historical data showing
- Ensure `portfolio_memory.enabled: true` in config
- Check that you're calling `record_trade_outcome()` after trades
- Verify outcomes are being saved to `data/memory/`

### Low confidence in recommendations
- Need at least 20 trades per provider
- Check `sample_sizes` in recommendations dict
- Increase `context_window` for more data

### Memory not loading
- Check file permissions in `data/memory/`
- Verify JSON files are valid (not corrupted)
- Look for warnings in logs during `_load_memory()`

## References

- **Experience Replay**: Mnih et al., "Human-level control through deep reinforcement learning", Nature 2015
- **Thompson Sampling**: Agrawal & Goyal, "Analysis of Thompson Sampling for the Multi-armed Bandit Problem", COLT 2012
- **Meta-Learning**: Finn et al., "Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks", ICML 2017
- **Ensemble Methods**: Mungoli, "Adaptive Learning and Forecasting of COVID-19 in India", arXiv 2023
- **Risk Metrics**: Sharpe, "The Sharpe Ratio", Journal of Portfolio Management 1994

## Support

For issues or questions:
1. Check logs for warnings/errors
2. Verify configuration is correct
3. Ensure memory files exist and are readable
4. Review this documentation for usage patterns

---

**Version**: 2.0
**Last Updated**: January 2025
**Author**: Finance Feedback Engine Team
