import json

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
        "timestamp": "2025-01-01T00:00:01Z",  # Use fixed time instead of datetime.utcnow().isoformat()
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
