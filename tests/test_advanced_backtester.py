import pandas as pd
from datetime import datetime, timezone
import pytest
from finance_feedback_engine.backtesting.advanced_backtester import AdvancedBacktester
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from tests.mocks.mock_data_provider import MockHistoricalDataProvider

@pytest.fixture
def sample_historical_data():
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", end="2023-01-31", freq='D'))
    data = {
        'open': [100 + i for i in range(len(dates))],
        'high': [105 + i for i in range(len(dates))],
        'low': [98 + i for i in range(len(dates))],
        'close': [102 + i for i in range(len(dates))],
        'volume': [1000 + i*10 for i in range(len(dates))],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'timestamp'
    return df

@pytest.fixture
def mock_decision_engine(sample_historical_data):
    config = {
        'decision_engine': {
            'ai_provider': 'local',
            'model_name': 'test_model'
        }
    }
    # This is a mock provider that will be used by the DecisionEngine
    mock_provider = MockHistoricalDataProvider(sample_historical_data)
    engine = DecisionEngine(config, data_provider=mock_provider)
    return engine

def test_advanced_backtester_runs_without_errors(mock_decision_engine, sample_historical_data):
    # The backtester itself uses a mock provider that gives it the full dataset
    backtester_provider = MockHistoricalDataProvider(sample_historical_data)
    backtester = AdvancedBacktester(historical_data_provider=backtester_provider)
    
    results = backtester.run_backtest(
        asset_pair="BTCUSD",
        start_date="2023-01-01",
        end_date="2023-01-31",
        decision_engine=mock_decision_engine
    )

    assert results is not None
    assert "metrics" in results
    assert "trades" in results
    assert results['metrics']['initial_balance'] == 10000.0


def test_advanced_backtester_simple_strategy(sample_historical_data):
    class SimpleDecisionEngine(DecisionEngine):
        def generate_decision(self, asset_pair, market_data, balance, portfolio):
            # The timestamp is the name of the series, which is the index of the row
            timestamp = market_data.name
            if timestamp.day == 1:
                return {'action': 'BUY', 'suggested_amount': 10000}
            elif timestamp.day == 31:
                return {'action': 'SELL'}
            else:
                return {'action': 'HOLD'}

    backtester_provider = MockHistoricalDataProvider(sample_historical_data)
    backtester = AdvancedBacktester(historical_data_provider=backtester_provider)
    
    results = backtester.run_backtest(
        asset_pair="BTCUSD",
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 1, 31),
        decision_engine=SimpleDecisionEngine({}, data_provider=backtester_provider)
    )

    assert results is not None
    assert "metrics" in results
    assert "trades" in results
    assert results['metrics']['initial_balance'] == 10000.0
    assert results['metrics']['total_trades'] == 2
    assert results['metrics']['net_return_pct'] > 0
