# Live Trade Monitoring - Quick Reference

## Quick Start

### Start Monitoring
```bash
python main.py monitor start
```

Monitor automatically:
- Detects new trades within 30s
- Updates prices/P&L every 30s
- Records metrics when trades close
- Max 2 concurrent trades tracked

### Check Status
```bash
python main.py monitor status
```

### View Metrics
```bash
python main.py monitor metrics
```

## Python API

```python
from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.monitoring import TradeMonitor

# Initialize
engine = FinanceFeedbackEngine(config="config/config.local.yaml")

# Create monitor
monitor = TradeMonitor(
    platform=engine.trading_platform,
    detection_interval=30,  # Scan for new trades every 30s
    poll_interval=30        # Update positions every 30s
)

# Start
monitor.start()

# Get active trades
trades = monitor.get_active_trades()

# Get summary
summary = monitor.get_monitoring_summary()

# Stop (graceful shutdown)
monitor.stop(timeout=10.0)
```

## With Portfolio Memory (ML Feedback)

```python
from finance_feedback_engine.memory import PortfolioMemoryEngine

portfolio_memory = PortfolioMemoryEngine(config=config)

monitor = TradeMonitor(
    platform=platform,
    portfolio_memory=portfolio_memory  # Enables ML feedback
)
```

## Configuration

### Detection Interval
How often to check for new trades (default: 30s)
```python
monitor = TradeMonitor(platform=platform, detection_interval=60)
```

### Poll Interval
How often to update position prices (default: 30s)
```python
monitor = TradeMonitor(platform=platform, poll_interval=15)
```

### Max Concurrent Trades
Edit `trade_monitor.py`:
```python
class TradeMonitor:
    MAX_CONCURRENT_TRADES = 5  # Default is 2
```

## Trade Metrics

### Captured Per Trade
- Entry/exit prices and times
- Holding duration (hours)
- Realized P&L
- Peak P&L and max drawdown
- Exit reason (stop loss, take profit, manual)

### Aggregate Stats
- Win rate %
- Total/average P&L
- Best/worst trades
- Average holding time

## Data Locations

**Raw Metrics:** `data/trade_metrics/trade_{id}_{timestamp}.json`

**Portfolio Memory:** `data/{memory_dir}/` (if integrated)

## Export for Training

```python
from finance_feedback_engine.monitoring import TradeMetricsCollector

collector = TradeMetricsCollector()
training_data = collector.export_for_model_training(
    output_file="data/training_export.json"
)
```

## Thread Structure

```
Main Thread
├── Detection Loop (every 30s)
└── ThreadPoolExecutor (max 2 workers)
    ├── TradeTrackerThread #1
    └── TradeTrackerThread #2
```

## Workflow

1. **Start monitor** → `python main.py monitor start`
2. **Open trade** → On Coinbase Advanced
3. **Detected** → Within 30s: "🔔 New trade detected"
4. **Tracked** → Updates every 30s with price/P&L
5. **Closed** → Detected on next poll
6. **Metrics** → Saved to `data/trade_metrics/`
7. **View** → `python main.py monitor metrics`

## Example Output

### Detection
```
🔔 New trade detected: BTC-20DEC30_LONG | LONG 1.0 @ $95,000.00
✅ Started tracking trade: BTC-20DEC30_LONG | Active trackers: 1/2
```

### Updates
```
Position update: BTC-20DEC30_LONG | Price: $95,500.00 | PnL: $500.00
```

### Completion
```
📊 Trade completed: BTC-20DEC30_LONG | PnL: $1,500.00 | Duration: 4.25h
Trade metrics recorded: BTC-20DEC30_LONG | File: trade_BTC-20DEC30_LONG_20251123.json
```

## Troubleshooting

**Monitor not detecting trades?**
- Check platform connection
- Verify `get_portfolio_breakdown()` works
- Check API rate limits

**Threads not stopping?**
- Increase timeout: `monitor.stop(timeout=30)`

**Missing metrics?**
- Check `data/trade_metrics/` exists
- Verify write permissions
- Review logs for errors

## Documentation

- Full Guide: [docs/LIVE_TRADE_MONITORING.md](docs/LIVE_TRADE_MONITORING.md)
- Implementation: [LIVE_MONITORING_IMPLEMENTATION.md](LIVE_MONITORING_IMPLEMENTATION.md)
- Example: [examples/live_monitoring_example.py](examples/live_monitoring_example.py)
