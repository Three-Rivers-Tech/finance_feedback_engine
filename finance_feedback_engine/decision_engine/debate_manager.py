"""
Debate mode decision manager.

Implements debate-style decision making with:
- Bullish provider argument
- Bearish provider argument
- Judge provider decision
"""

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .policy_actions import (
    POLICY_ACTION_VERSION,
    build_ai_decision_envelope,
    build_policy_package,
    get_legacy_action_compatibility,
    get_policy_action_family,
    is_derisking_policy_action,
    is_policy_action,
    is_structurally_valid,
)

logger = logging.getLogger(__name__)

MATERIAL_CONFIDENCE_GAP = 15


def _normalize_market_regime(value: Any) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.lower() in {"unknown", "none", "null", "n/a", "na"}:
        return None
    return normalized


def _with_policy_action_metadata(decision: Dict[str, Any]) -> Dict[str, Any]:
    """Add bounded policy-action metadata to a role decision when present."""
    enriched = deepcopy(decision)
    action = enriched.get("action")
    if is_policy_action(action):
        enriched.setdefault("policy_action", action)
        enriched.setdefault("policy_action_version", POLICY_ACTION_VERSION)
        enriched.setdefault("policy_action_family", get_policy_action_family(action))
        enriched.setdefault(
            "legacy_action_compatibility", get_legacy_action_compatibility(action)
        )
    else:
        enriched.setdefault("policy_action", None)
        enriched.setdefault("policy_action_version", None)
        enriched.setdefault("policy_action_family", None)
        enriched.setdefault("legacy_action_compatibility", None)
    return enriched




def _directional_side(action: Optional[str]) -> Optional[str]:
    action = str(action or '').upper()
    if action == 'HOLD':
        return None
    if action.endswith('_LONG') or 'LONG' in action or action == 'BUY':
        return 'bull'
    if action.endswith('_SHORT') or 'SHORT' in action or action == 'SELL':
        return 'bear'
    return None


# Minimum absolute confidence for a single-sided hold override
_HOLD_OVERRIDE_MIN_CONFIDENCE = 70


