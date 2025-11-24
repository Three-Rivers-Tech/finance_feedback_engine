"""Example: Live Trade Monitoring System."""

from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.monitoring import TradeMonitor
from finance_feedback_engine.memory import PortfolioMemoryEngine
import time

# Load engine with your config
engine = FinanceFeedbackEngine(config_path="config/config.local.yaml")

# Initialize portfolio memory for ML feedback
portfolio_memory = PortfolioMemoryEngine(
    storage_dir="data/demo_memory"
)

# Create trade monitor
monitor = TradeMonitor(
    platform=engine.trading_platform,
    portfolio_memory=portfolio_memory,
    detection_interval=30,  # Check for new trades every 30 seconds
    poll_interval=30  # Update position prices every 30 seconds
)

print("🔍 Starting Live Trade Monitor")
print(f"  Max concurrent trades: {monitor.MAX_CONCURRENT_TRADES}")
print(f"  Detection interval: {monitor.detection_interval}s")
print(f"  Poll interval: {monitor.poll_interval}s")
print()

# Start monitoring
monitor.start()

try:
    print("✅ Monitor is running!")
    print()
    print("Monitor will automatically detect and track:")
    print("  • New trades opened on Coinbase")
    print("  • Price updates and P&L changes")
    print("  • Trade exits and final metrics")
    print()
    print("Metrics are saved to:")
    print("  • data/trade_metrics/ (raw metrics)")
    print("  • data/demo_memory/ (portfolio memory)")
    print()
    print("Press Ctrl+C to stop monitoring...")
    print()
    
    # Keep running and show periodic status
    while monitor.is_running:
        time.sleep(10)
        
        # Show active trades
        active_trades = monitor.get_active_trades()
        if active_trades:
            print(f"\n📊 Active Trades: {len(active_trades)}")
            for trade in active_trades:
                print(
                    f"  {trade['product_id']} {trade['side']}: "
                    f"${trade['current_pnl']:.2f} PnL "
                    f"({trade['holding_hours']:.2f}h)"
                )
        
        # Show summary
        summary = monitor.get_monitoring_summary()
        metrics = summary['trade_metrics']
        if metrics['total_trades'] > 0:
            print(f"\n📈 Performance Summary:")
            print(f"  Total trades: {metrics['total_trades']}")
            print(f"  Win rate: {metrics['win_rate']:.1f}%")
            print(f"  Total P&L: ${metrics['total_pnl']:.2f}")

except KeyboardInterrupt:
    print("\n\n⏹️  Stopping monitor...")
    
    # Graceful shutdown
    if monitor.stop(timeout=10.0):
        print("✅ Monitor stopped cleanly")
    else:
        print("⚠️  Monitor forced shutdown (timeout)")
    
    # Show final metrics
    print("\n📊 Final Metrics Summary:")
    print(monitor.metrics_collector.get_metrics_summary())

print("\n✅ Done!")
