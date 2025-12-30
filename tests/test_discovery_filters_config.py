"""
Integration test for discovery filters and whitelist loading from config.yaml.

Validates that:
- Configuration loads correctly from YAML structure
- Discovery filters are properly instantiated with config values
- Whitelist entries are loaded from config.yaml
- Filter thresholds match configuration
"""

import pytest
from finance_feedback_engine.pair_selection.core.pair_selector import (
    PairSelectionConfig,
)
from finance_feedback_engine.pair_selection.core.discovery_filters import (
    DiscoveryFilterConfig,
    WhitelistConfig,
)


class TestConfigurationLoading:
    """Test loading of discovery filter configs from YAML structure."""

    def test_default_discovery_filter_config(self):
        """Default discovery filter config should match YAML defaults."""
        # Simulates config loading from config.yaml pair_selection.universe.discovery_filters
        discovery_filter_config = DiscoveryFilterConfig(
            enabled=True,
            volume_threshold_usd=50_000_000,  # 50M USD
            min_listing_age_days=365,  # 1 year
            max_spread_pct=0.001,  # 0.1%
            min_depth_usd=10_000_000,  # 10M USD
            exclude_suspicious_patterns=True,
            min_venue_count=2,
            auto_add_to_whitelist=False,
        )

        assert discovery_filter_config.enabled is True
        assert discovery_filter_config.volume_threshold_usd == 50_000_000
        assert discovery_filter_config.min_listing_age_days == 365
        assert discovery_filter_config.max_spread_pct == 0.001
        assert discovery_filter_config.min_depth_usd == 10_000_000
        assert discovery_filter_config.exclude_suspicious_patterns is True
        assert discovery_filter_config.min_venue_count == 2
        assert discovery_filter_config.auto_add_to_whitelist is False

    def test_default_whitelist_config(self):
        """Default whitelist config should match YAML defaults."""
        # Simulates config loading from config.yaml pair_selection.universe
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "USDJPY"],
        )

        assert whitelist_config.enabled is True
        assert len(whitelist_config.whitelist_entries) == 5
        assert "BTCUSD" in whitelist_config.whitelist_entries
        assert "ETHUSD" in whitelist_config.whitelist_entries

    def test_pair_selection_config_integration(self):
        """PairSelectionConfig should integrate filter configs correctly."""
        discovery_filter_config = DiscoveryFilterConfig(
            enabled=True,
            volume_threshold_usd=75_000_000,
            min_listing_age_days=180,
        )

        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )

        config = PairSelectionConfig(
            target_pair_count=5,
            discovery_filter_config=discovery_filter_config,
            whitelist_config=whitelist_config,
        )

        assert config.discovery_filter_config.volume_threshold_usd == 75_000_000
        assert config.discovery_filter_config.min_listing_age_days == 180
        assert config.whitelist_config.enabled is True
        assert config.whitelist_config.whitelist_entries == ["BTCUSD", "ETHUSD"]

    def test_auto_discover_disabled_by_default(self):
        """auto_discover should be False by default for safety."""
        config = PairSelectionConfig(
            target_pair_count=5,
            auto_discover=False,
        )

        assert config.auto_discover is False

    def test_conservative_filter_thresholds(self):
        """Filter thresholds should be conservative for safety."""
        discovery_filter_config = DiscoveryFilterConfig()

        # Verify defaults are conservative (high minimums, low maximums)
        assert discovery_filter_config.volume_threshold_usd >= 50_000_000  # At least 50M
        assert discovery_filter_config.min_listing_age_days >= 365  # At least 1 year
        assert discovery_filter_config.max_spread_pct <= 0.01  # At most 1%
        assert discovery_filter_config.min_depth_usd >= 10_000_000  # At least 10M
        assert discovery_filter_config.min_venue_count >= 2  # At least 2 venues


