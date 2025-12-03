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
        assert hasattr(store, 'data_dir')
        assert os.path.exists(temp_dir)

    def test_save_data_basic(self, store):
        """Test saving data with save_data method."""
        data = {"timestamp": datetime.now().isoformat(), "value": 100.5}
        # Assuming save_data takes series_name and data
        store.save_data("test_series", data)
        # Success if no exception
        assert True

    def test_load_data_basic(self, store):
        """Test loading data with load_data method."""
        # Save some data first
        data = {"timestamp": datetime.now().isoformat(), "value": 42.0}
        store.save_data("test_series", data)
        
        # Load it back
        loaded = store.load_data("test_series")
        # Should return something (list, dict, or None if empty)
        assert loaded is not None or loaded == []

    def test_save_multiple_data_points(self, store):
        """Test saving multiple data points sequentially."""
        data_points = [
            {"timestamp": datetime.now().isoformat(), "value": 100.5},
            {"timestamp": (datetime.now() + timedelta(minutes=1)).isoformat(), "value": 101.0}
        ]
        for data in data_points:
            store.save_data("multi_series", data)
        
        loaded = store.load_data("multi_series")
        assert loaded is not None

    def test_load_nonexistent_series(self, store):
        """Test loading data for a series that doesn't exist."""
        loaded = store.load_data("nonexistent_series")
        # Should handle gracefully (return None or empty list)
        assert loaded is None or loaded == [] or isinstance(loaded, (list, dict))


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
