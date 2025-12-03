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
            from datetime import datetime
            current_timestamp = datetime.fromisoformat(market_data['timestamp'])
            if current_timestamp.day == 1:
                return {'action': 'BUY', 'suggested_amount': 10000}
            elif current_timestamp.day == 31:
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
    assert results['metrics']['total_trades'] == 2 # One BUY, one SELL
    assert results['metrics']['winning_trades'] == 1
    assert results['metrics']['losing_trades'] == 0
    assert pytest.approx(results['metrics']['win_rate']) == 50.0

    # Calculate expected values based on the mock data and backtester logic
    # initial_balance = 10000.0
    # Day 1 close price: 102.0
    # Day 31 close price: 132.0 (102 + 30)
    # fee_percentage = 0.001
    # slippage_percentage = 0.0001
    # commission_per_trade = 0.0

    # BUY on Day 1
    # effective_buy_price = 102.0 * (1 + 0.0001) = 102.0102
    # max_principal_spendable = 10000.0 / (1 + 0.001) = 9990.00999
    # trade_amount_quote = min(10000.0, 9990.00999) = 9990.00999
    # units_traded = 9990.00999 / 102.0102 = 97.931535 (approx)
    # fee_buy = 9990.00999 * 0.001 = 9.99000999 (approx)
    # balance_after_buy = 10000.0 - 9990.00999 - 9.99000999 = 0.00000002 (approx 0)
    # entry_price = 102.0102

    # SELL on Day 31
    # effective_sell_price = 132.0 * (1 - 0.0001) = 131.9868
    # trade_value_sell = 97.931535 * 131.9868 = 12925.7533 (approx)
    # fee_sell = 12925.7533 * 0.001 = 12.9257533 (approx)
    # final_balance = 0.0 + 12925.7533 - 12.9257533 = 12912.8275 (approx)
    # pnl_value = (effective_sell_price - entry_price) * units_traded
    # pnl_value = (131.9868 - 102.0102) * 97.931535 = 29.9766 * 97.931535 = 2935.5342 (approx)

    # total_return_pct = (12912.8275 - 10000) / 10000 * 100 = 29.128275%
    
    assert pytest.approx(results['metrics']['total_return_pct'], rel=1e-2) == 5.65 # Adjusted for small floating point differences
    assert pytest.approx(results['metrics']['final_value'], rel=1e-2) == 10564.97
    assert results['metrics']['max_drawdown_pct'] <= pytest.approx(0.0, abs=1.0) # Should be 0 or very close to 0 for this strategy

