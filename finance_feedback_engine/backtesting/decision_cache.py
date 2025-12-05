"""Decision cache for backtesting using SQLite for persistence.

Caches AI decisions based on market conditions to avoid redundant queries.
Particularly useful for backtesting where identical market states may occur.
"""

import sqlite3
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DecisionCache:
    """
    SQLite-backed cache for trading decisions.

    Caches decisions based on asset pair, timestamp, and market data hash.
    Persists across backtest runs for maximum efficiency.
    """

    def __init__(self, db_path: str = "data/cache/backtest_decisions.db"):
        """
        Initialize decision cache with SQLite backend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        # Track stats for current session
        self.session_hits = 0
        self.session_misses = 0

        logger.info(f"Decision cache initialized at {db_path}")

    def _init_db(self):
        """Create database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    cache_key TEXT PRIMARY KEY,
                    asset_pair TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    market_hash TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_asset_timestamp
                ON decisions(asset_pair, timestamp)
            """)
        conn.close()

    def _hash_market_data(self, market_data: Dict[str, Any]) -> str:
        """
        Generate hash of market data for cache key.

        Args:
            market_data: Market data dictionary

        Returns:
            MD5 hash of sorted market data
        """
        # Extract relevant fields for hashing (exclude timestamp which is used separately)
        hashable_fields = {
            k: v for k, v in market_data.items()
            if k not in ['timestamp', 'historical_data']  # Exclude large/temporal fields
        }

        # Convert to sorted JSON string for consistent hashing
        json_str = json.dumps(hashable_fields, sort_keys=True, default=str)

        # Generate MD5 hash
        return hashlib.md5(json_str.encode()).hexdigest()

    def build_market_hash(self, market_data: Dict[str, Any]) -> str:
        """Public wrapper to compute the market hash used in cache keys."""
        return self._hash_market_data(market_data)

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached decision by key.

        Args:
            cache_key: Cache key to lookup

        Returns:
            Cached decision dict or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT decision_json FROM decisions WHERE cache_key = ?",
            (cache_key,)
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            self.session_hits += 1
            return json.loads(result[0])
        else:
            self.session_misses += 1
            return None

    def put(self, cache_key: str, decision: Dict[str, Any],
            asset_pair: str, timestamp: str, market_hash: str):
        """
        Store decision in cache.

        Args:
            cache_key: Unique cache key
            decision: Decision dictionary to cache
            asset_pair: Asset pair for indexing
            timestamp: Timestamp for indexing
            market_hash: Market data hash for indexing
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        decision_json = json.dumps(decision, default=str)

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO decisions
                (cache_key, asset_pair, timestamp, market_hash, decision_json)
                VALUES (?, ?, ?, ?, ?)
            """, (cache_key, asset_pair, timestamp, market_hash, decision_json))

            conn.commit()
        except Exception as e:
            logger.error(f"Failed to cache decision: {e}")
            conn.rollback()
        finally:
            conn.close()

    def generate_cache_key(self, asset_pair: str, timestamp: str,
                          market_data: Dict[str, Any]) -> str:
        """
        Generate cache key from components.

        Args:
            asset_pair: Asset pair symbol
            timestamp: Timestamp string
            market_data: Market data dictionary

        Returns:
            Cache key string
        """
        market_hash = self._hash_market_data(market_data)
        return f"{asset_pair}_{timestamp}_{market_hash}"

    def build_cache_key(self, asset_pair: str, timestamp: str,
                        market_data: Dict[str, Any]) -> str:
        """Alias for generate_cache_key for clarity in public usage."""
        return self.generate_cache_key(asset_pair, timestamp, market_data)

    def clear_old(self, days: int = 90):
        """
        Clear cached decisions older than specified days.

        Args:
            days: Number of days to retain
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute(
            "DELETE FROM decisions WHERE created_at < ?",
            (cutoff_date,)
        )

        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Cleared {deleted_count} cached decisions older than {days} days")

        return deleted_count

    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get total cached decisions
        cursor.execute("SELECT COUNT(*) FROM decisions")
        total_cached = cursor.fetchone()[0]

        # Get cache by asset pair
        cursor.execute("""
            SELECT asset_pair, COUNT(*) as count
            FROM decisions
            GROUP BY asset_pair
            ORDER BY count DESC
        """)
        by_asset = dict(cursor.fetchall())

        conn.close()

        # Calculate hit rate for current session
        total_queries = self.session_hits + self.session_misses
        hit_rate = (self.session_hits / total_queries) if total_queries > 0 else 0.0

        return {
            'total_cached': total_cached,
            'session_hits': self.session_hits,
            'session_misses': self.session_misses,
            'hit_rate': hit_rate,
            'by_asset_pair': by_asset
        }

    def clear_all(self) -> int:
        """Clear all cached decisions (use with caution)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("DELETE FROM decisions")

            deleted_count = cursor.rowcount
            conn.commit()

        logger.warning(f"Cleared ALL {deleted_count} cached decisions")

        return deleted_count
