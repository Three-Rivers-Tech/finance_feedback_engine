import json
import logging

import pytest

from finance_feedback_engine.decision_engine.ensemble_manager import EnsembleDecisionManager


def test_update_base_weights_mutates_state_and_persists_history(tmp_path):
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 1.0,
                "debate_mode": False,
            },
        }
    )

    provider_decisions = {
        "local": {"action": "BUY", "confidence": 80},
        "qwen": {"action": "SELL", "confidence": 75},
    }

    assert manager.base_weights == {"local": 0.5, "qwen": 0.5}
    assert manager.performance_tracker.performance_history == {}

    manager.update_base_weights(
        provider_decisions=provider_decisions,
        actual_outcome="BUY",
        performance_metric=10.0,
    )

    assert manager.performance_tracker.performance_history["local"] == {
        "correct": 1,
        "total": 1,
        "avg_performance": 10.0,
    }
    assert manager.performance_tracker.performance_history["qwen"] == {
        "correct": 0,
        "total": 1,
        "avg_performance": 10.0,
    }
    assert manager.base_weights["local"] > manager.base_weights["qwen"]
    assert abs(sum(manager.base_weights.values()) - 1.0) < 1e-9
    assert manager.base_weights["local"] == pytest.approx(0.8021739859022077)
    assert manager.base_weights["qwen"] == pytest.approx(0.19782601409779235)

    history_path = tmp_path / "ensemble_history.json"
    assert history_path.exists()

    history = json.loads(history_path.read_text())
    assert history["local"]["correct"] == 1
    assert history["local"]["total"] == 1
    assert history["qwen"]["correct"] == 0
    assert history["qwen"]["total"] == 1


def test_update_base_weights_logs_before_after_packet(tmp_path, caplog):
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 1.0,
                "debate_mode": False,
            },
        }
    )

    provider_decisions = {
        "local": {"action": "BUY", "confidence": 80},
        "qwen": {"action": "SELL", "confidence": 75},
    }

    with caplog.at_level(logging.INFO):
        manager.update_base_weights(
            provider_decisions=provider_decisions,
            actual_outcome="BUY",
            performance_metric=10.0,
        )

    assert (
        "Adaptive weights evaluated | actual_outcome=BUY | performance_metric=10.0 | "
        "provider_decisions=['local', 'qwen'] | weights_before={'local': 0.5, 'qwen': 0.5} | "
        "weights_after={'local': 0.8021739859022077, 'qwen': 0.19782601409779235} | changed=True | changed_keys=['local', 'qwen'] | history_path="
    ) in caplog.text


def test_update_base_weights_defaults_history_under_data_decisions_when_persistence_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    manager = EnsembleDecisionManager(
        {
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 1.0,
                "debate_mode": False,
            },
        }
    )

    manager.update_base_weights(
        provider_decisions={
            "local": {"action": "BUY", "confidence": 80},
            "qwen": {"action": "SELL", "confidence": 75},
        },
        actual_outcome="BUY",
        performance_metric=10.0,
    )

    assert manager.performance_tracker.history_path.resolve() == (tmp_path / "data" / "decisions" / "ensemble_history.json").resolve()
    assert (tmp_path / "data" / "decisions" / "ensemble_history.json").exists()
    assert not (tmp_path / "data" / "ensemble_history.json").exists()


def test_update_base_weights_logs_no_change_packet(tmp_path, caplog):
    stable_weights = {"local": 0.8021739859022077, "qwen": 0.19782601409779235}
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": stable_weights,
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 1.0,
                "debate_mode": False,
            },
        }
    )

    manager.performance_tracker.performance_history = {
        "local": {"correct": 1, "total": 1, "avg_performance": 10.0},
        "qwen": {"correct": 0, "total": 1, "avg_performance": 10.0},
    }

    with caplog.at_level(logging.INFO):
        manager.update_base_weights(
            provider_decisions={
                "local": {"action": "BUY", "confidence": 80},
                "qwen": {"action": "SELL", "confidence": 75},
            },
            actual_outcome="BUY",
            performance_metric=10.0,
        )

    assert (
        "Adaptive weights evaluated | actual_outcome=BUY | performance_metric=10.0 | "
        "provider_decisions=['local', 'qwen'] | weights_before={'local': 0.8021739859022077, 'qwen': 0.19782601409779235} | "
        "weights_after={'local': 0.8021739859022077, 'qwen': 0.19782601409779235} | changed=False | changed_keys=[] | history_path="
    ) in caplog.text


