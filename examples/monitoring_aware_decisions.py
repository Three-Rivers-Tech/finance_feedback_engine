"""
Example: Monitoring-Aware AI Trading Decisions

This example demonstrates how the trade monitoring engine data
is automatically fed into the AI decision pipeline, giving AI models
full awareness of:
- Active open positions
- Real-time P&L
- Position concentration/risk metrics
- Recent trading performance
- Available monitoring slots

The AI will factor this into all trading recommendations.
"""

import yaml
from finance_feedback_engine import FinanceFeedbackEngine
from finance_feedback_engine.monitoring import (
    TradeMonitor,
    TradeMetricsCollector
)


def main():
    print("=" * 70)
    print("MONITORING-AWARE AI TRADING DECISIONS")
    print("=" * 70)
    print()
    
    # Load configuration
    with open('config/config.local.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Initialize engine
    print("1. Initializing Finance Feedback Engine...")
    engine = FinanceFeedbackEngine(config)
    
    # Initialize monitoring components
    print("2. Initializing trade monitoring system...")
    metrics_collector = TradeMetricsCollector()
    trade_monitor = TradeMonitor(
        platform=engine.trading_platform,
        metrics_collector=metrics_collector,
        detection_interval=30,
        poll_interval=30
    )
    
    # CRITICAL: Enable monitoring integration
    print("3. Enabling monitoring context integration...")
    engine.enable_monitoring_integration(
        trade_monitor=trade_monitor,
        metrics_collector=metrics_collector
    )
    print("   ✓ AI models now have full position/trade awareness!\n")
    
    # Demonstrate decision-making with monitoring context
    print("=" * 70)
    print("SCENARIO: Making trading decision with live position awareness")
    print("=" * 70)
    print()
    
    # Analyze BTCUSD
    print("Analyzing BTCUSD...")
    print("The AI will receive:")
    print("  • All active positions (futures + spot)")
    print("  • Current P&L for each position")
    print("  • Risk exposure metrics (leverage, concentration)")
    print("  • Number of active monitored trades")
    print("  • Recent performance (win rate, avg P&L)")
    print()
    
    decision = engine.analyze_asset('BTCUSD')
    
    print("\n" + "=" * 70)
    print("AI DECISION (with full position awareness):")
    print("=" * 70)
    print(f"Asset: {decision['asset_pair']}")
    print(f"Action: {decision['action']}")
    print(f"Confidence: {decision['confidence']}%")
    print(f"Reasoning: {decision['reasoning']}")
    print()
    
    if decision.get('position_type'):
        print("Position Details:")
        print(f"  Type: {decision['position_type']}")
        print(f"  Entry Price: ${decision.get('entry_price', 0):.2f}")
        print(f"  Recommended Size: {decision.get('recommended_position_size', 0):.6f}")
        print(f"  Risk: {decision.get('risk_percentage', 1)}%")
        print(f"  Stop Loss: {decision.get('stop_loss_percentage', 2)}%")
        print()
    
    # Show what monitoring context was available
    print("=" * 70)
    print("MONITORING CONTEXT PROVIDED TO AI:")
    print("=" * 70)
    
    if hasattr(engine.trading_platform, 'get_portfolio_breakdown'):
        portfolio = engine.trading_platform.get_portfolio_breakdown()
        
        futures_positions = portfolio.get('futures_positions', [])
        if futures_positions:
            print(f"\nActive Positions: {len(futures_positions)}")
            for pos in futures_positions:
                side = pos.get('side', 'N/A')
                product = pos.get('product_id', 'N/A')
                contracts = pos.get('contracts', 0)
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                
                pnl_sign = '+' if pnl >= 0 else ''
                print(
                    f"  • {side} {product}: {contracts:.2f} contracts "
                    f"@ ${entry:.2f} (current ${current:.2f}) "
                    f"| P&L: {pnl_sign}${pnl:.2f}"
                )
        else:
            print("\nNo active positions currently")
        
        # Show risk metrics
        total_value = portfolio.get('total_value_usd', 0)
        unrealized_pnl = portfolio.get('futures_summary', {}).get('unrealized_pnl', 0)
        
        print("\nAccount Metrics:")
        print(f"  Total Value: ${total_value:,.2f}")
        print(f"  Unrealized P&L: ${unrealized_pnl:,.2f}")
    else:
        print("\nPlatform does not support detailed portfolio breakdown")
    
    print("\nMonitoring Slots:")
    print(f"  Active: {len(trade_monitor.active_trackers)}")
    print(f"  Max: {trade_monitor.MAX_CONCURRENT_TRADES}")
    print(f"  Available: {trade_monitor.MAX_CONCURRENT_TRADES - len(trade_monitor.active_trackers)}")
    
    print("\n" + "=" * 70)
    print("KEY BENEFITS OF MONITORING INTEGRATION:")
    print("=" * 70)
    print("""
1. POSITION AWARENESS
   - AI knows exactly what positions are currently open
   - Won't recommend conflicting trades
   - Considers correlation and diversification

2. RISK MANAGEMENT
   - AI aware of current leverage and exposure
   - Adjusts position sizing based on existing risk
   - Prevents over-concentration in single asset

3. PERFORMANCE LEARNING
   - AI sees recent win/loss patterns
   - Adapts recommendations based on what's working
   - Factors in current P&L when sizing new trades

4. CAPACITY AWARENESS
   - AI knows how many trades are being monitored
   - Won't overwhelm monitoring system capacity
   - Prioritizes quality over quantity

5. REAL-TIME CONTEXT
   - All data is live from actual platform
   - No stale or cached position data
   - Decision reflects current trading state
""")
    
    print("=" * 70)
    print("NEXT STEPS:")
    print("=" * 70)
    print("""
To use monitoring-aware decisions in production:

1. Enable monitoring in config:
   monitoring:
     enable_context_integration: true
     detection_interval: 30
     poll_interval: 30

2. Initialize components:
   engine = FinanceFeedbackEngine(config)
   monitor = TradeMonitor(...)
   engine.enable_monitoring_integration(monitor, metrics_collector)

3. Start monitor (optional - for live tracking):
   monitor.start()

4. Make decisions as usual:
   decision = engine.analyze_asset('BTCUSD')
   # AI automatically gets full position context!

The AI will ALWAYS have position awareness once integration is enabled.
No code changes needed in your decision-making workflow!
""")
    

if __name__ == '__main__':
    try:
        main()
    except FileNotFoundError:
        print("\n⚠️  config/config.local.yaml not found!")
        print("Create it first with your platform credentials.")
        print("See config/examples/ for templates.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
