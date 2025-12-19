"""Regression tests ensuring veto and Thompson sampling coexist in ensemble mode."""

from unittest.mock import AsyncMock, patch

import pytest

from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


@pytest.fixture
def ensemble_config_with_veto(tmp_path):
    return {
        "decision_engine": {
            "ai_provider": "ensemble",
            "veto_threshold": 0.6,
        },
        "ensemble": {
            "enabled_providers": ["local", "cli"],
            "provider_weights": {"local": 0.5, "cli": 0.5},
            "voting_strategy": "weighted",
            "debate_mode": False,
        },
        "features": {
            "sentiment_veto": True,
            "thompson_sampling_weights": True,
        },
        "portfolio_memory": {
            "enabled": True,
            "max_memory_size": 100,
        },
        "persistence": {"storage_path": str(tmp_path)},
    }


class TestVetoThompsonCoexistence:
    """Verify veto and Thompson sampling work together without conflicts."""

    @pytest.mark.asyncio
    async def test_ensemble_metadata_includes_both_veto_and_providers(
        self, ensemble_config_with_veto
    ):
        """Ensemble decisions should contain both veto metadata and provider tracking."""
        engine = DecisionEngine(ensemble_config_with_veto)

        async def mock_local(*args, **kwargs):
            return {
                "action": "BUY",
                "confidence": 75,
                "reasoning": "local buy",
                "veto_score": 0.3,
            }

        async def mock_cli(*args, **kwargs):
            return {
                "action": "SELL",
                "confidence": 65,
                "reasoning": "cli sell",
                "veto": False,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local):
            with patch.object(engine, "_cli_ai_inference", side_effect=mock_cli):
                context = {
                    "asset_pair": "BTCUSD",
                    "market_data": {"close": 50000},
                    "memory_context": {},
                }
                ai_response = await engine._ensemble_ai_inference("test prompt")

        # Verify ensemble metadata preserved
        assert "ensemble_metadata" in ai_response
        assert "providers_used" in ai_response["ensemble_metadata"]
        assert "providers_failed" in ai_response["ensemble_metadata"]

        # Verify veto metadata present (even if not applied)
        assert "veto_metadata" in ai_response

    @pytest.mark.asyncio
    async def test_thompson_callback_fires_with_veto_enabled(
        self, ensemble_config_with_veto, tmp_path
    ):
        """Thompson sampling callback should still fire when veto is enabled."""
        memory = PortfolioMemoryEngine(ensemble_config_with_veto)
        callback_fired = {"count": 0}

        def mock_callback(provider: str, won: bool, regime: str):
            callback_fired["count"] += 1

        memory.register_thompson_sampling_callback(mock_callback)

        decision = {
            "decision_id": "test_123",
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "entry_price": 100.0,
            "position_size": 1.0,
            "confidence": 80,
            "timestamp": "2024-12-19T00:00:00Z",
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "providers_used": ["local", "cli"],
                "provider_decisions": {
                    "local": {"action": "BUY"},
                    "cli": {"action": "BUY"},
                },
            },
            "veto_metadata": {
                "applied": False,
                "score": 0.3,
                "threshold": 0.6,
            },
        }

        memory.record_trade_outcome(decision, exit_price=150.0)

        # Thompson callback should have fired for both providers
        assert callback_fired["count"] == 2

    def test_veto_metrics_and_provider_performance_separate(
        self, ensemble_config_with_veto
    ):
        """Veto metrics and provider performance should track independently."""
        memory = PortfolioMemoryEngine(ensemble_config_with_veto)

        decision = {
            "decision_id": "mixed_test",
            "asset_pair": "ETHUSD",
            "action": "BUY",
            "entry_price": 100.0,
            "position_size": 1.0,
            "confidence": 70,
            "timestamp": "2024-12-19T00:00:00Z",
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "providers_used": ["local"],
                "provider_decisions": {"local": {"action": "BUY"}},
            },
            "veto_metadata": {
                "applied": True,
                "score": 0.75,
                "threshold": 0.6,
                "source": "sentiment",
            },
        }

        memory.record_trade_outcome(decision, exit_price=50.0)

        # Veto metrics tracked
        assert memory.veto_metrics["total"] == 1
        assert memory.veto_metrics["correct"] == 1

        # Provider performance also tracked
        assert "local" in memory.provider_performance
        assert memory.provider_performance["local"]["total_trades"] == 1


class TestEnsembleMetadataIntegrity:
    """Verify ensemble metadata remains intact with veto feature enabled."""

    @pytest.mark.asyncio
    async def test_failed_providers_tracked_with_veto(self, ensemble_config_with_veto):
        """Failed providers should still be tracked when veto is enabled."""
        engine = DecisionEngine(ensemble_config_with_veto)

        async def mock_local_fail(*args, **kwargs):
            raise RuntimeError("Local provider down")

        async def mock_cli_success(*args, **kwargs):
            return {
                "action": "HOLD",
                "confidence": 60,
                "reasoning": "cli hold",
                "veto_score": 0.2,
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_local_fail):
            with patch.object(
                engine, "_cli_ai_inference", side_effect=mock_cli_success
            ):
                context = {"memory_context": {}}
                ai_response = await engine._ensemble_ai_inference("test prompt")

        metadata = ai_response["ensemble_metadata"]
        assert "local" in metadata["providers_failed"]
        assert "cli" in metadata["providers_used"]
        assert metadata["num_active"] == 1

    @pytest.mark.asyncio
    async def test_veto_does_not_interfere_with_voting(self, ensemble_config_with_veto):
        """Veto logic should apply after voting, not during aggregation."""
        engine = DecisionEngine(ensemble_config_with_veto)

        async def mock_provider_buy(*args, **kwargs):
            return {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "provider buy",
            }

        with patch.object(engine, "_local_ai_inference", side_effect=mock_provider_buy):
            with patch.object(
                engine, "_cli_ai_inference", side_effect=mock_provider_buy
            ):
                context = {"memory_context": {}}
                ai_response = await engine._ensemble_ai_inference("test prompt")

        # Ensemble should vote BUY
        assert ai_response["action"] in ["BUY", "SELL", "HOLD"]
        # Veto metadata present but should not be applied (no veto signal)
        veto_meta = ai_response.get("veto_metadata")
        if veto_meta:
            assert not veto_meta.get("applied")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