def test_calculate_adaptive_weights_uses_avg_performance_as_secondary_signal(tmp_path):
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 0.5,
                "debate_mode": False,
            },
        }
    )

    manager.performance_tracker.performance_history = {
        "local": {"correct": 1, "total": 2, "avg_performance": 8.0},
        "qwen": {"correct": 1, "total": 2, "avg_performance": -8.0},
    }

    adaptive_weights = manager.performance_tracker.calculate_adaptive_weights(
        manager.enabled_providers,
        manager.base_weights,
    )

    assert adaptive_weights["local"] > adaptive_weights["qwen"]
    assert abs(sum(adaptive_weights.values()) - 1.0) < 1e-9


def test_adaptive_weight_formula_uses_config_blend_constants(tmp_path):
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 0.5,
                "debate_mode": False,
                "adaptive_accuracy_weight": 0.5,
                "adaptive_performance_weight": 0.5,
                "adaptive_performance_scale": 2.0,
            },
        }
    )

    manager.performance_tracker.performance_history = {
        "local": {"correct": 1, "total": 2, "avg_performance": 8.0},
        "qwen": {"correct": 1, "total": 2, "avg_performance": -8.0},
    }

    weights = manager.performance_tracker.calculate_adaptive_weights(
        manager.enabled_providers,
        manager.base_weights,
    )

    assert weights["local"] > weights["qwen"]
    spread = weights["local"] - weights["qwen"]

    manager2 = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path / "default")},
            "ensemble": {
                "enabled_providers": ["local", "qwen"],
                "provider_weights": {"local": 0.5, "qwen": 0.5},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 0.5,
                "debate_mode": False,
            },
        }
    )
    manager2.performance_tracker.performance_history = dict(manager.performance_tracker.performance_history)
    weights2 = manager2.performance_tracker.calculate_adaptive_weights(
        manager2.enabled_providers,
        manager2.base_weights,
    )
    default_spread = weights2["local"] - weights2["qwen"]

    assert spread > default_spread, (
        f"Custom blend (perf_weight=0.5, scale=2.0) should produce wider spread than default. "
        f"Got spread={spread:.6f} vs default_spread={default_spread:.6f}"
    )


def test_debate_mode_base_weights_use_seat_keys(tmp_path):
    """In debate mode, base_weights must be keyed by seat (bull/bear/judge),
    not by model name. This ensures weights_before and weights_after in the
    adaptation log always use the same key domain."""
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["deepseek-r1:8b"],
                "provider_weights": {"deepseek-r1:8b": 1.0},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 1.0,
                "debate_mode": True,
                "debate_providers": {
                    "bull": "deepseek-r1:8b",
                    "bear": "deepseek-r1:8b",
                    "judge": "deepseek-r1:8b",
                },
            },
        }
    )

    # base_weights must be seat-keyed, not model-keyed
    assert set(manager.base_weights.keys()) == {"bull", "bear", "judge"}, (
        f"Expected seat keys in base_weights, got: {list(manager.base_weights.keys())}"
    )
    assert abs(sum(manager.base_weights.values()) - 1.0) < 1e-9


def test_debate_mode_adaptation_logs_consistent_keys(tmp_path, caplog):
    """weights_before and weights_after must both use seat keys in debate mode."""
    manager = EnsembleDecisionManager(
        {
            "persistence": {"storage_path": str(tmp_path)},
            "ensemble": {
                "enabled_providers": ["deepseek-r1:8b"],
                "provider_weights": {"deepseek-r1:8b": 1.0},
                "voting_strategy": "weighted",
                "adaptive_learning": True,
                "learning_rate": 1.0,
                "debate_mode": True,
                "debate_providers": {
                    "bull": "deepseek-r1:8b",
                    "bear": "deepseek-r1:8b",
                    "judge": "deepseek-r1:8b",
                },
            },
        }
    )

    provider_decisions = {
        "bull": {"action": "BUY", "confidence": 80},
        "bear": {"action": "SELL", "confidence": 75},
        "judge": {"action": "BUY", "confidence": 70},
    }

    with caplog.at_level(logging.INFO):
        manager.update_base_weights(
            provider_decisions=provider_decisions,
            actual_outcome="BUY",
            performance_metric=10.0,
        )

    # Find the adaptation log line
    log_line = [r for r in caplog.records if "Adaptive weights evaluated" in r.message]
    assert log_line, "Expected an Adaptive weights evaluated log line"

    msg = log_line[0].message
    # Neither weights_before nor weights_after should contain model names
    for model_name in ["deepseek-r1:8b", "llama3.1:8b", "gemma2:9b"]:
        assert model_name not in msg, (
            f"Model name {model_name!r} found in adaptation log — expected seat keys only. Log: {msg}"
        )
    # Both should contain seat keys
    for seat in ["bull", "bear", "judge"]:
        assert seat in msg, f"Seat key {seat!r} missing from adaptation log. Log: {msg}"
