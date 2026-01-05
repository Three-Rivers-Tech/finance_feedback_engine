"""
Ollama readiness checker for agent startup.

Verifies Ollama is running and required models are available before starting the agent.
Provides diagnostics and remediation guidance.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)


class OllamaReadinessChecker:
    """Checks Ollama service availability and model prerequisites."""

    def __init__(self, ollama_host: Optional[str] = None):
        """
        Initialize checker.

        Args:
            ollama_host: Ollama service host URL (defaults to env var OLLAMA_HOST or localhost:11434)
        """
        if ollama_host is None:
            ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_host = ollama_host
        if ollama:
            self.client = ollama.Client(host=ollama_host)
        else:
            self.client = None

    def check_service_available(self) -> Tuple[bool, Optional[str]]:
        """
        Check if Ollama service is reachable.

        Returns:
            Tuple of (is_available, error_message)
        """
        if not self.client:
            return False, "ollama package not installed; run: pip install ollama"

        try:
            self.client.list()
            return True, None
        except Exception as e:
            return False, (
                f"Ollama service unavailable at {self.ollama_host}: {e}\n"
                f"Ensure Ollama is running (e.g., ollama serve) or update OLLAMA_HOST env var"
            )

    def get_available_models(self) -> List[str]:
        """
        Get list of installed models.

        Returns:
            List of model names (tags)
        """
        if not self.client:
            return []

        try:
            models_response = self.client.list()
            available_models = (
                models_response.models
                if hasattr(models_response, "models")
                else models_response.get("models", [])
            )
            return [
                (
                    model.model
                    if hasattr(model, "model")
                    else model.get("name", "unknown")
                )
                for model in available_models
            ]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def check_models_installed(
        self, required_models: List[str]
    ) -> Tuple[bool, Dict[str, bool], List[str]]:
        """
        Check if required models are installed.

        Args:
            required_models: List of model tags to check

        Returns:
            Tuple of (all_present, per_model_status_dict, missing_models_list)
        """
        available = self.get_available_models()
        status = {}
        missing = []

        for model_name in required_models:
            # Check both full name and base name (e.g., "mistral" matches "mistral:latest")
            model_base = model_name.lower().split(":")[0]
            found = any(
                model_name.lower() in avail.lower()
                or model_base in avail.lower().split(":")[0]
                for avail in available
            )
            status[model_name] = found
            if not found:
                missing.append(model_name)

        return len(missing) == 0, status, missing

    def check_debate_readiness(
        self, debate_providers: Dict[str, str]
    ) -> Tuple[bool, Dict[str, str], List[str]]:
        """
        Check if all debate seat providers (bull/bear/judge) are available.

        Args:
            debate_providers: Dict like {"bull": "mistral:latest", "bear": "llama2:13b", "judge": "codellama"}

        Returns:
            Tuple of (all_ready, per_seat_status, missing_models)
        """
        seat_status = {}
        missing = []
        available = self.get_available_models()

        for seat, provider in debate_providers.items():
            # Check if provider is an Ollama model tag (contains ':' or matches installed models)
            if ":" in provider or provider in available:
                seat_status[seat] = provider
            else:
                # Try to match base name against installed models
                base = provider.lower().split(":")[0]
                matched = [
                    av for av in available if base in av.lower().split(":")[0]
                ]
                if matched:
                    seat_status[seat] = matched[0]
                else:
                    seat_status[seat] = provider
                    missing.append(provider)

        return len(missing) == 0, seat_status, missing

    def get_remediation_hints(self, missing_models: List[str]) -> str:
        """
        Generate user-friendly remediation commands.

        Args:
            missing_models: List of missing model tags

        Returns:
            Formatted remediation guidance
        """
        if not missing_models:
            return ""

        hints = "To download missing models:\n"
        for model in missing_models:
            hints += f"  ollama pull {model}\n"
        return hints


def verify_ollama_for_agent(
    config: Dict,
    debate_mode: bool = True,
    debate_providers: Optional[Dict[str, str]] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Pre-flight check for Ollama before starting agent.

    Args:
        config: Agent/engine configuration
        debate_mode: Whether debate mode is enabled
        debate_providers: Debate seat providers if debate_mode=True

    Returns:
        Tuple of (is_ready, error_message)
    """
    checker = OllamaReadinessChecker()

    # Check service availability
    service_ok, service_err = checker.check_service_available()
    if not service_ok:
        return False, service_err

    # If debate mode, check debate seat models
    if debate_mode and debate_providers:
        resolved_debate = resolve_debate_providers(debate_providers, config)
        ready, seat_status, missing = checker.check_debate_readiness(
            resolved_debate
        )
        if not ready:
            hints = checker.get_remediation_hints(missing)
            err = (
                f"Debate mode enabled but the following models are not installed:\n"
                f"  {', '.join(missing)}\n\n{hints}"
            )
            return False, err

    return True, None


def resolve_debate_providers(
    debate_providers: Dict[str, str], config: Dict[str, Any]
) -> Dict[str, str]:
    """
    Resolve placeholder/local debate providers into concrete model tags.

    - If a provider is "local" or blank, use configured decision_engine.local_models
      as the source of real tags.
    - Falls back to LocalLLMProvider defaults when local_models is empty.

    Args:
        debate_providers: Raw debate provider mapping from config
        config: Full config dict for fallback local model hints

    Returns:
        Dict of resolved debate providers with real model tags where possible
    """

    try:
        from finance_feedback_engine.decision_engine.local_llm_provider import (
            LocalLLMProvider,
        )
    except Exception:
        LocalLLMProvider = None

    # Ordered list of candidates pulled from config.local_models, else hard defaults
    local_models: List[str] = (
        config.get("decision_engine", {}).get("local_models", []) or []
    )

    fallback_models: List[str] = []
    if LocalLLMProvider:
        fallback_models = [
            LocalLLMProvider.DEFAULT_MODEL,
            LocalLLMProvider.SECONDARY_MODEL,
            LocalLLMProvider.FALLBACK_MODEL,
        ]

    # Ensure we have at least three candidates to map bull/bear/judge
    candidates = [m for m in local_models if m] or fallback_models
    if not candidates:
        candidates = [
            "mistral:7b-instruct",
            "llama3.2:3b-instruct-fp16",
            "deepseek-r1:8b",
        ]

    resolved: Dict[str, str] = {}
    used = set()
    candidate_idx = 0

    for seat, provider in debate_providers.items():
        provider_str = str(provider).strip()
        if provider_str and provider_str.lower() != "local":
            resolved[seat] = provider_str
            used.add(provider_str.lower())
            continue

        # Map "local"/blank to next available candidate, avoiding duplicates where possible
        while candidate_idx < len(candidates):
            candidate = candidates[candidate_idx]
            candidate_idx += 1
            if candidate and candidate.lower() not in used:
                resolved[seat] = candidate
                used.add(candidate.lower())
                break
        else:
            # Fallback: reuse first candidate if we ran out (should be rare)
            resolved[seat] = candidates[0]

    return resolved
