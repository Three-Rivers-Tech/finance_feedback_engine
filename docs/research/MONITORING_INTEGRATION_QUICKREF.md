# Monitoring Integration Quick Reference

## One-Time Setup

```python
from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.monitoring import TradeMonitor, TradeMetricsCollector

# Initialize
engine = FinanceFeedbackEngine(config)
monitor = TradeMonitor(platform=engine.trading_platform)
metrics = TradeMetricsCollector()

# Enable integration (AI gets full position awareness)
engine.enable_monitoring_integration(monitor, metrics)
```

## Make Decisions (No Code Changes!)

```python
# AI automatically receives:
# - Active positions
# - Current P&L
# - Risk metrics
# - Recent performance
decision = engine.analyze_asset('BTCUSD')
```

## What AI Sees

```
=== LIVE TRADING CONTEXT ===
Active Positions: 2
  • LONG BTC-PERP-INTX: 0.50 @ $95000 (current $96500) | P&L: +$750
  • SHORT ETH-PERP-INTX: 1.00 @ $3200 (current $3100) | P&L: +$100

Risk Exposure:
  • Total Exposure: $144,000.00
  • Leverage: 2.88x
  • Net Exposure: $48,000.00

Recent Performance (24h):
  • Trades: 5 | Win Rate: 60%
  • Total P&L: $1,250
```

## Config (Optional)

```yaml
monitoring:
  enable_context_integration: true  # default
  detection_interval: 30  # seconds
  poll_interval: 30       # seconds
```

## Test

```bash
python test_monitoring_integration.py
python examples/monitoring_aware_decisions.py
```

## Key Benefits

✅ AI knows all open positions  
✅ Won't make conflicting trades  
✅ Adjusts risk based on current exposure  
✅ Learns from recent performance  
✅ Prevents over-concentration  

No code changes after setup - just enable once!
