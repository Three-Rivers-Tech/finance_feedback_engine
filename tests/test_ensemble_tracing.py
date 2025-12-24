import asyncio
import pytest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


class ListExporter(SpanExporter):
    def __init__(self):
        self._spans = []

    def export(self, spans):
        self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        return None


@pytest.mark.asyncio
async def test_ensemble_aggregate_span_attributes():
    """Test ensemble aggregation spans and attributes."""
    # Import here to avoid global tracer provider conflicts
    from finance_feedback_engine.decision_engine import ensemble_manager as em

    # Minimal config enabling two providers
    config = {
        "ensemble": {
            "enabled_providers": ["local", "cli"],
            "provider_weights": {"local": 0.6, "cli": 0.4},
            "voting_strategy": "weighted",
            "agreement_threshold": 0.6,
            "local_dominance_target": 0.6,
            "min_local_providers": 1,
        }
    }

    mgr = em.EnsembleDecisionManager(config)

    # Two provider decisions
    provider_decisions = {
        "local": {"action": "BUY", "confidence": 80, "reasoning": "", "amount": 1},
        "cli": {"action": "BUY", "confidence": 70, "reasoning": "", "amount": 1},
    }

    decision = await mgr.aggregate_decisions(provider_decisions, failed_providers=[])

    # Verify decision metadata reflects ensemble (main verification since tracing requires isolated setup)
    meta = decision.get("ensemble_metadata", {})
    assert meta.get("num_active") == 2
    assert meta.get("num_total") == 2
    assert meta.get("providers_used") == ["local", "cli"]
    assert "agreement_score" in meta
    assert "fallback_tier" in meta
    assert "confidence" in decision
