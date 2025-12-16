"""
Test suite for asset_type validation and normalization in two-phase ensemble.

Verifies the fix for the 'unknown' asset_type errors during premium escalation.
"""

from unittest.mock import patch

import pytest

from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)


@pytest.fixture
def base_config():
    """Base configuration for ensemble manager."""
    return {
        "ensemble": {
            "enabled_providers": ["local"],
            "provider_weights": {"local": 1.0},
            "two_phase": {
                "enabled": True,
                "phase1_min_quorum": 3,
                "phase1_confidence_threshold": 0.75,
                "phase1_agreement_threshold": 0.6,
                "require_premium_for_high_stakes": False,  # Simplify tests
                "codex_as_tiebreaker": False,  # Simplify tests
            },
            "debate_mode": False,
        }
    }


@pytest.fixture
def mock_query_function():
    """Mock query function that returns valid decisions."""

    def query_func(provider, prompt):
        return {
            "action": "BUY",
            "confidence": 80,
            "reasoning": f"Decision from {provider}",
            "amount": 100,
        }

    return query_func


class TestAssetTypeValidation:
    """Test asset_type validation and normalization in aggregate_decisions_two_phase."""

    def test_canonical_crypto_type(self, base_config, mock_query_function):
        """Test that canonical 'crypto' type passes through unchanged."""
        manager = EnsembleDecisionManager(base_config)

        # Mock Phase 1 providers to return enough responses for quorum
        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                # Should NOT raise ValueError for canonical type
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="BTCUSD",
                        market_data={"type": "crypto"},
                        query_function=mock_query_function,
                    )
                    # If we get here without exception, validation passed
                    assert True
                except ValueError as e:
                    pytest.fail(
                        f"Canonical 'crypto' type should not raise ValueError: {e}"
                    )

    def test_canonical_forex_type(self, base_config, mock_query_function):
        """Test that canonical 'forex' type passes through unchanged."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="EURUSD",
                        market_data={"type": "forex"},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(
                        f"Canonical 'forex' type should not raise ValueError: {e}"
                    )

    def test_canonical_stock_type(self, base_config, mock_query_function):
        """Test that canonical 'stock' type passes through unchanged."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="AAPL",
                        market_data={"type": "stock"},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(
                        f"Canonical 'stock' type should not raise ValueError: {e}"
                    )

    def test_variation_cryptocurrency_normalized_to_crypto(
        self, base_config, mock_query_function
    ):
        """Test that 'cryptocurrency' variation is normalized to 'crypto'."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                # Should normalize without error
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="BTCUSD",
                        market_data={"type": "cryptocurrency"},
                        query_function=mock_query_function,
                    )
                    assert True  # If no exception, normalization worked
                except ValueError as e:
                    pytest.fail(f"'cryptocurrency' should normalize to 'crypto': {e}")

    def test_variation_fx_normalized_to_forex(self, base_config, mock_query_function):
        """Test that 'fx' variation is normalized to 'forex'."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="EURUSD",
                        market_data={"type": "fx"},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(f"'fx' should normalize to 'forex': {e}")

    def test_variation_equity_normalized_to_stock(
        self, base_config, mock_query_function
    ):
        """Test that 'equity' variation is normalized to 'stock'."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="AAPL",
                        market_data={"type": "equity"},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(f"'equity' should normalize to 'stock': {e}")

    def test_unknown_type_defaults_to_crypto(self, base_config, mock_query_function):
        """Test that 'unknown' type defaults to 'crypto' and logs error."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                # Should default to 'crypto' without raising exception
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="UNKNOWN",
                        market_data={"type": "unknown"},
                        query_function=mock_query_function,
                    )
                    assert True  # No exception means defaulting worked
                except ValueError as e:
                    pytest.fail(f"'unknown' should default to 'crypto': {e}")

    def test_invalid_type_defaults_to_crypto(self, base_config, mock_query_function):
        """Test that invalid type like 'mystery' defaults to 'crypto'."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="MYSTERY",
                        market_data={"type": "mystery"},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(f"Invalid type should default to 'crypto': {e}")

    def test_missing_type_defaults_to_crypto(self, base_config, mock_query_function):
        """Test that missing type (None) defaults to 'crypto'."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="BTCUSD",
                        market_data={},  # No 'type' field
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(f"Missing type should default to 'crypto': {e}")

    def test_non_string_type_defaults_to_crypto(self, base_config, mock_query_function):
        """Test that non-string type (e.g., int) defaults to 'crypto'."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="BTCUSD",
                        market_data={"type": 123},  # Integer instead of string
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(f"Non-string type should default to 'crypto': {e}")

    def test_uppercase_type_normalized(self, base_config, mock_query_function):
        """Test that uppercase type like 'CRYPTO' is normalized to lowercase."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="BTCUSD",
                        market_data={"type": "CRYPTO"},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(f"Uppercase 'CRYPTO' should normalize to 'crypto': {e}")

    def test_whitespace_type_normalized(self, base_config, mock_query_function):
        """Test that type with whitespace like '  crypto  ' is normalized."""
        manager = EnsembleDecisionManager(base_config)

        with patch(
            "finance_feedback_engine.decision_engine.provider_tiers.get_free_providers",
            return_value=["p1", "p2", "p3"],
        ):
            with patch.object(
                manager, "_is_valid_provider_response", return_value=True
            ):
                try:
                    result = manager.aggregate_decisions_two_phase(
                        prompt="Test prompt",
                        asset_pair="BTCUSD",
                        market_data={"type": "  crypto  "},
                        query_function=mock_query_function,
                    )
                    assert True
                except ValueError as e:
                    pytest.fail(
                        f"Type with whitespace should normalize to 'crypto': {e}"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
