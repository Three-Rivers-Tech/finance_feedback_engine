"""
Tests for Pair Discovery Filters and Whitelist System.

Validates that:
- Whitelist mode takes precedence over discovery
- Discovery filters block low-liquidity/suspicious pairs
- Configuration properly loads from config.yaml
- Filter thresholds work as expected
"""

import pytest
from finance_feedback_engine.pair_selection.core.discovery_filters import (
    DiscoveryFilterConfig,
    PairDiscoveryFilter,
    PairMetrics,
    WhitelistConfig,
)


class TestWhitelistMode:
    """Test whitelist-based pair selection."""

    def test_whitelist_enabled_returns_whitelisted_pairs_only(self):
        """Whitelist mode should return only whitelisted pairs."""
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )
        discovery_config = DiscoveryFilterConfig(enabled=True)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        # Discovered pairs include non-whitelisted entries
        discovered = ["BTCUSD", "ETHUSD", "SHIBUSD", "DOGEUSD"]

        filtered, rejections = filter_obj.filter_pairs(discovered)

        assert filtered == ["BTCUSD", "ETHUSD"]
        assert "SHIBUSD" in rejections
        assert rejections["SHIBUSD"] == "NOT_IN_WHITELIST"
        assert "DOGEUSD" in rejections

    def test_whitelist_empty_discovered_pairs(self):
        """Whitelist mode with empty discovered pairs."""
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )
        discovery_config = DiscoveryFilterConfig(enabled=True)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)
        filtered, rejections = filter_obj.filter_pairs([])

        assert filtered == ["BTCUSD", "ETHUSD"]
        assert len(rejections) == 0

    def test_whitelist_disabled_uses_discovery_filters(self):
        """When whitelist disabled, discovery filters should apply."""
        whitelist_config = WhitelistConfig(
            enabled=False,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            volume_threshold_usd=50_000_000,
        )

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "BTCUSD": PairMetrics(
                pair="BTCUSD",
                volume_24h_usd=100_000_000,  # Above threshold
                listing_age_days=3000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
            "SHIBUSD": PairMetrics(
                pair="SHIBUSD",
                volume_24h_usd=10_000_000,  # Below threshold
                listing_age_days=500,
                bid_ask_spread_pct=0.01,
                order_book_depth_usd=5_000_000,
                venue_count=2,
                suspicious_pattern_score=0.3,
            ),
        }

        discovered = ["BTCUSD", "SHIBUSD"]
        filtered, rejections = filter_obj.filter_pairs(discovered, pair_metrics)

        assert "BTCUSD" in filtered
        assert "SHIBUSD" not in filtered
        assert "SHIBUSD" in rejections
        assert "LOW_VOLUME" in rejections["SHIBUSD"]


