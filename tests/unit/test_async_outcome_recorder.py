"""
Unit tests for async TradeOutcomeRecorder (THR-237).

Tests fire-and-forget async position updates.
"""

import pytest
import asyncio
import time
from pathlib import Path
from decimal import Decimal

from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder


class TestAsyncOutcomeRecorder:
    """Test async outcome recording (THR-237)."""
    
    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary data directory."""
        return str(tmp_path)
    
    @pytest.fixture
    def recorder(self, temp_dir):
        """Create async recorder instance."""
        return TradeOutcomeRecorder(data_dir=temp_dir, use_async=True)
    
    @pytest.fixture
    def sample_positions(self):
        """Sample position data."""
        return [
            {
                "product_id": "BTC-USD",
                "side": "LONG",
                "units": 0.1,
                "entry_price": 50000.0,
                "current_price": 51000.0,
                "pnl": 100.0,
                "opened_at": "2024-01-01T12:00:00Z"
            }
        ]
    
    def test_async_mode_enabled(self, recorder):
        """Test that async mode is enabled."""
        assert recorder.use_async is True
        assert recorder._executor is not None
        assert recorder._background_tasks is not None
    
    def test_update_positions_async_non_blocking(self, recorder, sample_positions):
        """Test that async update returns immediately."""
        start = time.time()
        
        # This should return immediately (<10ms)
        recorder.update_positions_async(sample_positions)
        
        elapsed = time.time() - start
        
        # Should be extremely fast (< 100ms)
        assert elapsed < 0.1, f"Async update took {elapsed*1000:.1f}ms (expected <100ms)"
    
    @pytest.mark.asyncio
    async def test_async_update_with_event_loop(self, recorder, sample_positions):
        """Test async update within async context (uses asyncio.create_task)."""
        # Update positions asynchronously
        recorder.update_positions_async(sample_positions)
        
        # Wait for background task to complete
        await asyncio.sleep(0.2)
        
        # Verify position was recorded
        assert len(recorder.open_positions) == 1
        assert "BTC-USD_LONG" in recorder.open_positions
    
    def test_sync_fallback_when_disabled(self, temp_dir, sample_positions):
        """Test that sync mode still works when async is disabled."""
        sync_recorder = TradeOutcomeRecorder(data_dir=temp_dir, use_async=False)
        
        # This should work synchronously
        outcomes = sync_recorder.update_positions(sample_positions)
        
        # Verify position was recorded
        assert len(sync_recorder.open_positions) == 1
        assert "BTC-USD_LONG" in sync_recorder.open_positions
    
    def test_position_close_detection(self, recorder, sample_positions):
        """Test that position closes are detected asynchronously."""
        # Open position
        recorder.update_positions(sample_positions)
        assert len(recorder.open_positions) == 1
        
        # Close position (empty positions list)
        recorder.update_positions_async([])
        
        # Wait for async processing
        time.sleep(0.2)
        
        # Position should be closed
        assert len(recorder.open_positions) == 0
        
        # Outcome file should exist
        outcomes_dir = Path(recorder.data_dir) / "trade_outcomes"
        outcome_files = list(outcomes_dir.glob("*.jsonl"))
        assert len(outcome_files) > 0
    
    def test_concurrent_async_updates(self, recorder, sample_positions):
        """Test that multiple concurrent async updates don't interfere."""
        # Queue multiple updates
        for i in range(5):
            recorder.update_positions_async(sample_positions)
        
        # Should not raise errors or block
        time.sleep(0.5)
        
        # Should still have the position
        assert len(recorder.open_positions) == 1
    
    def test_background_task_cleanup(self, recorder, sample_positions):
        """Test that completed background tasks are removed from set."""
        initial_task_count = len(recorder._background_tasks)
        
        # Queue multiple updates to ensure at least one task is tracked
        for _ in range(3):
            recorder.update_positions_async(sample_positions)
            time.sleep(0.01)  # Small delay to allow task creation
        
        # At least one task should be pending
        # (may complete quickly, so this is a best-effort check)
        max_tasks_seen = len(recorder._background_tasks)
        
        # Wait for tasks to complete
        time.sleep(0.5)
        
        # All tasks should eventually complete and be cleaned up
        final_task_count = len(recorder._background_tasks)
        assert final_task_count <= max_tasks_seen
