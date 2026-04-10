"""Decision validator for trading decisions."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from .execution_quality import ExecutionQualityControls, calculate_size_multiplier
from .policy_actions import (
    POLICY_ACTION_VERSION,
    attach_sizing_translation_context,
    build_action_context,
    build_control_outcome,
    build_policy_package,
    build_policy_trace,
    build_policy_state,
    get_legacy_action_compatibility,
    get_policy_action_family,
    get_position_orientation,
    is_entry_policy_action,
    is_exit_policy_action,
    is_long_policy_action,
    is_policy_action,
    is_short_policy_action,
    # Stage 49-62: Policy trace contract builders
    build_policy_dataset_row_from_decision,
    build_policy_evaluation_batch,
    build_policy_evaluation_run,
    build_policy_evaluation_summary,
    build_policy_evaluation_scorecard,
    build_policy_evaluation_result,
    build_policy_evaluation_aggregate,
    build_policy_evaluation_comparison,
    build_policy_candidate_comparison_set,
    build_policy_candidate_benchmark_summary,
    build_policy_baseline_evaluation_set,
    build_policy_baseline_evaluation_report,
    build_policy_baseline_evaluation_session,
    build_policy_baseline_workflow_summary,
    build_policy_baseline_candidate_comparison_group,
    build_policy_baseline_candidate_comparison_summary,
    build_policy_selection_recommendation_set,
    build_policy_selection_recommendation_summary,
    build_policy_selection_promotion_decision_set,
    build_policy_selection_promotion_decision_summary,
    build_policy_selection_rollout_decision_set,
    build_policy_selection_rollout_decision_summary,
    build_policy_selection_runtime_switch_set,
    build_policy_selection_runtime_switch_summary,
    build_policy_selection_deployment_execution_set,
    build_policy_selection_deployment_execution_summary,
    build_policy_selection_orchestration_set,
    build_policy_selection_orchestration_summary,
    build_policy_selection_scheduler_request_set,
    build_policy_selection_scheduler_request_summary,
    build_policy_selection_job_spec_set,
    build_policy_selection_job_spec_summary,
    build_policy_selection_submission_envelope_set,
    build_policy_selection_submission_envelope_summary,
    build_policy_selection_adapter_payload_set,
    build_policy_selection_adapter_payload_summary,
    build_policy_selection_provider_binding_contract_set,
    build_policy_selection_provider_binding_contract_summary,
    build_policy_selection_provider_client_shape_set,
    build_policy_selection_provider_client_shape_summary,
    build_policy_selection_provider_implementation_contract_set,
    build_policy_selection_provider_implementation_contract_summary,
    build_policy_selection_execution_interface_contract_set,
    build_policy_selection_execution_interface_contract_summary,
    build_policy_selection_execution_request_set,
    build_policy_selection_execution_request_summary,
    build_policy_selection_submission_transport_envelope_set,
    build_policy_selection_submission_transport_envelope_summary,
    build_policy_selection_provider_dispatch_contract_set,
    build_policy_selection_provider_dispatch_contract_summary,
    build_policy_selection_dispatch_attempt_contract_set,
    build_policy_selection_dispatch_attempt_contract_summary,
    build_policy_selection_execution_result_set,
    build_policy_selection_execution_result_summary,
    build_policy_selection_execution_receipt_set,
    build_policy_selection_execution_receipt_summary,
    build_policy_selection_execution_tracking_set,
    build_policy_selection_execution_tracking_summary,
    build_policy_selection_execution_fill_set,
    build_policy_selection_execution_fill_summary,
    build_policy_selection_trade_outcome_set,
    build_policy_selection_trade_outcome_summary,
    build_policy_selection_learning_feedback_set,
    build_policy_selection_learning_feedback_summary,
    build_policy_selection_learning_analytics_set,
    build_policy_selection_learning_analytics_summary,
    build_policy_selection_adaptive_recommendation_set,
    build_policy_selection_adaptive_recommendation_summary,
    build_policy_selection_adaptive_activation_set,
    build_policy_selection_adaptive_activation_summary,
    build_policy_selection_adaptive_weight_mutation_set,
    build_policy_selection_adaptive_weight_mutation_summary,
    build_policy_selection_adaptive_control_persistence_set,
    build_policy_selection_adaptive_control_persistence_summary,
    build_policy_selection_adaptive_control_snapshot_set,
    build_policy_selection_adaptive_control_snapshot_summary,
    build_policy_selection_adaptive_control_runtime_apply_set,
    build_policy_selection_adaptive_control_runtime_apply_summary,
    build_policy_selection_adaptive_control_config_patch_contract_set,
    build_policy_selection_adaptive_control_config_patch_contract_summary,
    build_policy_selection_adaptive_control_runtime_config_materialization_set,
    build_policy_selection_adaptive_control_runtime_config_materialization_summary,
    build_policy_selection_adaptive_control_config_update_transport_contract_set,
    build_policy_selection_adaptive_control_config_update_transport_contract_summary,
    build_policy_selection_adaptive_control_agent_lifecycle_control_contract_set,
    build_policy_selection_adaptive_control_agent_lifecycle_control_contract_summary,
    build_policy_selection_adaptive_control_health_readiness_observability_contract_set,
    build_policy_selection_adaptive_control_health_readiness_observability_contract_summary,
    build_policy_selection_adaptive_control_dashboard_status_aggregation_contract_set,
    build_policy_selection_adaptive_control_dashboard_status_aggregation_contract_summary,
    build_policy_selection_adaptive_control_notification_delivery_contract_set,
    build_policy_selection_adaptive_control_notification_delivery_contract_summary,
    build_policy_selection_adaptive_control_alert_dispatch_contract_set,
    build_policy_selection_adaptive_control_alert_dispatch_contract_summary,
    build_policy_selection_adaptive_control_trade_execution_contract_set,
    build_policy_selection_adaptive_control_trade_execution_contract_summary,
    build_policy_selection_adaptive_control_exchange_order_placement_contract_set,
    build_policy_selection_adaptive_control_exchange_order_placement_contract_summary,
    build_policy_selection_adaptive_control_exchange_authentication_contract_set,
    build_policy_selection_adaptive_control_exchange_authentication_contract_summary,
    build_policy_selection_adaptive_control_exchange_credential_wiring_contract_set,
    build_policy_selection_adaptive_control_exchange_credential_wiring_contract_summary,
    build_policy_selection_adaptive_control_exchange_http_transport_contract_set,
    build_policy_selection_adaptive_control_exchange_http_transport_contract_summary,
    build_policy_selection_adaptive_control_exchange_response_handling_contract_set,
    build_policy_selection_adaptive_control_exchange_response_handling_contract_summary,
    build_policy_selection_adaptive_control_exchange_execution_confirmation_contract_set,
    build_policy_selection_adaptive_control_exchange_execution_confirmation_contract_summary,
)

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
        action = ai_response.get("policy_action") or ai_response.get("action", "HOLD")
        effective_legacy_action = (
            get_legacy_action_compatibility(action)
            if is_policy_action(action)
            else action
        )
        canonical_entry_action = bool(is_policy_action(action) and is_entry_policy_action(action))
        legacy_entry_action = (not is_policy_action(action)) and effective_legacy_action in ["BUY", "SELL"]
        entry_sizing_required = canonical_entry_action or legacy_entry_action

        # Extract position sizing results
        # Use calculated position size from position_sizing_result
        recommended_position_size = position_sizing_result.get("recommended_position_size")
        stop_loss_price = position_sizing_result.get("stop_loss_price")
        sizing_stop_loss_percentage = position_sizing_result.get(
            "sizing_stop_loss_percentage", 0
        )
        risk_percentage = position_sizing_result.get("risk_percentage", 0)
        signal_only = position_sizing_result.get("signal_only", False)
        policy_sizing_intent = position_sizing_result.get("policy_sizing_intent")
        provider_translation_result = position_sizing_result.get("provider_translation_result")
        translation_provider = None
        translated_size = None
        translated_effective_exposure_pct = None
        semantic_drift_detected = False
        translation_notes = None
        sizing_semantics_version = None
        sizing_anchor = None
        provider_translation_required = False
        canonical_policy_state = build_policy_state(
            position_state=context.get("position_state"),
            market_data=context.get("market_data"),
            volatility=context.get("volatility"),
            portfolio=context.get("portfolio"),
            market_regime=context.get("market_regime"),
        )

        if isinstance(policy_sizing_intent, dict):
            sizing_semantics_version = policy_sizing_intent.get("version", 1)
            sizing_anchor = policy_sizing_intent.get("sizing_anchor")
            provider_translation_required = bool(
                policy_sizing_intent.get("provider_agnostic", False)
            ) and entry_sizing_required

        if isinstance(provider_translation_result, dict):
            translation_provider = provider_translation_result.get("provider")
            translated_size = provider_translation_result.get("translated_size")
            translated_effective_exposure_pct = provider_translation_result.get(
                "effective_exposure_pct"
            )
            semantic_drift_detected = bool(
                provider_translation_result.get("semantic_drift_detected", False)
            )
            translation_notes = provider_translation_result.get("translation_notes")
        
        logger.debug(
            f"Position sizing extracted: size={recommended_position_size}, "
            f"stop_loss=${stop_loss_price}, risk={risk_percentage}"
        )

        # Calculate suggested_amount based on action and position sizing
        suggested_amount = ai_response.get("amount", 0)

        # Override suggested_amount to 0 for HOLD with no position
        if effective_legacy_action == "HOLD" and not has_existing_position:
            suggested_amount = 0
            logger.debug("Overriding suggested_amount to 0 (HOLD with no position)")

        # For non-signal-only BUY/SELL: recommended_position_size is in asset units (e.g., BTC);
        # convert to USD notional by multiplying by current_price when the quote is USD/USDT
        if (
            not signal_only
            and entry_sizing_required
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

        # For exit/close actions (CLOSE_SHORT, CLOSE_LONG, REDUCE_*): derive
        # suggested_amount from the existing position size, not from entry sizing.
        # Position sizing intentionally returns 0 for de-risking actions, so we must
        # source the amount from the current position contracts.
        _is_exit_action = is_policy_action(action) and is_exit_policy_action(action)
        if (
            _is_exit_action
            and has_existing_position
            and current_price > 0
            and (suggested_amount is None or float(suggested_amount or 0) <= 0)
        ):
            position_state = context.get("position_state")
            if isinstance(position_state, dict):
                position_contracts = float(position_state.get("contracts", 0) or 0)
            else:
                position_contracts = 0
            if position_contracts > 0:
                suggested_amount = position_contracts * current_price
                recommended_position_size = position_contracts
                logger.info(
                    "Exit sizing: $%.2f USD notional for %s (%.6f contracts @ $%.2f)",
                    suggested_amount,
                    action,
                    position_contracts,
                    current_price,
                )
            else:
                logger.warning(
                    "Exit sizing: no position contracts found for %s %s; suggested_amount remains %.2f",
                    action,
                    asset_pair,
                    float(suggested_amount or 0),
                )

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

        policy_action = None
        policy_action_version = None
        policy_action_family = None
        legacy_action_compatibility = None
        structural_action_validity = None
        current_position_state = None
        legal_actions = None
        invalid_reason = None
        risk_vetoed = False
        risk_veto_reason = None
        gatekeeper_message = None
        action_context_version = None
        canonical_action_context = None
        canonical_control_outcome = None
        canonical_policy_package = None
        canonical_policy_trace = None

        if is_policy_action(action):
            policy_action = action
            policy_action_version = POLICY_ACTION_VERSION
            policy_action_family = get_policy_action_family(action)
            legacy_action_compatibility = get_legacy_action_compatibility(action)
            action_context_version = 1


            raw_position_state = (
                context.get("position_state")
                if isinstance(context.get("position_state"), str)
                else (context.get("position_state", {}) or {}).get("state")
            )
            veto_result = (
                context.get("policy_action_veto_result")
                or ai_response.get("policy_action_veto_result")
                or {}
            )
            if isinstance(veto_result, dict):
                risk_vetoed = bool(veto_result.get("risk_vetoed", False))
                risk_veto_reason = veto_result.get("risk_veto_reason")
                gatekeeper_message = veto_result.get("gatekeeper_message")

            canonical_action_context = build_action_context(
                position_state=raw_position_state,
                policy_action=action,
                risk_vetoed=risk_vetoed,
                risk_veto_reason=risk_veto_reason,
                gatekeeper_message=gatekeeper_message,
            )
            current_position_state = canonical_action_context.get("current_position_state")
            legal_actions = canonical_action_context.get("legal_actions")
            structural_action_validity = canonical_action_context.get("structural_action_validity")
            invalid_reason = canonical_action_context.get("invalid_action_reason")
            canonical_control_outcome = build_control_outcome(
                action=action,
                structural_action_validity=structural_action_validity,
                invalid_action_reason_text=invalid_reason,
                risk_vetoed=risk_vetoed,
                risk_veto_reason=risk_veto_reason,
            )
            canonical_policy_package = attach_sizing_translation_context(
                build_policy_package(
                    policy_state=canonical_policy_state,
                    action_context=canonical_action_context,
                    policy_sizing_intent=None,
                    provider_translation_result=None,
                    control_outcome=canonical_control_outcome,
                ),
                policy_sizing_intent=policy_sizing_intent,
                provider_translation_result=provider_translation_result,
            )
            canonical_policy_trace = build_policy_trace(
                policy_package=canonical_policy_package,
                action=action,
                policy_action=policy_action,
                legacy_action_compatibility=legacy_action_compatibility,
                confidence=ai_response.get("confidence", 50),
                reasoning=ai_response.get("reasoning", "No reasoning provided"),
                asset_pair=asset_pair,
                ai_provider=ai_response.get("ai_provider"),
                timestamp=None,
                decision_id=decision_id,
                policy_family=ai_response.get("policy_family"),
                decision_mode=ai_response.get("decision_mode"),
                coverage_bucket=ai_response.get("coverage_bucket"),
                exploration_metadata=ai_response.get("exploration_metadata"),
            )
        
        confidence_pct = float(ai_response.get("confidence", 0) or 0)
        volatility = float(context.get("volatility", 0.0) or 0.0)
        size_multiplier = calculate_size_multiplier(
            confidence_pct=confidence_pct,
            min_conf_threshold_pct=min_conf_threshold_pct,
            volatility=volatility,
            controls=controls,
        )

        if entry_sizing_required and recommended_position_size:
            recommended_position_size = float(recommended_position_size) * size_multiplier
            if suggested_amount:
                suggested_amount = float(suggested_amount) * size_multiplier

        # Assemble decision object
        decision = {
            "id": decision_id,
            "asset_pair": asset_pair,
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "policy_action": policy_action,
            "policy_action_version": policy_action_version,
            "policy_action_family": policy_action_family,
            "legacy_action_compatibility": legacy_action_compatibility,
            "structural_action_validity": structural_action_validity,
            "current_position_state": current_position_state,
            "legal_actions": legal_actions,
            "invalid_action_reason": invalid_reason,
            "risk_vetoed": risk_vetoed,
            "risk_veto_reason": risk_veto_reason,
            "gatekeeper_message": gatekeeper_message,
            "action_context_version": action_context_version,
            "policy_state": canonical_policy_state,
            "action_context": canonical_action_context,
            "control_outcome": canonical_control_outcome,
            "policy_package": canonical_policy_package,
            "policy_trace": canonical_policy_trace,
            "policy_family": ai_response.get("policy_family"),
            "decision_mode": ai_response.get("decision_mode"),
            "coverage_bucket": ai_response.get("coverage_bucket"),
            "exploration_metadata": ai_response.get("exploration_metadata"),
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
            "policy_sizing_intent": policy_sizing_intent,
            "provider_translation_result": provider_translation_result,
            "translation_provider": translation_provider,
            "translated_size": translated_size,
            "translated_effective_exposure_pct": translated_effective_exposure_pct,
            "semantic_drift_detected": semantic_drift_detected,
            "translation_notes": translation_notes,
            "sizing_semantics_version": sizing_semantics_version,
            "sizing_anchor": sizing_anchor,
            "provider_translation_required": provider_translation_required,
            "effective_size_basis": "usd_notional" if is_crypto else "asset_units",
            "portfolio_stop_loss_percentage": self.portfolio_stop_loss_percentage,
            "portfolio_take_profit_percentage": self.portfolio_take_profit_percentage,
            "market_data": context.get("market_data", {}),
            "balance_snapshot": context.get("balance", {}),
            "price_change": context.get("price_change", 0.0),
            "volatility": context.get("volatility", 0.0),
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

        # Preserve top-level audit fields from upstream decision construction
        if "decision_origin" in ai_response:
            decision["decision_origin"] = ai_response.get("decision_origin")
        if ai_response.get("market_regime"):
            decision["market_regime"] = ai_response.get("market_regime")

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

        # Build Stage 49-62 contract chain for observability
        contract_chain = self._build_stage_49_62_contract_chain(decision)
        if contract_chain:
            decision["policy_trace"]["stage_49_62_contract_chain"] = contract_chain

        return decision

    @staticmethod
    def _determine_position_type(action: str) -> Optional[str]:
        """Determine coarse position orientation from shared canonical-first semantics."""
        return get_position_orientation(action)


    def _build_stage_49_62_contract_chain(self, decision: dict) -> dict:
        """Build Stage 49-62 policy trace contract chain for observability."""
        try:
            dataset_row = build_policy_dataset_row_from_decision(decision)
            if not dataset_row:
                return {}
            
            evaluation_batch = build_policy_evaluation_batch([dataset_row])
            evaluation_run = build_policy_evaluation_run(evaluation_batch.get("rows", []))
            evaluation_summary = build_policy_evaluation_summary(evaluation_run)
            evaluation_scorecard = build_policy_evaluation_scorecard(evaluation_summary)
            evaluation_result = build_policy_evaluation_result(evaluation_summary, evaluation_scorecard)
            evaluation_aggregate = build_policy_evaluation_aggregate([evaluation_result])
            evaluation_comparison = build_policy_evaluation_comparison(evaluation_aggregate, evaluation_aggregate)
            
            comparison_set = build_policy_candidate_comparison_set([evaluation_comparison])
            benchmark_summary = build_policy_candidate_benchmark_summary(comparison_set)
            
            baseline_set = build_policy_baseline_evaluation_set([benchmark_summary])
            baseline_report = build_policy_baseline_evaluation_report(baseline_set)
            evaluation_session = build_policy_baseline_evaluation_session([baseline_report])
            workflow_summary = build_policy_baseline_workflow_summary(evaluation_session)
            
            comparison_group = build_policy_baseline_candidate_comparison_group([workflow_summary], [workflow_summary])
            comparison_summary = build_policy_baseline_candidate_comparison_summary(comparison_group)
            
            recommendation_set = build_policy_selection_recommendation_set([comparison_summary])
            recommendation_summary = build_policy_selection_recommendation_summary(recommendation_set)
            
            promotion_decision_set = build_policy_selection_promotion_decision_set([recommendation_summary])
            promotion_decision_summary = build_policy_selection_promotion_decision_summary(promotion_decision_set)
            
            rollout_decision_set = build_policy_selection_rollout_decision_set([promotion_decision_summary])
            rollout_decision_summary = build_policy_selection_rollout_decision_summary(rollout_decision_set)
            
            runtime_switch_set = build_policy_selection_runtime_switch_set([rollout_decision_summary])
            runtime_switch_summary = build_policy_selection_runtime_switch_summary(runtime_switch_set)
            
            deployment_execution_set = build_policy_selection_deployment_execution_set([runtime_switch_summary])
            deployment_execution_summary = build_policy_selection_deployment_execution_summary(deployment_execution_set)
            
            orchestration_set = build_policy_selection_orchestration_set([deployment_execution_summary])
            orchestration_summary = build_policy_selection_orchestration_summary(orchestration_set)
            
            # Stage 59-62: Exchange execution confirmation contracts
            exchange_execution = {}
            
            # Stage 59: Order placement contracts
            order_placement_set = build_policy_selection_adaptive_control_exchange_order_placement_contract_set(
                [orchestration_summary]
            )
            if order_placement_set:
                exchange_execution["order_placement_contract"] = build_policy_selection_adaptive_control_exchange_order_placement_contract_summary(
                    order_placement_set
                )
            
            # Stage 60: Authentication contracts
            auth_set = build_policy_selection_adaptive_control_exchange_authentication_contract_set([orchestration_summary])
            if auth_set:
                exchange_execution["authentication_contract"] = build_policy_selection_adaptive_control_exchange_authentication_contract_summary(
                    auth_set
                )
            
            # Stage 60b: Credential wiring contracts
            credential_set = build_policy_selection_adaptive_control_exchange_credential_wiring_contract_set([orchestration_summary])
            if credential_set:
                exchange_execution["credential_wiring_contract"] = build_policy_selection_adaptive_control_exchange_credential_wiring_contract_summary(
                    credential_set
                )
            
            # Stage 61: HTTP transport contracts
            transport_set = build_policy_selection_adaptive_control_exchange_http_transport_contract_set([orchestration_summary])
            if transport_set:
                exchange_execution["http_transport_contract"] = build_policy_selection_adaptive_control_exchange_http_transport_contract_summary(
                    transport_set
                )
            
            # Stage 61b: Response handling contracts
            response_set = build_policy_selection_adaptive_control_exchange_response_handling_contract_set([orchestration_summary])
            if response_set:
                exchange_execution["response_handling_contract"] = build_policy_selection_adaptive_control_exchange_response_handling_contract_summary(
                    response_set
                )
            
            # Stage 62: Execution confirmation contracts
            exec_conf_set = build_policy_selection_adaptive_control_exchange_execution_confirmation_contract_set([orchestration_summary])
            if exec_conf_set:
                exchange_execution["execution_confirmation_contract"] = build_policy_selection_adaptive_control_exchange_execution_confirmation_contract_summary(
                    exec_conf_set
                )
            
            # Attach exchange execution to orchestration summary
            if exchange_execution:
                orchestration_summary["exchange_execution"] = exchange_execution
            
            return {
                "dataset_row": dataset_row,
                "evaluation_summary": evaluation_summary,
                "comparison_summary": comparison_summary,
                "recommendation_summary": recommendation_summary,
                "promotion_decision_summary": promotion_decision_summary,
                "rollout_decision_summary": rollout_decision_summary,
                "runtime_switch_summary": runtime_switch_summary,
                "deployment_execution_summary": deployment_execution_summary,
                "orchestration_summary": orchestration_summary,
            }
        except Exception as e:
            logger.warning(f"Failed to build contract chain: {e}")
            return {}
