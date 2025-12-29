"""
Unit tests for PairUniverseCache.

Tests TTL caching for discovered trading pairs.
"""

import pytest
import time
from finance_feedback_engine.pair_selection.core.pair_universe import PairUniverseCache


class TestPairUniverseCache:
    """Test suite for PairUniverseCache."""

    @pytest.fixture
    def cache(self):
        """Create PairUniverseCache with 1-hour TTL."""
        return PairUniverseCache(ttl_hours=1)

    def test_initialization(self, cache):
        """Test cache initialization."""
        assert cache.ttl_seconds == 3600  # 1 hour in seconds
        assert isinstance(cache.cache, dict)
        assert len(cache.cache) == 0

    def test_set_and_get(self, cache):
        """Test basic set and get operations."""
        pairs = ['BTCUSD', 'ETHUSD', 'EURUSD']
        
        # Set cache
        cache.set('coinbase', pairs)
        
        # Get cache
        retrieved = cache.get('coinbase')
        
        assert retrieved == pairs
        assert isinstance(retrieved, list)

    def test_get_nonexistent_exchange(self, cache):
        """Test get for exchange that hasn't been cached."""
        result = cache.get('nonexistent')
        assert result is None

    def test_multiple_exchanges(self, cache):
        """Test caching multiple exchanges independently."""
        coinbase_pairs = ['BTCUSD', 'ETHUSD']
        oanda_pairs = ['EURUSD', 'GBPJPY']
        
        cache.set('coinbase', coinbase_pairs)
        cache.set('oanda', oanda_pairs)
        
        # Both should be retrievable
        assert cache.get('coinbase') == coinbase_pairs
        assert cache.get('oanda') == oanda_pairs

    def test_overwrite_cache(self, cache):
        """Test that setting cache for same exchange overwrites old data."""
        old_pairs = ['BTCUSD', 'ETHUSD']
        new_pairs = ['SOLUSD', 'ADAUSD', 'XRPUSD']
        
        cache.set('coinbase', old_pairs)
        assert cache.get('coinbase') == old_pairs
        
        # Overwrite
        cache.set('coinbase', new_pairs)
        assert cache.get('coinbase') == new_pairs

    def test_empty_pair_list(self, cache):
        """Test caching empty pair list."""
        cache.set('empty_exchange', [])
        
        result = cache.get('empty_exchange')
        assert result == []
        assert isinstance(result, list)

    def test_cache_independence(self):
        """Test that multiple cache instances are independent."""
        cache1 = PairUniverseCache(ttl_hours=1)
        cache2 = PairUniverseCache(ttl_hours=1)
        
        cache1.set('coinbase', ['BTCUSD'])
        
        # cache2 should not have this data
        assert cache2.get('coinbase') is None
