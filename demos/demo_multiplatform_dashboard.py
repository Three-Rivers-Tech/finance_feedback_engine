#!/usr/bin/env python3
"""
Multi-platform portfolio dashboard example.

Shows how the dashboard aggregates data from multiple trading platforms
(Coinbase, Oanda, etc.) into a unified view.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.trading_platforms import BaseTradingPlatform
from finance_feedback_engine.dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard
)


class SimulatedCoinbasePlatform(BaseTradingPlatform):
    """Simulated Coinbase platform with crypto holdings."""

    def __init__(self, credentials):
        super().__init__(credentials)

    def get_balance(self):
        return {"CASH_USD": 5000.0}

    def execute_trade(self, decision):
        return {"success": True, "message": "simulated"}

    def get_account_info(self):
        return {"platform": "coinbase_simulated"}

    def get_portfolio_breakdown(self):
        return {
            'total_value_usd': 45000.00,
            'num_assets': 2,
            'holdings': [
                {
                    'asset': 'BTC',
                    'amount': 0.75,
                    'value_usd': 30000.00,
                    'allocation_pct': 66.67
                },
                {
                    'asset': 'ETH',
                    'amount': 5.0,
                    'value_usd': 15000.00,
                    'allocation_pct': 33.33
                }
            ]
        }


class SimulatedOandaPlatform(BaseTradingPlatform):
    """Simulated Oanda platform with forex positions."""

    def __init__(self, credentials):
        super().__init__(credentials)

    def get_balance(self):
        return {"USD": 10000.0}

    def execute_trade(self, decision):
        return {"success": True, "message": "simulated"}

    def get_account_info(self):
        return {"platform": "oanda_simulated"}

    def get_portfolio_breakdown(self):
        return {
            'total_value_usd': 12500.00,
            'num_assets': 3,
            'holdings': [
                {
                    'asset': 'EUR_USD',
                    'amount': 100000.0,  # 100k units
                    'value_usd': 7500.00,
                    'allocation_pct': 60.0
                },
                {
                    'asset': 'GBP_USD',
                    'amount': 50000.0,
                    'value_usd': 3000.00,
                    'allocation_pct': 24.0
                },
                {
                    'asset': 'USD',
                    'amount': 2000.00,
                    'value_usd': 2000.00,
                    'allocation_pct': 16.0
                }
            ]
        }


def main():
    """Demo multi-platform portfolio aggregation."""
    print("=" * 80)
    print("Multi-Platform Portfolio Dashboard Demo")
    print("=" * 80)
    print()
    print("This demo shows how the dashboard aggregates portfolio data from")
    print("multiple trading platforms (Coinbase for crypto, Oanda for forex)")
    print("into a unified view.")
    print()

    # Create simulated platforms
    coinbase = SimulatedCoinbasePlatform({})
    oanda = SimulatedOandaPlatform({})

    # Aggregate across both platforms
    platforms = [coinbase, oanda]
    aggregator = PortfolioDashboardAggregator(platforms)
    aggregated_data = aggregator.aggregate()

    # Display unified dashboard
    display_portfolio_dashboard(aggregated_data)

    # Show summary
    print()
    print("=" * 80)
    print("Summary:")
    print("  Coinbase (Crypto):  $45,000.00 (2 assets)")
    print("  Oanda (Forex):      $12,500.00 (3 assets)")
    print(f"  {'─' * 76}")
    print("  Total:              $57,500.00 (5 assets)")
    print()
    print("The dashboard automatically aggregates portfolio metrics from each")
    print("platform, giving you a complete view of your holdings across")
    print("different asset classes and trading platforms.")
    print("=" * 80)


if __name__ == '__main__':
    main()
