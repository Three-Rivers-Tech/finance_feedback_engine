"""
Two-phase ensemble aggregation with smart premium API escalation.

Implements a two-phase decision making process:
- Phase 1: Query free-tier providers
- Phase 2: Escalate to premium providers if needed
"""

import asyncio
import logging
from typing import Any, Dict, List

from ..exceptions import InsufficientProvidersError

logger = logging.getLogger(__name__)

# Canonical asset types (must match provider_tiers.py expectations)
CANONICAL_ASSET_TYPES = {"crypto", "forex", "stock"}

# Normalization mapping: common variations -> canonical type
ASSET_TYPE_NORMALIZATION = {
    "cryptocurrency": "crypto",
    "cryptocurrencies": "crypto",
    "digital_currency": "crypto",
    "digital": "crypto",
    "btc": "crypto",
    "eth": "crypto",
    "foreign_exchange": "forex",
    "fx": "forex",
    "currency": "forex",
    "currency_pair": "forex",
    "equities": "stock",
    "equity": "stock",
    "shares": "stock",
    "stocks": "stock",
}


class TwoPhaseAggregator:
    """
    Handles two-phase ensemble aggregation with premium API escalation.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize two-phase aggregator.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.two_phase_config = config.get("ensemble", {}).get("two_phase", {})
        self.enabled = self.two_phase_config.get("enabled", False)

    async def aggregate_two_phase(
        self,
        prompt: str,
        asset_pair: str,
        market_data: Dict[str, Any],
        query_function: callable,
    ) -> Dict[str, Any]:
        """
        Two-phase ensemble aggregation with smart premium API escalation.

        OPTIMIZED: Phase 1 and Phase 2 now run in parallel for improved latency.
        Premium provider is queried simultaneously with free providers.

        Phase 1: Query free-tier providers (5 Ollama + Qwen)
          - Require minimum 3 successful responses (quorum)
          - Calculate weighted consensus and agreement rate

        Phase 2: Escalate to premium providers if:
          - Phase 1 confidence < threshold (default 75%)
          - Phase 1 agreement < threshold (default 60%)
          - High-stakes position (size > threshold)

        Premium provider selection by asset type:
          - Crypto -> Copilot CLI
          - Forex/Stock -> Gemini
          - Fallback -> Codex (if primary fails)
          - Tiebreaker -> Codex (if primary disagrees with Phase 1)

        Args:
            prompt: Decision prompt for AI providers
            asset_pair: Asset pair being analyzed
            market_data: Market data dict (must include 'type' field)
            query_function: Function to query individual providers

        Returns:
            Decision dict with two-phase metadata

        Raises:
            InsufficientProvidersError: If Phase 1 quorum not met
        """
        from ..decision_engine.provider_tiers import (
            get_fallback_provider,
            get_free_providers,
            get_premium_provider_for_asset,
        )
        from ..utils.cost_tracker import check_budget, log_premium_call

        # ===== EARLY ASSET_TYPE VALIDATION AND NORMALIZATION =====
        # Extract raw asset_type from market_data
        raw_asset_type = market_data.get("type", None)

        # Normalize asset_type
        if raw_asset_type is None:
            logger.warning(
                f"Asset type missing in market_data for {asset_pair}. "
                "Defaulting to 'crypto' for safe escalation."
            )
            normalized_asset_type = "crypto"  # Safe default
        elif isinstance(raw_asset_type, str):
            raw_lower = raw_asset_type.lower().strip()

            # Check if already canonical
            if raw_lower in CANONICAL_ASSET_TYPES:
                normalized_asset_type = raw_lower
            # Check if it's a known variation
            elif raw_lower in ASSET_TYPE_NORMALIZATION:
                normalized_asset_type = ASSET_TYPE_NORMALIZATION[raw_lower]
                logger.info(
                    f"Asset type normalized: '{raw_asset_type}' -> '{normalized_asset_type}' "
                    f"for {asset_pair}"
                )
            # Handle unknown/invalid asset types
            else:
                logger.error(
                    f"Invalid asset_type '{raw_asset_type}' for {asset_pair}. "
                    f"Expected one of {CANONICAL_ASSET_TYPES} or variations. "
                    "Defaulting to 'crypto' for safe escalation."
                )
                normalized_asset_type = "crypto"  # Safe default
        else:
            logger.error(
                f"Asset type is not a string (type: {type(raw_asset_type)}) for {asset_pair}. "
                "Defaulting to 'crypto' for safe escalation."
            )
            normalized_asset_type = "crypto"  # Safe default

        # Final validation: ensure normalized type is in canonical set
        if normalized_asset_type not in CANONICAL_ASSET_TYPES:
            logger.error(
                f"CRITICAL: Normalized asset_type '{normalized_asset_type}' is not canonical! "
                f"This should never happen. Aborting escalation for {asset_pair}."
            )
            raise ValueError(
                f"Asset type validation failed: '{normalized_asset_type}' is not in {CANONICAL_ASSET_TYPES}. "
                "Cannot proceed with premium escalation."
            )

        logger.info(f"Asset type validated for {asset_pair}: '{normalized_asset_type}'")

        # Update market_data with normalized type for downstream use
        market_data = market_data.copy()  # Avoid mutating caller's dict
        market_data["type"] = normalized_asset_type

        # If two-phase not enabled, return None to indicate standard aggregation
        if not self.enabled:
            logger.info("Two-phase mode not enabled, using standard aggregation")
            return None

        # ===== PHASE 1 EXECUTION =====
        logger.info(f"=== TWO-PHASE: Running Phase 1 providers for {asset_pair} ===")

        free_tier = get_free_providers()
        phase1_quorum = self.two_phase_config.get("phase1_min_quorum", 3)

        # Create tasks for Phase 1 providers only
        phase1_tasks = [query_function(provider, prompt) for provider in free_tier]

        # Execute Phase 1 queries in parallel
        results = await asyncio.gather(*phase1_tasks, return_exceptions=True)

        # Process Phase 1 results (free tier)
        phase1_decisions = {}
        phase1_failed = []

        for i, provider in enumerate(free_tier):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"Phase 1: {provider} failed: {result}")
                phase1_failed.append(provider)
            else:
                decision = result
                if self._is_valid_provider_response(decision, provider):
                    phase1_decisions[provider] = decision
                    logger.info(
                        f"Phase 1: {provider} -> {decision.get('action')} ({decision.get('confidence')}%)"
                    )
                else:
                    logger.warning(f"Phase 1: {provider} returned invalid response")
                    phase1_failed.append(provider)

        # Check Phase 1 quorum
        phase1_success_count = len(phase1_decisions)

        if phase1_success_count < phase1_quorum:
            logger.error(
                f"Phase 1 quorum failure: {phase1_success_count}/{len(free_tier)} "
                f"succeeded (need ≥{phase1_quorum})"
            )
            # Get the providers that actually succeeded
            providers_succeeded = list(phase1_decisions.keys())
            providers_failed = phase1_failed

            raise InsufficientProvidersError(
                f"Phase 1 quorum not met: {phase1_success_count}/{len(free_tier)} "
                f"providers succeeded (required: {phase1_quorum})",
                providers_failed=providers_failed,
                providers_succeeded=providers_succeeded,
            )

        # Aggregate Phase 1 decisions (metrics only; final aggregation handled upstream)
        phase1_metrics = self._calculate_phase1_metrics(phase1_decisions)
        phase1_confidence_ratio = (
            phase1_metrics["avg_confidence"] / 100.0
            if phase1_metrics["avg_confidence"]
            else 0.0
        )

        phase1_result = {
            "provider_decisions": phase1_decisions,
            "failed_providers": phase1_failed,
            "num_success": phase1_success_count,
            "quorum_met": True,
            "phase1_metrics": phase1_metrics,
        }

        # Process Phase 2 results
        confidence_threshold = self.two_phase_config.get(
            "phase1_confidence_threshold", 0.75
        )
        agreement_threshold = self.two_phase_config.get(
            "phase1_agreement_threshold", 0.6
        )
        require_premium_for_high_stakes = self.two_phase_config.get(
            "require_premium_for_high_stakes", True
        )
        high_stakes_threshold = self.two_phase_config.get(
            "high_stakes_position_threshold", 1000
        )
        max_premium_calls = self.two_phase_config.get("max_premium_calls_per_day", 50)

        # Determine if Phase 2 escalation is required
        position_value = self._extract_position_value(market_data)

        escalation_triggers = []
        if phase1_confidence_ratio < confidence_threshold:
            escalation_triggers.append("low_confidence")
        if phase1_metrics["agreement"] < agreement_threshold:
            escalation_triggers.append("low_agreement")
        if require_premium_for_high_stakes and position_value >= high_stakes_threshold:
            escalation_triggers.append("high_stakes")

        should_escalate = len(escalation_triggers) > 0

        # Budget gate for premium calls
        if should_escalate and not check_budget(max_premium_calls):
            logger.warning("Premium call budget exceeded; skipping Phase 2 escalation")
            return {
                "phase1_result": phase1_result,
                "phase2_decisions": {},
                "phase2_failed": [],
                "phase2_primary_used": None,
                "phase2_fallback_used": False,
                "codex_tiebreaker_used": False,
                "normalized_asset_type": normalized_asset_type,
                "two_phase_config": self.two_phase_config,
                "phase2_triggered": False,
                "phase2_skip_reason": "budget_exceeded",
                "phase2_escalation_reason": None,
                "escalation_triggers": escalation_triggers,
                "position_value": position_value,
            }

        # Skip Phase 2 when thresholds are satisfied
        if not should_escalate:
            logger.info("Phase 1 met thresholds; skipping Phase 2 escalation")
            return {
                "phase1_result": phase1_result,
                "phase2_decisions": {},
                "phase2_failed": [],
                "phase2_primary_used": None,
                "phase2_fallback_used": False,
                "codex_tiebreaker_used": False,
                "normalized_asset_type": normalized_asset_type,
                "two_phase_config": self.two_phase_config,
                "phase2_triggered": False,
                "phase2_skip_reason": "thresholds_met",
                "phase2_escalation_reason": None,
                "escalation_triggers": escalation_triggers,
                "position_value": position_value,
            }

        # Premium provider selection happens only when escalation is required
        primary_provider = get_premium_provider_for_asset(normalized_asset_type)
        fallback_provider = get_fallback_provider()
        codex_as_tiebreaker = self.two_phase_config.get("codex_as_tiebreaker", True)

        # Process the premium provider result (from parallel execution)
        phase2_decisions = {}
        phase2_primary_used = None
        phase2_fallback_used = False
        codex_tiebreaker_used = False
        phase2_failed = []

        phase2_escalation_reason = "|".join(escalation_triggers)

        # Execute premium provider now that escalation is confirmed
        try:
            primary_provider_result = await query_function(primary_provider, prompt)
        except Exception as exc:
            primary_provider_result = exc

        if isinstance(primary_provider_result, Exception):
            logger.error(
                f"Phase 2: {primary_provider} failed: {primary_provider_result}"
            )
            phase2_failed.append(primary_provider)

            # Fallback to Codex - check if it was also in parallel execution (depends on config)
            # For now, execute fallback synchronously since it's only used in specific scenarios
            if (
                codex_as_tiebreaker
            ):  # Only use if tiebreaker is needed and primary fails
                try:
                    fallback_decision = await query_function(fallback_provider, prompt)
                    if self._is_valid_provider_response(
                        fallback_decision, fallback_provider
                    ):
                        phase2_decisions[fallback_provider] = fallback_decision
                        phase2_fallback_used = True
                        logger.info(
                            f"Phase 2: {fallback_provider} (fallback) -> {fallback_decision.get('action')} "
                            f"({fallback_decision.get('confidence')}%)"
                        )
                    else:
                        logger.warning(
                            f"Phase 2: {fallback_provider} (fallback) returned invalid response"
                        )
                        phase2_failed.append(fallback_provider)
                except Exception as e2:
                    logger.error(
                        f"Phase 2: {fallback_provider} (fallback) also failed: {e2}"
                    )
                    phase2_failed.append(fallback_provider)
        else:
            primary_decision = primary_provider_result
            if self._is_valid_provider_response(primary_decision, primary_provider):
                phase2_decisions[primary_provider] = primary_decision
                phase2_primary_used = primary_provider
                logger.info(
                    f"Phase 2: {primary_provider} -> {primary_decision.get('action')} "
                    f"({primary_decision.get('confidence')}%)"
                )

                # Check if Codex tiebreaker needed (primary disagrees with Phase 1)
                if codex_as_tiebreaker and primary_decision.get(
                    "action"
                ) != phase1_metrics.get("majority_action", ""):
                    logger.info(
                        f"Phase 2: {primary_provider} disagrees with Phase 1 -> calling Codex tiebreaker"
                    )
                    try:
                        codex_decision = await query_function(fallback_provider, prompt)
                        if self._is_valid_provider_response(
                            codex_decision, fallback_provider
                        ):
                            phase2_decisions[fallback_provider] = codex_decision
                            codex_tiebreaker_used = True
                            logger.info(
                                f"Phase 2: {fallback_provider} (tiebreaker) -> {codex_decision.get('action')} "
                                f"({codex_decision.get('confidence')}%)"
                            )
                    except Exception as e:
                        logger.warning(f"Phase 2: Codex tiebreaker failed: {e}")
            else:
                logger.warning(f"Phase 2: {primary_provider} returned invalid response")
                phase2_failed.append(primary_provider)

        # Log premium API calls only when escalation actually occurred
        if should_escalate:
            # Include which premium path was exercised
            premium_reason_parts = []
            if phase2_escalation_reason:
                premium_reason_parts.append(phase2_escalation_reason)
            if phase2_primary_used:
                premium_reason_parts.append("primary_used")
            if phase2_fallback_used:
                premium_reason_parts.append("fallback_used")
            if codex_tiebreaker_used:
                premium_reason_parts.append("codex_tiebreaker")

            log_premium_call(
                asset=asset_pair,
                asset_type=normalized_asset_type,
                phase="phase2",
                primary_provider=phase2_primary_used,
                codex_called=codex_tiebreaker_used or phase2_fallback_used,
                escalation_reason=(
                    "|".join(premium_reason_parts) if premium_reason_parts else None
                ),
            )

        return {
            "phase1_result": phase1_result,
            "phase2_decisions": phase2_decisions,
            "phase2_failed": phase2_failed,
            "phase2_primary_used": phase2_primary_used,
            "phase2_fallback_used": phase2_fallback_used,
            "codex_tiebreaker_used": codex_tiebreaker_used,
            "normalized_asset_type": normalized_asset_type,
            "two_phase_config": self.two_phase_config,
            "phase2_triggered": True,
            "phase2_skip_reason": None,
            "phase2_escalation_reason": phase2_escalation_reason,
            "escalation_triggers": escalation_triggers,
            "position_value": position_value,
        }

    def _is_valid_provider_response(
        self, decision: Dict[str, Any], provider: str
    ) -> bool:
        """
        Validate that a provider response dict is well-formed.

        Args:
            decision: Decision dictionary from provider to validate
            provider: Name of the provider for logging

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(decision, dict):
            logger.warning(f"Provider {provider}: decision is not a dict")
            return False

        if "action" not in decision or "confidence" not in decision:
            logger.warning(
                f"Provider {provider}: missing required keys 'action' or 'confidence'"
            )
            return False

        if decision["action"] not in ["BUY", "SELL", "HOLD"]:
            logger.warning(
                f"Provider {provider}: invalid action '{decision['action']}'"
            )
            return False

        conf = decision["confidence"]
        if not isinstance(conf, (int, float)):
            logger.warning(f"Provider {provider}: confidence is not numeric")
            return False
        if not (0 <= conf <= 100):
            logger.warning(
                f"Provider {provider}: Confidence {conf} out of range [0, 100]"
            )
            return False

        return True

    def _calculate_phase1_metrics(
        self, decisions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate agreement, majority action, and average confidence for Phase 1."""
        from collections import Counter

        actions: List[str] = []
        confidences: List[float] = []

        for decision in decisions.values():
            action = decision.get("action")
            confidence = decision.get("confidence")
            if action is not None:
                actions.append(action)
            if isinstance(confidence, (int, float)):
                confidences.append(float(confidence))

        if actions:
            counts = Counter(actions)
            majority_action, majority_count = counts.most_common(1)[0]
            agreement = majority_count / len(actions)
        else:
            majority_action = None
            agreement = 0.0

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "majority_action": majority_action,
            "agreement": agreement,
            "avg_confidence": avg_confidence,
        }

    def _extract_position_value(self, market_data: Dict[str, Any]) -> float:
        """Best-effort extraction of position value for high-stakes gating."""
        if not isinstance(market_data, dict):
            return 0.0

        # Direct field if provided
        position_value = market_data.get("position_value")
        if isinstance(position_value, (int, float)):
            return float(position_value)

        # Derive from position size * price if available
        position_size = market_data.get("position_size")
        price = market_data.get("close") or market_data.get("price")
        if isinstance(position_size, (int, float)) and isinstance(price, (int, float)):
            return abs(float(position_size) * float(price))

        return 0.0
