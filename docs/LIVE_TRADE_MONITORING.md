# Live Trade Monitoring System

## Overview

The Live Trade Monitoring System automatically detects, tracks, and analyzes your open trades in real-time, providing comprehensive metrics and ML feedback loop integration.

## Features

### Automatic Trade Detection
- Continuously polls Coinbase Advanced for open positions
- Detects new trades within 30 seconds (configurable)
- Tracks up to 2 concurrent trades (configurable via `MAX_CONCURRENT_TRADES`)

### Real-time Position Tracking
- Updates position prices every 30 seconds (configurable)
- Tracks unrealized P&L in real-time
- Records peak P&L and maximum drawdown
- Monitors for stop loss and take profit conditions

### Complete Trade Lifecycle Management
1. **Entry**: Captures initial position details
2. **Monitoring**: Continuous price/P&L updates
3. **Exit**: Detects position close
4. **Metrics**: Final performance calculation
5. **Cleanup**: Thread termination and resource release

## Current Status

The Live Trade Monitoring System is fully integrated and operational, providing real-time insights into trading performance and facilitating adaptive learning through feedback loops.

## Architecture

```
TradeMonitor (Main Thread)
├── Detection Loop (every 30s)
│   ├── Poll platform for open positions
│   ├── Detect new trades
│   └── Queue for tracking
│
├── ThreadPoolExecutor (max_workers=2)
│   ├── TradeTrackerThread #1
│   │   └── Poll position updates (every 30s)
│   │       ├── Track P&L metrics
│   │       ├── Detect exit
│   │       └── Return metrics
│   │
│   └── TradeTrackerThread #2
│       └── (same as #1)
│
└── Metrics Callback
    ├── TradeMetricsCollector
    │   └── Save to data/trade_metrics/
    │
    └── PortfolioMemoryEngine
        └── Save to data/[memory_dir]/
```

## Usage

### CLI Commands

#### Start Monitoring
```bash
python main.py monitor start
```

Starts the monitoring system and keeps it running. Press Ctrl+C to stop.

**Output:**
```
🔍 Starting Live Trade Monitor

✓ Monitor started successfully
  Max concurrent trades: 2
  Detection interval: 30s
  Poll interval: 30s

Monitor is running in background...
Use 'python main.py monitor status' to check status
Use 'python main.py monitor stop' to stop monitoring
```

#### Check Status
```bash
python main.py monitor status
```

Shows currently open positions being monitored.

**Output:**
```
📊 Trade Monitor Status

                    Open Positions (Monitored)
┏━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Product ID    ┃ Side ┃ Contracts ┃   Entry ┃  Current ┃      PnL ┃
┡━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ BTC-20DEC30   │ LONG │       1.0 │ $95,000 │  $96,500 │  +$1,500 │
│ ETH-20DEC30   │ SHORT│       5.0 │  $3,500 │   $3,450 │    +$250 │
└───────────────┴──────┴───────────┴─────────┴──────────┴──────────┘

Total open positions: 2
```

#### View Performance Metrics
```bash
python main.py monitor metrics
```

Shows aggregate performance statistics from completed trades.

**Output:**
```
📈 Trade Performance Metrics

Total Trades:     15
Winning Trades:   9
Losing Trades:    6
Win Rate:         60.0%
Total P&L:        $4,250.00
Average P&L:      $283.33

Recent Trades:
┏━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Product       ┃ Side  ┃ Duration ┃      PnL ┃ Exit Reason       ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ BTC-20DEC30   │ LONG  │    4.25h │   +$850  │ take_profit_likely│
│ ETH-20DEC30   │ SHORT │    2.10h │   +$320  │ manual_close      │
│ BTC-20DEC30   │ LONG  │    6.75h │   -$450  │ stop_loss_likely  │
└───────────────┴───────┴──────────┴──────────┴───────────────────┘
```

### Python API

```python
from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.monitoring import TradeMonitor
from finance_feedback_engine.memory import PortfolioMemoryEngine

# Initialize engine
engine = FinanceFeedbackEngine(config="config/config.local.yaml")

# Optional: Add portfolio memory for ML feedback
portfolio_memory = PortfolioMemoryEngine(config="config/config.local.yaml")

# Create monitor
monitor = TradeMonitor(
    platform=engine.trading_platform,
    portfolio_memory=portfolio_memory,
    detection_interval=30,  # seconds
    poll_interval=30  # seconds
)

# Start monitoring
monitor.start()

# ... monitor runs in background ...

# Get active trades
active_trades = monitor.get_active_trades()
for trade in active_trades:
    print(f"{trade['product_id']}: ${trade['current_pnl']:.2f} PnL")

# Get summary
summary = monitor.get_monitoring_summary()
print(f"Active trackers: {summary['active_trackers']}")
print(f"Total tracked: {summary['total_tracked']}")

# Stop monitoring (graceful shutdown)
monitor.stop(timeout=10.0)
```

## Configuration

### Detection Interval
How often to poll platform for new trades (default: 30s)

```python
monitor = TradeMonitor(
    platform=platform,
    detection_interval=60  # Check every 60 seconds
)
```

### Poll Interval
How often to update position prices (default: 30s)

```python
monitor = TradeMonitor(
    platform=platform,
    poll_interval=15  # Update every 15 seconds
)
```

### Max Concurrent Trades
Modify `MAX_CONCURRENT_TRADES` constant in `TradeMonitor` class:

```python
# In trade_monitor.py
class TradeMonitor:
    MAX_CONCURRENT_TRADES = 5  # Allow 5 concurrent trades
```

