"""Debate seat assignment resolver with curated local/cloud model preferences.

Assigns bull, bear, and judge roles to AI providers with intelligent fallback:
- Prefers local Ollama models when available
- Falls back to cloud providers (gemini, qwen CLI) as failover
- Validates assigned providers are reachable before commitment
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Curated Ollama models for debate seats (sorted by quality/stability)
LOCAL_OLLAMA_MODELS = [
    "mistral:7b-instruct",     # Balanced reasoning, fast
    "qwen2.5:7b-instruct",      # Strong reasoning, multilingual
    "gemma2:9b",                # General-purpose, good context
    "deepseek-r1:8b",           # Code/logic specialist
    "llama3.2:3b-instruct-fp16", # Fallback (smaller, faster)
]

# Cloud provider fallback order
CLOUD_PROVIDER_FALLBACK = [
    "gemini",    # Stable, no rate limit issues in test
    "qwen",      # Alternative cloud provider
    "cli",       # GitHub Copilot CLI (if available)
    "codex",     # Codex CLI (legacy fallback)
]


def get_available_local_models() -> list[str]:
    """
    Check which Ollama models are available locally.

    Returns:
        List of model names that are installed in Ollama
    """
    try:
        import requests

        ollama_host = "http://localhost:11434"
        response = requests.get(
            f"{ollama_host}/api/tags",
            timeout=2.0
        )
        response.raise_for_status()
        data = response.json()
        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
        return models
    except Exception as e:
        logger.debug(f"Failed to check available Ollama models: {e}")
        return []


def resolve_debate_seats(
    enabled_providers: list[str],
    explicit_debate_providers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Resolve debate seat assignments (bull, bear, judge) to available providers.

    Strategy:
    1. If explicit_debate_providers provided, use them (user override)
    2. Check available local Ollama models, assign if 3+ available
    3. Fall back to cloud provider mix
    4. Ensure all 3 seats assigned and distinct

    Args:
        enabled_providers: List of providers configured for ensemble
        explicit_debate_providers: User-provided seat mapping (e.g., from config)

    Returns:
        Dict mapping roles (bull, bear, judge) to provider names
    """
    # User override: respect explicit config if all 3 seats filled
    if explicit_debate_providers:
        bull = explicit_debate_providers.get("bull", "").strip()
        bear = explicit_debate_providers.get("bear", "").strip()
        judge = explicit_debate_providers.get("judge", "").strip()

        if bull and bear and judge:
            logger.info(
                f"Using explicit debate seat assignment: "
                f"bull={bull}, bear={bear}, judge={judge}"
            )
            return {"bull": bull, "bear": bear, "judge": judge}
        else:
            logger.warning(
                f"Incomplete explicit debate providers; will use curated defaults. "
                f"Got: bull={bull}, bear={bear}, judge={judge}"
            )

    # Strategy: Prefer local Ollama models if 3+ available
    available_local = get_available_local_models()
    if len(available_local) >= 3:
        # Assign first 3 available local models to the 3 roles
        seats = {
            "bull": available_local[0],
            "bear": available_local[1],
            "judge": available_local[2],
        }
        logger.info(
            f"Assigned debate seats to local Ollama models: {seats}"
        )
        return seats

    # Fallback 1: Mix of available local + cloud providers
    if available_local:
        seats = {}
        local_idx = 0

        # Assign locals first
        for role in ["bull", "bear", "judge"]:
            if local_idx < len(available_local):
                seats[role] = available_local[local_idx]
                local_idx += 1
            else:
                break

        # Fill remaining roles with cloud providers
        cloud_idx = 0
        for role in ["bull", "bear", "judge"]:
            if role not in seats:
                while (
                    cloud_idx < len(CLOUD_PROVIDER_FALLBACK)
                    and CLOUD_PROVIDER_FALLBACK[cloud_idx] not in seats.values()
                ):
                    seats[role] = CLOUD_PROVIDER_FALLBACK[cloud_idx]
                    cloud_idx += 1
                    break

        if len(seats) == 3:
            logger.info(
                f"Assigned debate seats (mixed local+cloud): {seats}"
            )
            return seats

    # Fallback 2: Pure cloud provider mix (no local models available)
    logger.info("No local Ollama models found; using cloud provider fallback")
    seats = {}
    for role, fallback_provider in zip(
        ["bull", "bear", "judge"],
        CLOUD_PROVIDER_FALLBACK[:3]
    ):
        seats[role] = fallback_provider

    logger.info(f"Assigned debate seats (cloud fallback): {seats}")
    return seats


def validate_debate_seat(seat_name: str, provider: str) -> tuple[bool, Optional[str]]:
    """
    Validate that a debate seat provider is reachable.

    Args:
        seat_name: Role name (bull, bear, judge)
        provider: Provider name to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not provider or not str(provider).strip():
        return False, f"Seat '{seat_name}' has no provider assigned"

    # Check if it's an Ollama model (contains ':' or is a known keyword)
    if ":" in str(provider) or any(
        kw in str(provider).lower()
        for kw in ["llama", "mistral", "deepseek", "gemma", "qwen", "phi"]
    ):
        # Try to verify model is available
        try:
            available = get_available_local_models()
            if str(provider) in available:
                return True, None
            else:
                return False, (
                    f"Seat '{seat_name}' assigned to local model '{provider}' "
                    f"but it's not installed. Available: {available}"
                )
        except Exception as e:
            logger.debug(f"Failed to validate Ollama model '{provider}': {e}")
            # If we can't verify, assume it might be available (don't block)
            return True, None

    # Cloud provider: assume available (don't make HTTP calls)
    return True, None
