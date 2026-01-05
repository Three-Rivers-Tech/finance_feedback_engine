"""Position sizing calculator for trading decisions."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Minimum order sizes for different platforms (USD notional value)
MIN_ORDER_SIZE_CRYPTO = 10.0  # Coinbase minimum order size
MIN_ORDER_SIZE_FOREX = 1.0  # Oanda minimum micro lot
MIN_ORDER_SIZE_DEFAULT = 10.0  # Default minimum for unknown platforms


class PositionSizingCalculator:
    """
    Calculator for position sizing based on risk management principles.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Import Kelly Criterion calculator if available
        try:
            from .kelly_criterion import KellyCriterionCalculator

            self.kelly_calculator = KellyCriterionCalculator(config)
        except ImportError:
            logger.warning(
                "Kelly Criterion calculator not available, falling back to risk-based sizing"
            )
            self.kelly_calculator = None

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
        # Check if we have valid balance
        has_valid_balance = (
            relevant_balance
            and len(relevant_balance) > 0
            and sum(relevant_balance.values()) > 0
        )

        # Determine if we should calculate position sizing (no signal-only mode)
        should_calculate = has_valid_balance and (
            action in ["BUY", "SELL"]
            or (action == "HOLD" and has_existing_position)
        )

        # Get risk parameters from agent config
        agent_config = self.config.get("agent", {})
        risk_percentage = agent_config.get("risk_percentage", 0.01)
        default_stop_loss = agent_config.get("sizing_stop_loss_percentage", 0.02)
        use_dynamic_stop_loss = agent_config.get("use_dynamic_stop_loss", True)

        # Check if Kelly Criterion should be used
        use_kelly_criterion = agent_config.get("use_kelly_criterion", False)
        kelly_config = agent_config.get("kelly_criterion", {})

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
                atr_multiplier=agent_config.get("atr_multiplier", 2.0),
                min_percentage=agent_config.get("min_stop_loss_pct", 0.01),
                max_percentage=agent_config.get("max_stop_loss_pct", 0.05),
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

            # Calculate position size using either Kelly Criterion or risk-based method
            if use_kelly_criterion and self.kelly_calculator:
                # Use Kelly Criterion for position sizing
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

            # Calculate stop loss price
            position_type = self._determine_position_type(action)
            stop_loss_price = 0
            if position_type == "LONG" and current_price > 0:
                stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
            elif position_type == "SHORT" and current_price > 0:
                stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)

            result.update(
                {
                    "recommended_position_size": recommended_position_size,
                    "stop_loss_price": stop_loss_price,
                    "sizing_stop_loss_percentage": sizing_stop_loss_percentage,
                    "risk_percentage": risk_percentage,
                }
            )

            if action == "HOLD" and has_existing_position:
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

        # CASE 2: No valid balance - use minimum order size (no signal-only mode)
        logger.warning(
            "No valid %s balance - using minimum order size for trade execution",
            balance_source,
        )

        # HOLD without position: no sizing needed
        if action == "HOLD" and not has_existing_position:
            logger.info("HOLD without existing position - no position sizing needed")
            result["recommended_position_size"] = 0
            result["stop_loss_price"] = current_price
            result["sizing_stop_loss_percentage"] = sizing_stop_loss_percentage
            result["risk_percentage"] = risk_percentage
            return result

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

        # Calculate stop loss price
        if current_price > 0 and sizing_stop_loss_percentage > 0:
            if action == "BUY":
                stop_loss_price = current_price * (1 - sizing_stop_loss_percentage)
            else:
                stop_loss_price = current_price * (1 + sizing_stop_loss_percentage)
        else:
            stop_loss_price = current_price

        result.update(
            {
                "recommended_position_size": recommended_position_size,
                "stop_loss_price": stop_loss_price,
                "sizing_stop_loss_percentage": sizing_stop_loss_percentage,
                "risk_percentage": risk_percentage,
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
            Suggested position size in units of asset
        """
        if entry_price == 0 or stop_loss_percentage == 0:
            return 0.0

        # Amount willing to risk in dollar terms
        risk_amount = account_balance * risk_percentage

        # Price distance of stop loss
        stop_loss_distance = entry_price * stop_loss_percentage

        # Position size = Risk Amount / Stop Loss Distance
        position_size = risk_amount / stop_loss_distance

        return position_size

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
