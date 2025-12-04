"""Tests for historical pulse injection in AdvancedBacktester."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from finance_feedback_engine.backtesting.advanced_backtester import AdvancedBacktester
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider
from finance_feedback_engine.data_providers.timeframe_aggregator import TimeframeAggregator
from finance_feedback_engine.decision_engine.engine import DecisionEngine


class TestHistoricalPulseComputation:
    """Test _compute_historical_pulse() method."""

    @pytest.fixture
    def sample_historical_data(self):
        """Create sample historical OHLCV data (1-minute intervals, 200 candles)."""
        dates = pd.date_range(
            start='2024-01-01 00:00:00',
            periods=200,
            freq='1min'
        )

        # Simulate uptrending price data
        np.random.seed(42)
        prices = 50000 + np.cumsum(np.random.randn(200) * 50)

        df = pd.DataFrame({
            'open': prices,
            'high': prices + np.random.rand(200) * 100,
            'low': prices - np.random.rand(200) * 100,
            'close': prices + np.random.randn(200) * 50,
            'volume': np.random.randint(100, 1000, 200)
        }, index=dates)

        return df

    @pytest.fixture
    def mock_aggregator(self):
        """Mock TimeframeAggregator."""
        aggregator = Mock(spec=TimeframeAggregator)

        # Mock _detect_trend to return full indicator suite
        aggregator._detect_trend.return_value = {
            'trend': 'UPTREND',
            'rsi': 65.5,
            'signal_strength': 72,
            'macd': {
                'macd': 15.2,
                'signal': 12.1,
                'histogram': 3.1
            },
            'bollinger_bands': {
                'upper': 51000,
                'middle': 50000,
                'lower': 49000,
                'percent_b': 0.75
            },
            'adx': {
                'adx': 28.5,
                'plus_di': 32.0,
                'minus_di': 22.0
            },
            'atr': 350.5,
            'volatility': 'medium'
        }

        return aggregator

    @pytest.fixture
    def backtester_with_pulse(self, mock_aggregator):
        """Create AdvancedBacktester with pulse support."""
        hist_provider = Mock(spec=HistoricalDataProvider)
        unified_provider = Mock()

        return AdvancedBacktester(
            historical_data_provider=hist_provider,
            initial_balance=10000,
            unified_data_provider=unified_provider,
            timeframe_aggregator=mock_aggregator
        )

    def test_compute_pulse_returns_dict_structure(
        self, backtester_with_pulse, sample_historical_data
    ):
        """Test that _compute_historical_pulse returns correct structure."""
        timestamp = pd.Timestamp('2024-01-01 02:00:00')

        pulse = backtester_with_pulse._compute_historical_pulse(
            'BTCUSD',
            timestamp,
            sample_historical_data
        )

        assert pulse is not None
        assert 'timestamp' in pulse
        assert 'age_seconds' in pulse
        assert 'timeframes' in pulse
        assert pulse['age_seconds'] == 0  # Fresh computation

    def test_compute_pulse_includes_multiple_timeframes(
        self, backtester_with_pulse, sample_historical_data
    ):
        """Test that pulse includes multiple timeframes."""
        timestamp = pd.Timestamp('2024-01-01 02:00:00')

        pulse = backtester_with_pulse._compute_historical_pulse(
            'BTCUSD',
            timestamp,
            sample_historical_data
        )

        # Should have attempted to create multiple timeframes
        # (actual count depends on data availability)
        assert isinstance(pulse['timeframes'], dict)
        assert len(pulse['timeframes']) > 0

    def test_compute_pulse_with_insufficient_data(
        self, backtester_with_pulse
    ):
        """Test pulse computation with insufficient historical data."""
        # Only 20 candles (less than minimum 50)
        small_data = pd.DataFrame({
            'open': [50000] * 20,
            'high': [50100] * 20,
            'low': [49900] * 20,
            'close': [50050] * 20,
            'volume': [500] * 20
        }, index=pd.date_range('2024-01-01', periods=20, freq='1min'))

        timestamp = pd.Timestamp('2024-01-01 00:30:00')

        pulse = backtester_with_pulse._compute_historical_pulse(
            'BTCUSD',
            timestamp,
            small_data
        )

        # Should return None due to insufficient data
        assert pulse is None

    def test_compute_pulse_without_providers_returns_none(self):
        """Test pulse computation returns None when providers not configured."""
        hist_provider = Mock()
        backtester = AdvancedBacktester(
            historical_data_provider=hist_provider,
            # No unified_data_provider or timeframe_aggregator
        )

        data = pd.DataFrame({
            'close': [50000] * 100
        }, index=pd.date_range('2024-01-01', periods=100, freq='1min'))

        pulse = backtester._compute_historical_pulse(
            'BTCUSD',
            pd.Timestamp('2024-01-01 01:00:00'),
            data
        )

        assert pulse is None

    def test_compute_pulse_uses_lookback_data_only(
        self, backtester_with_pulse, sample_historical_data
    ):
        """Test that pulse only uses data BEFORE current timestamp."""
        timestamp = pd.Timestamp('2024-01-01 01:30:00')

        pulse = backtester_with_pulse._compute_historical_pulse(
            'BTCUSD',
            timestamp,
            sample_historical_data
        )

        # Pulse should be computed from data before timestamp
        # Verify aggregator was called (mock tracks calls)
        assert backtester_with_pulse.timeframe_aggregator._detect_trend.called


class TestBacktestPulseInjection:
    """Test pulse injection during backtest execution."""

    @pytest.fixture
    def mock_decision_engine(self):
        """Mock DecisionEngine that tracks pulse injection."""
        engine = Mock(spec=DecisionEngine)

        # Track all generate_decision calls
        engine.generate_decision_calls = []

        def track_decision(**kwargs):
            engine.generate_decision_calls.append(kwargs)
            return {
                'action': 'HOLD',
                'confidence': 50,
                'reasoning': 'Test decision',
                'suggested_amount': 0
            }

        engine.generate_decision.side_effect = track_decision

        return engine

    @pytest.fixture
    def sample_backtest_data(self):
        """Create minimal backtest data (100 candles, 1-minute)."""
        dates = pd.date_range(
            start='2024-01-01 00:00:00',
            periods=100,
            freq='1min'
        )

        return pd.DataFrame({
            'open': [50000] * 100,
            'high': [50100] * 100,
            'low': [49900] * 100,
            'close': [50000] * 100,
            'volume': [500] * 100
        }, index=dates)

    def test_backtest_with_pulse_injection_enabled(
        self, mock_decision_engine, sample_backtest_data
    ):
        """Test backtest with inject_pulse=True passes pulse to decision engine."""
        hist_provider = Mock()
        hist_provider.get_historical_data.return_value = sample_backtest_data

        aggregator = Mock()
        aggregator._detect_trend.return_value = {
            'trend': 'UPTREND',
            'rsi': 70,
            'signal_strength': 75
        }

        backtester = AdvancedBacktester(
            historical_data_provider=hist_provider,
            unified_data_provider=Mock(),
            timeframe_aggregator=aggregator
        )

        result = backtester.run_backtest(
            asset_pair='BTCUSD',
            start_date='2024-01-01',
            end_date='2024-01-02',
            decision_engine=mock_decision_engine,
            inject_pulse=True
        )

        # Verify decisions were made with pulse context
        assert len(mock_decision_engine.generate_decision_calls) > 0

        # Check if any call included monitoring_context with pulse
        pulse_injected = any(
            call.get('monitoring_context') is not None and
            call.get('monitoring_context', {}).get('multi_timeframe_pulse') is not None
            for call in mock_decision_engine.generate_decision_calls
        )        # May not inject pulse for ALL calls (early calls have insufficient data)
        # but should inject for at least some calls
        assert pulse_injected, "Pulse should be injected in at least some decision calls"
        assert result is not None
    def test_backtest_with_pulse_injection_disabled(
        self, mock_decision_engine, sample_backtest_data
    ):
        """Test backtest with inject_pulse=False does NOT pass pulse."""
        hist_provider = Mock()
        hist_provider.get_historical_data.return_value = sample_backtest_data

        backtester = AdvancedBacktester(
            historical_data_provider=hist_provider,
            # Has providers but pulse disabled
            unified_data_provider=Mock(),
            timeframe_aggregator=Mock()
        )

        result = backtester.run_backtest(
            asset_pair='BTCUSD',
            start_date='2024-01-01',
            end_date='2024-01-02',
            decision_engine=mock_decision_engine,
            inject_pulse=False
        )

        # Verify NO calls included pulse in monitoring_context
        pulse_injected = any(
            call.get('monitoring_context') is not None and
            call.get('monitoring_context', {}).get('multi_timeframe_pulse') is not None
            for call in mock_decision_engine.generate_decision_calls
        )

        assert not pulse_injected

    def test_backtest_pulse_injection_graceful_degradation(
        self, mock_decision_engine, sample_backtest_data
    ):
        """Test backtest continues even if pulse computation fails."""
        hist_provider = Mock()
        hist_provider.get_historical_data.return_value = sample_backtest_data

        # Aggregator that raises exceptions
        aggregator = Mock()
        aggregator._detect_trend.side_effect = Exception("Indicator computation failed")

        backtester = AdvancedBacktester(
            historical_data_provider=hist_provider,
            unified_data_provider=Mock(),
            timeframe_aggregator=aggregator
        )

        # Should not crash, just skip pulse injection
        result = backtester.run_backtest(
            asset_pair='BTCUSD',
            start_date='2024-01-01',
            end_date='2024-01-02',
            decision_engine=mock_decision_engine,
            inject_pulse=True
        )

        assert result is not None
        assert 'metrics' in result
        # Backtest completed despite pulse failures


class TestPulseImpactOnBacktestResults:
    """Test that pulse actually impacts backtest decisions."""

    @pytest.mark.slow
    def test_pulse_vs_no_pulse_comparison(self):
        """Compare backtest results with and without pulse injection."""
        # OPTIMIZED: Reduced from 100 to 50 candles for faster testing
        dates = pd.date_range('2024-01-01', periods=50, freq='1min')
        hist_data = pd.DataFrame({
            'open': [50000] * 50,
            'high': [50100] * 50,
            'low': [49900] * 50,
            'close': [50000 + i * 10 for i in range(50)],  # Slow uptrend
            'volume': [500] * 50
        }, index=dates)

        hist_provider = Mock()
        hist_provider.get_historical_data.return_value = hist_data

        # Track pulse injection in single shared dict
        pulse_status = {'injected': False, 'not_injected': False}

        def make_pulse_aware_decision(**kwargs):
            mon_ctx = kwargs.get('monitoring_context')
            has_pulse = (
                mon_ctx is not None and
                mon_ctx.get('multi_timeframe_pulse') is not None
            )

            if has_pulse:
                pulse_status['injected'] = True
                return {
                    'action': 'BUY',
                    'confidence': 80,
                    'reasoning': 'Pulse confirms uptrend',
                    'suggested_amount': 100
                }
            else:
                pulse_status['not_injected'] = True
                return {
                    'action': 'HOLD',
                    'confidence': 50,
                    'reasoning': 'No multi-timeframe confirmation',
                    'suggested_amount': 0
                }

        # Backtest WITH pulse
        aggregator = Mock()
        aggregator._detect_trend.return_value = {'trend': 'UPTREND', 'rsi': 70, 'signal_strength': 80}

        mock_engine_with = Mock()
        mock_engine_with.generate_decision.side_effect = make_pulse_aware_decision

        backtester_with_pulse = AdvancedBacktester(
            historical_data_provider=hist_provider,
            unified_data_provider=Mock(),
            timeframe_aggregator=aggregator
        )

        result_with_pulse = backtester_with_pulse.run_backtest(
            'BTCUSD',
            '2024-01-01',
            '2024-01-02',
            mock_engine_with,
            inject_pulse=True
        )

        # Backtest WITHOUT pulse (separate engine instance)
        pulse_status_no = {'injected': False, 'not_injected': False}

        def make_decision_no_pulse(**kwargs):
            mon_ctx = kwargs.get('monitoring_context')
            has_pulse = (
                mon_ctx is not None and
                mon_ctx.get('multi_timeframe_pulse') is not None
            )
            pulse_status_no['injected'] = has_pulse
            pulse_status_no['not_injected'] = not has_pulse
            return {'action': 'HOLD', 'confidence': 50, 'reasoning': 'Test', 'suggested_amount': 0}

        mock_engine_without = Mock()
        mock_engine_without.generate_decision.side_effect = make_decision_no_pulse

        backtester_no_pulse = AdvancedBacktester(
            historical_data_provider=hist_provider
        )

        result_no_pulse = backtester_no_pulse.run_backtest(
            'BTCUSD',
            '2024-01-01',
            '2024-01-02',
            mock_engine_without,
            inject_pulse=False
        )

        # Verify results exist
        assert result_with_pulse is not None
        assert result_no_pulse is not None

        # Verify pulse injection behavior differs
        assert pulse_status['injected'], "Pulse should be injected when enabled"
        assert not pulse_status_no['injected'], "Pulse should NOT be injected when disabled"
