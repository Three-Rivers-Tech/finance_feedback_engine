"""Cache performance metrics collection (Phase 2 optimization)."""

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CacheMetrics:
    """Track cache performance metrics for monitoring and optimization."""

    def __init__(self):
        """Initialize cache metrics tracker."""
        self.hits = 0
        self.misses = 0
        self.total_requests = 0
        self.cache_sizes: Dict[str, int] = {}
        self.start_time = datetime.now()
        self.cache_names: Dict[str, Dict[str, int]] = {}  # Per-cache stats

    def record_hit(self, cache_name: str) -> None:
        """
        Record cache hit.

        Args:
            cache_name: Name of the cache (e.g., 'portfolio', 'market_data')
        """
        self.hits += 1
        self.total_requests += 1

        # Track per-cache stats
        if cache_name not in self.cache_names:
            self.cache_names[cache_name] = {"hits": 0, "misses": 0}
        self.cache_names[cache_name]["hits"] += 1

        logger.debug(f"Cache hit: {cache_name}")

    def record_miss(self, cache_name: str) -> None:
        """
        Record cache miss.

        Args:
            cache_name: Name of the cache
        """
        self.misses += 1
        self.total_requests += 1

        # Track per-cache stats
        if cache_name not in self.cache_names:
            self.cache_names[cache_name] = {"hits": 0, "misses": 0}
        self.cache_names[cache_name]["misses"] += 1

        logger.debug(f"Cache miss: {cache_name}")

    def update_cache_size(self, cache_name: str, size: int) -> None:
        """
        Update cache size metric.

        Args:
            cache_name: Name of the cache
            size: Current size of the cache
        """
        self.cache_sizes[cache_name] = size

    def get_hit_rate(self) -> float:
        """
        Calculate overall cache hit rate percentage.

        Returns:
            Hit rate as percentage (0-100)
        """
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100

    def get_cache_hit_rate(self, cache_name: str) -> float:
        """
        Calculate hit rate for a specific cache.

        Args:
            cache_name: Name of the cache

        Returns:
            Hit rate as percentage (0-100)
        """
        if cache_name not in self.cache_names:
            return 0.0

        cache_stats = self.cache_names[cache_name]
        total = cache_stats["hits"] + cache_stats["misses"]

        if total == 0:
            return 0.0

        return (cache_stats["hits"] / total) * 100

    def get_summary(self) -> Dict[str, Any]:
        """
        Get cache performance summary.

        Returns:
            Dictionary with comprehensive cache metrics
        """
        uptime = (datetime.now() - self.start_time).total_seconds()

        # Calculate per-cache hit rates
        per_cache_stats = {}
        for cache_name, stats in self.cache_names.items():
            total = stats["hits"] + stats["misses"]
            hit_rate = (stats["hits"] / total * 100) if total > 0 else 0.0
            per_cache_stats[cache_name] = {
                "hits": stats["hits"],
                "misses": stats["misses"],
                "total_requests": total,
                "hit_rate_percent": hit_rate,
                "size": self.cache_sizes.get(cache_name, 0),
            }

        return {
            "overall": {
                "hits": self.hits,
                "misses": self.misses,
                "total_requests": self.total_requests,
                "hit_rate_percent": self.get_hit_rate(),
                "uptime_seconds": uptime,
                "uptime_hours": uptime / 3600,
                "requests_per_second": (
                    self.total_requests / uptime if uptime > 0 else 0
                ),
            },
            "per_cache": per_cache_stats,
            "timestamp": datetime.now().isoformat(),
        }

    def log_summary(self) -> None:
        """Log cache performance summary."""
        summary = self.get_summary()
        overall = summary["overall"]

        logger.info(
            f"Cache Performance Summary: {overall['hit_rate_percent']:.1f}% hit rate "
            f"({overall['hits']} hits, {overall['misses']} misses) "
            f"over {overall['uptime_hours']:.1f} hours"
        )

        # Log per-cache stats
        for cache_name, stats in summary["per_cache"].items():
            logger.info(
                f"  {cache_name}: {stats['hit_rate_percent']:.1f}% hit rate "
                f"({stats['hits']}/{stats['total_requests']} requests, size: {stats['size']})"
            )

    def reset(self) -> None:
        """Reset all metrics (useful for testing or periodic resets)."""
        self.hits = 0
        self.misses = 0
        self.total_requests = 0
        self.cache_sizes.clear()
        self.cache_names.clear()
        self.start_time = datetime.now()
        logger.info("Cache metrics reset")

    def get_efficiency_score(self) -> float:
        """
        Calculate cache efficiency score (0-100).

        Combines hit rate and request volume to assess cache effectiveness.

        Returns:
            Efficiency score (0-100)
        """
        hit_rate = self.get_hit_rate()
        if self.total_requests == 0:
            return 0.0

        # Efficiency score considers both hit rate and usage
        # Higher usage with high hit rate = better efficiency
        uptime = (datetime.now() - self.start_time).total_seconds()
        requests_per_minute = (self.total_requests / uptime) * 60 if uptime > 0 else 0

        # Normalize requests per minute (assume 10 requests/min is good)
        usage_factor = min(requests_per_minute / 10, 1.0)

        # Weighted score: 70% hit rate, 30% usage
        efficiency = (hit_rate * 0.7) + (usage_factor * 100 * 0.3)

        return min(efficiency, 100.0)
