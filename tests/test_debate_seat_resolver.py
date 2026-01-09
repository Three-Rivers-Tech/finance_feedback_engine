"""Unit tests for curated debate seat resolver (THR-63)."""

import pytest
from unittest.mock import patch, MagicMock

from finance_feedback_engine.decision_engine.debate_seat_resolver import (
    resolve_debate_seats,
    validate_debate_seat,
    get_available_local_models,
)


def test_resolve_seats_explicit_override():
    """User-provided debate_providers should override auto-resolution."""
    explicit = {"bull": "claude", "bear": "gpt4", "judge": "custom"}
    result = resolve_debate_seats([], explicit_debate_providers=explicit)

    assert result == {"bull": "claude", "bear": "gpt4", "judge": "custom"}


def test_resolve_seats_prefers_local_ollama():
    """When 3+ local Ollama models available, prefer them."""
    local_models = [
        "mistral:7b-instruct",
        "qwen2.5:7b-instruct",
        "gemma2:9b",
        "deepseek-r1:8b",
    ]

    with patch(
        "finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models",
        return_value=local_models,
    ):
        result = resolve_debate_seats(
            enabled_providers=["local", "gemini"],
            explicit_debate_providers=None
        )

        assert result["bull"] == "mistral:7b-instruct"
        assert result["bear"] == "qwen2.5:7b-instruct"
        assert result["judge"] == "gemma2:9b"


def test_resolve_seats_mixed_local_cloud():
    """When fewer than 3 local models, mix with cloud providers."""
    local_models = ["mistral:7b-instruct", "qwen2.5:7b-instruct"]

    with patch(
        "finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models",
        return_value=local_models,
    ):
        result = resolve_debate_seats(
            enabled_providers=["local", "gemini"],
            explicit_debate_providers=None
        )

        # First 2 should be local
        assert result["bull"] == "mistral:7b-instruct"
        assert result["bear"] == "qwen2.5:7b-instruct"
        # Third should be cloud fallback
        assert result["judge"] in ["gemini", "qwen", "cli", "codex"]


def test_resolve_seats_cloud_fallback():
    """When no local models, fall back to cloud providers."""
    with patch(
        "finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models",
        return_value=[],
    ):
        result = resolve_debate_seats(
            enabled_providers=["gemini", "qwen"],
            explicit_debate_providers=None
        )

        # All should be cloud providers
        assert result["bull"] in ["gemini", "qwen", "cli", "codex"]
        assert result["bear"] in ["gemini", "qwen", "cli", "codex"]
        assert result["judge"] in ["gemini", "qwen", "cli", "codex"]
        # All 3 should be assigned
        assert len(result) == 3


def test_validate_debate_seat_ollama_model():
    """Validate Ollama model seat assignment."""
    with patch(
        "finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models",
        return_value=["mistral:7b-instruct", "qwen2.5:7b-instruct"],
    ):
        # Valid installed model
        is_valid, error = validate_debate_seat("bull", "mistral:7b-instruct")
        assert is_valid is True
        assert error is None

        # Invalid: not installed
        is_valid, error = validate_debate_seat("bull", "llama3.2:13b")
        assert is_valid is False
        assert "not installed" in error


def test_validate_debate_seat_cloud_provider():
    """Cloud providers are assumed valid (don't make HTTP calls)."""
    is_valid, error = validate_debate_seat("bull", "gemini")
    assert is_valid is True
    assert error is None


def test_validate_debate_seat_empty():
    """Empty provider fails validation."""
    is_valid, error = validate_debate_seat("judge", "")
    assert is_valid is False
    assert "no provider assigned" in error


def test_resolve_seats_incomplete_explicit():
    """If explicit providers incomplete, fall back to auto-resolution."""
    # Missing judge
    incomplete = {"bull": "claude", "bear": "gpt4"}

    with patch(
        "finance_feedback_engine.decision_engine.debate_seat_resolver.get_available_local_models",
        return_value=["mistral:7b-instruct", "qwen2.5:7b-instruct", "gemma2:9b"],
    ):
        result = resolve_debate_seats(
            enabled_providers=["local"],
            explicit_debate_providers=incomplete
        )

        # Should have auto-resolved with local models
        assert result["bull"] == "mistral:7b-instruct"
        assert result["bear"] == "qwen2.5:7b-instruct"
        assert result["judge"] == "gemma2:9b"
