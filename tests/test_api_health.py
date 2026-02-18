"""Unit tests for finance_feedback_engine.api.health."""

from types import SimpleNamespace

import pytest

from finance_feedback_engine.api.health import get_health_status


@pytest.fixture
def healthy_engine():
    """Engine stub with all optional collaborators present."""
    circuit_breaker = SimpleNamespace(
        state=SimpleNamespace(name="CLOSED"),
        failure_count=0,
    )
    data_provider = SimpleNamespace(
        alpha_vantage=SimpleNamespace(circuit_breaker=circuit_breaker)
    )
    platform = SimpleNamespace(
        get_balance=lambda: {"FUTURES_USD": "100.5", "FUTURES_USDC": "50.25"}
    )
    decision_store = SimpleNamespace(
        get_recent_decisions=lambda limit=1: [{"timestamp": "2026-02-17T23:00:00Z"}]
    )
    return SimpleNamespace(
        data_provider=data_provider,
        platform=platform,
        decision_store=decision_store,
    )


def test_get_health_status_healthy_path(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 100},
    )

    result = get_health_status(healthy_engine)

    assert result["status"] == "healthy"
    assert result["database"]["available"] is True
    assert result["circuit_breakers"]["alpha_vantage"] == {
        "state": "CLOSED",
        "failure_count": 0,
    }
    assert result["portfolio_balance"]["total"] == pytest.approx(150.75)
    assert result["last_decision_at"] == "2026-02-17T23:00:00Z"


def test_get_health_status_unhealthy_when_database_unavailable(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": False, "error": "down", "latency_ms": 0},
    )

    result = get_health_status(healthy_engine)

    assert result["status"] == "unhealthy"
    assert result["database"]["error"] == "down"


def test_get_health_status_degraded_when_database_slow(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 1501},
    )

    result = get_health_status(healthy_engine)

    assert result["status"] == "degraded"


def test_get_health_status_handles_database_exception(monkeypatch, healthy_engine):
    def raise_db_error():
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        raise_db_error,
    )

    result = get_health_status(healthy_engine)

    assert result["status"] == "unhealthy"
    assert result["database"]["available"] is False
    assert result["database"]["error"] == "boom"


def test_get_health_status_marks_unhealthy_without_data_provider(monkeypatch):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 50},
    )

    engine = SimpleNamespace()
    result = get_health_status(engine)

    assert result["status"] == "unhealthy"
    assert result["circuit_breakers"]["error"] == "data_provider not available"


def test_get_health_status_circuit_breaker_defaults_when_attrs_missing(monkeypatch):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 10},
    )

    # state/failure_count intentionally missing
    cb = SimpleNamespace()
    engine = SimpleNamespace(
        data_provider=SimpleNamespace(alpha_vantage=SimpleNamespace(circuit_breaker=cb)),
        platform=SimpleNamespace(get_balance=lambda: {"FUTURES_USD": 0, "FUTURES_USDC": 0}),
        decision_store=SimpleNamespace(get_recent_decisions=lambda limit=1: []),
    )

    result = get_health_status(engine)

    assert result["status"] == "healthy"
    assert result["circuit_breakers"]["alpha_vantage"] == {
        "state": "UNKNOWN",
        "failure_count": 0,
    }


def test_get_health_status_handles_platform_and_decision_store_failures(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 10},
    )

    healthy_engine.platform = SimpleNamespace(
        get_balance=lambda: (_ for _ in ()).throw(RuntimeError("balance down"))
    )
    healthy_engine.decision_store = SimpleNamespace(
        get_recent_decisions=lambda limit=1: (_ for _ in ()).throw(RuntimeError("read down"))
    )

    result = get_health_status(healthy_engine)

    assert result["status"] == "degraded"
    assert result["portfolio_balance"] is None
    assert result["portfolio_balance_error"] == "balance down"
    assert result["last_decision_at"] is None
    assert result["last_decision_error"] == "read down"


def test_get_health_status_degrades_when_circuit_breaker_lookup_raises(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 10},
    )

    class BrokenProvider:
        @property
        def alpha_vantage(self):
            raise RuntimeError("cb unavailable")

    healthy_engine.data_provider = BrokenProvider()

    result = get_health_status(healthy_engine)

    assert result["status"] == "degraded"
    assert result["circuit_breakers"]["error"] == "cb unavailable"


def test_get_health_status_balance_passthrough_for_non_dict(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 10},
    )
    healthy_engine.platform = SimpleNamespace(get_balance=lambda: 42.0)

    result = get_health_status(healthy_engine)

    assert result["status"] == "healthy"
    assert result["portfolio_balance"] == 42.0


def test_get_health_status_degraded_when_balance_empty(monkeypatch, healthy_engine):
    monkeypatch.setattr(
        "finance_feedback_engine.api.health.check_database_health",
        lambda: {"available": True, "latency_ms": 10},
    )
    healthy_engine.platform = SimpleNamespace(get_balance=lambda: None)

    result = get_health_status(healthy_engine)

    assert result["status"] == "degraded"
    assert result["portfolio_balance"] is None
    assert result["portfolio_balance_error"] == "empty balance returned"
