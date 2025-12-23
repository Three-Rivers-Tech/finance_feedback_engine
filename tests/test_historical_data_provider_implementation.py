"""Tests for HistoricalDataProvider implementation."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=10, freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "open": np.random.uniform(100, 110, 10),
            "high": np.random.uniform(110, 120, 10),
            "low": np.random.uniform(90, 100, 10),
            "close": np.random.uniform(100, 110, 10),
            "volume": np.random.randint(1000, 10000, 10),
        },
        index=dates,
    )


@pytest.fixture
def mock_alpha_vantage():
    """Mock AlphaVantageProvider."""
    with patch(
        "finance_feedback_engine.data_providers.historical_data_provider.AlphaVantageProvider"
    ) as mock:
        yield mock


@pytest.mark.external_service
class TestHistoricalDataProvider:
    """Test suite for HistoricalDataProvider."""

    def test_initialization(self, tmp_path):
        """Test provider initialization."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        assert provider.api_key == "test_api_key"
        assert provider.cache_dir == tmp_path / "cache"
        assert provider.validator is not None
        assert provider.data_store is not None
        assert provider.cache_dir.exists()

    def test_initialization_default_cache_dir(self):
        """Test provider initialization with default cache directory."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(api_key="test_api_key")

        assert provider.cache_dir == Path("data/historical_cache")
        assert provider.validator is not None
        assert provider.data_store is not None

    @patch(
        "finance_feedback_engine.data_providers.historical_data_provider.asyncio.run"
    )
    def test_fetch_raw_data(
        self, mock_asyncio_run, mock_alpha_vantage, tmp_path, sample_ohlcv_data
    ):
        """Test fetching raw data from Alpha Vantage."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        # Setup mock to return candles
        candles = [
            {
                "date": "2024-01-01T00:00:00Z",
                "open": 100.0,
                "high": 110.0,
                "low": 95.0,
                "close": 105.0,
                "volume": 1000,
            },
            {
                "date": "2024-01-01T01:00:00Z",
                "open": 105.0,
                "high": 115.0,
                "low": 100.0,
                "close": 110.0,
                "volume": 1500,
            },
        ]
        mock_asyncio_run.return_value = candles

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        df = provider._fetch_raw_data("BTCUSD", start, end, timeframe="1h")

        assert not df.empty
        assert len(df) == 2
        assert all(
            col in df.columns for col in ["open", "high", "low", "close", "volume"]
        )
        assert isinstance(df.index, pd.DatetimeIndex)

    @patch(
        "finance_feedback_engine.data_providers.historical_data_provider.asyncio.run"
    )
    def test_fetch_raw_data_caching(
        self, mock_asyncio_run, mock_alpha_vantage, tmp_path
    ):
        """Test that fetched data is cached to parquet."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        candles = [
            {
                "date": "2024-01-01T00:00:00Z",
                "open": 100.0,
                "high": 110.0,
                "low": 95.0,
                "close": 105.0,
            }
        ]
        mock_asyncio_run.return_value = candles

        cache_dir = tmp_path / "cache"
        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(cache_dir)
        )

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        # First call should fetch from API
        df1 = provider._fetch_raw_data("BTCUSD", start, end, timeframe="1h")
        assert not df1.empty

    

        # Cache file should exist

        cache_files = list(cache_dir.glob("BTCUSD_*.parquet"))

        if not cache_files:

             # Fallback for case sensitivity

             cache_files = list(cache_dir.glob("btcusd_*.parquet"))

        assert len(cache_files) > 0
        # Second call should load from cache (asyncio.run not called again)
        mock_asyncio_run.reset_mock()
        df2 = provider._fetch_raw_data("BTCUSD", start, end, timeframe="1h")
        assert not df2.empty
        mock_asyncio_run.assert_not_called()

    def test_get_historical_data_with_string_dates(self, tmp_path):
        """Test get_historical_data with string date inputs."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            # Setup mock to return valid DataFrame
            dates = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
            mock_df = pd.DataFrame(
                {
                    "open": [100.0] * 5,
                    "high": [110.0] * 5,
                    "low": [95.0] * 5,
                    "close": [105.0] * 5,
                    "volume": [1000] * 5,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            # Call with string dates
            df = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )

            assert not df.empty
            assert len(df) == 5
            mock_fetch.assert_called_once()

    def test_get_historical_data_with_datetime_objects(self, tmp_path):
        """Test get_historical_data with datetime objects."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            dates = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
            mock_df = pd.DataFrame(
                {
                    "open": [100.0] * 5,
                    "high": [110.0] * 5,
                    "low": [95.0] * 5,
                    "close": [105.0] * 5,
                    "volume": [1000] * 5,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 2)

            df = provider.get_historical_data("BTCUSD", start, end, timeframe="1h")

            assert not df.empty
            # Verify timezone was added
            call_args = mock_fetch.call_args[0]
            assert call_args[1].tzinfo == timezone.utc
            assert call_args[2].tzinfo == timezone.utc

    def test_get_historical_data_uses_cache_first(self, tmp_path):
        """Test that get_historical_data checks cache before fetching."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        # Setup mock data store with cached data
        cached_df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [110.0],
                "low": [95.0],
                "close": [105.0],
                "volume": [1000],
            },
            index=pd.DatetimeIndex(["2024-01-01"], tz="UTC"),
        )

        with patch.object(
            provider.data_store, "load_dataframe", return_value=cached_df
        ) as mock_load:
            with patch.object(provider, "_fetch_raw_data") as mock_fetch:
                df = provider.get_historical_data(
                    "BTCUSD",
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    timeframe="1h",
                )

                # Should load from cache
                mock_load.assert_called_once()
                # Should NOT fetch from API
                mock_fetch.assert_not_called()
                assert not df.empty

    def test_get_historical_data_validates_data(self, tmp_path):
        """Test that fetched data is validated."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            dates = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
            mock_df = pd.DataFrame(
                {
                    "open": [
                        100.0,
                        -50.0,
                        105.0,
                        102.0,
                        108.0,
                    ],  # Negative price (invalid)
                    "high": [110.0, 55.0, 115.0, 112.0, 118.0],
                    "low": [95.0, -60.0, 95.0, 92.0, 98.0],  # Negative price (invalid)
                    "close": [105.0, 50.0, 110.0, 107.0, 113.0],
                    "volume": [1000, 1500, 2000, 1800, 2200],
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            with patch.object(
                provider.validator, "validate_dataframe"
            ) as mock_validate:
                mock_validate.return_value = {}  # No errors

                df = provider.get_historical_data(
                    "BTCUSD",
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    timeframe="1h",
                )

                # Validation should have been called
                mock_validate.assert_called_once()
                assert not df.empty

    def test_get_historical_data_persists_to_store(self, tmp_path):
        """Test that fetched data is persisted to data store."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            dates = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
            mock_df = pd.DataFrame(
                {
                    "open": [100.0] * 5,
                    "high": [110.0] * 5,
                    "low": [95.0] * 5,
                    "close": [105.0] * 5,
                    "volume": [1000] * 5,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            with patch.object(provider.data_store, "save_dataframe") as mock_save:
                df = provider.get_historical_data(
                    "BTCUSD",
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    timeframe="1h",
                )

                # Data should be persisted
                mock_save.assert_called_once()
                assert not df.empty

    def test_get_historical_data_handles_empty_result(self, tmp_path):
        """Test handling of empty result from API."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data", return_value=pd.DataFrame()):
            df = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )

            assert df.empty

    def test_get_historical_data_adds_missing_columns(self, tmp_path):
        """Test that missing expected columns are added as NaN."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            # DataFrame missing 'volume' column
            dates = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
            mock_df = pd.DataFrame(
                {
                    "open": [100.0] * 5,
                    "high": [110.0] * 5,
                    "low": [95.0] * 5,
                    "close": [105.0] * 5,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            df = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )

            # Volume column should be added with NaN
            assert "volume" in df.columns
            assert df["volume"].isna().all()

    def test_get_historical_data_sorts_by_index(self, tmp_path):
        """Test that data is sorted chronologically."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            # Unsorted dates
            dates = pd.to_datetime(
                [
                    "2024-01-01T03:00:00Z",
                    "2024-01-01T01:00:00Z",
                    "2024-01-01T04:00:00Z",
                    "2024-01-01T02:00:00Z",
                ],
                utc=True,
            )
            mock_df = pd.DataFrame(
                {
                    "open": [100.0] * 4,
                    "high": [110.0] * 4,
                    "low": [95.0] * 4,
                    "close": [105.0] * 4,
                    "volume": [1000] * 4,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            df = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )

            # Should be sorted
            assert df.index.is_monotonic_increasing

    def test_get_historical_data_handles_persistence_failure(self, tmp_path):
        """Test graceful handling when persistence fails."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(tmp_path / "cache")
        )

        with patch.object(provider, "_fetch_raw_data") as mock_fetch:
            dates = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
            mock_df = pd.DataFrame(
                {
                    "open": [100.0] * 5,
                    "high": [110.0] * 5,
                    "low": [95.0] * 5,
                    "close": [105.0] * 5,
                    "volume": [1000] * 5,
                },
                index=dates,
            )
            mock_fetch.return_value = mock_df

            with patch.object(
                provider.data_store,
                "save_dataframe",
                side_effect=Exception("Disk full"),
            ):
                # Should not raise, just log warning
                df = provider.get_historical_data(
                    "BTCUSD",
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    timeframe="1h",
                )

                # Data should still be returned
                assert not df.empty


class TestHistoricalDataProviderIntegration:
    """Integration tests for HistoricalDataProvider with real components."""

    def test_full_workflow_without_cache(self, tmp_path):
        """Test complete workflow: fetch -> validate -> persist."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        cache_dir = tmp_path / "cache"
        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(cache_dir)
        )

        with patch(
            "finance_feedback_engine.data_providers.historical_data_provider.asyncio.run"
        ) as mock_run:
            # Mock API response
            candles = [
                {
                    "date": f"2024-01-01T{i:02d}:00:00Z",
                    "open": 100.0 + i,
                    "high": 110.0 + i,
                    "low": 95.0 + i,
                    "close": 105.0 + i,
                    "volume": 1000,
                }
                for i in range(5)
            ]
            mock_run.return_value = candles

            df = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )

            # Verify data was fetched
            assert not df.empty
            assert len(df) == 5

            # Verify persistence
            cache_files = list(cache_dir.glob("*.parquet"))
            assert len(cache_files) > 0

    def test_full_workflow_with_cache(self, tmp_path):
        """Test that second fetch uses cache."""
        from finance_feedback_engine.data_providers.historical_data_provider import (
            HistoricalDataProvider,
        )

        cache_dir = tmp_path / "cache"
        provider = HistoricalDataProvider(
            api_key="test_api_key", cache_dir=str(cache_dir)
        )

        with patch(
            "finance_feedback_engine.data_providers.historical_data_provider.asyncio.run"
        ) as mock_run:
            candles = [
                {
                    "date": "2024-01-01T00:00:00Z",
                    "open": 100.0,
                    "high": 110.0,
                    "low": 95.0,
                    "close": 105.0,
                    "volume": 1000,
                }
            ]
            mock_run.return_value = candles

            # First call - should fetch
            df1 = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )
            assert not df1.empty
            assert mock_run.call_count == 1

            # Second call - should use cache
            df2 = provider.get_historical_data(
                "BTCUSD", start_date="2024-01-01", end_date="2024-01-02", timeframe="1h"
            )
            assert not df2.empty
            # Should not fetch again
            assert mock_run.call_count == 1

            # DataFrames should be identical
            pd.testing.assert_frame_equal(df1, df2)
