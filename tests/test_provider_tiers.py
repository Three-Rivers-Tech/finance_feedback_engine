"""Tests for decision_engine.provider_tiers module."""

import pytest

from finance_feedback_engine.decision_engine.provider_tiers import (
    FREE_TIER,
    PREMIUM_TIER,
    get_fallback_provider,
    get_free_providers,
    get_premium_providers,
    get_tier,
)


class TestProviderTierConstants:
    """Test provider tier constants."""

    def test_tier_constants_are_lists(self):
        """Test that tier constants are lists of provider names."""
        assert isinstance(FREE_TIER, list)
        assert isinstance(PREMIUM_TIER, list)
        assert len(FREE_TIER) > 0
        assert len(PREMIUM_TIER) > 0

    def test_no_overlap_between_tiers(self):
        """Test that free and premium tiers don't overlap."""
        overlap = set(FREE_TIER) & set(PREMIUM_TIER)
        assert len(overlap) == 0


class TestGetTier:
    """Test get_tier function."""

    def test_get_tier_cli(self):
        """Test getting tier for CLI provider."""
        tier = get_tier("cli")
        assert tier == "premium"

    def test_get_tier_codex(self):
        """Test getting tier for Codex provider."""
        tier = get_tier("codex")
        assert tier == "premium"

    def test_get_tier_gemini(self):
        """Test getting tier for Gemini provider."""
        tier = get_tier("gemini")
        assert tier == "premium"

    def test_get_tier_free_provider(self):
        """Test getting tier for a free provider."""
        # Use first provider from FREE_TIER
        if FREE_TIER:
            tier = get_tier(FREE_TIER[0])
            assert tier == "free"

    def test_get_tier_unknown_provider(self):
        """Test getting tier for unknown provider."""
        tier = get_tier("nonexistent_provider_xyz")
        assert tier == "unknown"


class TestGetProviders:
    """Test get provider list functions."""

    def test_get_free_providers_returns_list(self):
        """Test getting list of free providers."""
        free_providers = get_free_providers()

        assert isinstance(free_providers, list)
        # Should match FREE_TIER constant
        assert free_providers == FREE_TIER

    def test_get_premium_providers_returns_list(self):
        """Test getting list of premium providers."""
        premium_providers = get_premium_providers()

        assert isinstance(premium_providers, list)
        # Should match PREMIUM_TIER constant
        assert premium_providers == PREMIUM_TIER

    def test_premium_providers_include_known_providers(self):
        """Test that premium tier includes expected providers."""
        premium_providers = get_premium_providers()

        # Known premium providers
        for provider in ["cli", "codex", "gemini"]:
            assert provider in premium_providers


class TestGetFallbackProvider:
    """Test get_fallback_provider function."""

    def test_get_fallback_provider_returns_string(self):
        """Test getting fallback provider."""
        fallback = get_fallback_provider()

        assert fallback is not None
        assert isinstance(fallback, str)

    def test_fallback_provider_has_tier(self):
        """Test that fallback provider has a valid tier."""
        fallback = get_fallback_provider()
        tier = get_tier(fallback)

        # Fallback should have either free or premium tier, not unknown
        assert tier in ["free", "premium"]


class TestProviderTierIntegration:
    """Integration tests for provider tier logic."""

    def test_all_free_providers_return_free_tier(self):
        """Test that all FREE_TIER providers return 'free' from get_tier."""
        for provider in FREE_TIER:
            assert get_tier(provider) == "free"

    def test_all_premium_providers_return_premium_tier(self):
        """Test that all PREMIUM_TIER providers return 'premium' from get_tier."""
        for provider in PREMIUM_TIER:
            assert get_tier(provider) == "premium"

    def test_tier_classification_consistent(self):
        """Test that tier classification is consistent."""
        all_providers = FREE_TIER + PREMIUM_TIER

        for provider in all_providers:
            tier = get_tier(provider)
            if tier == "free":
                assert provider in FREE_TIER
            elif tier == "premium":
                assert provider in PREMIUM_TIER


class TestOllamaModels:
    """Test Ollama-specific functions."""

    def test_get_ollama_models(self):
        """Test getting Ollama models (excludes qwen CLI)."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_ollama_models,
        )

        ollama_models = get_ollama_models()

        assert isinstance(ollama_models, list)
        assert "qwen" not in ollama_models  # CLI provider excluded
        assert len(ollama_models) > 0

        # Should be subset of free tier
        for model in ollama_models:
            assert model in FREE_TIER

    def test_is_ollama_model(self):
        """Test checking if provider is Ollama model."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            is_ollama_model,
        )

        # Ollama models should return True
        assert is_ollama_model("llama3.2:3b-instruct-fp16") is True
        assert is_ollama_model("deepseek-r1:8b") is True

        # CLI providers should return False
        assert is_ollama_model("qwen") is False
        assert is_ollama_model("cli") is False
        assert is_ollama_model("gemini") is False

    def test_get_total_vram_required(self):
        """Test calculating total VRAM requirements."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_total_vram_required,
        )

        total_vram = get_total_vram_required()

        assert isinstance(total_vram, float)
        assert total_vram > 0
        # Should be sum of all model requirements
        assert total_vram > 20  # At least 20GB total

    def test_get_total_download_size(self):
        """Test calculating total download size."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_total_download_size,
        )

        total_size = get_total_download_size()

        assert isinstance(total_size, float)
        assert total_size > 0
        # Should be sum of all model sizes
        assert total_size > 15  # At least 15GB total


class TestAssetBasedRouting:
    """Test asset-based premium provider routing."""

    def test_get_premium_provider_for_crypto(self):
        """Test that crypto assets route to CLI."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_premium_provider_for_asset,
        )

        provider = get_premium_provider_for_asset("crypto")
        assert provider == "cli"

    def test_get_premium_provider_for_forex(self):
        """Test that forex assets route to Gemini."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_premium_provider_for_asset,
        )

        provider = get_premium_provider_for_asset("forex")
        assert provider == "gemini"

    def test_get_premium_provider_for_stock(self):
        """Test that stock assets route to Gemini."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_premium_provider_for_asset,
        )

        provider = get_premium_provider_for_asset("stock")
        assert provider == "gemini"

    def test_get_premium_provider_invalid_asset_type(self):
        """Test that invalid asset type raises ValueError."""
        from finance_feedback_engine.decision_engine.provider_tiers import (
            get_premium_provider_for_asset,
        )

        with pytest.raises(ValueError) as exc_info:
            get_premium_provider_for_asset("invalid_type")

        assert "Invalid asset_type" in str(exc_info.value)
        assert "crypto" in str(exc_info.value)
        assert "forex" in str(exc_info.value)
        assert "stock" in str(exc_info.value)
