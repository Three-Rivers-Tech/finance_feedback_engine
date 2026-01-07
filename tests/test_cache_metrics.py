"""Tests for cache metrics tracking."""

import time
from datetime import datetime

import pytest

from finance_feedback_engine.utils.cache_metrics import CacheMetrics


class TestCacheMetrics:
    """Test suite for CacheMetrics class."""

    @pytest.fixture
    def metrics(self):
        """Create a fresh CacheMetrics instance."""
        return CacheMetrics()

    def test_init(self):
        """Test CacheMetrics initialization."""
        metrics = CacheMetrics()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.total_requests == 0
        assert metrics.cache_sizes == {}
        assert metrics.cache_names == {}
        assert isinstance(metrics.start_time, datetime)

    def test_record_hit(self, metrics):
        """Test recording cache hit."""
        metrics.record_hit("portfolio")

        assert metrics.hits == 1
        assert metrics.misses == 0
        assert metrics.total_requests == 1
        assert "portfolio" in metrics.cache_names
        assert metrics.cache_names["portfolio"]["hits"] == 1
        assert metrics.cache_names["portfolio"]["misses"] == 0

    def test_record_miss(self, metrics):
        """Test recording cache miss."""
        metrics.record_miss("portfolio")

        assert metrics.hits == 0
        assert metrics.misses == 1
        assert metrics.total_requests == 1
        assert "portfolio" in metrics.cache_names
        assert metrics.cache_names["portfolio"]["hits"] == 0
        assert metrics.cache_names["portfolio"]["misses"] == 1

    def test_record_multiple_hits_and_misses(self, metrics):
        """Test recording multiple hits and misses."""
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")
        metrics.record_hit("market_data")
        metrics.record_miss("market_data")

        assert metrics.hits == 3
        assert metrics.misses == 2
        assert metrics.total_requests == 5

        # Check per-cache stats
        assert metrics.cache_names["portfolio"]["hits"] == 2
        assert metrics.cache_names["portfolio"]["misses"] == 1
        assert metrics.cache_names["market_data"]["hits"] == 1
        assert metrics.cache_names["market_data"]["misses"] == 1

    def test_update_cache_size(self, metrics):
        """Test updating cache size."""
        metrics.update_cache_size("portfolio", 100)
        metrics.update_cache_size("market_data", 50)

        assert metrics.cache_sizes["portfolio"] == 100
        assert metrics.cache_sizes["market_data"] == 50

    def test_get_hit_rate_zero_requests(self, metrics):
        """Test hit rate calculation with zero requests."""
        hit_rate = metrics.get_hit_rate()

        assert hit_rate == 0.0

    def test_get_hit_rate_all_hits(self, metrics):
        """Test hit rate with all hits."""
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")

        hit_rate = metrics.get_hit_rate()

        assert hit_rate == 100.0

    def test_get_hit_rate_all_misses(self, metrics):
        """Test hit rate with all misses."""
        metrics.record_miss("portfolio")
        metrics.record_miss("portfolio")

        hit_rate = metrics.get_hit_rate()

        assert hit_rate == 0.0

    def test_get_hit_rate_mixed(self, metrics):
        """Test hit rate with mixed hits and misses."""
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")
        metrics.record_miss("portfolio")

        hit_rate = metrics.get_hit_rate()

        assert hit_rate == 50.0

    def test_get_cache_hit_rate_nonexistent_cache(self, metrics):
        """Test hit rate for non-existent cache."""
        hit_rate = metrics.get_cache_hit_rate("nonexistent")

        assert hit_rate == 0.0

    def test_get_cache_hit_rate_specific_cache(self, metrics):
        """Test hit rate for specific cache."""
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")

        hit_rate = metrics.get_cache_hit_rate("portfolio")

        assert hit_rate == 75.0  # 3 hits out of 4 total

    def test_get_cache_hit_rate_multiple_caches(self, metrics):
        """Test hit rates for multiple caches independently."""
        # Portfolio: 3/4 = 75%
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")

        # Market data: 1/3 = 33.33%
        metrics.record_hit("market_data")
        metrics.record_miss("market_data")
        metrics.record_miss("market_data")

        portfolio_rate = metrics.get_cache_hit_rate("portfolio")
        market_rate = metrics.get_cache_hit_rate("market_data")

        assert portfolio_rate == 75.0
        assert abs(market_rate - 33.33) < 0.01

    def test_get_summary(self, metrics):
        """Test getting comprehensive summary."""
        metrics.record_hit("portfolio")
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")
        metrics.update_cache_size("portfolio", 50)

        summary = metrics.get_summary()

        # Check overall stats
        assert summary["overall"]["hits"] == 2
        assert summary["overall"]["misses"] == 1
        assert summary["overall"]["total_requests"] == 3
        assert abs(summary["overall"]["hit_rate_percent"] - 66.67) < 0.01
        assert summary["overall"]["uptime_seconds"] >= 0

        # Check per-cache stats
        assert "portfolio" in summary["per_cache"]
        assert summary["per_cache"]["portfolio"]["hits"] == 2
        assert summary["per_cache"]["portfolio"]["misses"] == 1
        assert summary["per_cache"]["portfolio"]["total_requests"] == 3
        assert summary["per_cache"]["portfolio"]["size"] == 50

        # Check timestamp
        assert "timestamp" in summary

    def test_get_summary_empty_metrics(self, metrics):
        """Test getting summary with no data."""
        summary = metrics.get_summary()

        assert summary["overall"]["hits"] == 0
        assert summary["overall"]["misses"] == 0
        assert summary["overall"]["total_requests"] == 0
        assert summary["overall"]["hit_rate_percent"] == 0.0
        assert summary["per_cache"] == {}

    def test_log_summary(self, metrics, caplog):
        """Test logging summary."""
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")

        metrics.log_summary()

        # Check that summary was logged
        assert any("Cache Performance Summary" in record.message for record in caplog.records)

    def test_reset(self, metrics):
        """Test resetting metrics."""
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")
        metrics.update_cache_size("portfolio", 100)

        metrics.reset()

        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.total_requests == 0
        assert metrics.cache_sizes == {}
        assert metrics.cache_names == {}

    def test_get_efficiency_score_zero_requests(self, metrics):
        """Test efficiency score with zero requests."""
        score = metrics.get_efficiency_score()

        assert score == 0.0

    def test_get_efficiency_score_high_hit_rate(self, metrics):
        """Test efficiency score with high hit rate."""
        # Simulate 10 hits and 0 misses
        for _ in range(10):
            metrics.record_hit("portfolio")

        score = metrics.get_efficiency_score()

        # Should be high due to 100% hit rate
        assert score >= 70.0

    def test_get_efficiency_score_low_hit_rate(self, metrics):
        """Test efficiency score with low hit rate."""
        # Simulate 1 hit and 9 misses
        metrics.record_hit("portfolio")
        for _ in range(9):
            metrics.record_miss("portfolio")

        score = metrics.get_efficiency_score()

        # Should be low due to 10% hit rate
        assert score <= 30.0

    def test_get_efficiency_score_capped_at_100(self, metrics):
        """Test that efficiency score is capped at 100."""
        # Simulate many hits to try to exceed 100
        for _ in range(1000):
            metrics.record_hit("portfolio")

        score = metrics.get_efficiency_score()

        assert score <= 100.0

    def test_requests_per_second_calculation(self, metrics):
        """Test requests per second calculation."""
        metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")

        time.sleep(0.1)  # Wait a bit for uptime

        summary = metrics.get_summary()

        # Should have positive requests per second
        assert summary["overall"]["requests_per_second"] > 0

    def test_uptime_tracking(self, metrics):
        """Test that uptime is tracked."""
        time.sleep(0.1)

        summary = metrics.get_summary()

        assert summary["overall"]["uptime_seconds"] >= 0.1
        assert summary["overall"]["uptime_hours"] >= 0

    def test_multiple_cache_names(self, metrics):
        """Test tracking multiple distinct caches."""
        metrics.record_hit("portfolio")
        metrics.record_hit("market_data")
        metrics.record_hit("positions")
        metrics.record_miss("trades")

        assert len(metrics.cache_names) == 4
        assert "portfolio" in metrics.cache_names
        assert "market_data" in metrics.cache_names
        assert "positions" in metrics.cache_names
        assert "trades" in metrics.cache_names

    def test_cache_size_updates(self, metrics):
        """Test that cache sizes can be updated multiple times."""
        metrics.update_cache_size("portfolio", 10)
        metrics.update_cache_size("portfolio", 20)
        metrics.update_cache_size("portfolio", 30)

        assert metrics.cache_sizes["portfolio"] == 30

    def test_per_cache_independence(self, metrics):
        """Test that per-cache stats are independent."""
        # Portfolio: high hit rate
        for _ in range(9):
            metrics.record_hit("portfolio")
        metrics.record_miss("portfolio")

        # Market data: low hit rate
        metrics.record_hit("market_data")
        for _ in range(9):
            metrics.record_miss("market_data")

        portfolio_rate = metrics.get_cache_hit_rate("portfolio")
        market_rate = metrics.get_cache_hit_rate("market_data")

        assert portfolio_rate == 90.0
        assert market_rate == 10.0
        # Overall hit rate should be 50%
        assert metrics.get_hit_rate() == 50.0

    def test_summary_timestamp_format(self, metrics):
        """Test that summary timestamp is in ISO format."""
        metrics.record_hit("portfolio")
        summary = metrics.get_summary()

        timestamp_str = summary["timestamp"]
        # Should be able to parse as ISO format
        timestamp = datetime.fromisoformat(timestamp_str)
        assert isinstance(timestamp, datetime)
