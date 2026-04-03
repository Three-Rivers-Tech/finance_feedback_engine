"""Position sizing calculator for trading decisions."""

import logging
import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .policy_actions import get_legacy_action_compatibility, get_position_orientation

try:
    from .sortino_gate import SortinoGateResult
except ImportError:
    SortinoGateResult = None  # Graceful degradation if sortino_gate not available

logger = logging.getLogger(__name__)

# Minimum order sizes for different platforms (USD notional value)
MIN_ORDER_SIZE_CRYPTO = 10.0  # Coinbase minimum order size
MIN_ORDER_SIZE_FOREX = 1.0  # Oanda minimum micro lot
MIN_ORDER_SIZE_DEFAULT = 10.0  # Default minimum for unknown platforms


@dataclass(frozen=True)
class PolicySizingIntent:
    """Provider-agnostic sizing intent used as a Stage 1 migration seam."""

    semantic_action: str
    target_exposure_pct: Optional[float]
    target_delta_pct: float
    reduction_fraction: Optional[float]
    sizing_anchor: str
    provider_agnostic: bool = True
    version: int = 1


@dataclass(frozen=True)
class ProviderTranslationResult:
    """Additive Stage 2 scaffold for provider-specific translation metadata."""

    provider: str
    policy_sizing_intent: Dict[str, Any]
    translated_size: Optional[float]
    effective_exposure_pct: Optional[float]
    semantic_drift_detected: bool
    translation_notes: Optional[str]
    version: int = 1




def _normalize_action_for_sizing(action: str | None) -> tuple[str, str]:
    """Return (normalized_action, legacy_action) for legacy and policy actions."""
    normalized_action = str(action or "HOLD").upper()
    try:
        legacy_action = get_legacy_action_compatibility(normalized_action) or normalized_action
    except ValueError:
        legacy_action = normalized_action
    return normalized_action, legacy_action

