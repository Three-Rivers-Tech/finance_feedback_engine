"""Risk gatekeeper module."""

from __future__ import annotations

from typing import Dict, Tuple


class RiskGatekeeper:
    """Validate trade decisions against risk constraints."""

    @staticmethod
    def _count_holdings_by_category(
        holdings: Dict[str, str],
    ) -> Dict[str, int]:
        """
        Count holdings per asset category.

        Args:
            holdings: Mapping from asset ID to its category.

        Returns:
            Mapping from category to number of holdings.
        """
        counts: Dict[str, int] = {}
        for category in holdings.values():
            counts[category] = counts.get(category, 0) + 1
        return counts

    def validate_trade(
        self,
        decision: Dict,
        context: Dict,
    ) -> Tuple[bool, str]:
        """
        Validate a trade decision against drawdown, correlation,
        and volatility/confidence thresholds.

        Args:
            decision: Dict with trade details. Expected keys:
                ``action``, ``asset_category``, ``volatility``,
                optional ``model_confidence``.
            context: Dict with portfolio context. Expected keys:
                ``recent_performance`` (with ``total_pnl``) and
                ``holdings`` (asset_id → category).

        Returns:
            Tuple ``(is_allowed, message)`` where ``is_allowed`` is ``True``
            if the trade passes all checks, otherwise ``False``.
        """
        # Max Drawdown Check
        recent_perf = context.get("recent_performance", {})
        total_pnl = recent_perf.get("total_pnl", 0.0)
        if total_pnl < -0.05:
            return False, "Max drawdown exceeded"

        # Correlation Check
        asset_category = decision.get("asset_category")
        if asset_category is not None:
            holdings = context.get("holdings", {})
            category_counts = self._count_holdings_by_category(holdings)
            if (
                category_counts.get(asset_category, 0) >= 2
                and decision.get("action") == "BUY"
            ):
                return False, "Correlation limit exceeded"

        # Volatility / Confidence Check
        volatility = decision.get("volatility", 0.0)
        confidence = decision.get("model_confidence", 0.0)
        if volatility > 0.05 and confidence < 0.80:
            return False, "Volatility/confidence threshold exceeded"

        # All checks passed
        return True, "Trade approved"