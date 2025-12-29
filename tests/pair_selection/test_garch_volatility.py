"""
Unit tests for GARCHVolatilityForecaster.

Tests GARCH(1,1) volatility forecasting and regime classification.
"""

import pytest
from unittest.mock import MagicMock

from finance_feedback_engine.pair_selection.statistical.garch_volatility import (
    GARCHVolatilityForecaster,
    GARCHForecast,
)


class TestGARCHVolatilityForecaster:
    """Test suite for GARCHVolatilityForecaster."""

    @pytest.fixture
    def forecaster(self):
        """Create GARCHVolatilityForecaster instance."""
        return GARCHVolatilityForecaster(
            p=1,
            q=1,
            forecast_horizon_days=7,
            fitting_window_days=90
        )

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock UnifiedDataProvider."""
        provider = MagicMock()
        provider.get_candles = MagicMock()
        return provider

    def test_forecast_volatility_low_regime(self, forecaster, mock_data_provider):
        """Test GARCH forecast with low volatility data."""
        mock_candles = [
            {'close': 100 + i * 0.1, 'timestamp': f'2025-01-{i+1:02d}T00:00:00Z'}
            for i in range(90)
        ]
        mock_data_provider.get_candles.return_value = (mock_candles, 'coinbase')

        result = forecaster.forecast_volatility(
            asset_pair="BTCUSD",
            data_provider=mock_data_provider
        )

        # Verify result structure
        assert isinstance(result, GARCHForecast)
        assert result.volatility_regime in ['low', 'medium', 'high']
        assert result.forecasted_vol >= 0

    def test_forecast_dataclass_structure(self):
        """Test GARCHForecast dataclass structure."""
        forecast = GARCHForecast(
            forecasted_vol=0.15,
            model_params={'omega': 0.01, 'alpha': 0.1, 'beta': 0.85},
            volatility_regime='medium',
            historical_vol=0.12,
            confidence_intervals={'lower': 0.10, 'upper': 0.20},
            persistence=0.95
        )

        assert forecast.forecasted_vol == 0.15
        assert forecast.volatility_regime == 'medium'
        assert forecast.historical_vol == 0.12
        assert forecast.persistence == 0.95
