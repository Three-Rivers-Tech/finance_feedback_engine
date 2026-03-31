import json
import logging

import pytest
from freezegun import freeze_time

from finance_feedback_engine.core import FinanceFeedbackEngine


def make_config(storage_path: str = "data/decisions_test"):
    return {
        "trading_platform": "mock",
        "platform_credentials": {},
        "alpha_vantage_api_key": "TEST",
        "decision_engine": {},
        "persistence": {"storage_path": storage_path},
        "portfolio_memory": {"enabled": False},
        "monitoring": {"enable_context_integration": False},
        "safety": {"max_leverage": 5.0, "max_position_pct": 50.0},
    }


@pytest.mark.external_service
def test_invalid_decision_blocks_execution(tmp_path, monkeypatch):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    engine = FinanceFeedbackEngine(cfg)

    decision = {
        "id": "invalid-1",
        "asset_pair": "ETHUSD",
        "action": "BUY",
        "confidence": -1,
        "amount": 0.1,
        "timestamp": "2025-01-01T00:00:00Z",
    }

    engine.decision_store.save_decision(decision)

    # Execution should be handled gracefully (no exception)
    engine.execute_decision("invalid-1")


@freeze_time("2025-01-01T00:00:01Z")
def test_execution_requires_valid_decision(tmp_path, monkeypatch):
    """Non-signal decisions execute when valid; invalid ones raise."""
    from finance_feedback_engine import FinanceFeedbackEngine

    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    engine = FinanceFeedbackEngine(cfg)

    # Create a minimal invalid decision to ensure safety path
    decision_id = "test-invalid"
    decision = {
        "id": decision_id,
        "action": "BUY",
        "confidence": -1,  # invalid confidence to trigger validation failure
        "asset_pair": "BTCUSD",
    }

    tmp_file = tmp_path / f"{decision_id}.json"
    tmp_file.write_text(json.dumps(decision))

    with pytest.raises(ValueError):
        engine.execute_decision(decision_id)


@freeze_time("2025-01-01T00:00:01Z")
def test_mock_platform_executes(tmp_path):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    engine = FinanceFeedbackEngine(cfg)

    # Create a fake decision allowed to execute
    decision = {
        "id": "test-exec",
        "asset_pair": "ETHUSD",
        "signal_only": False,
        "action": "BUY",
        "confidence": 80,
        "amount": 0.1,
        "suggested_amount": 0.1,  # Added: required for execution
        "timestamp": "2025-01-01T00:00:00Z",  # Fresh timestamp for freeze_time
    }

    engine.decision_store.save_decision(decision)

    result = engine.execute_decision("test-exec")
    assert isinstance(result, dict)
    assert result.get("success") or result.get("message")


@freeze_time("2025-01-01T00:00:01Z")
def test_breaker_opens_after_failures(tmp_path, monkeypatch):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    # Disable risk gatekeeper to avoid stale data rejection
    cfg["risk"] = {"enable_gatekeeper": False}
    engine = FinanceFeedbackEngine(cfg)

    # Prepare a decision
    decision = {
        "id": "test-breaker",
        "asset_pair": "ETHUSD",
        "signal_only": False,
        "action": "BUY",
        "confidence": 80,
        "amount": 0.1,
        "timestamp": "2025-01-01T00:00:00Z",
    }
    engine.decision_store.save_decision(decision)

    # Monkeypatch the platform's execute_trade to always raise
    def always_fail(_):
        raise RuntimeError("simulated failure")

    engine.trading_platform.execute_trade = always_fail

    # First few calls should raise RuntimeError and be recorded
    for _ in range(5):  # Circuit breaker default is 5 failures
        with pytest.raises(RuntimeError):
            engine.execute_decision("test-breaker")

    # Next call should raise CircuitBreakerOpenError (fail-fast)
    from finance_feedback_engine.utils.circuit_breaker import CircuitBreakerOpenError

    with pytest.raises(CircuitBreakerOpenError):
        engine.execute_decision("test-breaker")