def _judge_hold_override(
    bull_case: Dict[str, Any],
    bear_case: Dict[str, Any],
    judge_decision: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Override judge HOLD when one advocate has a strong entry signal.

    Previously required BOTH bull=bullish AND bear=bearish simultaneously,
    which never happened in practice (0/4853 decisions). Relaxed to: if
    either advocate recommends a directional ENTRY action with confidence
    >= 70% and a material gap over the other, override the judge.
    Note: exit/derisking overrides are handled by _judge_exit_override.
    """
    if str(judge_decision.get('action', '')).upper() != 'HOLD':
        return None

    bull_side = _directional_side(bull_case.get('action'))
    bear_side = _directional_side(bear_case.get('action'))

    bull_conf = int(bull_case.get('confidence', 0) or 0)
    bear_conf = int(bear_case.get('confidence', 0) or 0)

    # Original strict mode: both must be directional + gap check
    if bull_side == 'bull' and bear_side == 'bear':
        gap = abs(bull_conf - bear_conf)
        if gap >= MATERIAL_CONFIDENCE_GAP:
            stronger_side = 'bull' if bull_conf > bear_conf else 'bear'
            stronger_case = bull_case if stronger_side == 'bull' else bear_case
            override = deepcopy(stronger_case)
            override['reasoning'] = (
                f"Judge HOLD overridden: {stronger_side} case materially stronger by confidence gap {gap}. | "
                f"Judge said HOLD ({judge_decision.get('confidence', 0)}). | "
                f"Original {stronger_side} reasoning: {stronger_case.get('reasoning', '')}"
            )
            override['judge_hold_override_applied'] = True
            override['judge_hold_override_side'] = stronger_side
            override['judge_hold_override_gap'] = gap
            override['original_judge_decision'] = deepcopy(judge_decision)
            return override

    # Relaxed mode: ONE advocate is directional with high confidence,
    # the other is HOLD or weakly opposed. This unblocks entries that the
    # judge conservatively suppresses.
    candidates = []
    if bull_side == 'bull' and bull_conf >= _HOLD_OVERRIDE_MIN_CONFIDENCE:
        # Bull wants to go long with high confidence
        other_conf = bear_conf if bear_side == 'bear' else 0
        gap = bull_conf - other_conf
        if gap >= MATERIAL_CONFIDENCE_GAP:
            candidates.append(('bull', bull_case, bull_conf, gap))
    if bear_side == 'bear' and bear_conf >= _HOLD_OVERRIDE_MIN_CONFIDENCE:
        # Bear wants to go short with high confidence
        other_conf = bull_conf if bull_side == 'bull' else 0
        gap = bear_conf - other_conf
        if gap >= MATERIAL_CONFIDENCE_GAP:
            candidates.append(('bear', bear_case, bear_conf, gap))

    if not candidates:
        return None

    # Pick the strongest candidate
    stronger_side, stronger_case, _, gap = max(candidates, key=lambda c: c[2])
    # Skip exit/derisking actions — those are handled by _judge_exit_override
    stronger_action = str(stronger_case.get('action', '')).upper()
    if stronger_action.startswith(('CLOSE_', 'REDUCE_')):
        return None
    override = deepcopy(stronger_case)
    override['reasoning'] = (
        f"Judge HOLD overridden: {stronger_side} case materially stronger by confidence gap {gap}. | "
        f"Judge said HOLD ({judge_decision.get('confidence', 0)}). | "
        f"Original {stronger_side} reasoning: {stronger_case.get('reasoning', '')}"
    )
    override['judge_hold_override_applied'] = True
    override['judge_hold_override_side'] = stronger_side
    override['judge_hold_override_gap'] = gap
    override['original_judge_decision'] = deepcopy(judge_decision)
    return override

EXIT_OVERRIDE_CONFIDENCE_THRESHOLD = 75


def _judge_exit_override(
    bull_case: Dict[str, Any],
    bear_case: Dict[str, Any],
    judge_decision: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Override judge HOLD when a role recommends exit/derisking with high confidence.

    DATA-DRIVEN: Bear calls CLOSE_SHORT 508 times, judge overrules to HOLD 444 times
    (87% suppressed). The system correctly identifies exit signals but the judge is
    too conservative about acting on them. Unlike _judge_hold_override (which checks
    the confidence *gap* for entry signals), this checks if EITHER role recommends a
    CLOSE_* or REDUCE_* action with absolute confidence >= 75%.
    """
    if str(judge_decision.get("action", "")).upper() != "HOLD":
        return None

    for role_name, role_case in [("bull", bull_case), ("bear", bear_case)]:
        action = role_case.get("action")
        if not action or not is_policy_action(action):
            continue

        if not is_derisking_policy_action(action):
            continue

        role_conf = int(role_case.get("confidence", 0) or 0)
        if role_conf < EXIT_OVERRIDE_CONFIDENCE_THRESHOLD:
            continue

        # This role recommends an exit/derisking action with high confidence.
        override = deepcopy(role_case)
        override["reasoning"] = (
            f"Judge HOLD overridden (exit conservatism fix): {role_name} recommends "
            f"{action} with confidence {role_conf}% >= {EXIT_OVERRIDE_CONFIDENCE_THRESHOLD}% threshold. | "
            f"Judge said HOLD ({judge_decision.get('confidence', 0)}%). | "
            f"Original {role_name} reasoning: {role_case.get('reasoning', '')}"
        )
        override["judge_exit_override_applied"] = True
        override["judge_exit_override_role"] = role_name
        override["judge_exit_override_action"] = action
        override["judge_exit_override_confidence"] = role_conf
        override["original_judge_decision"] = deepcopy(judge_decision)
        logger.info(
            "Judge exit override triggered: %s recommends %s (%d%% confidence), "
            "overriding judge HOLD (%s%% confidence)",
            role_name,
            action,
            role_conf,
            judge_decision.get("confidence", 0),
        )
        return override

    return None


class DebateManager:
    """
    Manages debate-style decision making with multiple providers taking different roles.

    Debate mode is always active and provides structured decision making where:
    - A bullish provider advocates for buy/long positions
    - A bearish provider advocates for sell/short positions
    - A judge provider makes the final decision considering both arguments
    """

    def __init__(self, debate_providers: Dict[str, str]):
        """
        Initialize debate manager.

        Args:
            debate_providers: Dictionary mapping roles ('bull', 'bear', 'judge')
                             to provider names. All roles must be present.
        """
        self.debate_providers = debate_providers

    def synthesize_debate_decision(
        self,
        bull_case: Dict[str, Any],
        bear_case: Dict[str, Any],
        judge_decision: Dict[str, Any],
        failed_debate_providers: Optional[List[str]] = None,
        failed_debate_roles: Optional[List[Dict[str, Any]]] = None,
        position_state: Optional[str] = None,
        market_regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synthesize debate decisions from bull, bear, and judge providers.

        Args:
            bull_case: Decision from bullish provider
            bear_case: Decision from bearish provider
            judge_decision: Final decision from judge provider
            failed_debate_providers: List of provider names that failed

        Returns:
            Synthesized decision with debate metadata
        """
        # Default failed providers list
        failed_debate_providers = failed_debate_providers or []

        # Validate that all debate results contain required keys
        required_keys = {"action", "confidence"}
        missing_keys = {}

        for name, decision in [
            ("bull_case", bull_case),
            ("bear_case", bear_case),
            ("judge_decision", judge_decision),
        ]:
            if decision is None:
                missing_keys[name] = list(required_keys)
        failed_roles = [
            role
            for role, provider in self.debate_providers.items()
            if provider in failed_debate_providers
        ]
        providers_used = [
            p
            for p in self.debate_providers.values()
            if p not in failed_debate_providers
        ]
        unique_providers = set(self.debate_providers.values())
        num_total = len(unique_providers)
        num_active = len(providers_used)
        failure_rate = (
            len(set(failed_debate_providers)) / num_total if num_total > 0 else 0.0
        )

        if missing_keys:
            error_details = ", ".join(
                [f"{name}: missing {keys}" for name, keys in missing_keys.items()]
            )
            raise ValueError(f"Debate results missing required keys - {error_details}")

        hold_override = _judge_hold_override(bull_case, bear_case, judge_decision)
        # OPT-1: Check exit override when judge says HOLD but a role wants to exit/derisk.
        # Applied after hold_override so that exit signals aren't masked by the gap check.
        exit_override = (
            _judge_exit_override(bull_case, bear_case, judge_decision)
            if hold_override is None
            else None
        )
        final_decision_source = (
            hold_override
            if hold_override is not None
            else (exit_override if exit_override is not None else judge_decision)
        )

        # Defense-in-depth: if the synthesized action is structurally invalid
        # for the current position state, force HOLD.  This catches cases where
        # an override promoted an invalid role action that slipped past the
        # earlier per-role gate.
        if position_state is not None:
            synth_action = final_decision_source.get("action") or final_decision_source.get("policy_action")
            if synth_action and is_policy_action(synth_action) and not is_structurally_valid(synth_action, position_state):
                logger.warning(
                    "Debate synthesize: final action %s invalid for position_state=%s — forcing HOLD",
                    synth_action, position_state,
                )
                final_decision_source = deepcopy(final_decision_source)
                original_action = synth_action
                final_decision_source["action"] = "HOLD"
                final_decision_source["policy_action"] = "HOLD"
                final_decision_source["confidence"] = min(
                    int(final_decision_source.get("confidence", 50) or 50), 40,
                )
                final_decision_source["reasoning"] = (
                    f"[SYNTH-POSITION-GATE] {original_action} invalid for "
                    f"position_state={position_state}. "
                    + str(final_decision_source.get("reasoning", ""))
                )
                final_decision_source["position_state_coerced"] = True
                final_decision_source["position_state_original_action"] = original_action

        final_decision = _with_policy_action_metadata(final_decision_source)
        judge_policy_package = (
            judge_decision.get("policy_package") if isinstance(judge_decision, dict) else None
        )

        final_decision["debate_metadata"] = {
            "bull_case": bull_case,
            "bear_case": bear_case,
            "judge_reasoning": judge_decision.get("reasoning", ""),
            "debate_providers": self.debate_providers,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "judge_hold_override_applied": bool(hold_override),
            "judge_hold_override_side": hold_override.get("judge_hold_override_side") if hold_override else None,
            "judge_hold_override_gap": hold_override.get("judge_hold_override_gap") if hold_override else None,
            "judge_exit_override_applied": bool(exit_override),
            "judge_exit_override_role": exit_override.get("judge_exit_override_role") if exit_override else None,
            "judge_exit_override_action": exit_override.get("judge_exit_override_action") if exit_override else None,
            "judge_exit_override_confidence": exit_override.get("judge_exit_override_confidence") if exit_override else None,
        }
        providers_used = list(
            set(
                p
                for p in self.debate_providers.values()
                if p not in failed_debate_providers
            )
        )

        # Add ensemble metadata for consistency
        explicit_failed_roles = {
            str(item.get("role"))
            for item in (failed_debate_roles or [])
            if isinstance(item, dict) and item.get("role")
        }
        if explicit_failed_roles:
            failed_roles = sorted(explicit_failed_roles)
        else:
            failed_roles = [
                role
                for role, provider in self.debate_providers.items()
                if provider in failed_debate_providers
            ]
        providers_used = [
            p
            for role, p in self.debate_providers.items()
            if role not in failed_roles
        ]
        num_total = len(self.debate_providers)
        num_active = len(providers_used)
        failure_rate = (
            len(failed_debate_providers) / num_total if num_total > 0 else 0.0
        )

        # Track decisions by role (not provider) to avoid collisions
        # when multiple roles use same provider (e.g., all using "local")
        role_decisions = {}
        debate_seats = {}
        
        if "bull" not in failed_roles:
            role_decisions["bull"] = {
                **_with_policy_action_metadata(bull_case),
                "role": "bull",
                "provider": self.debate_providers["bull"],
            }
            debate_seats["bull"] = self.debate_providers["bull"]
            
        if "bear" not in failed_roles:
            role_decisions["bear"] = {
                **_with_policy_action_metadata(bear_case),
                "role": "bear", 
                "provider": self.debate_providers["bear"],
            }
            debate_seats["bear"] = self.debate_providers["bear"]
            
        if "judge" not in failed_roles:
            role_decisions["judge"] = {
                **_with_policy_action_metadata(judge_decision),
                "role": "judge",
                "provider": self.debate_providers["judge"],
            }
            debate_seats["judge"] = self.debate_providers["judge"]
        
        # Provider-keyed view for downstream consumers that still read provider_decisions.
        # Debate seats remain the canonical role-aware structure when roles matter.
        provider_decisions = {}
        for role_name, role_decision in role_decisions.items():
            provider_name = role_decision.get("provider")
            if not provider_name:
                continue
            provider_decisions[provider_name] = {
                key: value
                for key, value in role_decision.items()
                if key != "role"
            }

        final_decision["ensemble_metadata"] = {
            "providers_used": providers_used,
            "providers_failed": failed_debate_providers,
            "num_active": num_active,
            "num_total": num_total,
            "failure_rate": failure_rate,
            "original_weights": {},
            "adjusted_weights": {},
            "weight_adjustment_applied": False,
            "voting_strategy": "debate",
            "fallback_tier": "none",
            "provider_decisions": provider_decisions,  # Legacy (backward compat)
            "role_decisions": role_decisions,  # NEW: decisions by role (bull/bear/judge)
            "debate_seats": debate_seats,  # NEW: role -> provider mapping
            "agreement_score": 1.0,  # Judge makes final decision
            "confidence_variance": 0.0,
            "confidence_adjusted": False,
            "local_priority_applied": False,
            "local_models_used": [],
            "debate_mode": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "judge_hold_override_applied": bool(hold_override),
            "judge_hold_override_side": hold_override.get("judge_hold_override_side") if hold_override else None,
            "judge_hold_override_gap": hold_override.get("judge_hold_override_gap") if hold_override else None,
            "judge_exit_override_applied": bool(exit_override),
            "judge_exit_override_role": exit_override.get("judge_exit_override_role") if exit_override else None,
            "judge_exit_override_action": exit_override.get("judge_exit_override_action") if exit_override else None,
        }
        if not final_decision.get("decision_origin"):
            final_decision["decision_origin"] = "judge"
        normalized_final_regime = _normalize_market_regime(final_decision.get("market_regime"))
        if normalized_final_regime:
            final_decision["market_regime"] = normalized_final_regime
        else:
            final_decision.pop("market_regime", None)
            for candidate in (
                judge_decision,
                bull_case,
                bear_case,
                {"market_regime": market_regime} if market_regime else None,
            ):
                if isinstance(candidate, dict):
                    normalized_candidate_regime = _normalize_market_regime(candidate.get("market_regime"))
                    if normalized_candidate_regime:
                        final_decision["market_regime"] = normalized_candidate_regime
                        break

        final_decision = build_ai_decision_envelope(
            decision=final_decision,
            policy_package=(
                build_policy_package(
                    policy_state=judge_policy_package.get("policy_state"),
                    action_context=judge_policy_package.get("action_context"),
                    policy_sizing_intent=judge_policy_package.get("policy_sizing_intent"),
                    provider_translation_result=judge_policy_package.get("provider_translation_result"),
                    control_outcome=judge_policy_package.get("control_outcome"),
                )
                if isinstance(judge_policy_package, dict)
                else None
            ),
        )

        decision_label = final_decision.get("policy_action") or final_decision.get("action")
        logger.info(
            f"Debate decision: {decision_label} "
            f"({final_decision['confidence']}%) - "
            f"Judge: {self.debate_providers['judge']}"
        )
        logger.info(
            "DEBATE MANAGER shape: origin=%s regime=%s has_ensemble=%s filtered=%s",
            final_decision.get("decision_origin") if isinstance(final_decision, dict) else None,
            final_decision.get("market_regime") if isinstance(final_decision, dict) else None,
            bool(final_decision.get("ensemble_metadata")) if isinstance(final_decision, dict) else False,
            final_decision.get("filtered_reason_code") if isinstance(final_decision, dict) else None,
        )

        return final_decision
