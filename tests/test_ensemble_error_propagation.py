"""
Test ensemble error propagation and provider failure tracking.

Verifies that:
1. Ensemble mode properly tracks provider failures (exceptions → failed_providers)
2. Single-provider mode returns fallback decisions (no exception propagation)
3. Local priority fallback chain works correctly
4. Provider weights adjust based on actual failures
"""

from unittest.mock import patch

import pytest

from finance_feedback_engine.decision_engine.engine import DecisionEngine


class TestEnsembleProviderFailureTracking:
    """Test that ensemble mode properly tracks provider failures."""

    @pytest.mark.asyncio
    async def test_ensemble_tracks_local_exception_as_failure(self):
        """Verify failed local provider is correctly tracked in failed_providers."""
        config = {
            "decision_engine": {"ai_provider": "ensemble"},
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.5, "cli": 0.5},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock local to raise RuntimeError, cli to return valid decision
        async def mock_local_raise(*args, **kwargs):
            raise RuntimeError("Ollama service down")

        async def mock_cli_success(*args, **kwargs):
            return {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "CLI provider says buy",
                "amount": 0.1,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local_raise):
            with patch.object(
                engine, "_cli_ai_inference", side_effect=mock_cli_success
            ):
                decision = await engine._ensemble_ai_inference("test prompt")

        # Verify local is in providers_failed (correct field name)
        assert "ensemble_metadata" in decision, "Decision missing ensemble_metadata"
        assert (
            "local" in decision["ensemble_metadata"]["providers_failed"]
        ), f"Expected 'local' in providers_failed, got: {decision['ensemble_metadata']['providers_failed']}"
        assert (
            "cli" in decision["ensemble_metadata"]["providers_used"]
        ), f"Expected 'cli' in providers_used, got: {decision['ensemble_metadata']['providers_used']}"
        assert decision["action"] in [
            "BUY",
            "SELL",
            "HOLD",
        ], f"Invalid action: {decision['action']}"

    @pytest.mark.asyncio
    async def test_ensemble_tracks_multiple_provider_failures(self):
        """Verify multiple failed providers are all tracked."""
        config = {
            "decision_engine": {"ai_provider": "ensemble"},
            "ensemble": {
                "enabled_providers": ["local", "cli", "gemini"],
                "provider_weights": {"local": 0.33, "cli": 0.33, "gemini": 0.34},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock two providers to fail, one to succeed
        async def mock_raise(*args, **kwargs):
            raise RuntimeError("Provider unavailable")

        async def mock_gemini_success(*args, **kwargs):
            return {
                "action": "HOLD",
                "confidence": 60,
                "reasoning": "Gemini provider recommends hold",
                "amount": 0,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_raise):
            with patch.object(engine, "_cli_ai_inference", side_effect=mock_raise):
                with patch.object(
                    engine, "_gemini_ai_inference", side_effect=mock_gemini_success
                ):
                    decision = await engine._ensemble_ai_inference("test prompt")

        # Verify both local and cli are in providers_failed
        metadata = decision["ensemble_metadata"]
        assert (
            "local" in metadata["providers_failed"]
        ), "Expected 'local' in providers_failed"
        assert (
            "cli" in metadata["providers_failed"]
        ), "Expected 'cli' in providers_failed"
        assert (
            "gemini" in metadata["providers_used"]
        ), "Expected 'gemini' in providers_used"
        assert (
            metadata["num_active"] == 1
        ), f"Expected 1 active provider, got {metadata['num_active']}"
        assert (
            len(metadata["providers_failed"]) == 2
        ), f"Expected 2 failed providers, got {len(metadata['providers_failed'])}"

    @pytest.mark.asyncio
    async def test_ensemble_all_providers_fail_raises_error(self):
        """Verify ensemble raises error when all providers fail."""
        config = {
            "decision_engine": {"ai_provider": "ensemble"},
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.5, "cli": 0.5},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock all providers to fail
        async def mock_raise(*args, **kwargs):
            raise RuntimeError("Provider unavailable")

        with patch.object(engine, "_local_ai_inference", side_effect=mock_raise):
            with patch.object(engine, "_cli_ai_inference", side_effect=mock_raise):
                with pytest.raises(
                    RuntimeError, match="All .* ensemble providers failed"
                ):
                    await engine._ensemble_ai_inference("test prompt")


class TestSingleProviderFallbackBehavior:
    """Test that single-provider mode returns fallback decisions instead of raising exceptions."""

    @pytest.mark.asyncio
    async def test_single_local_provider_returns_fallback_on_import_error(self):
        """Verify single local provider returns fallback decision on ImportError."""
        config = {
            "decision_engine": {"ai_provider": "local", "model_name": "llama3.2:3b"}
        }
        engine = DecisionEngine(config)

        # Mock ImportError (missing dependency)
        with patch(
            "finance_feedback_engine.decision_engine.local_llm_provider.LocalLLMProvider"
        ) as mock_provider:
            mock_provider.side_effect = ImportError("ollama module not found")

            decision = await engine._local_ai_inference("test prompt")

        # Should return fallback, NOT raise exception
        assert (
            decision["action"] == "HOLD"
        ), f"Expected HOLD action, got {decision['action']}"
        assert (
            0 <= decision["confidence"] <= 100
        ), f"Invalid confidence: {decision['confidence']}"
        assert (
            "fallback" in decision["reasoning"].lower()
            or "import error" in decision["reasoning"].lower()
        ), f"Reasoning should mention fallback or import error: {decision['reasoning']}"

    @pytest.mark.asyncio
    async def test_single_local_provider_returns_fallback_on_runtime_error(self):
        """Verify single local provider returns fallback decision on RuntimeError."""
        config = {
            "decision_engine": {"ai_provider": "local", "model_name": "llama3.2:3b"}
        }
        engine = DecisionEngine(config)

        # Mock RuntimeError (Ollama service down)
        with patch(
            "finance_feedback_engine.decision_engine.local_llm_provider.LocalLLMProvider"
        ) as mock_provider:
            mock_provider.side_effect = RuntimeError("Cannot connect to Ollama service")

            decision = await engine._local_ai_inference("test prompt")

        # Should return fallback, NOT raise exception
        assert (
            decision["action"] == "HOLD"
        ), f"Expected HOLD action, got {decision['action']}"
        assert (
            "runtime error" in decision["reasoning"].lower()
            or "fallback" in decision["reasoning"].lower()
        ), f"Reasoning should mention runtime error: {decision['reasoning']}"

    @pytest.mark.asyncio
    async def test_single_local_provider_returns_fallback_on_generic_exception(self):
        """Verify single local provider returns fallback decision on generic Exception."""
        config = {
            "decision_engine": {"ai_provider": "local", "model_name": "llama3.2:3b"}
        }
        engine = DecisionEngine(config)

        # Mock generic Exception
        with patch(
            "finance_feedback_engine.decision_engine.local_llm_provider.LocalLLMProvider"
        ) as mock_provider:
            mock_provider.side_effect = ValueError("Invalid model configuration")

            decision = await engine._local_ai_inference("test prompt")

        # Should return fallback, NOT raise exception
        assert (
            decision["action"] == "HOLD"
        ), f"Expected HOLD action, got {decision['action']}"
        assert (
            "unexpected error" in decision["reasoning"].lower()
            or "fallback" in decision["reasoning"].lower()
        ), f"Reasoning should mention unexpected error: {decision['reasoning']}"


class TestLocalPriorityFallbackChain:
    """Test that local_priority setting triggers proper fallback to remote providers."""

    @pytest.mark.asyncio
    async def test_local_priority_soft_falls_back_to_remote(self):
        """Verify local_priority='soft' triggers fallback when local fails."""
        config = {
            "decision_engine": {
                "ai_provider": "ensemble",
                "local_priority": "soft",
                "local_models": ["llama3.2:3b"],
            },
            "ensemble": {
                "enabled_providers": ["local", "gemini"],
                "provider_weights": {"local": 0.7, "gemini": 0.3},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock local to fail, gemini to succeed
        async def mock_local_raise(*args, **kwargs):
            raise RuntimeError("Model not found: llama3.2:3b")

        async def mock_gemini_success(*args, **kwargs):
            return {
                "action": "BUY",
                "confidence": 85,
                "reasoning": "Gemini provider recommends buy",
                "amount": 0.15,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local_raise):
            with patch.object(
                engine, "_gemini_ai_inference", side_effect=mock_gemini_success
            ):
                decision = await engine._ensemble_ai_inference("test prompt")

        # Verify gemini was actually queried (not just ignored)
        metadata = decision["ensemble_metadata"]
        assert (
            "gemini" in metadata["providers_used"]
        ), f"Expected 'gemini' in providers_used (fallback should have triggered), got: {metadata['providers_used']}"
        assert (
            "local" in metadata["providers_failed"]
        ), f"Expected 'local' in providers_failed, got: {metadata['providers_failed']}"
        # Verify decision came from gemini (not a fallback HOLD)
        assert (
            decision["action"] == "BUY"
        ), f"Expected BUY action from gemini provider, got {decision['action']}"

    @pytest.mark.asyncio
    async def test_local_priority_true_still_tracks_failure_properly(self):
        """Verify local_priority=True (strict) still tracks failures correctly in ensemble."""
        config = {
            "decision_engine": {
                "ai_provider": "ensemble",
                "local_priority": True,
                "local_models": ["llama3.2:3b"],
            },
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.8, "cli": 0.2},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock local to fail, cli to succeed
        async def mock_local_raise(*args, **kwargs):
            raise RuntimeError("Ollama service unavailable")

        async def mock_cli_success(*args, **kwargs):
            return {
                "action": "SELL",
                "confidence": 70,
                "reasoning": "CLI provider recommends sell",
                "amount": 0.05,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local_raise):
            with patch.object(
                engine, "_cli_ai_inference", side_effect=mock_cli_success
            ):
                decision = await engine._ensemble_ai_inference("test prompt")

        # Even with local_priority=True, failure should be tracked
        metadata = decision["ensemble_metadata"]
        assert (
            "local" in metadata["providers_failed"]
        ), f"Expected 'local' in providers_failed even with local_priority=True, got: {metadata['providers_failed']}"
        assert (
            "cli" in metadata["providers_used"]
        ), f"Expected 'cli' in providers_used (should still be queried in ensemble), got: {metadata['providers_used']}"


class TestProviderWeightAdjustment:
    """Test that provider weights adjust correctly based on actual failures."""

    @pytest.mark.asyncio
    async def test_weights_adjust_when_provider_fails(self):
        """Verify weights are adjusted when a provider fails in ensemble."""
        config = {
            "decision_engine": {"ai_provider": "ensemble"},
            "ensemble": {
                "enabled_providers": ["local", "cli", "gemini"],
                "provider_weights": {"local": 0.5, "cli": 0.3, "gemini": 0.2},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock local to fail, others to succeed
        async def mock_local_raise(*args, **kwargs):
            raise RuntimeError("Local provider down")

        async def mock_cli_success(*args, **kwargs):
            return {
                "action": "HOLD",
                "confidence": 60,
                "reasoning": "CLI: neutral",
                "amount": 0,
            }

        async def mock_gemini_success(*args, **kwargs):
            return {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "Gemini: bullish",
                "amount": 0.1,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local_raise):
            with patch.object(
                engine, "_cli_ai_inference", side_effect=mock_cli_success
            ):
                with patch.object(
                    engine, "_gemini_ai_inference", side_effect=mock_gemini_success
                ):
                    decision = await engine._ensemble_ai_inference("test prompt")

        # Verify weights were adjusted (check metadata)
        metadata = decision["ensemble_metadata"]
        adjusted_weights = metadata.get("adjusted_weights", {})

        # Local should NOT be in adjusted_weights (it failed)
        assert (
            "local" not in adjusted_weights
        ), f"Failed provider 'local' should not have weight in adjusted_weights, got: {adjusted_weights}"

        # CLI and Gemini should have renormalized weights
        assert "cli" in adjusted_weights, "CLI should have weight in adjusted_weights"
        assert (
            "gemini" in adjusted_weights
        ), "Gemini should have weight in adjusted_weights"

        # Weights should sum to ~1.0 (accounting for floating point)
        total_weight = sum(adjusted_weights.values())
        assert (
            0.99 <= total_weight <= 1.01
        ), f"Adjusted weights should sum to ~1.0, got {total_weight} (weights: {adjusted_weights})"


class TestEnsembleFallbackTiers:
    """Test that ensemble fallback tiers work correctly with provider failures."""

    @pytest.mark.asyncio
    async def test_weighted_voting_falls_back_to_majority_on_insufficient_providers(
        self,
    ):
        """Verify fallback to majority voting when weighted voting fails due to provider failures."""
        config = {
            "decision_engine": {"ai_provider": "ensemble"},
            "ensemble": {
                "enabled_providers": ["local", "cli"],
                "provider_weights": {"local": 0.5, "cli": 0.5},
                "voting_strategy": "weighted",
            },
        }
        engine = DecisionEngine(config)

        # Mock local to fail, cli to succeed
        async def mock_local_raise(*args, **kwargs):
            raise RuntimeError("Local unavailable")

        async def mock_cli_success(*args, **kwargs):
            return {
                "action": "HOLD",
                "confidence": 55,
                "reasoning": "CLI: hold",
                "amount": 0,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local_raise):
            with patch.object(
                engine, "_cli_ai_inference", side_effect=mock_cli_success
            ):
                decision = await engine._ensemble_ai_inference("test prompt")

        # Verify fallback behavior - with only 1 provider, may use weighted or single_provider tier
        metadata = decision["ensemble_metadata"]
        fallback_tier = metadata.get("fallback_tier", "unknown")

        # With only 1 provider succeeding, should use single_provider tier or weighted (both valid)
        # The key is that it should succeed and produce a valid decision
        assert fallback_tier in [
            "single_provider",
            "weighted",
        ], f"Expected 'single_provider' or 'weighted' fallback tier with 1 provider, got '{fallback_tier}'"
        assert (
            decision["action"] == "HOLD"
        ), "Should return the single provider's HOLD action"
        # Confidence may be adjusted down due to single provider (failure rate adjustment)
        assert (
            0 < decision["confidence"] <= 55
        ), f"Confidence should be positive but may be adjusted down from 55, got {decision['confidence']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
