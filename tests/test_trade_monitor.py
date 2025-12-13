"""
Comprehensive tests for TradeMonitor functionality.
Covers lifecycle management, P&L tracking, and monitoring context.
"""
import pytest
from unittest.mock import MagicMock
import time
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor


@pytest.fixture
def mock_platform():
    """Mock trading platform."""
    platform = MagicMock()
    platform.get_account_info.return_value = {
        'balance': 10000.0,
        'available': 9000.0
    }
    platform.get_positions.return_value = []
    return platform


@pytest.fixture
def trade_monitor(mock_platform):
    """Create TradeMonitor instance."""
    monitor = TradeMonitor(
        platform=mock_platform,
        poll_interval=1,  # Fast polling for tests
        detection_interval=1
    )
    yield monitor
    
    # Teardown: ensure monitor is stopped to prevent thread leaks
    if monitor.is_running:
        monitor.stop()
        # Wait for monitor to stop
        deadline = time.time() + 2.0
        while monitor.is_running:
            if time.time() > deadline:
                break
            time.sleep(0.05)


class TestTradeMonitorLifecycle:
    """Test monitor lifecycle and thread management."""
    
    def test_monitor_initialization(self, trade_monitor, mock_platform):
        """Test TradeMonitor initializes correctly."""
        assert trade_monitor.platform == mock_platform
        assert trade_monitor.poll_interval == 1
        assert trade_monitor.detection_interval == 1
        assert trade_monitor.is_running is False
    
    def test_monitor_start(self, trade_monitor):
        """Test starting the monitor."""
        trade_monitor.start()
        # Wait until is_running becomes True, with timeout
        deadline = time.time() + 2.0
        while not trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not start within timeout")
            time.sleep(0.05)

        assert trade_monitor.is_running is True

        trade_monitor.stop()
        # Wait until is_running becomes False, with timeout
        deadline = time.time() + 2.0
        while trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not stop within timeout")
            time.sleep(0.05)
    
    def test_monitor_stop(self, trade_monitor):
        """Test stopping the monitor."""
        trade_monitor.start()
        # Wait until is_running becomes True, with timeout
        deadline = time.time() + 2.0
        while not trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not start within timeout")
            time.sleep(0.05)
        assert trade_monitor.is_running is True

        trade_monitor.stop()
        # Wait until is_running becomes False, with timeout
        deadline = time.time() + 2.0
        while trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not stop within timeout")
            time.sleep(0.05)
        assert trade_monitor.is_running is False
    
    def test_monitor_double_start(self, trade_monitor):
        """Test that starting already-running monitor is safe."""
        trade_monitor.start()
        # Wait until is_running becomes True, with timeout
        deadline = time.time() + 2.0
        while not trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not start within timeout")
            time.sleep(0.05)

        # Second start should be no-op
        trade_monitor.start()
        assert trade_monitor.is_running is True

        trade_monitor.stop()
        # Wait until is_running becomes False, with timeout
        deadline = time.time() + 2.0
        while trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not stop within timeout")
            time.sleep(0.05)


class TestTradeMonitorPnLTracking:
    """Test P&L tracking and position monitoring."""
    
    def test_get_monitoring_summary_stopped(self, trade_monitor):
        """Test getting summary when monitor is stopped."""
        summary = trade_monitor.get_monitoring_summary()
        
        assert isinstance(summary, dict)
        assert 'is_running' in summary
        assert 'active_trackers' in summary
        assert summary['is_running'] is False
        assert summary['active_trackers'] == 0
    
    def test_get_monitoring_summary_running(self, trade_monitor):
        """Test getting summary when monitor is running."""
        trade_monitor.start()
        # Wait until is_running becomes True, with timeout
        deadline = time.time() + 2.0
        while not trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not start within timeout")
            time.sleep(0.05)

        summary = trade_monitor.get_monitoring_summary()

        assert summary['is_running'] is True
        assert 'active_trackers' in summary
        assert 'pending_trades' in summary

        trade_monitor.stop()
        # Wait until is_running becomes False, with timeout
        deadline = time.time() + 2.0
        while trade_monitor.is_running:
            if time.time() > deadline:
                pytest.fail("TradeMonitor did not stop within timeout")
            time.sleep(0.05)
    
    def test_get_active_trades_empty(self, trade_monitor):
        """Test getting active trades when none exist."""
        trades = trade_monitor.get_active_trades()
        
        assert isinstance(trades, list)
        assert len(trades) == 0


class TestTradeMonitorIntegration:
    """Integration tests for full monitoring workflows."""
    
    @pytest.mark.skip(reason="Timing-dependent test - monitor may not detect position in time window")
    def test_monitor_with_position(self, trade_monitor, mock_platform):
        """Test monitoring with active position."""
        # Set up platform with a position
        mock_platform.get_positions.return_value = [
            {
                'product_id': 'BTC-USD',
                'side': 'LONG',
                'size': 0.1,
                'entry_price': 50000.0,
                'current_price': 51000.0
            }
        ]
        
        trade_monitor.start()
        time.sleep(1.5)  # Let it detect the position
        
        summary = trade_monitor.get_monitoring_summary()
        assert summary['is_running'] is True
        assert summary['active_trackers'] > 0
        
        trade_monitor.stop()
        time.sleep(0.5)