class TestDiscoveryFilters:
    """Test discovery filter thresholds."""

    def test_volume_threshold_filter(self):
        """Pairs below volume threshold should be rejected."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            volume_threshold_usd=50_000_000,
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "BTCUSD": PairMetrics(
                pair="BTCUSD",
                volume_24h_usd=100_000_000,
                listing_age_days=3000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
            "LOWVOL": PairMetrics(
                pair="LOWVOL",
                volume_24h_usd=1_000_000,
                listing_age_days=3000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(
            ["BTCUSD", "LOWVOL"], pair_metrics
        )

        assert "BTCUSD" in filtered
        assert "LOWVOL" not in filtered
        assert "LOW_VOLUME" in rejections["LOWVOL"]

    def test_listing_age_filter(self):
        """Pairs below minimum listing age should be rejected."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            min_listing_age_days=365,
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "ESTABLISHED": PairMetrics(
                pair="ESTABLISHED",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
            "NEWPAIR": PairMetrics(
                pair="NEWPAIR",
                volume_24h_usd=100_000_000,
                listing_age_days=30,  # Too new
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(
            ["ESTABLISHED", "NEWPAIR"], pair_metrics
        )

        assert "ESTABLISHED" in filtered
        assert "NEWPAIR" not in filtered
        assert "TOO_NEW" in rejections["NEWPAIR"]

    def test_spread_threshold_filter(self):
        """Pairs with spreads above threshold should be rejected."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            max_spread_pct=0.001,  # 0.1%
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "TIGHT_SPREAD": PairMetrics(
                pair="TIGHT_SPREAD",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,  # Tight
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
            "WIDE_SPREAD": PairMetrics(
                pair="WIDE_SPREAD",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.01,  # Wide
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(
            ["TIGHT_SPREAD", "WIDE_SPREAD"], pair_metrics
        )

        assert "TIGHT_SPREAD" in filtered
        assert "WIDE_SPREAD" not in filtered
        assert "WIDE_SPREAD" in rejections
        assert "WIDE_SPREAD" in rejections["WIDE_SPREAD"]

    def test_depth_threshold_filter(self):
        """Pairs with shallow order books should be rejected."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            min_depth_usd=10_000_000,
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "DEEP": PairMetrics(
                pair="DEEP",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,  # Deep
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
            "SHALLOW": PairMetrics(
                pair="SHALLOW",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=1_000_000,  # Shallow
                venue_count=5,
                suspicious_pattern_score=0.1,
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(
            ["DEEP", "SHALLOW"], pair_metrics
        )

        assert "DEEP" in filtered
        assert "SHALLOW" not in filtered
        assert "SHALLOW_DEPTH" in rejections["SHALLOW"]

    def test_venue_count_filter(self):
        """Pairs on too few venues should be rejected."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            min_venue_count=3,
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "MULTI_VENUE": PairMetrics(
                pair="MULTI_VENUE",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,  # Multiple venues
                suspicious_pattern_score=0.1,
            ),
            "SINGLE_VENUE": PairMetrics(
                pair="SINGLE_VENUE",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=1,  # Too few venues
                suspicious_pattern_score=0.1,
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(
            ["MULTI_VENUE", "SINGLE_VENUE"], pair_metrics
        )

        assert "MULTI_VENUE" in filtered
        assert "SINGLE_VENUE" not in filtered
        assert "INSUFFICIENT_VENUES" in rejections["SINGLE_VENUE"]

    def test_suspicious_pattern_filter(self):
        """Pairs with high suspicious pattern scores should be rejected."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            exclude_suspicious_patterns=True,
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "CLEAN": PairMetrics(
                pair="CLEAN",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.3,  # Low suspicion
            ),
            "SUSPICIOUS": PairMetrics(
                pair="SUSPICIOUS",
                volume_24h_usd=100_000_000,
                listing_age_days=1000,
                bid_ask_spread_pct=0.0005,
                order_book_depth_usd=50_000_000,
                venue_count=5,
                suspicious_pattern_score=0.9,  # High suspicion
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(
            ["CLEAN", "SUSPICIOUS"], pair_metrics
        )

        assert "CLEAN" in filtered
        assert "SUSPICIOUS" not in filtered
        assert "SUSPICIOUS_PATTERN" in rejections["SUSPICIOUS"]

    def test_discovery_filters_disabled(self):
        """When discovery filters disabled, all pairs should pass."""
        discovery_config = DiscoveryFilterConfig(enabled=False)
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        pair_metrics = {
            "LOWVOL": PairMetrics(
                pair="LOWVOL",
                volume_24h_usd=1_000_000,
                listing_age_days=10,
                bid_ask_spread_pct=0.5,
                order_book_depth_usd=100_000,
                venue_count=1,
                suspicious_pattern_score=0.95,
            ),
        }

        filtered, rejections = filter_obj.filter_pairs(["LOWVOL"], pair_metrics)

        assert "LOWVOL" in filtered
        assert len(rejections) == 0


class TestAutoWhitelistAddition:
    """Test auto-add to whitelist functionality."""

    def test_auto_add_to_whitelist_enabled(self):
        """When auto_add enabled, discovered pairs should be added to whitelist."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            auto_add_to_whitelist=True,
        )
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD"],
        )

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        # Add new pair to whitelist
        result = filter_obj.add_to_whitelist("ETHUSD")

        assert result is True
        assert "ETHUSD" in whitelist_config.whitelist_entries

    def test_auto_add_to_whitelist_disabled(self):
        """When auto_add disabled, pairs should not be added."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            auto_add_to_whitelist=False,
        )
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD"],
        )

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)

        result = filter_obj.add_to_whitelist("ETHUSD")

        assert result is False
        assert "ETHUSD" not in whitelist_config.whitelist_entries


class TestFilterSummary:
    """Test filter summary generation."""

    def test_filter_summary_whitelist_mode(self):
        """Filter summary should reflect whitelist configuration."""
        discovery_config = DiscoveryFilterConfig(enabled=True)
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)
        summary = filter_obj.get_filter_summary()

        assert summary["whitelist_enabled"] is True
        assert summary["whitelist_count"] == 2
        assert summary["volume_threshold_usd"] == 50_000_000

    def test_filter_summary_discovery_mode(self):
        """Filter summary should reflect discovery configuration."""
        discovery_config = DiscoveryFilterConfig(
            enabled=True,
            volume_threshold_usd=100_000_000,
            min_listing_age_days=180,
        )
        whitelist_config = WhitelistConfig(enabled=False)

        filter_obj = PairDiscoveryFilter(discovery_config, whitelist_config)
        summary = filter_obj.get_filter_summary()

        assert summary["whitelist_enabled"] is False
        assert summary["discovery_filters_enabled"] is True
        assert summary["volume_threshold_usd"] == 100_000_000
        assert summary["min_listing_age_days"] == 180


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
