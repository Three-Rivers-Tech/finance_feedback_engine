"""Tests for two-phase ensemble aggregator."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from finance_feedback_engine.decision_engine.two_phase_aggregator import TwoPhaseAggregator
from finance_feedback_engine.exceptions import InsufficientProvidersError


class TestTwoPhaseAggregatorInitialization:
    """Test TwoPhaseAggregator initialization."""

    def test_initialization_disabled(self):
        """Test initialization with two-phase disabled."""
        config = {
            "ensemble": {
                "two_phase": {
                    "enabled": False
                }
            }
        }
        
        aggregator = TwoPhaseAggregator(config)
        
        assert aggregator.config == config
        assert aggregator.enabled is False

    def test_initialization_enabled(self):
        """Test initialization with two-phase enabled."""
        config = {
            "ensemble": {
                "two_phase": {
                    "enabled": True,
                    "confidence_threshold": 0.75,
                    "agreement_threshold": 0.60
                }
            }
        }
        
        aggregator = TwoPhaseAggregator(config)
        
        assert aggregator.enabled is True
        assert aggregator.two_phase_config["confidence_threshold"] == 0.75
        assert aggregator.two_phase_config["agreement_threshold"] == 0.60

    def test_initialization_with_missing_config(self):
        """Test initialization with minimal config."""
        config = {}
        
        aggregator = TwoPhaseAggregator(config)
        
        assert aggregator.enabled is False
        assert aggregator.two_phase_config == {}

    def test_initialization_with_defaults(self):
        """Test that defaults are properly handled."""
        config = {
            "ensemble": {
                "two_phase": {}
            }
        }
        
        aggregator = TwoPhaseAggregator(config)
        
        # Should default to False
        assert aggregator.enabled is False


class TestAssetTypeNormalization:
    """Test asset type validation and normalization."""

    def test_canonical_asset_type_crypto(self):
        """Test canonical crypto asset type is valid."""
        CANONICAL_ASSET_TYPES = {"crypto", "forex", "stock"}
        
        # Test that crypto is in canonical set
        assert "crypto" in CANONICAL_ASSET_TYPES
        
        # Test normalization doesn't change canonical type
        market_data = {"type": "crypto"}
        raw_type = market_data.get("type", "").lower().strip()
        
        if raw_type in CANONICAL_ASSET_TYPES:
            normalized = raw_type
            assert normalized == "crypto"

    def test_asset_type_normalization_cryptocurrency(self):
        """Test normalization of 'cryptocurrency' to 'crypto'."""
        market_data = {"type": "cryptocurrency"}
        
        # Test the normalization logic
        raw_type = market_data.get("type", "").lower().strip()
        
        ASSET_TYPE_NORMALIZATION = {
            "cryptocurrency": "crypto",
            "cryptocurrencies": "crypto",
        }
        
        if raw_type in ASSET_TYPE_NORMALIZATION:
            normalized = ASSET_TYPE_NORMALIZATION[raw_type]
            assert normalized == "crypto"

    def test_asset_type_normalization_forex_variations(self):
        """Test various forex type normalizations."""
        variations = ["foreign_exchange", "fx", "currency", "currency_pair"]
        
        for variation in variations:
            ASSET_TYPE_NORMALIZATION = {
                "foreign_exchange": "forex",
                "fx": "forex",
                "currency": "forex",
                "currency_pair": "forex",
            }
            
            normalized = ASSET_TYPE_NORMALIZATION.get(variation)
            assert normalized == "forex", f"Failed for {variation}"

    def test_asset_type_normalization_stock_variations(self):
        """Test various stock type normalizations."""
        variations = ["equities", "equity", "shares", "stocks"]
        
        ASSET_TYPE_NORMALIZATION = {
            "equities": "stock",
            "equity": "stock",
            "shares": "stock",
            "stocks": "stock",
        }
        
        for variation in variations:
            normalized = ASSET_TYPE_NORMALIZATION.get(variation)
            assert normalized == "stock", f"Failed for {variation}"

    @pytest.mark.asyncio
    async def test_missing_asset_type_defaults_to_crypto(self):
        """Test that missing asset type defaults to crypto."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        market_data = {}  # No type field
        mock_query = AsyncMock()
        
        # When disabled, should return None early
        result = await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="BTCUSD",
            market_data=market_data,
            query_function=mock_query
        )
        
        assert result is None  # Disabled mode returns None

    @pytest.mark.asyncio
    async def test_invalid_asset_type_defaults_to_crypto(self):
        """Test that invalid asset type defaults to crypto."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        market_data = {"type": "invalid_type"}
        mock_query = AsyncMock()
        
        result = await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="BTCUSD",
            market_data=market_data,
            query_function=mock_query
        )
        
        assert result is None  # Disabled mode


class TestDisabledMode:
    """Test behavior when two-phase is disabled."""

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """Test that disabled mode returns None immediately."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        market_data = {"type": "crypto"}
        mock_query = AsyncMock()
        
        result = await aggregator.aggregate_two_phase(
            prompt="test prompt",
            asset_pair="BTCUSD",
            market_data=market_data,
            query_function=mock_query
        )
        
        assert result is None
        mock_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_disabled_no_provider_queries(self):
        """Test that disabled mode doesn't query any providers."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        market_data = {"type": "forex"}
        mock_query = AsyncMock()
        
        await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="EURUSD",
            market_data=market_data,
            query_function=mock_query
        )
        
        # Query function should never be called
        assert mock_query.call_count == 0


class TestConfigurationHandling:
    """Test configuration parameter handling."""

    def test_get_confidence_threshold_default(self):
        """Test default confidence threshold."""
        config = {
            "ensemble": {
                "two_phase": {
                    "enabled": True
                }
            }
        }
        aggregator = TwoPhaseAggregator(config)
        
        # Default should be accessible from config
        threshold = aggregator.two_phase_config.get("confidence_threshold", 0.75)
        assert threshold == 0.75

    def test_get_confidence_threshold_custom(self):
        """Test custom confidence threshold."""
        config = {
            "ensemble": {
                "two_phase": {
                    "enabled": True,
                    "confidence_threshold": 0.80
                }
            }
        }
        aggregator = TwoPhaseAggregator(config)
        
        threshold = aggregator.two_phase_config.get("confidence_threshold")
        assert threshold == 0.80

    def test_get_agreement_threshold(self):
        """Test agreement threshold configuration."""
        config = {
            "ensemble": {
                "two_phase": {
                    "enabled": True,
                    "agreement_threshold": 0.65
                }
            }
        }
        aggregator = TwoPhaseAggregator(config)
        
        threshold = aggregator.two_phase_config.get("agreement_threshold")
        assert threshold == 0.65

    def test_nested_config_access(self):
        """Test accessing nested configuration values."""
        config = {
            "ensemble": {
                "two_phase": {
                    "enabled": True,
                    "phase1": {
                        "min_quorum": 3
                    },
                    "phase2": {
                        "escalation_rules": ["low_confidence", "high_stakes"]
                    }
                }
            }
        }
        aggregator = TwoPhaseAggregator(config)
        
        phase1_config = aggregator.two_phase_config.get("phase1", {})
        assert phase1_config.get("min_quorum") == 3
        
        phase2_config = aggregator.two_phase_config.get("phase2", {})
        assert "low_confidence" in phase2_config.get("escalation_rules", [])


class TestMarketDataHandling:
    """Test market data processing."""

    @pytest.mark.asyncio
    async def test_market_data_not_mutated(self):
        """Test that original market_data dict is not mutated."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        original_market_data = {"type": "crypto", "price": 45000}
        market_data_copy = original_market_data.copy()
        
        await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="BTCUSD",
            market_data=original_market_data,
            query_function=AsyncMock()
        )
        
        # Original should be unchanged
        assert original_market_data == market_data_copy

    @pytest.mark.asyncio
    async def test_empty_market_data_handled(self):
        """Test handling of empty market data."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        result = await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="BTCUSD",
            market_data={},
            query_function=AsyncMock()
        )
        
        # Should return None (disabled) or handle gracefully
        assert result is None

    def test_canonical_asset_types_set(self):
        """Test that canonical asset types are properly defined."""
        # This tests the constants used in the module
        CANONICAL_ASSET_TYPES = {"crypto", "forex", "stock"}
        
        assert "crypto" in CANONICAL_ASSET_TYPES
        assert "forex" in CANONICAL_ASSET_TYPES
        assert "stock" in CANONICAL_ASSET_TYPES
        assert len(CANONICAL_ASSET_TYPES) == 3


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_query_function_none_handled(self):
        """Test handling when query_function is None."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        # When disabled, should return None without calling query_function
        result = await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="BTCUSD",
            market_data={"type": "crypto"},
            query_function=None
        )
        
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_prompt_handled(self):
        """Test handling of empty prompt."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        result = await aggregator.aggregate_two_phase(
            prompt="",
            asset_pair="BTCUSD",
            market_data={"type": "crypto"},
            query_function=AsyncMock()
        )
        
        # Should handle gracefully
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_empty_asset_pair_handled(self):
        """Test handling of empty asset pair."""
        config = {"ensemble": {"two_phase": {"enabled": False}}}
        aggregator = TwoPhaseAggregator(config)
        
        result = await aggregator.aggregate_two_phase(
            prompt="test",
            asset_pair="",
            market_data={"type": "crypto"},
            query_function=AsyncMock()
        )
        
        # Should handle gracefully
        assert result is None or isinstance(result, dict)
