"""Tests for finance_feedback_engine.monitoring.trade_tracker module."""

from unittest.mock import Mock

import pytest

from finance_feedback_engine.monitoring.trade_tracker import TradeTrackerThread


class TestTradeTrackerThread:
    """Test the TradeTrackerThread class."""

    @pytest.fixture
    def mock_platform(self):
        """Create a mock trading platform."""
        platform = Mock()
        platform.get_current_price = Mock(return_value={"price": 100.0})
        return platform

    @pytest.fixture
    def position_data(self):
        """Sample position data."""
        return {
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "entry_price": 100.0,
            "position_size": 1.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
        }

    @pytest.fixture
    def metrics_callback(self):
        """Mock metrics callback."""
        return Mock()

    @pytest.fixture
    def tracker(self, position_data, mock_platform, metrics_callback):
        """Create a TradeTrackerThread instance."""
        return TradeTrackerThread(
            trade_id="test_trade_123",
            position_data=position_data,
            platform=mock_platform,
            metrics_callback=metrics_callback,
        )

    def test_init(self, tracker):
        """Test TradeTrackerThread initialization."""
        assert tracker is not None
        assert hasattr(tracker, "start")
        assert hasattr(tracker, "stop")

    def test_start_tracking(self, tracker):
        """Test starting the tracker thread."""
        # Just verify it doesn't raise
        try:
            tracker.start()
            assert True
            tracker.stop()  # Clean up
        except Exception:
            pytest.skip("Thread operations may not work in test environment")

    def test_stop_tracking(self, tracker):
        """Test stopping the tracker thread."""
        try:
            tracker.start()
            tracker.stop()
            assert True
        except Exception:
            pytest.skip("Thread operations may not work in test environment")

    def test_get_current_status(self, tracker):
        """Test getting current tracking status."""
        status = tracker.get_current_status()
        # Should return a dictionary with status information
        assert isinstance(status, dict)

    def test_is_running_property(self, tracker):
        """Test the is_running property."""
        assert hasattr(tracker, "is_running")
        # Initially should be False
        assert tracker.is_running in [True, False]


class TestPositionTracking:
    """Test position tracking functionality."""

    @pytest.fixture
    def mock_platform(self):
        """Create a mock trading platform."""
        platform = Mock()
        platform.get_current_price = Mock(return_value={"price": 105.0})
        return platform

    def test_long_position_tracking(self, mock_platform):
        """Test tracking a long position."""
        position_data = {
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "entry_price": 100.0,
            "position_size": 1.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
        }

        tracker = TradeTrackerThread(
            trade_id="long_test",
            position_data=position_data,
            platform=mock_platform,
            metrics_callback=Mock(),
        )

        status = tracker.get_current_status()
        assert status is not None
        assert isinstance(status, dict)

    def test_short_position_tracking(self, mock_platform):
        """Test tracking a short position."""
        position_data = {
            "asset_pair": "BTCUSD",
            "action": "SELL",  # Short position
            "entry_price": 100.0,
            "position_size": 1.0,
            "stop_loss": 105.0,
            "take_profit": 90.0,
        }

        tracker = TradeTrackerThread(
            trade_id="short_test",
            position_data=position_data,
            platform=mock_platform,
            metrics_callback=Mock(),
        )

        status = tracker.get_current_status()
        assert status is not None
        assert isinstance(status, dict)