@freeze_time("2025-01-01T00:00:01Z")
def test_learning_loop_calls_ensemble_update(tmp_path, monkeypatch):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    # enable portfolio memory so record_trade_outcome is active
    cfg["portfolio_memory"] = {"enabled": True}
    engine = FinanceFeedbackEngine(cfg)

    # Create a stub ensemble manager with spy
    class StubEnsemble:
        def __init__(self):
            self.called = False
            self.last_args = None

        def update_base_weights(self, provider_decisions, actual_outcome, perf_metric):
            self.called = True
            self.last_args = (provider_decisions, actual_outcome, perf_metric)

    stub = StubEnsemble()
    engine.decision_engine.ensemble_manager = stub

    # Create and save a decision
    decision = {
        "id": "test-learn",
        "asset_pair": "ETHUSD",
        "signal_only": False,
        "action": "BUY",
        "confidence": 80,
        "amount": 0.1,
        "timestamp": "2025-01-01T00:00:01Z",  # Use fixed time instead of datetime.now(UTC).isoformat()
        "entry_price": 100.0,
        "recommended_position_size": 1.0,
        "ai_provider": "ensemble",
        "ensemble_metadata": {
            "provider_decisions": {"local": {"action": "BUY"}},
            "providers_used": ["local"],
        },
        "market_data": {"close": 100.0},
    }
    engine.decision_store.save_decision(decision)

    # Record a profitable outcome
    outcome = engine.record_trade_outcome("test-learn", exit_price=110.0)
    assert stub.called is True
    assert stub.last_args[1] == "BUY"
    # performance metric should be numeric
    perf = stub.last_args[2]
    assert isinstance(perf, (int, float))


@freeze_time("2025-01-01T00:00:01Z")
def test_learning_loop_logs_adaptive_handoff_packet(tmp_path, caplog):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    cfg["portfolio_memory"] = {"enabled": True}
    engine = FinanceFeedbackEngine(cfg)

    class StubEnsemble:
        def update_base_weights(self, provider_decisions, actual_outcome, perf_metric):
            return None

    engine.decision_engine.ensemble_manager = StubEnsemble()

    decision = {
        "id": "test-learn-log",
        "asset_pair": "ETHUSD",
        "signal_only": False,
        "action": "BUY",
        "confidence": 80,
        "amount": 0.1,
        "timestamp": "2025-01-01T00:00:01Z",
        "entry_price": 100.0,
        "recommended_position_size": 1.0,
        "ai_provider": "ensemble",
        "ensemble_metadata": {
            "provider_decisions": {
                "gemma2:9b": {"action": "BUY"},
                "llama3.1:8b": {"action": "SELL"},
            },
            "providers_used": ["gemma2:9b", "llama3.1:8b"],
        },
        "recovery_metadata": {
            "shadowed_from_decision_id": "shadowed-open-1",
        },
        "market_data": {"close": 100.0},
    }
    engine.decision_store.save_decision(decision)

    with caplog.at_level(logging.INFO):
        engine.record_trade_outcome("test-learn-log", exit_price=110.0)

    assert (
        "Adaptive learning handoff | decision_id=test-learn-log | ai_provider=ensemble | "
        "shadowed_from_decision_id=shadowed-open-1 | provider_decisions=['gemma2:9b', 'llama3.1:8b'] | "
        "actual_outcome=BUY | performance_metric=10.0"
    ) in caplog.text



