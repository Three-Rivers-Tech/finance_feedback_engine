import pandas as pd
from datetime import datetime, timezone
import pytest
import logging
from finance_feedback_engine.backtesting.advanced_backtester import AdvancedBacktester
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from tests.mocks.mock_data_provider import MockHistoricalDataProvider

# Configure logging for debugging
logger = logging.getLogger(__name__)
@pytest.fixture
def sample_historical_data():
    logger.info("Creating sample_historical_data fixture")
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", end="2023-01-31", freq='D'), utc=True)
    data = {
        'open': [100 + i for i in range(len(dates))],
        'high': [105 + i for i in range(len(dates))],
        'low': [98 + i for i in range(len(dates))],
        'close': [102 + i for i in range(len(dates))],
        'volume': [1000 + i*10 for i in range(len(dates))],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = 'timestamp'
    logger.info(f"Created sample data with {len(df)} rows")
    return df

@pytest.fixture
def mock_decision_engine(sample_historical_data):
    logger.info("Creating mock_decision_engine fixture")
    config = {
        'decision_engine': {
            'ai_provider': 'mock',  # Changed from 'local' to 'mock' to avoid Ollama hanging
            'model_name': 'test_model'
        }
    }
    # This is a mock provider that will be used by the DecisionEngine
    mock_provider = MockHistoricalDataProvider(sample_historical_data)
    logger.info("Initializing DecisionEngine with mock provider")
    engine = DecisionEngine(config, data_provider=mock_provider)
    logger.info("DecisionEngine initialized successfully")
    return engine

def test_advanced_backtester_runs_without_errors(mock_decision_engine, sample_historical_data, caplog):
    caplog.set_level(logging.DEBUG)
    logger.info("="*80)

    # The backtester itself uses a mock provider that gives it the full dataset
    logger.info("Creating backtester_provider")
    backtester_provider = MockHistoricalDataProvider(sample_historical_data)
    logger.info("Initializing AdvancedBacktester")
    backtester = AdvancedBacktester(historical_data_provider=backtester_provider)

    logger.info("Starting backtest run")
    results = backtester.run_backtest(
        asset_pair="BTCUSD",
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2023, 1, 31, tzinfo=timezone.utc),
        decision_engine=mock_decision_engine
    )
    logger.info("Backtest run completed")

    assert results is not None
    assert "metrics" in results
    assert "trades" in results
    assert results['metrics']['initial_balance'] == 10000.0
    logger.info("TEST: test_advanced_backtester_runs_without_errors PASSED")
    logger.info("="*80)
def test_advanced_backtester_simple_strategy(sample_historical_data, caplog):
    caplog.set_level(logging.DEBUG)

    class SimpleDecisionEngine(DecisionEngine):
        def generate_decision(self, asset_pair, market_data, balance, portfolio, monitoring_context=None):
            from datetime import datetime
            logger.debug(f"SimpleDecisionEngine.generate_decision called for {market_data.get('timestamp')}")
            current_timestamp = datetime.fromisoformat(market_data['timestamp'].replace('Z', '+00:00'))
            if current_timestamp.day == 1:
                logger.info(f"Day {current_timestamp.day}: Returning BUY")
                return {'action': 'BUY', 'suggested_amount': 10000}
            elif current_timestamp.day == 31:
                logger.info(f"Day {current_timestamp.day}: Returning SELL")
                return {'action': 'SELL'}
            else:
                logger.debug(f"Day {current_timestamp.day}: Returning HOLD")
                return {'action': 'HOLD'}

    logger.info("Creating backtester_provider for simple strategy test")
    backtester_provider = MockHistoricalDataProvider(sample_historical_data)
    logger.info("Initializing AdvancedBacktester for simple strategy test")
    backtester = AdvancedBacktester(historical_data_provider=backtester_provider)

    logger.info("Creating SimpleDecisionEngine")
    simple_engine = SimpleDecisionEngine({}, data_provider=backtester_provider)
    logger.info("Starting backtest run with simple strategy")
    results = backtester.run_backtest(
        asset_pair="BTCUSD",
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2023, 1, 31, tzinfo=timezone.utc),
        decision_engine=simple_engine
    )
    logger.info("Backtest run completed for simple strategy")

    assert results is not None
    assert "metrics" in results
    assert "trades" in results
    assert results['metrics']['initial_balance'] == 10000.0
    assert results['metrics']['total_trades'] == 2 # One BUY, one SELL
    assert results['metrics']['winning_trades'] == 1
    assert results['metrics']['losing_trades'] == 0
    assert pytest.approx(results['metrics']['win_rate']) == 50.0

    logger.info(f"Metrics: {results['metrics']}")
    assert pytest.approx(results['metrics']['total_return_pct'], rel=1e-2) == 29.13
    assert pytest.approx(results['metrics']['final_value'], rel=1e-2) == 12912.83
    assert results['metrics']['max_drawdown_pct'] <= 0.0
    logger.info("TEST: test_advanced_backtester_simple_strategy PASSED")
    logger.info("="*80)