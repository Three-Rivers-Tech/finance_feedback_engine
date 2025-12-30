"""
Pair Universe Cache for Exchange Discovery.

Caches discovered trading pairs from exchanges to minimize API calls.
Uses time-to-live (TTL) caching with configurable expiration.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PairUniverseCache:
    """
    Cache discovered pairs with TTL to avoid repeated API calls.

    Maintains separate caches for each exchange (coinbase, oanda, etc.)
    with configurable time-to-live for freshness.

    Attributes:
        ttl_seconds: Cache expiration time in seconds
        cache: Dictionary mapping exchange name to (pairs, timestamp) tuple
    """

    def __init__(self, ttl_hours: int = 24):
        """
        Initialize Pair Universe Cache.

        Args:
            ttl_hours: Cache time-to-live in hours (default: 24)
        """
        if ttl_hours <= 0:
            raise ValueError(f"ttl_hours must be positive, got {ttl_hours}")
        self.ttl_seconds = ttl_hours * 3600
        self.cache: Dict[str, Tuple[List[str], float]] = {}

        logger.info(
            f"PairUniverseCache initialized (TTL: {ttl_hours}h = {self.ttl_seconds}s)"
        )

    def get(self, exchange: str) -> Optional[List[str]]:
        """
        Get cached pairs for an exchange if fresh.

        Args:
            exchange: Exchange name ('coinbase', 'oanda', or 'all')

        Returns:
            List of cached pairs if cache is fresh, None otherwise
        """
        if exchange not in self.cache:
            logger.debug(f"Cache miss: no entry for '{exchange}'")
            return None

        pairs, timestamp = self.cache[exchange]
        age_seconds = time.time() - timestamp

        if age_seconds < self.ttl_seconds:
            logger.debug(
                f"Cache hit: '{exchange}' ({len(pairs)} pairs, "
                f"age: {age_seconds:.0f}s / {self.ttl_seconds}s)"
            )
            return pairs
        else:
            logger.debug(
                f"Cache expired: '{exchange}' "
                f"(age: {age_seconds:.0f}s > TTL: {self.ttl_seconds}s)"
            )
            # Remove expired entry
            del self.cache[exchange]
            return None

    def set(self, exchange: str, pairs: List[str]):
        """
        Cache pairs for an exchange with current timestamp.

        Args:
            exchange: Exchange name ('coinbase', 'oanda', or 'all')
            pairs: List of discovered pairs
        """
        timestamp = time.time()
        self.cache[exchange] = (pairs, timestamp)

        logger.info(
            f"Cached {len(pairs)} pairs for '{exchange}' "
            f"(expires in {self.ttl_seconds}s)"
        )

    def invalidate(self, exchange: Optional[str] = None):
        """
        Invalidate cache entries.

        Args:
            exchange: Exchange to invalidate. If None, clears all caches.
        """
        if exchange is None:
            # Clear all caches
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"Invalidated all cache entries ({count} exchanges)")
        elif exchange in self.cache:
            # Clear specific exchange
            del self.cache[exchange]
            logger.info(f"Invalidated cache for '{exchange}'")
        else:
            logger.debug(f"No cache entry to invalidate for '{exchange}'")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats:
            {
                'total_entries': int,
                'exchanges': {
                    'coinbase': {'pairs_count': 50, 'age_seconds': 1200},
                    'oanda': {'pairs_count': 30, 'age_seconds': 800}
                }
            }
        """
        stats = {"total_entries": len(self.cache), "exchanges": {}}

        current_time = time.time()

        for exchange, (pairs, timestamp) in self.cache.items():
            age_seconds = current_time - timestamp
            stats["exchanges"][exchange] = {
                "pairs_count": len(pairs),
                "age_seconds": age_seconds,
                "is_fresh": age_seconds < self.ttl_seconds,
            }

        return stats
