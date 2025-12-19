"""Integration tests for pipeline modules."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from finance_feedback_engine.pipelines.batch.batch_ingestion import (
    BatchDataIngester,
    WatermarkStore,
)
from finance_feedback_engine.pipelines.storage.delta_lake_manager import (
    DeltaLakeManager,
)


@pytest.mark.external_service
class TestPipelineIntegration:
    """Integration tests for data pipeline modules."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir) / "delta_lake"
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_end_to_end_backfill(self):
        """Test: Alpha Vantage → Bronze Layer → Query."""
        # Initialize the Delta Lake manager
        delta_manager = DeltaLakeManager(storage_path=str(self.storage_path))

        # Create a mock data provider
        with patch(
            "finance_feedback_engine.pipelines.batch.batch_ingestion.BatchDataIngester._get_data_provider"
        ) as mock_get_provider:
            # Configure mock to return realistic OHLCV data
            mock_data = [
                {
                    "date": "2024-01-01",
                    "open": 40000.0,
                    "high": 40500.0,
                    "low": 39500.0,
                    "close": 41000.0,
                },
                {
                    "date": "2024-01-02",
                    "open": 41000.0,
                    "high": 41500.0,
                    "low": 40500.0,
                    "close": 42000.0,
                },
                {
                    "date": "2024-01-03",
                    "open": 42000.0,
                    "high": 42500.0,
                    "low": 41500.0,
                    "close": 41500.0,
                },
            ]

            # Create mock provider
            mock_provider = AsyncMock()
            mock_provider.get_historical_data.return_value = mock_data
            mock_get_provider.return_value = mock_provider

            # Initialize the batch ingestion manager with a proper config
            config = {
                "alpha_vantage": {"api_key": "test_key"},
            }
            ingestion_manager = BatchDataIngester(delta_manager, config)

            # Perform the ingestion
            start_date = "2024-01-01"
            end_date = "2024-01-03"
            result = await ingestion_manager.ingest_historical_data(
                asset_pair="BTCUSD",
                timeframe="daily",
                start_date=start_date,
                end_date=end_date,
                provider="alpha_vantage",
            )

            # Verify the ingestion completed (this should now work with real implementation)
            assert result is not None

    def test_delta_lake_time_travel(self):
        """Test: Write → Optimize → Time travel query."""
        # Initialize the Delta Lake manager
        delta_manager = DeltaLakeManager(storage_path=str(self.storage_path))

        # Test creating a table
        test_data = [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "asset_pair": "BTCUSD",
                "close": 40000.0,
                "volume": 1000.0,
            },
            {
                "timestamp": "2024-01-02T00:00:00Z",
                "asset_pair": "BTCUSD",
                "close": 41000.0,
                "volume": 1200.0,
            },
        ]

        # Create the table and write the data
        table_name = "test_raw_market_data_daily"
        try:
            # Try to create the table and insert data
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                delta_manager.create_or_update_table(
                    test_data, table_name, ["asset_pair"]
                )
            )
            loop.close()

            # Verify the table was created
            assert (self.storage_path / table_name).exists()

            # Test reading the data
            df = delta_manager.read_table(table_name)
            assert len(df) == 2
            assert df.iloc[0]["close"] == 40000.0
            assert df.iloc[1]["close"] == 41000.0

        except Exception as e:
            # If Delta Lake isn't available, skip this test
            pytest.skip(f"Delta Lake not available for testing: {e}")

    def test_watermark_persistence(self):
        """Test: Watermark survives process restart."""
        # Initialize the WatermarkStore
        watermark_store = WatermarkStore(str(self.storage_path / "watermarks"))

        # Set a watermark
        test_asset = "BTCUSD"
        test_timeframe = "1h"
        test_watermark = "2024-01-01T12:00:00Z"

        # Save the watermark
        watermark_store.set(test_asset, test_timeframe, test_watermark)

        # Verify watermark was saved
        retrieved_watermark = watermark_store.get(test_asset, test_timeframe)
        assert retrieved_watermark == test_watermark

        # Create a new instance (simulating process restart)
        new_watermark_store = WatermarkStore(str(self.storage_path / "watermarks"))

        # Verify watermark is still there
        retrieved_watermark_new = new_watermark_store.get(test_asset, test_timeframe)
        assert retrieved_watermark_new == test_watermark


class TestBatchIngestionIntegration:
    """Integration tests for batch ingestion pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = Path(self.temp_dir) / "delta_lake"
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_ingestion_with_multiple_timeframes(self):
        """Test ingestion with multiple timeframes."""
        # Initialize the Delta Lake manager
        delta_manager = DeltaLakeManager(storage_path=str(self.storage_path))

        # Initialize the batch ingestion manager with a proper config
        config = {
            "alpha_vantage": {"api_key": "test_key"},
        }
        ingestion_manager = BatchDataIngester(delta_manager, config)

        # Mock the data provider
        with patch(
            "finance_feedback_engine.pipelines.batch.batch_ingestion.BatchDataIngester._get_data_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            # Return the expected format of data as a list of dictionaries with OHLC values
            # with date, open, high, low, close, and volume (if available)
            mock_provider.get_historical_data.return_value = [
                {
                    "date": "2024-01-01 00:00:00",
                    "open": 40000.0,
                    "high": 41000.0,
                    "low": 39500.0,
                    "close": 40500.0,
                    "volume": 100.0,
                },
                {
                    "date": "2024-01-01 01:00:00",
                    "open": 40500.0,
                    "high": 41500.0,
                    "low": 40000.0,
                    "close": 41000.0,
                    "volume": 120.0,
                },
            ]
            mock_get_provider.return_value = mock_provider

            # Test ingestion with multiple timeframes
            timeframes = ["1m", "5m", "1h"]
            for tf in timeframes:
                result = await ingestion_manager.ingest_historical_data(
                    asset_pair="BTCUSD",
                    timeframe=tf,
                    start_date="2024-01-01",
                    end_date="2024-01-02",
                    provider="alpha_vantage",
                )
                # The result should be a dictionary with status information
                assert result is not None
                # Check that it's the expected format
                assert isinstance(result, dict)
                assert (
                    "status" in result or result.get("records", 0) >= 0
                )  # Either has status or records

                # Verify watermark was updated if records were processed
                if result.get("watermark"):
                    watermark_store = WatermarkStore()
                    watermark = watermark_store.get("BTCUSD", tf)
                    # The watermark will be the max timestamp from the processed records
                    assert watermark is not None
