#!/usr/bin/env python3
"""
Demo: Portfolio Memory Engine with Reinforcement Learning

This script demonstrates the Portfolio Memory Engine capabilities:
1. Recording trade outcomes with P&L
2. Analyzing performance metrics
3. Generating context for AI decisions
4. Getting provider recommendations
5. Market regime tracking
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demo_memory_engine():
    """Demonstrate Portfolio Memory Engine features."""
    from finance_feedback_engine.memory.portfolio_memory import (
        PortfolioMemoryEngine,
        TradeOutcome
    )
    
    print_section("PORTFOLIO MEMORY ENGINE DEMO")
    
    # Configuration
    config = {
        'persistence': {
            'storage_path': 'data/demo_memory'
        },
        'portfolio_memory': {
            'enabled': True,
            'max_memory_size': 100,
            'learning_rate': 0.1,
            'context_window': 10
        }
    }
    
    # Initialize memory engine
    print("Initializing Portfolio Memory Engine...")
    memory_engine = PortfolioMemoryEngine(config)
    print(f"✓ Memory engine initialized")
    print(f"  Storage path: {memory_engine.storage_path}")
    print(f"  Max memory: {memory_engine.max_memory_size}")
    print(f"  Context window: {memory_engine.context_window}")
    
    # ========================================================================
    # SECTION 1: Record Sample Trade Outcomes
    # ========================================================================
    print_section("1. RECORDING TRADE OUTCOMES")
    
    # Create sample decisions (simulating historical trades)
    sample_trades = [
        {
            'id': 'trade-001',
            'asset_pair': 'BTCUSD',
            'action': 'BUY',
            'timestamp': (datetime.utcnow() - timedelta(days=10)).isoformat(),
            'entry_price': 50000,
            'recommended_position_size': 0.1,
            'ai_provider': 'local',
            'confidence': 75,
            'market_data': {
                'close': 50000,
                'sentiment': {'overall_sentiment': 'Bullish'},
                'technical': {'price_trend': 'bullish', 'volatility': 5.0}
            }
        },
        {
            'id': 'trade-002',
            'asset_pair': 'BTCUSD',
            'action': 'BUY',
            'timestamp': (datetime.utcnow() - timedelta(days=9)).isoformat(),
            'entry_price': 51000,
            'recommended_position_size': 0.08,
            'ai_provider': 'cli',
            'confidence': 60,
            'market_data': {
                'close': 51000,
                'sentiment': {'overall_sentiment': 'Neutral'},
                'technical': {'price_trend': 'neutral', 'volatility': 3.0}
            }
        },
        {
            'id': 'trade-003',
            'asset_pair': 'BTCUSD',
            'action': 'SELL',
            'timestamp': (datetime.utcnow() - timedelta(days=8)).isoformat(),
            'entry_price': 52000,
            'recommended_position_size': 0.12,
            'ai_provider': 'ensemble',
            'ensemble_metadata': {
                'providers_used': ['local', 'cli', 'codex'],
                'voting_power': {'local': 0.4, 'cli': 0.3, 'codex': 0.3}
            },
            'confidence': 85,
            'market_data': {
                'close': 52000,
                'sentiment': {'overall_sentiment': 'Bearish'},
                'technical': {'price_trend': 'bearish', 'volatility': 8.0}
            }
        },
        {
            'id': 'trade-004',
            'asset_pair': 'ETHUSD',
            'action': 'BUY',
            'timestamp': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            'entry_price': 3000,
            'recommended_position_size': 2.0,
            'ai_provider': 'local',
            'confidence': 70,
            'market_data': {
                'close': 3000,
                'sentiment': {'overall_sentiment': 'Bullish'},
                'technical': {'price_trend': 'bullish', 'volatility': 6.0}
            }
        },
        {
            'id': 'trade-005',
            'asset_pair': 'BTCUSD',
            'action': 'BUY',
            'timestamp': (datetime.utcnow() - timedelta(days=6)).isoformat(),
            'entry_price': 49000,
            'recommended_position_size': 0.15,
            'ai_provider': 'cli',
            'confidence': 80,
            'market_data': {
                'close': 49000,
                'sentiment': {'overall_sentiment': 'Bullish'},
                'technical': {'price_trend': 'bullish', 'volatility': 4.0}
            }
        }
    ]
    
    # Simulate outcomes (profitable and unprofitable)
    outcomes_data = [
        {'exit_price': 52000, 'hit_tp': True},   # +2000 profit
        {'exit_price': 50500, 'hit_tp': False},  # -500 loss
        {'exit_price': 50000, 'hit_tp': True},   # +2000 profit (SHORT)
        {'exit_price': 3200, 'hit_tp': True},    # +200 profit (ETH)
        {'exit_price': 51000, 'hit_tp': True},   # +2000 profit
    ]
    
    print(f"Recording {len(sample_trades)} sample trade outcomes...\n")
    
    for i, (trade, outcome_data) in enumerate(zip(sample_trades, outcomes_data), 1):
        outcome = memory_engine.record_trade_outcome(
            decision=trade,
            exit_price=outcome_data['exit_price'],
            exit_timestamp=(
                datetime.fromisoformat(trade['timestamp']) + timedelta(hours=24)
            ).isoformat(),
            hit_take_profit=outcome_data['hit_tp']
        )
        
        profit_marker = "✓" if outcome.was_profitable else "✗"
        print(
            f"{profit_marker} Trade {i}: {outcome.asset_pair} {outcome.action} "
            f"→ ${outcome.realized_pnl:+.2f} ({outcome.pnl_percentage:+.2f}%)"
        )
    
    # ========================================================================
    # SECTION 2: Performance Analysis
    # ========================================================================
    print_section("2. PERFORMANCE ANALYSIS")
    
    print("Analyzing overall performance...\n")
    snapshot = memory_engine.analyze_performance()
    
    print("📊 PERFORMANCE METRICS")
    print(f"{'Metric':<25} {'Value':>15}")
    print("-" * 42)
    print(f"{'Total Trades':<25} {snapshot.total_trades:>15}")
    print(f"{'Winning Trades':<25} {snapshot.winning_trades:>15}")
    print(f"{'Losing Trades':<25} {snapshot.losing_trades:>15}")
    print(f"{'Win Rate':<25} {snapshot.win_rate:>14.1f}%")
    print(f"{'Total P&L':<25} ${snapshot.total_pnl:>14.2f}")
    print(f"{'Average Win':<25} ${snapshot.avg_win:>14.2f}")
    print(f"{'Average Loss':<25} ${snapshot.avg_loss:>14.2f}")
    print(f"{'Profit Factor':<25} {snapshot.profit_factor:>15.2f}")
    print(f"{'Max Drawdown':<25} {snapshot.max_drawdown:>14.2f}%")
    
    if snapshot.sharpe_ratio:
        print(f"{'Sharpe Ratio':<25} {snapshot.sharpe_ratio:>15.2f}")
    if snapshot.sortino_ratio:
        print(f"{'Sortino Ratio':<25} {snapshot.sortino_ratio:>15.2f}")
    
    # Provider performance
    if snapshot.provider_stats:
        print("\n\n🤖 PROVIDER PERFORMANCE")
        print(f"{'Provider':<15} {'Trades':>8} {'Win Rate':>10} {'Total P&L':>12}")
        print("-" * 50)
        for provider, stats in snapshot.provider_stats.items():
            print(
                f"{provider:<15} {stats['total_trades']:>8} "
                f"{stats['win_rate']:>9.1f}% ${stats['total_pnl']:>11.2f}"
            )
    
    # Regime performance
    if snapshot.regime_performance:
        print("\n\n🌍 MARKET REGIME PERFORMANCE")
        print(f"{'Regime':<20} {'Trades':>8} {'Win Rate':>10} {'Total P&L':>12}")
        print("-" * 55)
        for regime, stats in snapshot.regime_performance.items():
            print(
                f"{regime:<20} {stats['total_trades']:>8} "
                f"{stats['win_rate']:>9.1f}% ${stats['total_pnl']:>11.2f}"
            )
    
    # ========================================================================
    # SECTION 3: Context Generation
    # ========================================================================
    print_section("3. CONTEXT GENERATION FOR AI DECISIONS")
    
    print("Generating memory context for BTCUSD...\n")
    context = memory_engine.generate_context(asset_pair='BTCUSD')
    
    # Format for display
    formatted_context = memory_engine.format_context_for_prompt(context)
    print(formatted_context)
    
    # ========================================================================
    # SECTION 4: Provider Recommendations
    # ========================================================================
    print_section("4. PROVIDER WEIGHT RECOMMENDATIONS")
    
    print("Analyzing provider performance for weight recommendations...\n")
    recommendations = memory_engine.get_provider_recommendations()
    
    print(f"Recommendation Confidence: {recommendations['confidence'].upper()}")
    print()
    
    print("📈 RECOMMENDED PROVIDER WEIGHTS")
    print(f"{'Provider':<15} {'Recommended':>12} {'Current Win Rate':>18} {'Sample Size':>13}")
    print("-" * 62)
    
    for provider, weight in recommendations['recommended_weights'].items():
        stats = recommendations['provider_stats'].get(provider, {})
        sample_size = recommendations['sample_sizes'].get(provider, 0)
        win_rate = stats.get('win_rate', 0)
        
        print(
            f"{provider:<15} {weight:>11.1%} "
            f"{win_rate:>17.1f}% {sample_size:>13}"
        )
    
    # Detailed provider stats
    print("\n\n🎯 CONFIDENCE CALIBRATION BY PROVIDER")
    for provider, stats in recommendations['provider_stats'].items():
        print(f"\n{provider.upper()}:")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Overall Win Rate: {stats['win_rate']:.1f}%")
        print(f"  Avg P&L per Trade: ${stats['avg_pnl_per_trade']:.2f}")
        
        if 'high_confidence_winrate' in stats:
            print(f"  High Confidence (>70%): {stats['high_confidence_winrate']:.1f}% win rate")
            print(f"  Med Confidence (40-70%): {stats['medium_confidence_winrate']:.1f}% win rate")
            print(f"  Low Confidence (<40%): {stats['low_confidence_winrate']:.1f}% win rate")
    
    # ========================================================================
    # SECTION 5: Memory Summary
    # ========================================================================
    print_section("5. MEMORY ENGINE SUMMARY")
    
    summary = memory_engine.get_summary()
    
    print("📝 MEMORY ENGINE STATE")
    print(f"{'Metric':<30} {'Value':>20}")
    print("-" * 52)
    print(f"{'Total Outcomes':<30} {summary['total_outcomes']:>20}")
    print(f"{'Total Experiences':<30} {summary['total_experiences']:>20}")
    print(f"{'Total Snapshots':<30} {summary['total_snapshots']:>20}")
    print(f"{'Providers Tracked':<30} {summary['providers_tracked']:>20}")
    print(f"{'Regimes Tracked':<30} {summary['regimes_tracked']:>20}")
    print(f"{'Storage Path':<30} {summary['storage_path']:>20}")
    print(f"{'Max Memory Size':<30} {summary['max_memory_size']:>20}")
    print(f"{'Learning Rate':<30} {summary['learning_rate']:>20}")
    print(f"{'Context Window':<30} {summary['context_window']:>20}")
    
    # Save memory
    print("\n\nSaving memory to disk...")
    memory_engine.save_memory()
    print("✓ Memory saved successfully")
    
    # ========================================================================
    # SECTION 6: Integration Example
    # ========================================================================
    print_section("6. INTEGRATION WITH DECISION ENGINE")
    
    print("Example: How memory context informs new decisions\n")
    
    # Generate context for a new BTCUSD decision
    new_context = memory_engine.generate_context(asset_pair='BTCUSD')
    
    print("When analyzing BTCUSD, the AI will receive:")
    print(f"  • Historical trades: {new_context['total_historical_trades']}")
    print(f"  • Recent win rate: {new_context['recent_performance']['win_rate']:.1f}%")
    print(f"  • Recent P&L: ${new_context['recent_performance']['total_pnl']:.2f}")
    
    if 'asset_specific' in new_context:
        asset_stats = new_context['asset_specific']
        print(f"  • BTCUSD-specific win rate: {asset_stats['win_rate']:.1f}%")
        print(f"  • BTCUSD-specific P&L: ${asset_stats['total_pnl']:.2f}")
    
    if new_context.get('current_streak'):
        streak = new_context['current_streak']
        print(f"  • Current streak: {streak['count']} {streak['type']} trades")
    
    print("\n💡 This context helps the AI make more informed decisions:")
    print("   - Adjust confidence based on recent performance")
    print("   - Consider asset-specific historical success rate")
    print("   - Factor in current winning/losing streaks")
    print("   - Learn from past mistakes")
    
    # ========================================================================
    # DEMO COMPLETE
    # ========================================================================
    print_section("DEMO COMPLETE")
    
    print("✓ Portfolio Memory Engine demo completed successfully!")
    print()
    print("Next steps:")
    print("  1. Integrate with FinanceFeedbackEngine")
    print("  2. Enable in config: portfolio_memory.enabled = True")
    print("  3. Record real trade outcomes after execution")
    print("  4. Use get_provider_recommendations() to adapt weights")
    print("  5. Review performance snapshots periodically")
    print()
    print(f"Demo data saved to: {memory_engine.storage_path}")
    print()


if __name__ == '__main__':
    try:
        demo_memory_engine()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise
