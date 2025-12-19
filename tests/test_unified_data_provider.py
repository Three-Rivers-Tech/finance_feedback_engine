"""
Tests for UnifiedDataProvider, including multi-timeframe aggregation.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from finance_feedback_engine.data_providers.unified_data_provider import (
    UnifiedDataProvider,
)


@pytest.fixture
def mock_config():
    """Mock configuration for UnifiedDataProvider."""
    return {
        "data_providers": {
            "alpha_vantage": {"api_key": "test_key"},
            "coinbase": {"enabled": True},
            "oanda": {"enabled": False},
        },
        "cache": {"ttl_seconds": 300},
    }


@pytest.fixture
def mock_candles():
    """Mock candle data for testing."""
    return [
        {
            "timestamp": "2025-12-03T10:00:00Z",
            "open": 42000,
            "high": 42100,
            "low": 41900,
            "close": 42050,
            "volume": 100,
        },
        {
            "timestamp": "2025-12-03T10:01:00Z",
            "open": 42050,
            "high": 42200,
            "low": 42000,
            "close": 42150,
            "volume": 150,
        },
        {
            "timestamp": "2025-12-03T10:02:00Z",
            "open": 42150,
            "high": 42300,
            "low": 42100,
            "close": 42250,
            "volume": 200,
        },
    ]


@pytest.mark.external_service
class TestUnifiedDataProviderAggregation:
    """Tests for aggregate_all_timeframes method."""

    def test_aggregate_all_timeframes_basic(self, mock_config, mock_candles):
        """Test basic aggregation with successful data fetches."""
        provider = UnifiedDataProvider(mock_config)

        # Mock get_multi_timeframe_data to return successful data
        with patch.object(provider, "get_multi_timeframe_data") as mock_get:
            mock_get.return_value = {
                "1m": (mock_candles, "coinbase"),
                "5m": (mock_candles, "coinbase"),
                "15m": (mock_candles, "alpha_vantage"),
                "1h": (mock_candles, "alpha_vantage"),
                "4h": (mock_candles, "alpha_vantage"),
                "1d": (mock_candles, "alpha_vantage"),
            }

            result = provider.aggregate_all_timeframes("BTCUSD")

            # Verify structure
            assert "asset_pair" in result
            assert result["asset_pair"] == "BTCUSD"
            assert "timestamp" in result
            assert "timeframes" in result
            assert "metadata" in result

            # Verify all timeframes present
            assert len(result["timeframes"]) == 6
            for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
                assert tf in result["timeframes"]
                assert result["timeframes"][tf]["candles_count"] == 3
                assert result["timeframes"][tf]["source_provider"] in [
                    "coinbase",
                    "alpha_vantage",
                ]

            # Verify metadata
            assert len(result["metadata"]["available_timeframes"]) == 6
            assert len(result["metadata"]["missing_timeframes"]) == 0
            assert (
                result["metadata"]["cache_hit_rate"] == 0.0
            )  # All from real providers

    def test_aggregate_with_missing_data(self, mock_config, mock_candles):
        """Test graceful handling of missing timeframe data."""
        provider = UnifiedDataProvider(mock_config)

        # Mock with some missing data (1m unavailable)
        with patch.object(provider, "get_multi_timeframe_data") as mock_get:
            mock_get.return_value = {
                "1m": ([], "failed"),  # Missing
                "5m": (mock_candles, "coinbase"),
                "15m": (mock_candles, "alpha_vantage"),
            }

            result = provider.aggregate_all_timeframes(
                "BTCUSD", timeframes=["1m", "5m", "15m"]
            )

            # Verify missing data tracked
            assert "1m" in result["metadata"]["missing_timeframes"]
            assert len(result["metadata"]["available_timeframes"]) == 2
            assert "5m" in result["metadata"]["available_timeframes"]
            assert "15m" in result["metadata"]["available_timeframes"]

            # Verify 1m still in response but empty
            assert "1m" in result["timeframes"]
            assert result["timeframes"]["1m"]["candles_count"] == 0
            assert result["timeframes"]["1m"]["source_provider"] == "failed"

    def test_aggregate_custom_timeframes(self, mock_config, mock_candles):
        """Test custom timeframe list."""
        provider = UnifiedDataProvider(mock_config)

        custom_tfs = ["5m", "1h", "1d"]

        with patch.object(provider, "get_multi_timeframe_data") as mock_get:
            mock_get.return_value = {
                "5m": (mock_candles, "coinbase"),
                "1h": (mock_candles, "alpha_vantage"),
                "1d": (mock_candles, "alpha_vantage"),
            }

            result = provider.aggregate_all_timeframes("ETHUSD", timeframes=custom_tfs)

            assert result["asset_pair"] == "ETHUSD"
            assert len(result["timeframes"]) == 3
            assert set(result["metadata"]["requested_timeframes"]) == set(custom_tfs)

    def test_aggregate_metadata_tracking(self, mock_config, mock_candles):
        """Test metadata fields populated correctly."""
        provider = UnifiedDataProvider(mock_config)

        with patch.object(provider, "get_multi_timeframe_data") as mock_get:
            mock_get.return_value = {
                "1m": (mock_candles, "coinbase"),
                "5m": ([], "failed"),
                "1h": (mock_candles, "alpha_vantage"),
            }

            result = provider.aggregate_all_timeframes(
                "BTCUSD", timeframes=["1m", "5m", "1h"]
            )

            # Verify metadata structure
            metadata = result["metadata"]
            assert "requested_timeframes" in metadata
            assert "available_timeframes" in metadata
            assert "missing_timeframes" in metadata
            assert "cache_hit_rate" in metadata

            # Verify values
            assert metadata["requested_timeframes"] == ["1m", "5m", "1h"]
            assert len(metadata["available_timeframes"]) == 2
            assert "5m" in metadata["missing_timeframes"]
            assert 0.0 <= metadata["cache_hit_rate"] <= 1.0

    def test_aggregate_timestamp_format(self, mock_config, mock_candles):
        """Test timestamp is ISO 8601 UTC format."""
        provider = UnifiedDataProvider(mock_config)

        with patch.object(provider, "get_multi_timeframe_data") as mock_get:
            mock_get.return_value = {"1h": (mock_candles, "alpha_vantage")}

            result = provider.aggregate_all_timeframes("BTCUSD", timeframes=["1h"])

            # Verify ISO 8601 format
            timestamp = result["timestamp"]
            assert isinstance(timestamp, str)
            # Should be parseable as ISO 8601
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None  # Has timezone info

    def test_aggregate_empty_timeframes(self, mock_config):
        """Test handling of empty candles."""
        provider = UnifiedDataProvider(mock_config)

        with patch.object(provider, "get_multi_timeframe_data") as mock_get:
            mock_get.return_value = {
                "1m": ([], "coinbase"),  # Empty but not failed
                "5m": ([], "coinbase"),
            }

            result = provider.aggregate_all_timeframes(
                "BTCUSD", timeframes=["1m", "5m"]
            )

            # Empty candles still count as "missing" if no data
            assert len(result["metadata"]["missing_timeframes"]) == 2
            assert result["timeframes"]["1m"]["candles_count"] == 0
            assert result["timeframes"]["5m"]["candles_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