## Trade Metrics

### Captured Data

Each tracked trade records:

```python
{
    'trade_id': 'BTC-20DEC30_LONG',
    'product_id': 'BTC-20DEC30',
    'side': 'LONG',
    'entry_time': '2025-11-23T10:00:00Z',
    'exit_time': '2025-11-23T14:15:00Z',
    'holding_duration_seconds': 15300,
    'holding_duration_hours': 4.25,
    'entry_price': 95000.0,
    'exit_price': 96500.0,
    'position_size': 1.0,
    'realized_pnl': 1500.0,
    'peak_pnl': 1800.0,
    'max_drawdown': 200.0,
    'exit_reason': 'take_profit_likely',
    'price_updates_count': 17,
    'forced_stop': False,
    'final_status': 'completed'
}
```

### Storage Locations

**Raw Metrics**: `data/trade_metrics/`
- One JSON file per trade
- Filename: `trade_{id}_{timestamp}.json`

**Portfolio Memory**: `data/{memory_dir}/`
- Integrated with PortfolioMemoryEngine
- Used for ML model feedback

### Export for Training

```python
from finance_feedback_engine.monitoring import TradeMetricsCollector

collector = TradeMetricsCollector()

# Export training-ready data
training_data = collector.export_for_model_training(
    output_file="data/training_export.json"
)

print(f"Exported {len(training_data['trades'])} trades")
print(f"Win rate: {training_data['aggregate_stats']['win_rate']:.1f}%")
```

## Integration with PortfolioMemoryEngine

When `portfolio_memory` is provided, completed trades are automatically:
1. Converted to `TradeOutcome` format
2. Recorded in memory engine
3. Used for performance attribution
4. Fed back into AI decision-making

```python
# Monitor automatically calls:
portfolio_memory.record_trade_outcome(
    decision=decision,
    exit_price=exit_price,
    exit_timestamp=exit_time,
    hit_stop_loss=hit_stop_loss,
    hit_take_profit=hit_take_profit
)
```

## Thread Safety & Cleanup

### Graceful Shutdown
```python
# Clean shutdown with timeout
monitor.stop(timeout=10.0)
```

**Shutdown sequence:**
1. Set stop event
2. Stop all active trackers
3. Wait for main thread completion
4. Shutdown thread pool executor
5. Mark as not running

### Orphaned Trade Recovery

If monitor crashes/restarts:
1. New detection cycle finds existing positions
2. Already-tracked trades are skipped
3. New trades are queued for monitoring
4. Tracked set is restored from platform state

### Error Handling

All components handle errors gracefully:
- API failures → logged, continue monitoring
- Thread crashes → logged, tracker removed
- Metric recording errors → logged, don't block monitoring

## Limitations & Future Enhancements

### Current Limitations
1. **Trade linking**: Doesn't link detected positions to original decisions
2. **Exit price approximation**: Uses last known price (may differ from actual fill)
3. **Single platform**: Currently Coinbase Advanced only
4. **Persistence**: Monitor state not persisted across restarts

### Planned Enhancements
1. **Decision linking**: Match positions to decision IDs via order tracking
2. **Fill data**: Use actual fill prices from exchange API
3. **Multi-platform**: Support Oanda, Binance, etc.
4. **State persistence**: Save/restore monitor state
5. **Alert system**: Notifications on trade events
6. **Performance dashboard**: Real-time web UI

## Example Workflow

### 1. Start Monitor
```bash
python main.py monitor start
```

### 2. Open Trade (manually or via bot)
Trade opens on Coinbase Advanced

### 3. Automatic Detection (within 30s)
```
🔔 New trade detected: BTC-20DEC30_LONG | LONG 1.0 @ $95,000.00
✅ Started tracking trade: BTC-20DEC30_LONG | Active trackers: 1/2
```

### 4. Continuous Updates (every 30s)
```
Position update: BTC-20DEC30_LONG |
  Price: $95,500.00 | PnL: $500.00 |
  Peak: $500.00 | Drawdown: $0.00
```

### 5. Position Close (detected on next poll)
```
Position closed detected: BTC-20DEC30_LONG
Trade finalized: BTC-20DEC30_LONG |
  Duration: 4.25h | PnL: $1,500.00 | Reason: take_profit_likely
```

### 6. Metrics Recorded
```
📊 Trade completed: BTC-20DEC30_LONG |
  PnL: $1,500.00 | Duration: 4.25h
Trade metrics recorded: BTC-20DEC30_LONG |
  PnL: $1,500.00 | File: trade_BTC-20DEC30_LONG_20251123_141500.json
Trade outcome recorded in portfolio memory: BTC-20DEC30_LONG
```

### 7. View Metrics
```bash
python main.py monitor metrics
```

## Troubleshooting

### Monitor not detecting trades
- Check platform connection
- Verify `get_portfolio_breakdown()` returns positions
- Increase detection interval if API rate-limited

### Threads not stopping
- Increase timeout in `stop(timeout=XX)`
- Check logs for errors in tracker threads

### Missing metrics
- Check `data/trade_metrics/` directory exists
- Verify write permissions
- Check logs for recording errors

## See Also

- [Portfolio Memory Engine](PORTFOLIO_MEMORY_ENGINE.md)
- [Portfolio Tracking](PORTFOLIO_TRACKING.md)
- [Trading Platforms](../finance_feedback_engine/trading_platforms/)

## Conclusion

The Live Trade Monitoring System is essential for real-time trade management, ensuring that traders can make informed decisions based on accurate and timely data.
