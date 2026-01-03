"""
Ollama readiness checker for agent startup.

Verifies Ollama is running and required models are available before starting the agent.
Provides diagnostics and remediation guidance.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

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
        ready, seat_status, missing = checker.check_debate_readiness(
            debate_providers
        )
        if not ready:
            hints = checker.get_remediation_hints(missing)
            err = (
                f"Debate mode enabled but the following models are not installed:\n"
                f"  {', '.join(missing)}\n\n{hints}"
            )
            return False, err

    return True, None
