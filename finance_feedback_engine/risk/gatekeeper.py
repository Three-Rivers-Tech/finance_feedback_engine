"""Risk gatekeeper module with VaR and correlation analysis."""

from __future__ import annotations

from typing import Dict, Tuple, Optional
import logging

from finance_feedback_engine.utils.market_schedule import MarketSchedule
from finance_feedback_engine.utils.validation import validate_data_freshness

logger = logging.getLogger(__name__)


class RiskGatekeeper:
    """
    Validate trade decisions against risk constraints.

    Hybrid risk management approach:
    - Per-platform correlation: Max 2 assets with >0.7 correlation
    - Combined portfolio VaR: <5% daily loss at 95% confidence
    - Cross-platform correlation: Warning-only when >0.5

    Supports dual isolated portfolios (Coinbase + Oanda).
    """

    def __init__(
        self,
        max_drawdown_pct: float = 0.05,
        correlation_threshold: float = 0.7,
        max_correlated_assets: int = 2,
        max_var_pct: float = 0.05,  # 5% max daily VaR
        var_confidence: float = 0.95
    ):
        """
        Initialize risk gatekeeper.

        Args:
            max_drawdown_pct: Maximum portfolio drawdown (decimal)
            correlation_threshold: Correlation threshold for per-platform check
            max_correlated_assets: Max assets with high correlation per platform
            max_var_pct: Maximum portfolio VaR as % of portfolio value
            var_confidence: VaR confidence level (0.95 or 0.99)
        """
        self.max_drawdown_pct = max_drawdown_pct
        self.correlation_threshold = correlation_threshold
        self.max_correlated_assets = max_correlated_assets
        self.max_var_pct = max_var_pct
        self.var_confidence = var_confidence

        logger.info(
            f"RiskGatekeeper initialized: max_drawdown={max_drawdown_pct*100}%, "
            f"correlation_threshold={correlation_threshold}, "
            f"max_var={max_var_pct*100}% @ {var_confidence*100}% confidence"
        )

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

    def check_market_hours(self, decision: Dict) -> Tuple[bool, Dict]:
        """
        Check market hours and data freshness, overriding decision if needed.

        This is a gatekeeper-level enforcement that overrides AI decisions
        when markets are closed or data is stale, regardless of what the
        AI recommended.

        Args:
            decision: Decision dictionary containing market_data with
                     market_status and data_freshness

        Returns:
            Tuple of (needs_override, modified_decision)
            - needs_override: True if decision was modified
            - modified_decision: Updated decision dict (or original if no changes)
        """
        action = decision.get('action', 'HOLD')
        market_data = decision.get('market_data', {})
        market_status = market_data.get('market_status', {})
        data_freshness = market_data.get('data_freshness', {})

        needs_override = False
        modified_decision = decision.copy()
        reasoning = decision.get('reasoning', '')

        # Rule 1: Block trades when market is closed
        is_open = market_status.get('is_open', True)
        asset_type = market_data.get('asset_type', market_data.get('type', 'crypto'))

        # Crypto markets are 24/7, so only enforce for forex/stocks
        if not is_open and asset_type != 'crypto' and action in ['BUY', 'SELL']:
            logger.warning(
                f"[GATEKEEPER] Market is CLOSED for {asset_type}. "
                f"Overriding {action} → HOLD. Session: {market_status.get('session', 'Unknown')}"
            )
            modified_decision['action'] = 'HOLD'
            modified_decision['suggested_amount'] = 0
            modified_decision['recommended_position_size'] = None
            modified_decision['reasoning'] = (
                f"{reasoning}\n\n[BLOCKED BY GATEKEEPER: Market is Closed - "
                f"{market_status.get('session', 'Unknown')} session. "
                f"Cannot execute {action} orders when market is not open.]"
            )
            needs_override = True

        # Rule 2: Block trades when data is stale
        is_fresh = data_freshness.get('is_fresh', True)
        freshness_msg = data_freshness.get('message', '')

        if not is_fresh and action in ['BUY', 'SELL']:
            age_str = data_freshness.get('age_minutes', 'Unknown age')
            logger.error(
                f"[GATEKEEPER] Data is STALE ({age_str}). "
                f"Overriding {action} → HOLD. {freshness_msg}"
            )
            modified_decision['action'] = 'HOLD'
            modified_decision['suggested_amount'] = 0
            modified_decision['recommended_position_size'] = None

            # Append gatekeeper block message
            gatekeeper_msg = (
                f"\n\n[BLOCKED BY GATEKEEPER: Data is Stale - {age_str}. "
                f"{freshness_msg} Trading on outdated data is prohibited.]"
            )
            modified_decision['reasoning'] = f"{modified_decision.get('reasoning', reasoning)}{gatekeeper_msg}"
            needs_override = True

        if needs_override:
            logger.warning(
                f"[GATEKEEPER] Decision override applied: {decision['action']} → "
                f"{modified_decision['action']} for {decision.get('asset_pair', 'Unknown')}"
            )

        return needs_override, modified_decision

    def validate_trade(
        self,
        decision: Dict,
        context: Dict,
    ) -> Tuple[bool, str]:
        """
        Validate a trade decision against risk constraints.

        Enhanced with VaR and correlation analysis:
        1. Market hours and data freshness check (gatekeeper override)
        2. Max drawdown check (legacy)
        3. Per-platform correlation check (enhanced)
        4. Combined portfolio VaR check (new)
        5. Cross-platform correlation warning (new, non-blocking)
        6. Volatility/confidence check (legacy)

        Args:
            decision: Dict with trade details. Expected keys:
                ``action``, ``asset_category``, ``volatility``,
                ``confidence``, ``platform`` (optional).
            context: Dict with portfolio context. Expected keys:
                ``recent_performance`` (with ``total_pnl``),
                ``holdings`` (asset_id → category),
                ``var_analysis`` (optional, from VaRCalculator),
                ``correlation_analysis`` (optional, from CorrelationAnalyzer).

        Returns:
            Tuple ``(is_allowed, message)`` where ``is_allowed`` is ``True``
            if the trade passes all checks, otherwise ``False``.
        """
        # 0A. Gatekeeper Override Check (Market Hours & Data Freshness from Decision)
        # This enforces temporal constraints by overriding the decision if needed
        needs_override, modified_decision = self.check_market_hours(decision)
        if needs_override:
            # Update the original decision dict in-place with the modified values
            decision.update(modified_decision)
            logger.info(
                f"[GATEKEEPER] Decision was overridden to HOLD due to temporal constraints"
            )
            # After override to HOLD, the trade is technically "allowed" but neutralized
            # Return True since we've handled it, but log the override
            return True, "Decision overridden to HOLD (temporal constraints)"

        # 0B. Market Schedule Check (Legacy: from context for backward compatibility)
        # This provides additional validation using context data
        asset_pair = decision.get("asset_pair", "")
        asset_type = context.get("asset_type", "crypto")
        timestamp = context.get("timestamp")  # Unix timestamp or ISO string (for backtesting)

        if timestamp:
            # Convert ISO string to Unix timestamp if needed
            try:
                if isinstance(timestamp, str):
                    # Handle ISO format string: "2025-01-01T12:30:45.123456"
                    import datetime as _dt
                    dt_obj = _dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    unix_timestamp = int(dt_obj.timestamp())
                else:
                    # Already a Unix timestamp
                    unix_timestamp = int(timestamp)

                market_status = MarketSchedule.get_market_status_at_timestamp(
                    asset_pair, asset_type, unix_timestamp
                )
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse timestamp {timestamp}: {e}. Using live market status.")
                market_status = MarketSchedule.get_market_status(asset_pair, asset_type)
        else:
            market_status = MarketSchedule.get_market_status(asset_pair, asset_type)

        if not market_status["is_open"]:
            logger.warning(
                f"Market closed for {asset_pair} ({asset_type}). "
                f"Session: {market_status['session']}"
            )
            return False, f"Market closed ({market_status['session']})"

        if market_status["warning"]:
            logger.info(f"Market warning for {asset_pair}: {market_status['warning']}")

        # 1. Data Freshness Check (Prevents stale data decisions)
        market_data_timestamp = context.get("market_data_timestamp")
        if market_data_timestamp:
            # Determine timeframe for stocks
            timeframe = "intraday"
            if asset_type == "stocks":
                timeframe = context.get("timeframe", "intraday")

            try:
                is_fresh, age_str, freshness_msg = validate_data_freshness(
                    market_data_timestamp,
                    asset_type=asset_type,
                    timeframe=timeframe
                )

                if not is_fresh:
                    logger.error(f"Rejecting trade: {freshness_msg}")
                    return False, f"Stale market data ({age_str}): {freshness_msg}"

                if freshness_msg:  # Warning but still usable
                    logger.warning(f"Data freshness warning: {freshness_msg}")
            except ValueError as e:
                logger.error(f"Invalid market data timestamp: {e}")
                return False, f"Invalid timestamp: {str(e)}"

        # 2. Max Drawdown Check
        recent_perf = context.get("recent_performance", {})
        total_pnl = recent_perf.get("total_pnl", 0.0)
        if total_pnl < -self.max_drawdown_pct:
            logger.warning(
                f"Max drawdown exceeded: {total_pnl*100:.2f}% "
                f"(limit: {-self.max_drawdown_pct*100:.2f}%)"
            )
            return False, f"Max drawdown exceeded ({total_pnl*100:.2f}%)"

        # 3. Per-Platform Correlation Check (Enhanced)
        correlation_check_result = self._validate_correlation(decision, context)
        if not correlation_check_result[0]:
            return correlation_check_result

        # 4. Combined Portfolio VaR Check (New)
        var_check_result = self._validate_var(decision, context)
        if not var_check_result[0]:
            return var_check_result

        # 5. Cross-Platform Correlation Warning (Non-blocking)
        self._check_cross_platform_correlation(context)

        # 6. Volatility / Confidence Check
        volatility = decision.get("volatility", 0.0)
        # Confidence is stored as integer 0-100 in decision, convert to 0.0-1.0 for comparison
        raw_confidence = decision.get("confidence", 0)
        if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, (int, float)) or not 0 <= raw_confidence <= 100:
            logger.warning(
                f"Invalid confidence value: {raw_confidence}. Expected integer 0-100. Defaulting to 0."
            )
            raw_confidence = 0
        confidence = raw_confidence / 100.0
        if volatility > 0.05 and confidence < 0.80:
            logger.warning(
                f"Volatility/confidence threshold: vol={volatility:.3f}, "
                f"confidence={confidence:.2f}"
            )
            return False, "Volatility/confidence threshold exceeded"

        # All checks passed
        logger.info("Trade approved by RiskGatekeeper")
        return True, "Trade approved"

    def _validate_correlation(
        self,
        decision: Dict,
        context: Dict
    ) -> Tuple[bool, str]:
        """
        Validate per-platform correlation constraints.

        Uses correlation analysis if available, otherwise falls back
        to legacy category-based check.

        Args:
            decision: Trade decision
            context: Portfolio context

        Returns:
            Tuple (is_allowed, message)
        """
        # Check if we have correlation analysis in context
        correlation_analysis = context.get("correlation_analysis")

        if correlation_analysis:
            # Use enhanced correlation analysis
            platform = decision.get("platform", "").lower()

            # Determine which platform to check
            if "coinbase" in platform or decision.get("asset_pair", "").startswith("BTC"):
                platform_analysis = correlation_analysis.get("coinbase", {})
            elif "oanda" in platform or "_" in decision.get("asset_pair", ""):
                platform_analysis = correlation_analysis.get("oanda", {})
            else:
                # Unknown platform, skip correlation check
                platform_analysis = {}

            # Check for concentration warnings
            warning = platform_analysis.get("concentration_warning")
            if warning:
                logger.warning(f"Correlation warning: {warning}")
                return False, f"Correlation limit exceeded: {warning}"

        else:
            # Fallback to legacy category-based correlation check
            asset_category = decision.get("asset_category")
            if asset_category is not None:
                holdings = context.get("holdings", {})
                category_counts = self._count_holdings_by_category(holdings)
                if (
                    category_counts.get(asset_category, 0) >= self.max_correlated_assets
                    and decision.get("action") == "BUY"
                ):
                    logger.warning(
                        f"Category correlation limit: {category_counts.get(asset_category, 0)} "
                        f"assets in {asset_category} (limit: {self.max_correlated_assets})"
                    )
                    return False, "Correlation limit exceeded"

        return True, "Correlation check passed"

    def _validate_var(
        self,
        decision: Dict,
        context: Dict
    ) -> Tuple[bool, str]:
        """
        Validate combined portfolio VaR constraint.

        Args:
            decision: Trade decision
            context: Portfolio context with 'var_analysis'

        Returns:
            Tuple (is_allowed, message)
        """
        var_analysis = context.get("var_analysis")

        if not var_analysis:
            # No VaR analysis available, skip check
            return True, "VaR check skipped (no analysis)"

        # Get combined portfolio VaR
        combined_var = var_analysis.get("combined_var", {})
        var_pct = combined_var.get("var", 0.0)

        if var_pct > self.max_var_pct:
            logger.warning(
                f"Portfolio VaR exceeded: {var_pct*100:.2f}% "
                f"(limit: {self.max_var_pct*100:.2f}% @ {self.var_confidence*100}% confidence)"
            )
            return False, (
                f"Portfolio VaR limit exceeded: {var_pct*100:.2f}% "
                f"(max: {self.max_var_pct*100:.2f}%)"
            )

        logger.debug(
            f"VaR check passed: {var_pct*100:.2f}% < {self.max_var_pct*100:.2f}%"
        )
        return True, "VaR check passed"

    def _check_cross_platform_correlation(self, context: Dict) -> None:
        """
        Log warning for cross-platform correlation (non-blocking).

        Args:
            context: Portfolio context with 'correlation_analysis'
        """
        correlation_analysis = context.get("correlation_analysis")

        if not correlation_analysis:
            return

        cross_platform = correlation_analysis.get("cross_platform", {})
        warning = cross_platform.get("warning")

        if warning:
            logger.warning(f"⚠️  Cross-platform correlation: {warning}")
            # Note: This is warning-only, doesn't block trade
