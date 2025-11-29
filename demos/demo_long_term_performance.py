#!/usr/bin/env python3
"""
Demo: Long-term Performance Integration

This demonstrates how portfolio long-term performance (90-day metrics)
is now automatically included in AI decision-making context.
"""

import json
from pathlib import Path

# Mock the decision context to show what the AI sees
def demonstrate_ai_context():
    """Show what the AI model receives with long-term performance data."""
    
    print("\n" + "=" * 70)
    print("DEMONSTRATION: Long-Term Performance in AI Context")
    print("=" * 70)
    
    # Load the test context we generated
    context_file = Path("data/test_memory/test_context_output.json")
    
    if not context_file.exists():
        print("\n❌ Test context not found. Run test_long_term_performance.py first.")
        return
    
    with open(context_file) as f:
        context = json.load(f)
    
    # Simulate what the DecisionEngine._format_memory_context() produces
    print("\n📝 AI PROMPT SECTION - Portfolio Memory Context")
    print("-" * 70)
    
    long_term = context.get('long_term_performance', {})
    
    if long_term and long_term.get('has_data'):
        period_days = long_term.get('period_days', 90)
        
        prompt_text = f"""
============================================================
PORTFOLIO MEMORY & LEARNING CONTEXT
============================================================
Historical Trades: {context.get('total_historical_trades', 0)}
Recent Trades Analyzed: {context.get('recent_trades_analyzed', 0)}

LONG-TERM PERFORMANCE ({period_days} days):
------------------------------------------------------------
  Total Realized P&L: ${long_term.get('realized_pnl', 0):.2f}
  Total Trades: {long_term.get('total_trades', 0)}
  Win Rate: {long_term.get('win_rate', 0):.1f}%
  Profit Factor: {long_term.get('profit_factor', 0):.2f}
  ROI: {long_term.get('roi_percentage', 0):.1f}%

  Average Win: ${long_term.get('avg_win', 0):.2f}
  Average Loss: ${long_term.get('avg_loss', 0):.2f}
  Best Trade: ${long_term.get('best_trade', 0):.2f}
  Worst Trade: ${long_term.get('worst_trade', 0):.2f}

  Recent Momentum: {long_term.get('recent_momentum', 'N/A')}
"""
        if long_term.get('sharpe_ratio'):
            prompt_text += f"  Sharpe Ratio: {long_term['sharpe_ratio']:.2f}\n"
        
        if long_term.get('average_holding_hours'):
            prompt_text += f"  Average Holding Period: {long_term['average_holding_hours']:.1f} hours\n"
        
        prompt_text += f"""
Recent Performance:
  Win Rate: {context['recent_performance']['win_rate']:.1f}%
  Total P&L: ${context['recent_performance']['total_pnl']:.2f}
  Wins: {context['recent_performance']['winning_trades']}, Losses: {context['recent_performance']['losing_trades']}
  Current Streak: {context['current_streak']['count']} {context['current_streak']['type']} trades

============================================================

PERFORMANCE GUIDANCE FOR DECISION:
"""
        
        # Add conditional guidance based on performance
        lt_pnl = long_term.get('realized_pnl', 0)
        lt_win_rate = long_term.get('win_rate', 50)
        momentum = long_term.get('recent_momentum', 'stable')
        
        if lt_pnl < 0 and lt_win_rate < 45:
            prompt_text += """⚠ CAUTION: Long-term performance is negative. Consider being more conservative.
"""
        elif lt_pnl > 0 and lt_win_rate > 60:
            prompt_text += """✓ Long-term performance is strong. Current strategy is working well.
"""
        
        if momentum == 'declining':
            prompt_text += """⚠ Performance momentum is DECLINING. Recent trades performing worse than earlier ones.
"""
        elif momentum == 'improving':
            prompt_text += """✓ Performance momentum is IMPROVING. Recent trades performing better.
"""
        
        prompt_text += """
IMPORTANT: Consider this historical performance when making your recommendation.
If recent performance is poor, consider being more conservative.
If specific actions (BUY/SELL) have performed poorly, factor that into your decision.
"""
        
        print(prompt_text)
    else:
        print("\n❌ No long-term performance data available")
    
    print("\n" + "=" * 70)
    print("KEY FEATURES")
    print("=" * 70)
    print("""
✅ AUTOMATICALLY INCLUDED IN EVERY DECISION:

1. **Long-term P&L**: 90-day realized profit/loss
   - Helps AI understand overall portfolio health
   
2. **Win Rate**: Success rate over extended period
   - More reliable than recent trades alone
   
3. **Profit Factor**: Ratio of wins to losses
   - Shows risk/reward effectiveness
   
4. **ROI Percentage**: Return on investment
   - Contextualizes performance relative to capital
   
5. **Momentum Indicator**: Improving/Declining/Stable
   - Shows recent trend direction
   
6. **Sharpe Ratio**: Risk-adjusted returns
   - Professional metric for performance quality

CONFIGURABLE:
- Default: 90 days (adjustable via long_term_days parameter)
- Can filter by specific asset pair
- Includes performance-based warnings for AI
""")
    
    print("\n" + "=" * 70)
    print("USAGE IN YOUR CODE")
    print("=" * 70)
    print("""
The long-term performance is now AUTOMATICALLY included when you call:

```python
from finance_feedback_engine import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(config_path="config/config.yaml")

# The analyze_asset call now automatically includes 90-day performance
decision = engine.analyze_asset("BTCUSD")

# The AI sees all the long-term metrics shown above!
```

To customize the lookback period, you can configure it in the 
PortfolioMemoryEngine:

```python
# In config.yaml:
portfolio_memory:
  context_window: 20  # Recent trades
  # Add this:
  long_term_days: 120  # Use 120 days instead of 90
```

Or programmatically:

```python
memory_context = portfolio_memory.generate_context(
    asset_pair="BTCUSD",
    include_long_term=True,
    long_term_days=60  # Custom period
)
```
""")


if __name__ == "__main__":
    demonstrate_ai_context()
    
    print("\n✅ IMPLEMENTATION COMPLETE!")
    print("\nYour AI models now have access to:")
    print("  • 90-day realized P&L")
    print("  • Long-term win rate")
    print("  • Profit factor & ROI")
    print("  • Performance momentum")
    print("  • Risk-adjusted returns (Sharpe ratio)")
    print("\nThis provides much better context than just recent trades! 🚀\n")