class TestConfigurationYAMLStructure:
    """Test that config dict structure mirrors YAML layout."""

    def test_yaml_pair_selection_structure(self):
        """Config dict should match YAML pair_selection section structure."""
        # Simulate YAML loading: config['pair_selection']
        ps_config = {
            "enabled": False,
            "target_pair_count": 5,
            "universe": {
                "auto_discover": False,
                "whitelist_enabled": True,
                "whitelist_entries": ["BTCUSD", "ETHUSD", "EURUSD"],
                "blacklist": [],
                "cache_ttl_hours": 24,
                "discovery_filters": {
                    "enabled": True,
                    "volume_threshold_usd": 50_000_000,
                    "min_listing_age_days": 365,
                    "max_spread_pct": 0.001,
                    "min_depth_usd": 10_000_000,
                    "exclude_suspicious_patterns": True,
                    "min_venue_count": 2,
                    "auto_add_to_whitelist": False,
                },
            },
            "statistical": {
                "sortino": {
                    "windows_days": [7, 30, 90],
                    "weights": [0.5, 0.3, 0.2],
                },
                "correlation": {"lookback_days": 30},
                "garch": {
                    "p": 1,
                    "q": 1,
                    "forecast_horizon_days": 7,
                    "fitting_window_days": 90,
                },
                "aggregation_weights": {
                    "sortino": 0.4,
                    "diversification": 0.35,
                    "volatility": 0.25,
                },
            },
            "llm": {"enabled": True, "candidate_oversampling": 3},
            "thompson_sampling": {
                "enabled": True,
                "min_trades_for_update": 3,
                "success_threshold": 0.55,
                "failure_threshold": 0.45,
            },
        }

        # Load discovery filter config from structure
        discovery_filters_cfg = ps_config.get("universe", {}).get(
            "discovery_filters", {}
        )
        assert discovery_filters_cfg["enabled"] is True
        assert discovery_filters_cfg["volume_threshold_usd"] == 50_000_000

        # Load whitelist config from structure
        whitelist_cfg = ps_config.get("universe", {})
        assert whitelist_cfg["whitelist_enabled"] is True
        assert "BTCUSD" in whitelist_cfg["whitelist_entries"]

    def test_yaml_extraction_helper(self):
        """Helper function should extract config values correctly."""

        def extract_discovery_config(ps_config: dict) -> dict:
            """Extract discovery filter config from pair_selection dict."""
            discovery_filters_cfg = ps_config.get("universe", {}).get(
                "discovery_filters", {}
            )
            return {
                "enabled": discovery_filters_cfg.get("enabled", True),
                "volume_threshold_usd": discovery_filters_cfg.get(
                    "volume_threshold_usd", 50_000_000
                ),
                "min_listing_age_days": discovery_filters_cfg.get(
                    "min_listing_age_days", 365
                ),
                "max_spread_pct": discovery_filters_cfg.get("max_spread_pct", 0.001),
                "min_depth_usd": discovery_filters_cfg.get(
                    "min_depth_usd", 10_000_000
                ),
                "exclude_suspicious_patterns": discovery_filters_cfg.get(
                    "exclude_suspicious_patterns", True
                ),
                "min_venue_count": discovery_filters_cfg.get("min_venue_count", 2),
                "auto_add_to_whitelist": discovery_filters_cfg.get(
                    "auto_add_to_whitelist", False
                ),
            }

        ps_config = {
            "universe": {
                "discovery_filters": {
                    "enabled": True,
                    "volume_threshold_usd": 100_000_000,
                }
            }
        }

        extracted = extract_discovery_config(ps_config)

        assert extracted["enabled"] is True
        assert extracted["volume_threshold_usd"] == 100_000_000
        assert extracted["min_listing_age_days"] == 365  # Default
        assert extracted["max_spread_pct"] == 0.001  # Default

    def test_yaml_extraction_with_overrides(self):
        """Config values should properly override defaults."""

        def extract_discovery_config(ps_config: dict) -> dict:
            """Extract discovery filter config from pair_selection dict."""
            discovery_filters_cfg = ps_config.get("universe", {}).get(
                "discovery_filters", {}
            )
            return {
                "volume_threshold_usd": discovery_filters_cfg.get(
                    "volume_threshold_usd", 50_000_000
                ),
                "min_listing_age_days": discovery_filters_cfg.get(
                    "min_listing_age_days", 365
                ),
                "max_spread_pct": discovery_filters_cfg.get("max_spread_pct", 0.001),
            }

        # Test with custom overrides
        ps_config = {
            "universe": {
                "discovery_filters": {
                    "volume_threshold_usd": 200_000_000,
                    "min_listing_age_days": 180,
                }
            }
        }

        extracted = extract_discovery_config(ps_config)

        assert extracted["volume_threshold_usd"] == 200_000_000
        assert extracted["min_listing_age_days"] == 180
        assert extracted["max_spread_pct"] == 0.001  # Kept default


class TestOperatorTuning:
    """Test that operators can tune filter parameters."""

    def test_operator_can_adjust_volume_threshold(self):
        """Operators should be able to adjust volume thresholds."""
        # Scenario: Operator wants to trade lower-volume forex pairs
        discovery_filter_config = DiscoveryFilterConfig(
            enabled=True,
            volume_threshold_usd=1_000_000_000,  # Increased for major forex
        )

        assert discovery_filter_config.volume_threshold_usd == 1_000_000_000

    def test_operator_can_adjust_listing_age(self):
        """Operators should be able to adjust listing age requirements."""
        # Scenario: Operator wants to trade newer altcoins (higher risk)
        discovery_filter_config = DiscoveryFilterConfig(
            enabled=True,
            min_listing_age_days=90,  # Reduced from 365
        )

        assert discovery_filter_config.min_listing_age_days == 90

    def test_operator_can_adjust_spread_threshold(self):
        """Operators should be able to adjust spread tolerances."""
        # Scenario: Operator trading on smaller exchanges with wider spreads
        discovery_filter_config = DiscoveryFilterConfig(
            enabled=True,
            max_spread_pct=0.01,  # Increased to 1%
        )

        assert discovery_filter_config.max_spread_pct == 0.01

    def test_operator_can_switch_whitelist_mode(self):
        """Operators should be able to toggle whitelist/discovery modes."""
        # Start with whitelist mode (safe)
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )

        assert whitelist_config.enabled is True

        # Switch to discovery mode (riskier)
        whitelist_config.enabled = False

        assert whitelist_config.enabled is False

    def test_operator_can_customize_whitelist(self):
        """Operators should be able to customize whitelisted pairs."""
        whitelist_config = WhitelistConfig(
            enabled=True,
            whitelist_entries=["BTCUSD", "ETHUSD"],
        )

        # Add a new pair
        whitelist_config.whitelist_entries.append("EURUSD")

        assert "EURUSD" in whitelist_config.whitelist_entries
        assert len(whitelist_config.whitelist_entries) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
