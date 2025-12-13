"""Tests for finance_feedback_engine.persistence.timeseries_data_store module."""
import pytest
from datetime import datetime, timedelta
import tempfile
import shutil
import os

from finance_feedback_engine.persistence.timeseries_data_store import TimeSeriesDataStore


class TestTimeSeriesDataStore:
    """Test the TimeSeriesDataStore class - API: save_data, load_data."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test data."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    @pytest.fixture
    def store(self, temp_dir):
        """Create a TimeSeriesDataStore instance."""
        return TimeSeriesDataStore(storage_path=temp_dir)

    def test_init(self, store, temp_dir):
        """Test store initialization."""
        assert hasattr(store, 'storage_path')
        assert str(store.storage_path) == temp_dir  # Convert Path to string for comparison
        assert os.path.exists(temp_dir)

    def test_save_data_basic(self, store):
        """Test saving data with save_data method."""
        data = {"timestamp": datetime.now().isoformat(), "value": 100.5}
        expected_timestamp = data['timestamp']
        # Assuming save_data takes series_name and data
        store.save_data("test_series", data)
        
        # Verify the data was saved correctly
        loaded = store.load_data("test_series")
        assert isinstance(loaded, list)
        assert len(loaded) == 1
        saved_item = loaded[0]
        assert saved_item['value'] == 100.5
        assert saved_item['timestamp'] == expected_timestamp

    def test_load_data_basic(self, store):
        """Test loading data with load_data method."""
        # Save some data first
        data = {"timestamp": datetime.now().isoformat(), "value": 42.0}
        expected_timestamp = data['timestamp']
        store.save_data("test_series", data)
        
        # Load it back
        loaded = store.load_data("test_series")
        # Verify data was loaded correctly
        assert loaded is not None
        assert isinstance(loaded, list)
        assert len(loaded) == 1
        saved_item = loaded[0]
        assert saved_item['value'] == 42.0
        assert saved_item['timestamp'] == expected_timestamp

    def test_save_multiple_data_points(self, store):
        """Test saving multiple data points sequentially."""
        # Generate data points with timestamps
        base_time = datetime.now()
        data_points = [
            {"timestamp": base_time.isoformat(), "value": 100.5},
            {"timestamp": (base_time + timedelta(minutes=1)).isoformat(), "value": 101.0}
        ]
        for data in data_points:
            store.save_data("multi_series", data)
        
        # Load and verify all data points were saved (append behavior)
        loaded = store.load_data("multi_series")
        assert loaded is not None
        assert isinstance(loaded, list)
        assert len(loaded) == 2, f"Expected 2 data points, got {len(loaded)}"
        
        # Verify each data point is present with correct values
        values = [item['value'] for item in loaded]
        assert 100.5 in values, f"First data point value 100.5 not found in {values}"
        assert 101.0 in values, f"Second data point value 101.0 not found in {values}"
        
        # Verify timestamps are present and in order (append preserves order)
        timestamps = [item['timestamp'] for item in loaded]
        assert len(timestamps) == 2
        assert timestamps[0] < timestamps[1], f"Timestamps not in order: {timestamps}"

    def test_load_nonexistent_series(self, store):
        """Test loading data for a series that doesn't exist."""
        loaded = store.load_data("nonexistent_series")
        # Verify consistent handling of missing series
        # Expected behavior: return empty list (per API docs)
        assert loaded == [], \
            f"Expected empty list for nonexistent series, got {type(loaded).__name__}: {loaded}"


class TestDataPersistence:
    """Test data persistence across store instances."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test data."""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)

    def test_data_survives_store_recreation(self, temp_dir):
        """Test that saved data persists across store recreations."""
        # Create first store and save data
        store1 = TimeSeriesDataStore(storage_path=temp_dir)
        data = {"timestamp": datetime.now().isoformat(), "value": 42.0}
        store1.save_data("persistent_series", data)
        
        # Create new store instance with same directory
        store2 = TimeSeriesDataStore(storage_path=temp_dir)
        retrieved = store2.load_data("persistent_series")
        
        assert retrieved is not None

    def test_multiple_series(self, temp_dir):
        """Test handling multiple data series."""
        store = TimeSeriesDataStore(storage_path=temp_dir)
        store.save_data("series_a", {"timestamp": datetime.now().isoformat(), "value": 1.0})
        store.save_data("series_b", {"timestamp": datetime.now().isoformat(), "value": 2.0})
        
        data_a = store.load_data("series_a")
        data_b = store.load_data("series_b")
        
        # Both should exist
        assert data_a is not None
        assert data_b is not None
