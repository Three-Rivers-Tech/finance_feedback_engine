"""Ensure veto tracking coexists with Thompson Sampling callbacks."""

from unittest.mock import Mock

import pytest

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


def _build_config(tmp_path):
    return {
        "portfolio_memory": {
            "enabled": True,
            "max_memory_size": 50,
            "context_window": 10,
        },
        "persistence": {"storage_path": str(tmp_path)},
    }


def test_veto_does_not_block_thompson_updates(tmp_path):
    """Recording a vetoed trade still triggers the Thompson callback for providers."""
    memory = PortfolioMemoryEngine(_build_config(tmp_path))
    callback = Mock()
    memory.register_thompson_sampling_callback(callback)

    decision = {
        "decision_id": "veto_ts_1",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "entry_price": 100.0,
        "position_size": 1.0,
        "confidence": 70,
        "timestamp": "2024-12-19T00:00:00Z",
        "ai_provider": "ensemble",
        "ensemble_metadata": {
            "providers_used": ["local"],
            "provider_decisions": {"local": {"action": "BUY"}},
            "voting_strategy": "weighted",
        },
        "veto_metadata": {
            "applied": True,
            "score": 0.7,
            "threshold": 0.6,
            "source": "sentiment",
        },
        "market_data": {"regime": "trending"},
    }

    # Loss trade: veto was correct; provider should receive a loss update (won=False)
    memory.record_trade_outcome(decision, exit_price=90.0)

    callback.assert_called_once()
    called_kwargs = callback.call_args.kwargs
    assert called_kwargs["provider"] == "local"
    assert called_kwargs["won"] is False
    assert called_kwargs["regime"] == "trending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
