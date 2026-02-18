"""Decision validator for trading decisions."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from .execution_quality import ExecutionQualityControls, calculate_size_multiplier

logger = logging.getLogger(__name__)


class DecisionValidator:
    """
    Validator for trading decisions.
    """

    def __init__(self, config: Dict[str, Any], backtest_mode: bool = False):
        self.config = config
        self.backtest_mode = backtest_mode

        # Safely extract decision_engine config section
        decision_engine = config.get("decision_engine")
        if not isinstance(decision_engine, dict):
            decision_engine = {}

        # Extract portfolio parameters with validation
        stop_loss_raw = decision_engine.get("portfolio_stop_loss_percentage", 0.02)
        take_profit_raw = decision_engine.get("portfolio_take_profit_percentage", 0.05)

        # Validate numeric types, fall back to defaults if invalid
        if not isinstance(stop_loss_raw, (int, float)):
            logger.warning(
                f"Invalid portfolio_stop_loss_percentage type: {type(stop_loss_raw).__name__}. Using default: 0.02"
            )
            stop_loss_raw = 0.02
        if not isinstance(take_profit_raw, (int, float)):
            logger.warning(
                f"Invalid portfolio_take_profit_percentage type: {type(take_profit_raw).__name__}. Using default: 0.05"
            )
            take_profit_raw = 0.05

        self.portfolio_stop_loss_percentage = stop_loss_raw
        self.portfolio_take_profit_percentage = take_profit_raw

        # Compatibility: Convert legacy percentage values (>1) to decimals
        if self.portfolio_stop_loss_percentage > 1:
            logger.warning(
                f"Detected legacy portfolio_stop_loss_percentage {self.portfolio_stop_loss_percentage}%. Converting to decimal: {self.portfolio_stop_loss_percentage/100:.3f}"
            )
            self.portfolio_stop_loss_percentage /= 100
        if self.portfolio_take_profit_percentage > 1:
            logger.warning(
                f"Detected legacy portfolio_take_profit_percentage {self.portfolio_take_profit_percentage}%. Converting to decimal: {self.portfolio_take_profit_percentage/100:.3f}"
            )
            self.portfolio_take_profit_percentage /= 100

    def create_decision(
        self,
        asset_pair: str,
        context: Dict[str, Any],
        ai_response: Dict[str, Any],
        position_sizing_result: Dict[str, Any],
        relevant_balance: Dict[str, float],
        balance_source: str,
        has_existing_position: bool,
        is_crypto: bool,
        is_forex: bool,
    ) -> Dict[str, Any]:
        """
        Create structured decision object.

        Args:
            asset_pair: Asset pair
            context: Decision context
            ai_response: AI recommendation
            position_sizing_result: Position sizing results
            relevant_balance: Platform-specific balance
            balance_source: Name of balance source (for logging)
            has_existing_position: Whether an existing position exists
            is_crypto: Whether the asset is crypto
            is_forex: Whether the asset is forex

        Returns:
            Structured decision
        """
        decision_id = str(uuid.uuid4())

        # Extract basic decision parameters
        current_price = context.get("market_data", {}).get("close", 0)
        action = ai_response.get("action", "HOLD")

        # Extract position sizing results
        # Use calculated position size from position_sizing_result
        recommended_position_size = position_sizing_result.get("recommended_position_size")
        stop_loss_price = position_sizing_result.get("stop_loss_price")
        sizing_stop_loss_percentage = position_sizing_result.get(
            "sizing_stop_loss_percentage", 0
        )
        risk_percentage = position_sizing_result.get("risk_percentage", 0)
        signal_only = position_sizing_result.get("signal_only", False)
        
        logger.debug(
            f"Position sizing extracted: size={recommended_position_size}, "
            f"stop_loss=${stop_loss_price}, risk={risk_percentage}"
        )

        # Calculate suggested_amount based on action and position sizing
        suggested_amount = ai_response.get("amount", 0)

        # Override suggested_amount to 0 for HOLD with no position
        if action == "HOLD" and not has_existing_position:
            suggested_amount = 0
            logger.debug("Overriding suggested_amount to 0 (HOLD with no position)")

        # For non-signal-only BUY/SELL: recommended_position_size is in asset units (e.g., BTC);
        # convert to USD notional by multiplying by current_price when the quote is USD/USDT
        if (
            not signal_only
            and action in ["BUY", "SELL"]
            and recommended_position_size
            and current_price > 0
        ):
            # Crypto futures expect USD notional; we derive notional from unit size * price
            if is_crypto and (
                asset_pair.endswith("USD") or asset_pair.endswith("USDT")
            ):
                suggested_amount = recommended_position_size * current_price
                logger.info(
                    "Position sizing: $%.2f USD notional for crypto futures (%.6f units @ $%.2f)",
                    suggested_amount,
                    recommended_position_size,
                    current_price,
                )
            else:
                # For forex or other, use unit amount
                suggested_amount = recommended_position_size

        # Apply adaptive size scaling (confidence + volatility) to reduce tail-risk.
        agent_cfg = self.config.get("agent", {}) if isinstance(self.config, dict) else {}
        min_conf_threshold = agent_cfg.get("min_confidence_threshold", 0.70)
        if isinstance(min_conf_threshold, (int, float)) and min_conf_threshold <= 1:
            min_conf_threshold_pct = float(min_conf_threshold) * 100.0
        else:
            min_conf_threshold_pct = float(min_conf_threshold or 70.0)

        controls = ExecutionQualityControls(
            enabled=bool(agent_cfg.get("quality_gate_enabled", True)),
            full_size_confidence=float(agent_cfg.get("position_size_full_confidence", 90.0)),
            min_size_multiplier=float(agent_cfg.get("position_size_min_multiplier", 0.50)),
            high_volatility_threshold=float(agent_cfg.get("high_volatility_threshold", 0.04)),
            high_volatility_size_scale=float(agent_cfg.get("position_size_high_volatility_scale", 0.75)),
            extreme_volatility_threshold=float(agent_cfg.get("position_size_extreme_volatility_threshold", 0.07)),
            extreme_volatility_size_scale=float(agent_cfg.get("position_size_extreme_volatility_scale", 0.50)),
            min_risk_reward_ratio=float(agent_cfg.get("min_risk_reward_ratio", 1.25)),
            high_volatility_min_confidence=float(agent_cfg.get("high_volatility_min_confidence", 80.0)),
        )

        confidence_pct = float(ai_response.get("confidence", 0) or 0)
        volatility = float(context.get("volatility", 0.0) or 0.0)
        size_multiplier = calculate_size_multiplier(
            confidence_pct=confidence_pct,
            min_conf_threshold_pct=min_conf_threshold_pct,
            volatility=volatility,
            controls=controls,
        )

        if action in ["BUY", "SELL"] and recommended_position_size:
            recommended_position_size = float(recommended_position_size) * size_multiplier
            if suggested_amount:
                suggested_amount = float(suggested_amount) * size_multiplier

        # Assemble decision object
        decision = {
            "id": decision_id,
            "asset_pair": asset_pair,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "confidence": ai_response.get("confidence", 50),
            "reasoning": ai_response.get("reasoning", "No reasoning provided"),
            "suggested_amount": suggested_amount,
            "recommended_position_size": recommended_position_size,
            "position_type": self._determine_position_type(action),
            "entry_price": current_price,
            "stop_loss_price": stop_loss_price,
            "stop_loss_fraction": sizing_stop_loss_percentage,
            "take_profit_percentage": None,  # Individual trade TP is not explicitly set by the DecisionEngine
            "risk_percentage": risk_percentage,
            "signal_only": signal_only,
            "position_size_multiplier": size_multiplier,
            "quality_controls_enabled": controls.enabled,
            "portfolio_stop_loss_percentage": self.portfolio_stop_loss_percentage,
            "portfolio_take_profit_percentage": self.portfolio_take_profit_percentage,
            "market_data": context["market_data"],
            "balance_snapshot": context["balance"],
            "price_change": context["price_change"],
            "volatility": context["volatility"],
            # Surface portfolio unrealized P&L if available from platform data
            "portfolio_unrealized_pnl": (context.get("portfolio", {}) or {}).get(
                "unrealized_pnl"
            ),
            "executed": False,
            # These would be set by the AIDecisionManager
            "ai_provider": "unknown",  # Placeholder, will be set by calling class
            "model_name": "unknown",  # Placeholder, will be set by calling class
            "backtest_mode": self.backtest_mode,
            # --- Multi-timeframe and risk context fields ---
            "multi_timeframe_trend": context.get("multi_timeframe_trend"),
            "multi_timeframe_entry_signals": context.get(
                "multi_timeframe_entry_signals"
            ),
            "multi_timeframe_sources": context.get("multi_timeframe_sources"),
            "data_source_path": context.get("data_source_path"),
            "monitor_pulse_age_seconds": context.get("monitor_pulse_age_seconds"),
            "var_snapshot": context.get("var_snapshot"),
            "correlation_alerts": context.get("correlation_alerts"),
            "correlation_summary": context.get("correlation_summary"),
        }

        # Add ensemble metadata if available
        if "ensemble_metadata" in ai_response:
            decision["ensemble_metadata"] = ai_response["ensemble_metadata"]

        # Add action_votes if available (from weighted voting)
        if "action_votes" in ai_response:
            decision["action_votes"] = ai_response["action_votes"]

        # Add meta_features if available (from stacking)
        if "meta_features" in ai_response:
            decision["meta_features"] = ai_response["meta_features"]

        logger.info(
            "Decision created: %s %s (confidence: %s%%)",
            decision["action"],
            asset_pair,
            decision["confidence"],
        )

        return decision

    @staticmethod
    def _determine_position_type(action: str) -> Optional[str]:
        """
        Determine position type from action.

        Args:
            action: Trading action (BUY, SELL, or HOLD)

        Returns:
            Position type: 'LONG' for BUY, 'SHORT' for SELL, None for HOLD
        """
        if action == "BUY":
            return "LONG"
        elif action == "SELL":
            return "SHORT"
        return None
