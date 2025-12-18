"""Safety guardrails for trading operations."""

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class SafetyGuardrails:
    """Pre-flight safety checks before trading operations."""

    @staticmethod
    def validate_decision_safety(decision: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a trading decision meets safety requirements.

        Args:
            decision: Trading decision dictionary

        Returns:
            (is_safe, list_of_violations)
        """
        violations = []

        # Check data freshness
        if decision.get("stale_data", False):
            violations.append("Stale data detected")

        # Check confidence threshold
        confidence = decision.get("confidence", 0)
        if confidence < 70:
            violations.append(f"Confidence too low: {confidence}%")

        # Check position sizing
        position_size = decision.get("position_size", 0)
        if position_size <= 0:
            violations.append("Invalid position size")

        # Check risk parameters
        stop_loss = decision.get("stop_loss")
        take_profit = decision.get("take_profit")
        if not stop_loss or not take_profit:
            violations.append("Missing risk parameters")

        if violations:
            logger.warning(
                "Safety violations detected",
                extra={"violations": violations, "decision_id": decision.get("id")},
            )
            return False, violations

        return True, []

    @staticmethod
    def validate_market_conditions() -> Tuple[bool, str]:
        """
        Validate market conditions are suitable for trading.

        Returns:
            (is_valid, status_message)
        """
        # Placeholder for market hours check, volatility check, etc.
        # In a full implementation, this would check:
        # - Market hours
        # - Extreme volatility conditions
        # - News events
        # - System health
        return True, "Market conditions acceptable"
