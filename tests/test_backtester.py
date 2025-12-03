"""
Comprehensive tests for Backtester functionality.
Covers backtest execution, candle generation, and performance metrics.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from finance_feedback_engine.backtesting.backtester import Backtester, Candle, _parse_date


@pytest.fixture
def mock_data_provider():
    """Mock data provider for backtesting."""
    provider = MagicMock()
    # Make get_historical_data async
    async def get_historical_data_async(asset_pair, start, end):
        return [
            {'date': '2024-01-01', 'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 102.0},
            {'date': '2024-01-02', 'open': 102.0, 'high': 108.0, 'low': 101.0, 'close': 105.0},
            {'date': '2024-01-03', 'open': 105.0, 'high': 110.0, 'low': 103.0, 'close': 107.0},
            {'date': '2024-01-04', 'open': 107.0, 'high': 109.0, 'low': 104.0, 'close': 106.0},
            {'date': '2024-01-05', 'open': 106.0, 'high': 111.0, 'low': 105.0, 'close': 110.0},
        ]
    
    # Make get_market_data async
    async def get_market_data_async(asset_pair):
        return {'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 100.0}
    
    provider.get_historical_data = get_historical_data_async
    provider.get_market_data = get_market_data_async
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
        'fee_percentage': 0.1,
        'use_real_data': True
    }
    return Backtester(data_provider=mock_data_provider, config=config)


@pytest.fixture
def backtester_synthetic(mock_data_provider):
    """Create Backtester instance that uses synthetic data."""
    config = {
        'strategy': {
            'short_window': 2,
            'long_window': 3
        },
        'initial_balance': 10000.0,
        'fee_percentage': 0.1,
        'use_real_data': False  # Force synthetic data
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
    
    def test_backtester_initialization_no_config(self, mock_data_provider):
        """Test Backtester initialization without config."""
        backtester = Backtester(data_provider=mock_data_provider)
        assert backtester.config == {}
        assert backtester.default_short == 5
        assert backtester.default_long == 20
        assert backtester.default_initial_balance == 10_000.0
        assert backtester.default_fee_pct == 0.1
    
    @pytest.mark.asyncio
    async def test_run_backtest_basic(self, backtester):
        """Test basic backtest execution."""
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05',
            strategy_name='sma_crossover'
        )
        
        assert isinstance(results, dict)
        assert 'metrics' in results
        assert 'net_return_pct' in results['metrics']
        assert 'total_trades' in results['metrics']
        assert 'final_balance' in results['metrics']
        assert 'asset_pair' in results
        assert results['asset_pair'] == 'BTCUSD'


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
        
        assert 'metrics' in results
        assert 'max_drawdown_pct' in results['metrics']
        assert isinstance(results['metrics']['max_drawdown_pct'], (int, float))
        assert results['metrics']['max_drawdown_pct'] <= 0


class TestBacktesterErrorCases:
    """Test error handling and validation."""
    
    @pytest.mark.asyncio
    async def test_invalid_date_format(self, backtester):
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            await backtester.run(
                asset_pair='BTCUSD',
                start='2024/01/01',  # Wrong format
                end='2024-01-05'
            )
    
    @pytest.mark.asyncio
    async def test_end_before_start(self, backtester):
        """Test that end date before start raises ValueError."""
        with pytest.raises(ValueError, match="End date precedes start date"):
            await backtester.run(
                asset_pair='BTCUSD',
                start='2024-01-05',
                end='2024-01-01'  # End before start
            )
    
    @pytest.mark.asyncio
    async def test_short_window_gte_long_window(self, backtester):
        """Test that short >= long window raises ValueError."""
        with pytest.raises(ValueError, match="short_window must be < long_window"):
            await backtester.run(
                asset_pair='BTCUSD',
                start='2024-01-01',
                end='2024-01-05',
                short_window=10,
                long_window=10  # Equal to short
            )
    
    def test_parse_date_invalid_format(self):
        """Test _parse_date with invalid format."""
        with pytest.raises(ValueError, match="Invalid date format"):
            _parse_date("01-01-2024")


class TestBacktesterInsufficientData:
    """Test handling of insufficient candle data."""
    
    @pytest.mark.asyncio
    async def test_insufficient_candles_for_long_window(self, mock_data_provider):
        """Test backtest with insufficient candles."""
        # Provider returns only 2 candles
        async def get_historical_data_short(asset_pair, start, end):
            return [
                {'date': '2024-01-01', 'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 102.0},
                {'date': '2024-01-02', 'open': 102.0, 'high': 108.0, 'low': 101.0, 'close': 105.0},
            ]
        
        mock_data_provider.get_historical_data = get_historical_data_short
        
        config = {
            'strategy': {'short_window': 2, 'long_window': 10},  # Long window too big
            'use_real_data': True
        }
        backtester = Backtester(data_provider=mock_data_provider, config=config)
        
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-02'
        )
        
        # Should return insufficient_data flag
        assert results['metrics']['insufficient_data'] is True
        assert results['metrics']['total_trades'] == 0
        assert results['metrics']['net_return_pct'] == 0.0


class TestBacktesterSyntheticCandles:
    """Test synthetic candle generation."""
    
    @pytest.mark.asyncio
    async def test_synthetic_candle_generation(self, backtester_synthetic):
        """Test that synthetic candles are generated when real data unavailable."""
        results = await backtester_synthetic.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-10'
        )
        
        # Should have generated candles and run backtest
        assert results['candles_used'] > 0
        assert 'metrics' in results
        assert 'final_balance' in results['metrics']
    
    @pytest.mark.asyncio
    async def test_synthetic_candles_deterministic(self, backtester_synthetic):
        """Test that synthetic candles are deterministic (same seed = same candles)."""
        results1 = await backtester_synthetic.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05'
        )
        
        results2 = await backtester_synthetic.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05'
        )
        
        # Same input should give same output (deterministic)
        assert results1['metrics']['final_balance'] == results2['metrics']['final_balance']


class TestBacktesterParameters:
    """Test parameter overrides."""
    
    @pytest.mark.asyncio
    async def test_override_initial_balance(self, backtester):
        """Test overriding initial balance."""
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05',
            initial_balance=50000.0
        )
        
        assert results['metrics']['starting_balance'] == 50000.0
    
    @pytest.mark.asyncio
    async def test_override_fee_percentage(self, backtester):
        """Test overriding fee percentage."""
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05',
            fee_percentage=0.5
        )
        
        # Verify backtest ran (fees are applied internally)
        assert 'metrics' in results
        assert 'final_balance' in results['metrics']
    
    @pytest.mark.asyncio
    async def test_override_windows(self, backtester):
        """Test overriding short and long windows."""
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05',
            short_window=1,
            long_window=2
        )
        
        assert results['strategy']['short_window'] == 1
        assert results['strategy']['long_window'] == 2


class TestBacktesterProviderErrors:
    """Test handling of data provider errors."""
    
    @pytest.mark.asyncio
    async def test_provider_exception_fallback_to_synthetic(self, mock_data_provider):
        """Test that provider exception triggers synthetic candle generation."""
        # Make provider raise exception
        async def get_historical_data_error(asset_pair, start, end):
            raise Exception("Provider error")
        
        mock_data_provider.get_historical_data = get_historical_data_error
        
        config = {
            'strategy': {'short_window': 2, 'long_window': 3},
            'use_real_data': True
        }
        backtester = Backtester(data_provider=mock_data_provider, config=config)
        
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-10'
        )
        
        # Should fall back to synthetic candles
        assert results['candles_used'] > 0
        assert 'metrics' in results
    
    @pytest.mark.asyncio
    async def test_synthetic_candle_provider_error_fallback(self, mock_data_provider):
        """Test synthetic candle generation when get_market_data fails."""
        # Make get_market_data fail
        async def get_market_data_error(asset_pair):
            raise Exception("API error")
        
        mock_data_provider.get_market_data = get_market_data_error
        
        config = {
            'strategy': {'short_window': 2, 'long_window': 3},
            'use_real_data': False
        }
        backtester = Backtester(data_provider=mock_data_provider, config=config)
        
        results = await backtester.run(
            asset_pair='BTCUSD',
            start='2024-01-01',
            end='2024-01-05'
        )
        
        # Should use fallback price of 100.0
        assert results['candles_used'] > 0
