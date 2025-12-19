"""Tests ensuring veto and Thompson sampling features coexist without conflicts."""

import pytest

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


@pytest.fixture
def dual_feature_config(tmp_path):
    """Config with both veto and Thompson sampling enabled."""
    return {
        "portfolio_memory": {
            "enabled": True,
            "max_memory_size": 100,
            "learning_rate": 0.1,
            "context_window": 20,
        },
        "persistence": {"storage_path": str(tmp_path)},
        "features": {
            "sentiment_veto": True,
            "thompson_sampling_weights": True,
        },
        "decision_engine": {
            "ai_provider": "ensemble",
            "veto_threshold": 0.6,
        },
    }


class TestVetoThompsonCoexistence:
    """Test veto and Thompson sampling work together without conflicts."""

    def test_both_callbacks_fire_on_trade_outcome(self, dual_feature_config):
        """Both veto metrics and Thompson sampling should update."""
        memory = PortfolioMemoryEngine(dual_feature_config)

        thompson_calls = []

        def mock_thompson_callback(provider: str, won: bool, regime: str):
            thompson_calls.append({"provider": provider, "won": won, "regime": regime})

        memory.register_thompson_sampling_callback(mock_thompson_callback)

        decision = {
            "decision_id": "dual_test",
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
                    "local": {"action": "BUY", "confidence": 75},
                    "cli": {"action": "BUY", "confidence": 85},
                },
            },
            "veto_metadata": {
                "applied": False,
                "score": 0.3,
                "threshold": 0.6,
                "source": "sentiment",
            },
            "market_data": {"regime": "trending"},
        }

        # Winning trade
        memory.record_trade_outcome(decision, exit_price=150.0)

        # Veto metrics should be updated
        assert memory.veto_metrics["total"] == 1
        assert memory.veto_metrics["applied"] == 0
        assert memory.veto_metrics["correct"] == 1

        # Thompson sampling callback should fire
        assert len(thompson_calls) == 2
        assert thompson_calls[0]["provider"] in ["local", "cli"]
        assert thompson_calls[0]["won"] is True

    def test_veto_metadata_preserved_in_memory_context(self, dual_feature_config):
        """Memory context should include both veto stats and provider performance."""
        memory = PortfolioMemoryEngine(dual_feature_config)

        decision = {
            "decision_id": "ctx_test",
            "asset_pair": "ETHUSD",
            "action": "SELL",
            "entry_price": 200.0,
            "position_size": 1.0,
            "confidence": 70,
            "timestamp": "2024-12-19T00:00:00Z",
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "providers_used": ["local"],
                "provider_decisions": {"local": {"action": "SELL", "confidence": 70}},
            },
            "veto_metadata": {
                "applied": True,
                "score": 0.8,
                "threshold": 0.6,
                "source": "sentiment",
                "reason": "high risk",
            },
        }

        memory.record_trade_outcome(decision, exit_price=180.0)

        context = memory.generate_context(asset_pair="ETHUSD")

        assert context["has_history"] is True
        assert "veto_metrics" in context
        assert "veto_threshold_recommendation" in context
        assert "provider_performance" in context

    def test_thompson_callback_not_broken_by_veto(self, dual_feature_config):
        """Thompson callback should receive correct parameters even with veto present."""
        memory = PortfolioMemoryEngine(dual_feature_config)

        callback_args = []

        def capture_callback(provider: str, won: bool, regime: str):
            callback_args.append((provider, won, regime))

        memory.register_thompson_sampling_callback(capture_callback)

        decision = {
            "decision_id": "ts_veto_test",
            "asset_pair": "BTCUSD",
            "action": "BUY",
            "entry_price": 100.0,
            "position_size": 1.0,
            "confidence": 80,
            "timestamp": "2024-12-19T00:00:00Z",
            "ai_provider": "ensemble",
            "ensemble_metadata": {
                "providers_used": ["local"],
                "provider_decisions": {"local": {"action": "BUY", "confidence": 80}},
            },
            "veto_metadata": {"applied": False, "score": 0.2, "threshold": 0.6},
            "market_data": {"regime": "volatile"},
        }

        memory.record_trade_outcome(decision, exit_price=50.0)

        assert len(callback_args) == 1
        provider, won, regime = callback_args[0]
        assert provider == "local"
        assert won is False
        assert regime == "volatile"

    def test_veto_stats_persist_with_provider_performance(
        self, dual_feature_config, tmp_path
    ):
        """Both veto and provider stats should survive save/load cycle."""
        memory = PortfolioMemoryEngine(dual_feature_config)

        decision = {
            "decision_id": "persist_test",
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
                    "local": {"action": "BUY", "confidence": 75},
                    "cli": {"action": "BUY", "confidence": 85},
                },
            },
            "veto_metadata": {
                "applied": True,
                "score": 0.75,
                "threshold": 0.6,
                "source": "sentiment",
            },
        }

        memory.record_trade_outcome(decision, exit_price=50.0)

        filepath = tmp_path / "dual_feature.json"
        memory.save_to_disk(str(filepath))

        reloaded = PortfolioMemoryEngine.load_from_disk(str(filepath))

        assert reloaded.veto_metrics["total"] == 1
        assert "local" in reloaded.provider_performance
        assert "cli" in reloaded.provider_performance
