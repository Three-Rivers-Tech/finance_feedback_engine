"""Tests for real-time price monitoring and divergence detection (THR-22)."""

import pytest
from unittest.mock import Mock, patch
from finance_feedback_engine.data_providers.unified_data_provider import UnifiedDataProvider
from finance_feedback_engine.observability.metrics import record_price_divergence


class TestUnifiedDataProviderPriceMonitoring:
    """Test UnifiedDataProvider.get_current_price() method."""

    def test_get_current_price_success(self):
        """Test successful current price retrieval from platform."""
        provider = UnifiedDataProvider(cache_ttl=120)

        # Mock get_candles to return data
        mock_candles = [
            {"date": "2026-01-04T12:00:00Z", "open": 45000.0, "high": 45100.0, "low": 44900.0, "close": 45050.0},
            {"date": "2026-01-04T12:01:00Z", "open": 45050.0, "high": 45150.0, "low": 45000.0, "close": 45100.0},
        ]

        with patch.object(provider, 'get_candles', return_value=(mock_candles, 'coinbase')):
            result = provider.get_current_price("BTCUSD")

        assert result is not None
        assert result["asset_pair"] == "BTCUSD"
        assert result["price"] == 45100.0
        assert result["provider"] == "coinbase"
        assert "timestamp" in result

    def test_get_current_price_no_data(self):
        """Test get_current_price returns None when no candles available."""
        provider = UnifiedDataProvider(cache_ttl=120)

        with patch.object(provider, 'get_candles', return_value=([], 'coinbase')):
            result = provider.get_current_price("BTCUSD")

        assert result is None

    def test_get_current_price_missing_close(self):
        """Test get_current_price returns None when close price missing."""
        provider = UnifiedDataProvider(cache_ttl=120)

        mock_candles = [{"date": "2026-01-04T12:00:00Z", "open": 45000.0}]
        with patch.object(provider, 'get_candles', return_value=(mock_candles, 'coinbase')):
            result = provider.get_current_price("BTCUSD")

        assert result is None

    def test_get_current_price_exception_handling(self):
        """Test get_current_price handles exceptions gracefully."""
        provider = UnifiedDataProvider(cache_ttl=120)

        with patch.object(provider, 'get_candles', side_effect=Exception("API error")):
            result = provider.get_current_price("BTCUSD")

        assert result is None

    def test_cache_ttl_parameter(self):
        """Test UnifiedDataProvider respects cache_ttl parameter."""
        provider = UnifiedDataProvider(cache_ttl=60)

        # Check that cache was initialized with correct TTL
        assert provider._cache.ttl == 60

    def test_cache_ttl_default(self):
        """Test UnifiedDataProvider uses default 120s cache TTL."""
        provider = UnifiedDataProvider()

        assert provider._cache.ttl == 120


class TestPriceDivergenceMetrics:
    """Test price divergence metric recording."""

    def test_record_price_divergence_success(self):
        """Test metric recording with valid data."""
        with patch('finance_feedback_engine.observability.metrics._price_divergence_histogram') as mock_histogram:
            mock_histogram.record = Mock()

            # Manually set the global to our mock
            import finance_feedback_engine.observability.metrics as metrics_module
            metrics_module._price_divergence_histogram = mock_histogram

            record_price_divergence("BTCUSD", "coinbase", 1.5)

            mock_histogram.record.assert_called_once_with(
                1.5,
                {"asset_pair": "BTCUSD", "provider": "coinbase"}
            )

    def test_record_price_divergence_exception_handling(self):
        """Test metric recording handles exceptions gracefully."""
        # Should not raise exception even if histogram fails
        with patch('finance_feedback_engine.observability.metrics._price_divergence_histogram') as mock_histogram:
            mock_histogram.record.side_effect = Exception("Metric error")

            import finance_feedback_engine.observability.metrics as metrics_module
            metrics_module._price_divergence_histogram = mock_histogram

            # Should not raise
            record_price_divergence("BTCUSD", "coinbase", 1.5)
