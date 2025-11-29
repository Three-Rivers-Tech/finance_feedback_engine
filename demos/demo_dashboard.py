#!/usr/bin/env python3
"""Demo script showing the portfolio dashboard feature."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard
)

def main():
    """Run dashboard demo with mock platform."""
    # Simple mock config
    config = {
        'alpha_vantage_api_key': 'demo',
        'trading_platform': 'mock',
        'platform_credentials': {},
        'decision_engine': {
            'ai_provider': 'local',
            'model_name': 'default',
            'decision_threshold': 0.7
        },
        'persistence': {
            'storage_path': 'data/decisions',
            'max_decisions': 1000
        }
    }
    
    print("=" * 80)
    print("Portfolio Dashboard Demo")
    print("=" * 80)
    print()
    
    # Initialize engine with mock platform
    engine = FinanceFeedbackEngine(config)
    
    # Aggregate portfolio data
    # In a real multi-platform setup, you'd pass multiple platform instances
    platforms = [engine.trading_platform]
    aggregator = PortfolioDashboardAggregator(platforms)
    aggregated_data = aggregator.aggregate()
    
    # Display the dashboard
    display_portfolio_dashboard(aggregated_data)
    
    print()
    print("=" * 80)
    print("Dashboard Features:")
    print("  - Aggregates portfolio metrics from multiple trading platforms")
    print("  - Shows total value, asset count, and per-platform breakdown")
    print("  - Displays holdings with amount, USD value, and allocation %")
    print("  - Extensible for future metrics (risk, PnL, performance, etc.)")
    print()
    print("Usage:")
    print("  CLI: python main.py dashboard")
    print("  Interactive: python main.py --interactive")
    print("               > dashboard")
    print("=" * 80)

if __name__ == '__main__':
    main()
