"""Tests for utils.cost_tracker module."""

import pytest
import tempfile
from pathlib import Path
from finance_feedback_engine.utils.cost_tracker import (
    CostTracker,
    log_premium_call,
    check_budget,
    get_cost_tracker
)


class TestCostTracker:
    """Test suite for CostTracker class."""
    
    def test_init(self, tmp_path):
        """Test CostTracker initialization."""
        tracker = CostTracker(data_dir=str(tmp_path))
        assert tracker is not None
        assert (tmp_path / "api_costs").exists()
    
    def test_log_premium_call(self, tmp_path):
        """Test logging a premium API call."""
        tracker = CostTracker(data_dir=str(tmp_path))
        
        tracker.log_premium_call(
            asset='BTCUSD',
            asset_type='crypto',
            phase='phase2',
            primary_provider='cli',
            codex_called=False,
            escalation_reason='low_confidence',
            cost_estimate=0.05
        )
        
        # Check that log file was created
        log_files = list((tmp_path / "api_costs").glob("*.json"))
        assert len(log_files) > 0
    
    def test_get_today_costs(self, tmp_path):
        """Test getting today's costs."""
        tracker = CostTracker(data_dir=str(tmp_path))
        
        # Log some calls
        tracker.log_premium_call(
            asset='BTCUSD',
            asset_type='crypto',
            phase='phase2',
            cost_estimate=0.05
        )
        tracker.log_premium_call(
            asset='ETHUSD',
            asset_type='crypto',
            phase='phase2',
            cost_estimate=0.03
        )
        
        costs = tracker.get_today_costs()
        assert costs >= 0.08
    
    def test_get_cost_summary(self, tmp_path):
        """Test getting cost summary."""
        tracker = CostTracker(data_dir=str(tmp_path))
        
        tracker.log_premium_call(
            asset='BTCUSD',
            asset_type='crypto',
            phase='phase2',
            primary_provider='cli',
            cost_estimate=0.05
        )
        
        summary = tracker.get_cost_summary()
        assert 'total_cost' in summary or 'calls' in summary


class TestModuleFunctions:
    """Test module-level functions."""
    
    def test_log_premium_call_function(self, tmp_path, monkeypatch):
        """Test the module-level log_premium_call function."""
        # Use temp dir for testing
        monkeypatch.setenv('DATA_DIR', str(tmp_path))
        
        log_premium_call(
            asset='BTCUSD',
            asset_type='crypto',
            phase='phase2',
            cost_estimate=0.05
        )
        
        # Verify it doesn't raise an exception
        assert True
    
    def test_check_budget_function(self):
        """Test the check_budget function."""
        # Should return True/False or raise exception on over-budget
        result = check_budget(daily_limit=100.0)
        assert isinstance(result, bool)
    
    def test_get_cost_tracker_singleton(self):
        """Test get_cost_tracker returns a CostTracker instance."""
        tracker = get_cost_tracker()
        assert isinstance(tracker, CostTracker)
        
        # Should return same instance (singleton pattern)
        tracker2 = get_cost_tracker()
        assert tracker is tracker2
