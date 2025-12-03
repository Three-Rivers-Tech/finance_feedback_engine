#!/usr/bin/env python
"""Simple test script to debug backtesting."""

import logging
logging.basicConfig(level=logging.INFO)

from finance_feedback_engine.backtesting.advanced_backtester import AdvancedBacktester
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider
from finance_feedback_engine.decision_engine.engine import DecisionEngine

# Create simple providers
hist_provider = HistoricalDataProvider("test_key")
config = {
    'decision_engine': {
        'ai_provider': 'local',
    }
}

# Create decision engine with the hist provider as data provider
decision_engine = DecisionEngine(config, data_provider=hist_provider)

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

print(f"Results: {results}")