class PositionSizingCalculator:
    """
    Calculator for position sizing based on risk management principles.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Debug: log position sizing config on init
        agent_cfg = config.get("agent", {})
        pos_sizing_cfg = agent_cfg.get("position_sizing", {})
        logger.info(
            f"PositionSizingCalculator init: agent_cfg keys={list(agent_cfg.keys())[:10]}"
        )
        logger.info(
            f"PositionSizingCalculator initialized with risk_percentage={pos_sizing_cfg.get('risk_percentage', 'NOT SET')}"
        )
        
        # Import Kelly Criterion calculator if available
        try:
            from .kelly_criterion import KellyCriterionCalculator

            self.kelly_calculator = KellyCriterionCalculator(config)
        except ImportError:
            logger.warning(
                "Kelly Criterion calculator not available, falling back to risk-based sizing"
            )
            self.kelly_calculator = None


    def build_policy_sizing_intent(
        self,
        action: str,
        recommended_position_size: Optional[float],
        current_price: float,
    ) -> Dict[str, Any]:
        """Build a provider-agnostic sizing intent from current sizing outputs.

        Stage 1 intentionally keeps this directional at the semantic-action layer
        while separating shared sizing intent from provider-native quantity translation.
        """
        normalized_action = str(action or "HOLD").upper()
        target_exposure_pct: Optional[float] = None
        target_delta_pct = 0.0
        reduction_fraction: Optional[float] = None

        if (
            normalized_action in {"BUY", "SELL"}
            and recommended_position_size
            and current_price > 0
        ):
            target_exposure_pct = float(recommended_position_size) * float(current_price)
            target_delta_pct = target_exposure_pct
        elif normalized_action == "HOLD":
            target_delta_pct = 0.0

        sizing_anchor = "quarter_kelly_conservative"
        if self.kelly_calculator and hasattr(self.kelly_calculator, "get_sizing_anchor_metadata"):
            sizing_anchor = self.kelly_calculator.get_sizing_anchor_metadata().get(
                "sizing_anchor", sizing_anchor
            )

        return asdict(
            PolicySizingIntent(
                semantic_action=normalized_action,
                target_exposure_pct=target_exposure_pct,
                target_delta_pct=target_delta_pct,
                reduction_fraction=reduction_fraction,
                sizing_anchor=sizing_anchor,
            )
        )

    def build_provider_translation_result(
        self,
        provider: str,
        policy_sizing_intent: Optional[Dict[str, Any]],
        translated_size: Optional[float],
        effective_exposure_pct: Optional[float] = None,
        semantic_drift_detected: bool = False,
        translation_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build additive provider-translation scaffolding for Stage 2.

        This helper intentionally does not perform provider-specific translation yet.
        It only creates a common result shape so later Coinbase/OANDA work can hang
        off a shared contract without changing shared sizing intent semantics.
        """
        normalized_provider = str(provider or "unknown").lower()
        safe_intent = policy_sizing_intent if isinstance(policy_sizing_intent, dict) else {}

        return asdict(
            ProviderTranslationResult(
                provider=normalized_provider,
                policy_sizing_intent=safe_intent,
                translated_size=translated_size,
                effective_exposure_pct=effective_exposure_pct,
                semantic_drift_detected=semantic_drift_detected,
                translation_notes=translation_notes,
            )
        )

    def calculate_position_sizing_params(
        self,
        context: Dict[str, Any],
        current_price: float,
        action: str,
        has_existing_position: bool,
        relevant_balance: Dict[str, float],
        balance_source: str,
    ) -> Dict[str, Any]:
        """
        Calculate all position sizing parameters.

        Args:
            context: Decision context with market data and config
            current_price: Current asset price
            action: Trading action (BUY, SELL, HOLD)
            has_existing_position: Whether an existing position exists
            relevant_balance: Platform-specific balance
            balance_source: Name of balance source (for logging)

        Returns:
            Dict with keys:
            - recommended_position_size: Position size in units
            - stop_loss_price: Stop loss price level
            - sizing_stop_loss_percentage: Stop loss percentage used
            - risk_percentage: Risk percentage used
        """
        normalized_action, legacy_action = _normalize_action_for_sizing(action)

        # Check if we have valid balance
        has_valid_balance = (
            relevant_balance
            and len(relevant_balance) > 0
            and sum(relevant_balance.values()) > 0
        )
        
        logger.debug(
            "POSITION_SIZING INPUT: relevant_balance=%s, has_valid=%s, balance_source=%s, context_balance_snapshot=%s",
            relevant_balance,
            has_valid_balance,
            balance_source,
            context.get("balance_snapshot") if isinstance(context, dict) else None,
        )

        # Debug logging for position sizing
        logger.debug(
            f"Position sizing inputs: relevant_balance={relevant_balance}, "
            f"has_valid={has_valid_balance}, action={normalized_action}, legacy_action={legacy_action}, "
            f"has_existing_position={has_existing_position}, source={balance_source}"
        )

        # Fallback: derive crypto balance from richer context when balance snapshot is missing/empty
        # (e.g., transient balance fetch issue while portfolio breakdown is still available).
        if (not has_valid_balance) and isinstance(context, dict):
            logger.debug("ENTERING FALLBACK: has_valid_balance=False, context_type=%s", type(context).__name__)
            asset_pair = str(context.get("asset_pair", ""))
            market_type = str(context.get("market_data", {}).get("type", "")).lower()
            is_crypto_ctx = ("BTC" in asset_pair or "ETH" in asset_pair or market_type == "crypto")
            logger.debug("FALLBACK CRYPTO CHECK: asset_pair=%s, market_type=%s, is_crypto=%s", asset_pair, market_type, is_crypto_ctx)
            if is_crypto_ctx:
                fallback_val = None

                # 1) Preferred: current balance snapshot keys
                bs = context.get("balance_snapshot") or {}
                if isinstance(bs, dict):
                    for k in ("coinbase_FUTURES_USD", "FUTURES_USD", "coinbase_SPOT_USD", "SPOT_USD"):
                        v = bs.get(k)
                        try:
                            v_num = float(v)
                        except (TypeError, ValueError):
                            v_num = 0.0
                        if v_num > 0:
                            fallback_val = v_num
                            break

                # 2) Portfolio breakdown futures summary (buying power or total balance)
                if fallback_val is None:
                    pb = context.get("portfolio") or {}
                    if isinstance(pb, dict):
                        cb = (pb.get("platform_breakdowns") or {}).get("coinbase") or {}
                        fs = cb.get("futures_summary") or {}
                        for k in ("buying_power", "total_balance_usd"):
                            v = fs.get(k)
                            try:
                                v_num = float(v)
                            except (TypeError, ValueError):
                                v_num = 0.0
                            if v_num > 0:
                                fallback_val = v_num
                                break

                if fallback_val is not None:
                    relevant_balance = {"coinbase_FUTURES_USD": fallback_val}
                    balance_source = "CoinbaseFallback"
                    has_valid_balance = True
                    logger.info(
                        "Recovered Coinbase balance from context fallback: $%.2f",
                        fallback_val,
                    )

        # TODO(cmp6510): reconcile the balance-validity flow here. In live logs we can
        # reach this point with has_valid_balance=True / Coinbase context present, then later
        # still emit "No valid Coinbase balance - using minimum order size". The fallback,
        # should_calculate gate, and downstream minimum-order branch should share one canonical
        # notion of usable balance so logs and execution behavior stay consistent.
        # Determine if we should calculate position sizing (no signal-only mode)
        _is_derisking = has_existing_position and str(normalized_action).startswith(("CLOSE_", "REDUCE_"))
        should_calculate = has_valid_balance and not _is_derisking and (
            legacy_action in ["BUY", "SELL"]
            or (legacy_action == "HOLD" and has_existing_position)
            or legacy_action not in ["BUY", "SELL", "HOLD"]
        )
        
        if not should_calculate:
            logger.info(
                f"Position sizing skipped: has_valid_balance={has_valid_balance}, "
                f"action={action}, has_existing={has_existing_position}"
            )

        # Get risk parameters from agent config
        agent_config = self.config.get("agent", {})
        
        # Get position sizing config (THR-209)
        position_sizing_config = agent_config.get("position_sizing", {})

        # Helper function to safely get value from dict or object
        def safe_get(config, key, default):
            """Get value from dict or Pydantic object."""
            if isinstance(config, dict):
                return config.get(key, default)
            else:
                return getattr(config, key, default)

        # Read risk percentage from position_sizing config, fallback to old location, then default
        risk_percentage = position_sizing_config.get("risk_percentage", 
                                                     safe_get(agent_config, "risk_percentage", 0.01))
        
        logger.debug(
            f"Position sizing config loaded: risk_pct={risk_percentage}, "
            f"config_dict={position_sizing_config}"
        )
        default_stop_loss = safe_get(agent_config, "sizing_stop_loss_percentage", 0.02)
        use_dynamic_stop_loss = safe_get(agent_config, "use_dynamic_stop_loss", True)

        # Check if Kelly Criterion should be used
        use_kelly_criterion = safe_get(agent_config, "use_kelly_criterion", False)
        kelly_config = safe_get(agent_config, "kelly_criterion", {})

        # Compatibility: Convert legacy percentage values (>1) to decimals
        if risk_percentage > 1:
            logger.warning(
                f"Detected legacy risk_percentage {risk_percentage}%. "
                f"Converting to decimal: {risk_percentage/100:.3f}"
            )
            risk_percentage /= 100
        if default_stop_loss > 1:
            logger.warning(
                f"Detected legacy sizing_stop_loss_percentage {default_stop_loss}%. "
                f"Converting to decimal: {default_stop_loss/100:.3f}"
            )
            default_stop_loss /= 100

        # Calculate stop-loss percentage (dynamic or fixed)
        if use_dynamic_stop_loss:
            sizing_stop_loss_percentage = self.calculate_dynamic_stop_loss(
                current_price=current_price,
                context=context,
                default_percentage=default_stop_loss,
                atr_multiplier=safe_get(agent_config, "atr_multiplier", 2.0),
                min_percentage=safe_get(agent_config, "min_stop_loss_pct", 0.01),
                max_percentage=safe_get(agent_config, "max_stop_loss_pct", 0.05),
            )
        else:
            sizing_stop_loss_percentage = default_stop_loss
            logger.info(
                "Using fixed stop-loss: %.2f%% (dynamic stop-loss disabled)",
                default_stop_loss * 100,
            )

        # Initialize return values
        result = {
            "recommended_position_size": None,
            "stop_loss_price": None,
            "sizing_stop_loss_percentage": None,
            "risk_percentage": None,
            "position_sizing_method": "risk_based",  # Default method
        }

        # CASE 1: Normal mode with valid balance
        if should_calculate:
            total_balance = sum(relevant_balance.values())

            # --- Sortino-gated adaptive Kelly (Track SK Phase 2) ---
            # Check for sortino gate result in context. When present and
            # non-fixed, it overrides both the legacy use_kelly_criterion
            # flag and static risk-based sizing.
            sortino_gate_result = context.get("sortino_gate_result") if isinstance(context, dict) else None
            _use_sortino_kelly = (
                sortino_gate_result is not None
                and SortinoGateResult is not None
                and isinstance(sortino_gate_result, SortinoGateResult)
                and sortino_gate_result.sizing_mode != "fixed_risk"
                and sortino_gate_result.kelly_multiplier > 0
                and self.kelly_calculator is not None
            )

            if _use_sortino_kelly:
                # Dynamic Kelly: set multiplier from sortino gate, then size.
                # NOTE: single-thread-only — the temporary mutation of
                # kelly_fraction_multiplier is safe in the current synchronous
                # trading loop but would race under concurrent calls. If this
                # ever moves to async/threaded, pass multiplier as an explicit
                # arg to calculate_position_size instead.
                original_multiplier = getattr(
                    self.kelly_calculator, "kelly_fraction_multiplier", 0.25
                )
                _sortino_kelly_ok = False
                try:
                    self.kelly_calculator.kelly_fraction_multiplier = (
                        sortino_gate_result.kelly_multiplier
                    )
                    kelly_params = self._get_kelly_parameters(context, kelly_config)
                    recommended_position_size, kelly_details = (
                        self.kelly_calculator.calculate_position_size(
                            account_balance=total_balance,
                            win_rate=kelly_params["win_rate"],
                            avg_win=kelly_params["avg_win"],
                            avg_loss=kelly_params["avg_loss"],
                            current_price=current_price,
                            payoff_ratio=kelly_params["payoff_ratio"],
                        )
                    )

                    # Sanitize Kelly output: reject NaN, inf, negative
                    if (
                        recommended_position_size is None
                        or not math.isfinite(recommended_position_size)
                        or recommended_position_size < 0
                    ):
                        logger.warning(
                            "Sortino-Kelly returned invalid position size (%s), "
                            "falling back to risk-based sizing",
                            recommended_position_size,
                        )
                    else:
                        _sortino_kelly_ok = True
                        result["position_sizing_method"] = "sortino_kelly"
                        result["kelly_details"] = kelly_details
                        result["sortino_gate"] = {
                            "sizing_mode": sortino_gate_result.sizing_mode,
                            "kelly_multiplier": sortino_gate_result.kelly_multiplier,
                            "weighted_sortino": sortino_gate_result.weighted_sortino,
                            "trade_count": sortino_gate_result.trade_count,
                            "windows_used": sortino_gate_result.windows_used,
                            "short_window_veto": sortino_gate_result.short_window_veto,
                            "reason": sortino_gate_result.reason,
                        }
                        logger.info(
                            "Sortino-Kelly sizing: %s (multiplier=%.2f, sortino=%.3f, trades=%d)",
                            sortino_gate_result.sizing_mode,
                            sortino_gate_result.kelly_multiplier,
                            sortino_gate_result.weighted_sortino,
                            sortino_gate_result.trade_count,
                        )
                except Exception:
                    logger.warning(
                        "Sortino-Kelly sizing failed, falling back to risk-based",
                        exc_info=True,
                    )
                finally:
                    # Always restore original multiplier to avoid global mutation
                    self.kelly_calculator.kelly_fraction_multiplier = original_multiplier

                # If sortino-kelly failed or returned bad output, fall back to risk-based
                if not _sortino_kelly_ok:
                    recommended_position_size = self.calculate_position_size(
                        account_balance=total_balance,
                        risk_percentage=risk_percentage,
                        entry_price=current_price,
                        stop_loss_percentage=sizing_stop_loss_percentage,
                    )

            elif use_kelly_criterion and self.kelly_calculator and sortino_gate_result is None:
                # Legacy Kelly path: only when no sortino gate is present
                # If sortino gate IS present but says fixed_risk, we respect that
                # and fall through to risk-based sizing below.
                kelly_params = self._get_kelly_parameters(context, kelly_config)
                recommended_position_size, kelly_details = (
                    self.kelly_calculator.calculate_position_size(
                        account_balance=total_balance,
                        win_rate=kelly_params["win_rate"],
                        avg_win=kelly_params["avg_win"],
                        avg_loss=kelly_params["avg_loss"],
                        current_price=current_price,
                        payoff_ratio=kelly_params["payoff_ratio"],
                    )
                )
                result["position_sizing_method"] = "kelly_criterion"
                result["kelly_details"] = kelly_details
            else:
                # Use traditional risk-based position sizing
                recommended_position_size = self.calculate_position_size(
                    account_balance=total_balance,
                    risk_percentage=risk_percentage,
                    entry_price=current_price,
                    stop_loss_percentage=sizing_stop_loss_percentage,
                )
            
            # Apply position size caps (THR-209)
            if recommended_position_size and current_price > 0:
                # Determine environment
                from ..utils.environment import get_environment_name
                env = get_environment_name()
                
                # Get max position cap based on environment
                if env == "production":
                    max_position_usd = position_sizing_config.get("max_position_usd_prod", 500.0)
                else:
                    max_position_usd = position_sizing_config.get("max_position_usd_dev", 50.0)
                
                # Calculate current position value in USD
                position_value_usd = recommended_position_size * current_price
                
                # Cap if exceeded
                if position_value_usd > max_position_usd:
                    original_size = recommended_position_size
                    recommended_position_size = max_position_usd / current_price
                    logger.warning(
                        "Position size capped: %.4f units ($%.2f) → %.4f units ($%.2f) [%s env, max $%.2f]",
                        original_size,
                        position_value_usd,
                        recommended_position_size,
                        max_position_usd,
                        env,
                        max_position_usd
                    )

            # Calculate stop loss price with validation (SHORT position support)
            # Validate stop-loss percentage bounds
            MIN_STOP_LOSS_PCT = 0.005  # 0.5% minimum
            MAX_STOP_LOSS_PCT = 0.50  # 50% maximum (sanity check)

            if sizing_stop_loss_percentage < MIN_STOP_LOSS_PCT:
                logger.warning(
                    f"Stop-loss percentage {sizing_stop_loss_percentage:.3%} below minimum {MIN_STOP_LOSS_PCT:.3%}. "
                    f"Adjusting to minimum."
                )
                sizing_stop_loss_percentage = MIN_STOP_LOSS_PCT

            if sizing_stop_loss_percentage > MAX_STOP_LOSS_PCT:
                logger.warning(
                    f"Stop-loss percentage {sizing_stop_loss_percentage:.3%} above maximum {MAX_STOP_LOSS_PCT:.3%}. "
                    f"Capping to maximum."
                )
                sizing_stop_loss_percentage = MAX_STOP_LOSS_PCT

            # Validate current price
            if current_price <= 0:
                logger.error(
                    f"Invalid current_price: {current_price}. Cannot calculate stop-loss. "
                    f"Defaulting to 0."
                )
                stop_loss_price = 0
            else:
                position_type = self._determine_position_type(action)
                if position_type is None and legacy_action == "HOLD" and has_existing_position:
                    raw_position_state = context.get("position_state")
                    if isinstance(raw_position_state, dict):
                        context_position_state = str(raw_position_state.get("state") or raw_position_state.get("side") or "").upper()
                    else:
                        context_position_state = str(raw_position_state or "").upper()
                    if context_position_state == "LONG":
                        position_type = "LONG"
                    elif context_position_state == "SHORT":
                        position_type = "SHORT"

                if position_type == "LONG":
                    stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
                    # Validate: LONG stop-loss must be below entry
                    if stop_loss_price >= current_price:
                        logger.error(
                            f"LONG stop-loss {stop_loss_price:.2f} >= entry {current_price:.2f}. "
                            f"This should never happen. Setting to entry * 0.98"
                        )
                        stop_loss_price = current_price * 0.98
                elif position_type == "SHORT":
                    stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)
                    # Validate: SHORT stop-loss must be above entry
                    if stop_loss_price <= current_price:
                        logger.error(
                            f"SHORT stop-loss {stop_loss_price:.2f} <= entry {current_price:.2f}. "
                            f"This should never happen. Setting to entry * 1.02"
                        )
                        stop_loss_price = current_price * 1.02
                else:
                    logger.warning(
                        f"Unknown position type: {position_type}. Cannot calculate stop-loss."
                    )
                    stop_loss_price = 0

                # Final validation: Ensure minimum distance between entry and stop-loss
                if stop_loss_price > 0:
                    min_distance = current_price * MIN_STOP_LOSS_PCT
                    actual_distance = abs(stop_loss_price - current_price)

                    if actual_distance < min_distance:
                        logger.warning(
                            f"Stop-loss distance {actual_distance:.2f} too close to entry {current_price:.2f}. "
                            f"Minimum distance: {min_distance:.2f}. Adjusting."
                        )
                        if position_type == "LONG":
                            stop_loss_price = current_price * (1 - MIN_STOP_LOSS_PCT)
                        elif position_type == "SHORT":
                            stop_loss_price = current_price * (1 + MIN_STOP_LOSS_PCT)

            result.update(
                {
                    "recommended_position_size": recommended_position_size,
                    "stop_loss_price": stop_loss_price,
                    "sizing_stop_loss_percentage": sizing_stop_loss_percentage,
                    "risk_percentage": risk_percentage,
                    "policy_sizing_intent": self.build_policy_sizing_intent(
                        action=normalized_action,
                        recommended_position_size=recommended_position_size,
                        current_price=current_price,
                    ),
                }
            )

            if legacy_action == "HOLD" and has_existing_position:
                logger.info(
                    "HOLD with existing position: sizing (%.4f units) from %s",
                    recommended_position_size,
                    balance_source,
                )
            else:
                logger.info(
                    "Position sizing: %.4f units (balance: $%.2f from %s, risk: %.2f%%, sl: %.2f%%)",
                    recommended_position_size,
                    total_balance,
                    balance_source,
                    risk_percentage * 100,
                    sizing_stop_loss_percentage * 100,
                )

            return result

        # HOLD without position: no sizing needed
        if legacy_action == "HOLD" and not has_existing_position:
            logger.info("HOLD without existing position - no position sizing needed")
            result["recommended_position_size"] = 0
            result["stop_loss_price"] = current_price
            result["sizing_stop_loss_percentage"] = sizing_stop_loss_percentage
            result["risk_percentage"] = risk_percentage
            result["policy_sizing_intent"] = self.build_policy_sizing_intent(
                action=normalized_action,
                recommended_position_size=0,
                current_price=current_price,
            )
            return result

        # CLOSE/REDUCE actions are de-risking actions, not entry-sized actions.
        # They should never fall through to minimum-order fallback sizing.
        if has_existing_position and str(normalized_action).startswith(("CLOSE_", "REDUCE_")):
            logger.info(
                "Position sizing skipped for de-risking action: action=%s, has_existing=%s",
                normalized_action,
                has_existing_position,
            )
            result["recommended_position_size"] = 0
            result["stop_loss_price"] = current_price
            result["sizing_stop_loss_percentage"] = sizing_stop_loss_percentage
            result["risk_percentage"] = risk_percentage
            result["policy_sizing_intent"] = self.build_policy_sizing_intent(
                action=normalized_action,
                recommended_position_size=0,
                current_price=current_price,
            )
            return result

        # CASE 2: No valid balance - use minimum order size (no signal-only mode)
        if has_valid_balance:
            logger.warning(
                "Balance validity reconciliation: has_valid_balance=True but reached minimum-order fallback. "
                "action=%s, legacy_action=%s, has_existing_position=%s, balance_source=%s. "
                "This should not happen; filing through with risk-based sizing.",
                action, legacy_action, has_existing_position, balance_source,
            )
            total_balance = sum(relevant_balance.values())
            recommended_position_size = self.calculate_position_size(
                account_balance=total_balance,
                risk_percentage=risk_percentage,
                entry_price=current_price,
                stop_loss_percentage=sizing_stop_loss_percentage,
            )
            result.update({
                "recommended_position_size": recommended_position_size,
                "stop_loss_price": current_price,
                "sizing_stop_loss_percentage": sizing_stop_loss_percentage,
                "risk_percentage": risk_percentage,
                "position_sizing_method": "risk_based_fallback",
            })
            return result

        if str(balance_source).lower() in {"unknown", "combined"}:
            logger.info(
                "No valid %s balance - using minimum order size for trade execution",
                balance_source,
            )
        else:
            logger.warning(
                "No valid %s balance - using minimum order size for trade execution",
                balance_source,
            )

        # Determine minimum order size based on asset type
        is_crypto = (
            context.get("market_data", {}).get("type") == "crypto"
            or "BTC" in context["asset_pair"]
            or "ETH" in context["asset_pair"]
        )
        is_forex = (
            "_" in context["asset_pair"]
            or context.get("market_data", {}).get("type") == "forex"
        )

        if is_crypto:
            min_order_size = MIN_ORDER_SIZE_CRYPTO
        elif is_forex:
            min_order_size = MIN_ORDER_SIZE_FOREX
        else:
            min_order_size = MIN_ORDER_SIZE_DEFAULT

        # Calculate minimum viable position size
        if current_price > 0:
            min_position_size = min_order_size / current_price
            recommended_position_size = min_position_size

            logger.info(
                "Using minimum order size: $%.2f USD notional = %.6f units @ $%.2f",
                min_order_size,
                recommended_position_size,
                current_price,
            )
        else:
            # Price unavailable - return zero sizing (will be rejected by gatekeeper)
            recommended_position_size = 0
            logger.warning("Price unavailable; cannot compute minimum position size")

        # Calculate stop loss price using canonical-first orientation semantics.
        if current_price > 0 and sizing_stop_loss_percentage > 0:
            orientation = self._determine_position_type(action)
            if orientation == "LONG":
                stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
            elif orientation == "SHORT":
                stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)
            else:
                stop_loss_price = current_price
        else:
            stop_loss_price = current_price

        result.update(
            {
                "recommended_position_size": recommended_position_size,
                "stop_loss_price": stop_loss_price,
                "sizing_stop_loss_percentage": sizing_stop_loss_percentage,
                "risk_percentage": risk_percentage,
                "policy_sizing_intent": self.build_policy_sizing_intent(
                    action=normalized_action,
                    recommended_position_size=recommended_position_size,
                    current_price=current_price,
                ),
            }
        )

        return result

    def _get_kelly_parameters(
        self, context: Dict[str, Any], kelly_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract Kelly Criterion parameters from context and config.

        Args:
            context: Decision context containing market data and performance metrics
            kelly_config: Kelly-specific configuration

        Returns:
            Dictionary with Kelly parameters (win_rate, avg_win, avg_loss, payoff_ratio)
        """
        # Try to get historical performance metrics from context
        performance_metrics = context.get("performance_metrics", {})

        win_rate = performance_metrics.get(
            "win_rate", kelly_config.get("default_win_rate", 0.55)
        )
        avg_win = performance_metrics.get(
            "avg_win", kelly_config.get("default_avg_win", 100.0)
        )
        avg_loss = performance_metrics.get(
            "avg_loss", kelly_config.get("default_avg_loss", 75.0)
        )

        # Calculate payoff ratio if not provided
        payoff_ratio = performance_metrics.get(
            "payoff_ratio", kelly_config.get("default_payoff_ratio")
        )
        if payoff_ratio is None:
            payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

        # Apply bounds checking
        win_rate = max(0.0, min(1.0, win_rate))
        avg_win = max(0.0, avg_win)
        avg_loss = max(0.0, avg_loss)
        payoff_ratio = max(0.0, payoff_ratio)

        return {
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "payoff_ratio": payoff_ratio,
        }

    def _get_default_kelly_parameters(self) -> Dict[str, Any]:
        """
        Get default Kelly parameters when historical data is unavailable.

        Returns:
            Dictionary with default Kelly parameters
        """
        return {
            "win_rate": 0.55,  # 55% win rate
            "avg_win": 100.0,  # $100 average win
            "avg_loss": 75.0,  # $75 average loss
            "payoff_ratio": 1.33,  # 1.33:1 payoff ratio
        }

    def calculate_dynamic_stop_loss(
        self,
        current_price: float,
        context: Dict[str, Any],
        default_percentage: float = 0.02,
        atr_multiplier: float = 2.0,
        min_percentage: float = 0.01,
        max_percentage: float = 0.05,
    ) -> float:
        """
        Calculate dynamic stop-loss percentage based on market volatility (ATR).

        Uses ATR (Average True Range) from multi-timeframe pulse data to set
        stop-loss distance that adapts to current market volatility. Falls back
        to default percentage if ATR is unavailable.

        Args:
            current_price: Current asset price
            context: Decision context containing market_data and monitoring_context
            default_percentage: Fallback stop-loss percentage if ATR unavailable (default: 0.02 = 2%)
            atr_multiplier: Multiple of ATR to use for stop-loss (default: 2.0)
            min_percentage: Minimum stop-loss percentage (default: 0.01 = 1%)
            max_percentage: Maximum stop-loss percentage (default: 0.05 = 5%)

        Returns:
            Stop-loss percentage as decimal (e.g., 0.02 for 2%)
        """
        if current_price <= 0:
            return default_percentage

        atr_value = None

        # Try to get ATR from monitoring context (multi-timeframe pulse)
        monitoring_context = context.get("monitoring_context")
        if monitoring_context:
            pulse_data = monitoring_context.get("multi_timeframe_pulse")
            if pulse_data and isinstance(pulse_data, dict):
                # Check for ATR in daily timeframe (most reliable for position sizing)
                daily_data = pulse_data.get("1d") or pulse_data.get("daily")
                if daily_data and "atr" in daily_data:
                    atr_value = daily_data.get("atr")
                # Fallback to 4h timeframe if daily not available
                elif pulse_data.get("4h") and "atr" in pulse_data.get("4h", {}):
                    atr_value = pulse_data["4h"].get("atr")

        # Try to get ATR from market_data if not found in monitoring context
        if atr_value is None:
            market_data = context.get("market_data", {})
            if "atr" in market_data:
                atr_value = market_data.get("atr")
            # Check for pulse data directly in market_data
            elif "pulse" in market_data and isinstance(market_data["pulse"], dict):
                pulse = market_data["pulse"]
                daily_data = pulse.get("1d") or pulse.get("daily")
                if daily_data and "atr" in daily_data:
                    atr_value = daily_data.get("atr")

        # Calculate stop-loss based on ATR if available
        if atr_value is not None and atr_value > 0:
            # ATR-based stop-loss: use multiple of ATR as percentage of price
            atr_based_percentage = (atr_value * atr_multiplier) / current_price

            # Apply bounds
            stop_loss_percentage = max(
                min_percentage, min(atr_based_percentage, max_percentage)
            )

            logger.info(
                "Dynamic stop-loss: ATR=%.4f, ATR-based=%.2f%%, bounded=%.2f%% (min=%.2f%%, max=%.2f%%)",
                atr_value,
                atr_based_percentage * 100,
                stop_loss_percentage * 100,
                min_percentage * 100,
                max_percentage * 100,
            )
            return stop_loss_percentage
        else:
            # No ATR available, use default percentage
            logger.info(
                "ATR not available, using default stop-loss: %.2f%%",
                default_percentage * 100,
            )
            return default_percentage

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percentage: float = 0.01,
        entry_price: float = 0,
        stop_loss_percentage: float = 0.02,
    ) -> float:
        """
        Calculate appropriate position size based on risk management.

        Args:
            account_balance: Total account balance
            risk_percentage: Percentage of account to risk as decimal fraction (default 0.01 = 1%)
            entry_price: Entry price for the position
            stop_loss_percentage: Stop loss distance as decimal fraction (default 0.02 = 2%)

        Returns:
            Suggested position size in units of asset (always >= 0)
        """
        # Gemini Issue #1: Validate entry_price > 0 (prevent ZeroDivisionError)
        if entry_price <= 0:
            logger.warning(
                f"Invalid entry_price ({entry_price}) - must be > 0. Returning 0 position size."
            )
            return 0.0
        
        # Gemini Issue #3: Enforce minimum stop-loss distance (0.5%)
        MIN_STOP_LOSS_PCT = 0.005  # 0.5% minimum
        if stop_loss_percentage < MIN_STOP_LOSS_PCT:
            logger.warning(
                f"Stop loss too tight ({stop_loss_percentage:.3%}) - enforcing minimum {MIN_STOP_LOSS_PCT:.1%}"
            )
            stop_loss_percentage = MIN_STOP_LOSS_PCT
        
        # Validate inputs
        if account_balance <= 0:
            logger.warning(f"Invalid account_balance ({account_balance}) - returning 0 position size")
            return 0.0
        
        if risk_percentage <= 0 or risk_percentage > 0.10:  # Max 10% risk
            logger.warning(
                f"Invalid risk_percentage ({risk_percentage:.1%}) - must be 0-10%. Using 1% default."
            )
            risk_percentage = 0.01

        # Amount willing to risk in dollar terms
        risk_amount = account_balance * risk_percentage

        # Price distance of stop loss
        stop_loss_distance = entry_price * stop_loss_percentage

        # Position size = Risk Amount / Stop Loss Distance
        position_size = risk_amount / stop_loss_distance
        
        # Gemini Issue #2: Ensure position_size is always positive
        position_size = abs(position_size)
        
        # Final sanity check
        if position_size < 0 or position_size != position_size:  # Check for NaN
            logger.error(
                f"Position size calculation error: size={position_size}, "
                f"balance={account_balance}, risk={risk_percentage}, "
                f"entry={entry_price}, sl%={stop_loss_percentage}"
            )
            return 0.0

        return position_size

    @staticmethod
    def _determine_position_type(action: str) -> Optional[str]:
        """Determine position type from shared canonical-first action semantics."""
        return get_position_orientation(action)
