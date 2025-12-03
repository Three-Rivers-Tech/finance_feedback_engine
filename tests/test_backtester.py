"""
Comprehensive tests for Backtester functionality.
Covers backtest execution, candle generation, and performance metrics.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock
from finance_feedback_engine.backtesting.backtester import Backtester, Candle


@pytest.fixture
def mock_data_provider():
    """Mock data provider for backtesting."""
    provider = MagicMock()
    provider.get_historical_data.return_value = [
        {'timestamp': '2024-01-01', 'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 102.0},
        {'timestamp': '2024-01-02', 'open': 102.0, 'high': 108.0, 'low': 101.0, 'close': 105.0},
        {'timestamp': '2024-01-03', 'open': 105.0, 'high': 110.0, 'low': 103.0, 'close': 107.0},
        {'timestamp': '2024-01-04', 'open': 107.0, 'high': 109.0, 'low': 104.0, 'close': 106.0},
        {'timestamp': '2024-01-05', 'open': 106.0, 'high': 111.0, 'low': 105.0, 'close': 110.0},
    ]
    return provider


@pytest.fixture
def backtester(mock_data_provider):
    """Create Backtester instance."""
    config = {
        'strategy': {
            'short_window': 2,
            'long_window': 3
        },
        'initial_balance': 10000.0,
        'fee_percentage': 0.1
    }
    return Backtester(data_provider=mock_data_provider, config=config)


class TestBacktesterCore:
    """Test core backtester functionality."""
    
    def test_backtester_initialization(self, backtester, mock_data_provider):
        """Test Backtester initializes correctly."""
        assert backtester.data_provider == mock_data_provider
        assert backtester.default_short == 2
        assert backtester.default_long == 3
        assert backtester.default_initial_balance == 10000.0
        assert backtester.default_fee_pct == 0.1
    
    def test_run_backtest_basic(self, backtester):
        """Test basic backtest execution."""
        # run() is async, so we need to use asyncio.run
        results = asyncio.run(backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05',
            strategy_name='sma_crossover'
        ))
        
        assert isinstance(results, dict)
        # Results have 'metrics' dict with fields like 'net_return_pct', 'total_trades', 'final_balance'
        assert 'metrics' in results
        assert 'net_return_pct' in results['metrics']
        assert 'total_trades' in results['metrics']
        assert 'final_balance' in results['metrics']


class TestBacktesterCandles:
    """Test candle generation and manipulation."""
    
    def test_candle_creation(self):
        """Test Candle dataclass creation."""
        candle = Candle(
            timestamp=datetime(2024, 1, 1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0
        )
        
        assert candle.timestamp == datetime(2024, 1, 1)
        assert candle.open == 100.0
        assert candle.high == 105.0
        assert candle.low == 95.0
        assert candle.close == 102.0


class TestBacktesterMaxDrawdown:
    """Test max drawdown calculation."""
    
    @pytest.mark.asyncio
    async def test_max_drawdown_calculation(self, backtester):
        """Test max drawdown in backtest results."""
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05',
            strategy_name='sma_crossover',
            initial_balance=10000.0
        )
        
        # Max drawdown must be present in results metrics
        assert 'metrics' in results, "metrics should be present in results"
        assert 'max_drawdown_pct' in results['metrics'], "max_drawdown_pct should be in metrics"
        assert isinstance(results['metrics']['max_drawdown_pct'], (int, float))
        assert results['metrics']['max_drawdown_pct'] <= 0, "Drawdown should be negative or zero"