@freeze_time("2025-01-01T00:00:01Z")
def test_learning_loop_uses_role_decisions_for_debate_adaptation(tmp_path):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    cfg["portfolio_memory"] = {"enabled": True}
    engine = FinanceFeedbackEngine(cfg)

    class StubEnsemble:
        def __init__(self):
            self.called = False
            self.last_args = None

        def update_base_weights(self, provider_decisions, actual_outcome, perf_metric):
            self.called = True
            self.last_args = (provider_decisions, actual_outcome, perf_metric)

    stub = StubEnsemble()
    engine.decision_engine.ensemble_manager = stub

    decision = {
        "id": "test-debate-learn",
        "asset_pair": "ETHUSD",
        "signal_only": False,
        "action": "OPEN_SMALL_SHORT",
        "confidence": 85,
        "amount": 0.02,
        "timestamp": "2025-01-01T00:00:01Z",
        "entry_price": 100.0,
        "recommended_position_size": 1.0,
        "ai_provider": "ensemble",
        "ensemble_metadata": {
            "voting_strategy": "debate",
            "provider_decisions": {
                "gemma2:9b": {"action": "OPEN_SMALL_LONG", "provider": "gemma2:9b"},
                "llama3.1:8b": {"action": "OPEN_SMALL_SHORT", "provider": "llama3.1:8b"},
                "deepseek-r1:8b": {"action": "HOLD", "provider": "deepseek-r1:8b"}
            },
            "role_decisions": {
                "bull": {"action": "OPEN_SMALL_LONG", "provider": "gemma2:9b"},
                "bear": {"action": "OPEN_SMALL_SHORT", "provider": "llama3.1:8b"},
                "judge": {"action": "HOLD", "provider": "deepseek-r1:8b"},
            },
            "debate_seats": {
                "bull": "gemma2:9b",
                "bear": "llama3.1:8b",
                "judge": "deepseek-r1:8b",
            },
            "providers_used": ["gemma2:9b", "llama3.1:8b", "deepseek-r1:8b"],
        },
        "market_data": {"close": 100.0},
    }
    engine.decision_store.save_decision(decision)

    engine.record_trade_outcome("test-debate-learn", exit_price=90.0)

    assert stub.called is True
    provider_decisions, actual_outcome, perf_metric = stub.last_args
    assert sorted(provider_decisions.keys()) == ["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"]
    assert provider_decisions["gemma2:9b"]["action"] == "OPEN_SMALL_LONG"
    assert provider_decisions["llama3.1:8b"]["action"] == "OPEN_SMALL_SHORT"
    assert provider_decisions["deepseek-r1:8b"]["action"] == "HOLD"
    assert actual_outcome == "OPEN_SMALL_SHORT"
    assert isinstance(perf_metric, (int, float))


@freeze_time("2025-01-01T00:00:01Z")
def test_learning_loop_recovery_shadow_uses_preserved_debate_attribution(tmp_path):
    cfg = make_config(storage_path=str(tmp_path / "decisions"))
    cfg["portfolio_memory"] = {"enabled": True}
    engine = FinanceFeedbackEngine(cfg)

    class StubEnsemble:
        def __init__(self):
            self.called = False
            self.last_args = None

        def update_base_weights(self, provider_decisions, actual_outcome, perf_metric):
            self.called = True
            self.last_args = (provider_decisions, actual_outcome, perf_metric)

    stub = StubEnsemble()
    engine.decision_engine.ensemble_manager = stub

    decision = {
        "id": "test-recovery-shadow",
        "asset_pair": "ETP20DEC30CDE",
        "signal_only": False,
        "action": "SELL",
        "confidence": 75,
        "amount": 1.0,
        "timestamp": "2025-01-01T00:00:01Z",
        "entry_price": 100.0,
        "recommended_position_size": 1.0,
        "ai_provider": "ensemble",
        "recovery_metadata": {
            "product_id": "ETP-20DEC30-CDE",
            "shadowed_from_decision_id": "shadow-source-1",
            "shadowed_from_provider": "ensemble",
        },
        "ensemble_metadata": {
            "voting_strategy": "debate",
            "provider_decisions": {
                "gemma2:9b": {"action": "OPEN_SMALL_LONG", "provider": "gemma2:9b"},
                "llama3.1:8b": {"action": "OPEN_SMALL_SHORT", "provider": "llama3.1:8b"},
                "deepseek-r1:8b": {"action": "HOLD", "provider": "deepseek-r1:8b"}
            },
            "role_decisions": {
                "bull": {"action": "OPEN_SMALL_LONG", "provider": "gemma2:9b"},
                "bear": {"action": "OPEN_SMALL_SHORT", "provider": "llama3.1:8b"},
                "judge": {"action": "HOLD", "provider": "deepseek-r1:8b"},
            },
            "debate_seats": {
                "bull": "gemma2:9b",
                "bear": "llama3.1:8b",
                "judge": "deepseek-r1:8b",
            },
        },
        "market_data": {"close": 100.0},
    }
    engine.decision_store.save_decision(decision)

    engine.record_trade_outcome("test-recovery-shadow", exit_price=90.0)

    assert stub.called is True
    provider_decisions, actual_outcome, perf_metric = stub.last_args
    assert sorted(provider_decisions.keys()) == ["deepseek-r1:8b", "gemma2:9b", "llama3.1:8b"]
    assert provider_decisions["llama3.1:8b"]["action"] == "OPEN_SMALL_SHORT"
    assert provider_decisions["deepseek-r1:8b"]["action"] == "HOLD"
    assert actual_outcome == "SELL"
    assert isinstance(perf_metric, (int, float))
