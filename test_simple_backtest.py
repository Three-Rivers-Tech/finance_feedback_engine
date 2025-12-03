#!/usr/bin/env python
"""Test backtesting with a mock decision engine that doesn't hang."""

import logging
logging.basicConfig(level=logging.WARNING)

from finance_feedback_engine.backtesting.advanced_backtester import AdvancedBacktester
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider

# Create a simple mock decision engine
class MockDecisionEngine:
    def generate_decision(self, asset_pair, market_data, balance, portfolio):
        """Always return HOLD to test the backtest loop."""
        return {'action': 'HOLD'}

# Create providers
hist_provider = HistoricalDataProvider("test_key")
decision_engine = MockDecisionEngine()

# Create backtester
backtester = AdvancedBacktester(
    historical_data_provider=hist_provider,
    initial_balance=10000.0
)

print("Starting backtest...")
results = backtester.run_backtest(
    asset_pair="BTCUSD",
    start_date="2024-01-01",
    end_date="2024-01-10",
    decision_engine=decision_engine
)

print(f"\n=== BACKTEST RESULTS ===")
print(f"Initial Balance: ${results['metrics']['initial_balance']:.2f}")
print(f"Final Value: ${results['metrics']['final_value']:.2f}")
print(f"Total Return: {results['metrics']['total_return_pct']:.2f}%")
print(f"Total Trades: {results['metrics']['total_trades']}")
print(f"✅ Backtest completed successfully!")
