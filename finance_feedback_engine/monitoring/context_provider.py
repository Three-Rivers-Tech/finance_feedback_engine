"""Monitoring context provider for AI decision pipeline integration."""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from finance_feedback_engine.utils.shape_normalization import extract_portfolio_positions
from typing import Any, Dict, List, Optional

from finance_feedback_engine.decision_engine.policy_actions import (
    get_policy_action_family,
    get_legacy_action_compatibility,
    is_policy_action,
    normalize_policy_action,
)

logger = logging.getLogger(__name__)


def _coerce_monitoring_float(value: Any, default: float = 0.0) -> float:
    """Best-effort numeric coercion for monitoring payloads/tests."""
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_asset_key(value: Any) -> str:
    """Normalize asset identifiers (BTC-USD/BTC_USD/BTCUSD) into BTCUSD form."""
    return str(value or "").upper().replace("-", "").replace("_", "").strip()


from finance_feedback_engine.utils.product_id import product_id_to_asset_pair as _pid_to_pair


def _position_asset_keys(pos: Dict[str, Any]) -> set[str]:
    """Return candidate canonical asset keys for a position payload."""
    keys: set[str] = set()
    for field in ("asset_pair", "product_id", "instrument", "symbol", "asset"):
        raw = str(pos.get(field) or "").strip().upper()
        if not raw:
            continue
        normalized = _normalize_asset_key(raw)
        if normalized:
            keys.add(normalized)
        cfm_resolved = _pid_to_pair(raw)
        if cfm_resolved:
            keys.add(cfm_resolved)
        if "_" in raw and "-" not in raw:
            parts = raw.split("_")
            if len(parts) == 2:
                keys.add(_normalize_asset_key("".join(parts)))
    return keys


def _estimate_position_notional_usd(pos: Dict[str, Any]) -> float:
    """Best-effort USD notional estimate for monitoring/risk math."""
    contracts = abs(_coerce_monitoring_float(pos.get("contracts", 0) or pos.get("number_of_contracts", 0) or pos.get("units", 0) or pos.get("amount", 0) or pos.get("size", 0), 0.0))
    if contracts <= 0:
        return 0.0
    explicit_value = _coerce_monitoring_float(pos.get("notional_value") or pos.get("value_usd") or pos.get("usd_value"), 0.0)
    if explicit_value > 0:
        return abs(explicit_value)
    current_price = _coerce_monitoring_float(pos.get("current_price") or pos.get("mark_price") or pos.get("price"), 0.0)
    if current_price <= 0:
        return 0.0
    contract_size = _coerce_monitoring_float(pos.get("contract_size") or pos.get("contract_multiplier"), 1.0)
    if contract_size <= 0:
        contract_size = 1.0
    return contracts * current_price * contract_size


def enforce_slot_constraints(decision: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Prevent slot-consuming entry actions when monitoring context says no trade slots remain."""
    if not decision or not context:
        return decision

    normalized = dict(decision)
    raw_action = normalized.get("policy_action") or normalized.get("action")
    action = str(raw_action or "").upper()
    slots_available = context.get("slots_available")

    try:
        slots_value = int(slots_available)
    except (TypeError, ValueError):
        return normalized

    blocks_slot = False
    if is_policy_action(action):
        family = get_policy_action_family(normalize_policy_action(action))
        blocks_slot = family in {"open_long", "open_short"}
    else:
        blocks_slot = action == "BUY"

    if blocks_slot and slots_value <= 0:
        normalized["action"] = "HOLD"
        normalized["policy_action"] = "HOLD"
        normalized.setdefault(
            "override_reason",
            "Entry blocked by slot enforcement: no monitoring/trade slots available.",
        )
        normalized.setdefault("quality_flag", "slot_constrained")

    return normalized


class MonitoringContextProvider:
    """
    Provides real-time monitoring context for AI decision making.

    Aggregates:
    - Active open positions (from trade monitor)
    - Recent trade performance (from metrics collector)
    - Real-time P&L exposure
    - Portfolio risk metrics
    - Position concentration analysis

    Integrates with DecisionEngine to give AI models full awareness
    of actual trading state when making new decisions.
    """

    def __init__(
        self,
        platform,
        trade_monitor=None,
        metrics_collector=None,
        portfolio_initial_balance: float = 0.0,
    ):
        """
        Initialize monitoring context provider.

        Args:
            platform: Trading platform instance
            trade_monitor: Optional TradeMonitor instance for active trades
            metrics_collector: Optional TradeMetricsCollector for history
        """
        self.platform = platform
        self.trade_monitor = trade_monitor
        self.metrics_collector = metrics_collector
        self.portfolio_initial_balance = portfolio_initial_balance

        logger.info("MonitoringContextProvider initialized")

    async def get_monitoring_context_async(
        self, asset_pair: Optional[str] = None, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """Async variant of get_monitoring_context to avoid blocking the event loop."""
        context = {
            "timestamp": datetime.now(UTC).isoformat(),
            "has_monitoring_data": False,
            "active_positions": {"futures": []},
            "active_trades_count": 0,
            "recent_performance": {},
            "risk_metrics": {},
            "position_concentration": {},
            "multi_timeframe_pulse": None,
        }

        try:
            if hasattr(self.platform, "aget_portfolio_breakdown"):
                portfolio = await self.platform.aget_portfolio_breakdown()

                futures_positions, holdings = self._extract_active_positions_from_portfolio(portfolio)

                if asset_pair:
                    futures_positions = self._filter_positions_by_asset(
                        futures_positions, asset_pair
                    )
                    holdings = [h for h in holdings if asset_pair in h.get("asset", "")]

                context["active_positions"] = {
                    "futures": futures_positions,
                    "spot": holdings,
                }
                context["has_monitoring_data"] = True

            # Active trades count from monitor
            if self.trade_monitor:
                context["active_trades_count"] = len(self.trade_monitor.active_trackers)

            # Recent performance from metrics collector
            if self.metrics_collector:
                recent_metrics = self.metrics_collector.get_recent_metrics(
                    hours=lookback_hours, asset_pair=asset_pair
                )
                context["recent_performance"] = recent_metrics

            # Risk metrics
            context["risk_metrics"] = self._calculate_risk_metrics_from_dict(
                portfolio if hasattr(self.platform, "aget_portfolio_breakdown") else {}
            )

            # Position concentration
            context["position_concentration"] = self._calculate_concentration_from_dict(
                portfolio if hasattr(self.platform, "aget_portfolio_breakdown") else {}
            )

        except Exception as e:
            logger.error(f"Error getting async monitoring context: {e}", exc_info=True)
            context["error"] = str(e)

        return context

    def get_monitoring_context(
        self, asset_pair: Optional[str] = None, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get comprehensive monitoring context for AI decision making.

        Args:
            asset_pair: Specific asset to focus on (None = all assets)
            lookback_hours: Hours to look back for recent trades

        Returns:
            Dictionary with monitoring context including:
            - active_positions: Live positions from platform
            - active_trades_count: Number of monitored trades
            - recent_performance: Recent trade metrics
            - risk_metrics: Exposure and risk analysis
            - position_concentration: Asset allocation breakdown
        """
        context_timestamp = datetime.now(UTC).isoformat()
        context = {
            "timestamp": context_timestamp,
            "latest_market_data_timestamp": context_timestamp,
            "market_data_timestamp": context_timestamp,
            "asset_type": "crypto",
            "timeframe": "intraday",
            "market_status": None,
            "has_monitoring_data": False,
            "active_positions": {"futures": []},
            "active_trades_count": 0,
            "recent_performance": {},
            "risk_metrics": {},
            "position_concentration": {},
            "portfolio_breakdown": {},
            "multi_timeframe_pulse": None,  # Multi-TF technical indicators
        }

        try:
            # Get active positions from platform
            if hasattr(self.platform, "get_portfolio_breakdown"):
                # Use sync method for backward compatibility
                portfolio = self.platform.get_portfolio_breakdown()

                context["portfolio_breakdown"] = portfolio

                # Extract active positions
                futures_positions, holdings = self._extract_active_positions_from_portfolio(portfolio)

                # Filter by asset pair if specified
                if asset_pair:
                    futures_positions = self._filter_positions_by_asset(
                        futures_positions, asset_pair
                    )
                    holdings = [h for h in holdings if asset_pair in h.get("asset", "")]

                context["active_positions"] = {
                    "futures": futures_positions,
                    "spot": holdings,
                }

                # Calculate risk metrics from active positions
                context["risk_metrics"] = self._calculate_risk_metrics(
                    futures_positions, portfolio
                )

                # Position concentration analysis
                context["position_concentration"] = self._analyze_concentration(
                    portfolio
                )

                context["has_monitoring_data"] = True

        except ConnectionError as e:
            logger.error(
                "Failed to fetch active positions - connection error",
                extra={
                    "asset_pair": asset_pair,
                    "error": str(e),
                    "error_type": "connection",
                    "platform_type": type(self.platform).__name__ if self.platform else "None"
                },
                exc_info=True
            )
            # TODO: Alert on repeated position fetch failures (THR-XXX)
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                "Failed to fetch active positions - data validation error",
                extra={
                    "asset_pair": asset_pair,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "platform_type": type(self.platform).__name__ if self.platform else "None"
                }
            )
        except Exception as e:
            logger.error(
                "Failed to fetch active positions - unexpected error",
                extra={
                    "asset_pair": asset_pair,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "platform_type": type(self.platform).__name__ if self.platform else "None"
                },
                exc_info=True
            )
            # TODO: Monitor unexpected context provider errors (THR-XXX)

        # Get active trade monitoring data
        if self.trade_monitor:
            try:
                context["active_trades_count"] = len(self.trade_monitor.active_trackers)
                context["max_concurrent_trades"] = (
                    self.trade_monitor.MAX_CONCURRENT_TRADES
                )
                context["slots_available"] = (
                    self.trade_monitor.MAX_CONCURRENT_TRADES
                    - len(self.trade_monitor.active_trackers)
                )
            except (AttributeError, TypeError) as e:
                logger.warning(
                    "Failed to fetch active trades - attribute error",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "has_trade_monitor": bool(self.trade_monitor)
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to fetch active trades - unexpected error",
                    extra={
                        "asset_pair": asset_pair,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                # TODO: Monitor trade monitor access errors (THR-XXX)

        # Get recent performance metrics
        if self.metrics_collector:
            try:
                context["recent_performance"] = self._get_recent_performance(
                    asset_pair, lookback_hours
                )
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(
                    "Failed to fetch recent performance - data validation error",
                    extra={
                        "asset_pair": asset_pair,
                        "lookback_hours": lookback_hours,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "has_metrics_collector": bool(self.metrics_collector)
                    }
                )
            except Exception as e:
                logger.error(
                    "Failed to fetch recent performance - unexpected error",
                    extra={
                        "asset_pair": asset_pair,
                        "lookback_hours": lookback_hours,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                # TODO: Monitor metrics collector errors (THR-XXX)

        # Get multi-timeframe pulse from TradeMonitor (if configured)
        if self.trade_monitor and asset_pair:
            try:
                pulse = self.trade_monitor.get_latest_market_context(asset_pair)
                if pulse:
                    context["multi_timeframe_pulse"] = pulse
                    pulse_asset_type = pulse.get("asset_type", context["asset_type"])
                    pulse_timestamp = pulse.get("latest_market_data_timestamp") or pulse.get("market_data_timestamp")
                    if pulse_timestamp and str(pulse_asset_type).lower() != "crypto":
                        context["latest_market_data_timestamp"] = pulse_timestamp
                        context["market_data_timestamp"] = pulse_timestamp
                    context["asset_type"] = pulse_asset_type
                    context["timeframe"] = pulse.get("timeframe", context["timeframe"])
                    context["market_status"] = pulse.get("market_status", context["market_status"])
                    context["has_monitoring_data"] = True
                    logger.debug(
                        f"Fetched multi-timeframe pulse for {asset_pair}: "
                        f"{len(pulse.get('timeframes', {}))} timeframes"
                    )
            except Exception as e:
                logger.warning(f"Could not fetch multi-timeframe pulse: {e}")

        return context

    def _extract_active_positions_from_portfolio(self, portfolio: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Extract active futures/spot positions from either flat or platform_breakdowns shapes."""
        return extract_portfolio_positions(portfolio)

    def _filter_positions_by_asset(
        self, positions: List[Dict[str, Any]], asset_pair: str
    ) -> List[Dict[str, Any]]:
        """Filter positions matching an asset pair, handling CFM/INTX product ID formats.

        CFM products use non-obvious IDs like BIP-20DEC30-CDE for BTC perpetuals.
        This maps product prefixes to base assets for correct matching.
        """
        base = asset_pair.replace("-", "").replace("USD", "").replace("USDC", "").upper()
        matched = []
        for p in positions:
            pid = p.get("product_id", "")
            if asset_pair in pid:
                matched.append(p)
            else:
                pid_canonical = _pid_to_pair(pid)
                if pid_canonical and pid_canonical.replace("USD", "") == base:
                    matched.append(p)
                elif base in pid.upper():
                    matched.append(p)
        return matched

    def _calculate_risk_metrics(
        self, futures_positions: List[Dict[str, Any]], portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate risk metrics from active positions.

        Returns:
            Risk metrics including:
            - total_exposure_usd: Total notional value of positions
            - unrealized_pnl: Total unrealized P&L
            - long_exposure: Value of long positions
            - short_exposure: Value of short positions
            - net_exposure: Long - Short exposure
            - leverage_estimate: Rough leverage ratio
        """
        total_exposure = 0.0
        unrealized_pnl = 0.0
        long_exposure = 0.0
        short_exposure = 0.0

        for pos in futures_positions:
            side = str(pos.get("side", "LONG")).upper()
            notional = _estimate_position_notional_usd(pos)
            total_exposure += notional
            unrealized_pnl += _coerce_monitoring_float(pos.get("unrealized_pnl", 0), 0.0)

            if side == "LONG":
                long_exposure += notional
            else:
                short_exposure += notional

        total_value = _coerce_monitoring_float(portfolio.get("total_value_usd", 0), 0.0)
        summary_unrealized = None
        if total_value <= 0:
            for name, pdata in (portfolio.get("platform_breakdowns") or {}).items():
                if not isinstance(pdata, dict):
                    continue
                if str(name).lower() == "coinbase":
                    futures_summary = pdata.get("futures_summary") or {}
                    total_value = _coerce_monitoring_float(
                        futures_summary.get("total_balance_usd", 0)
                        or pdata.get("total_value_usd", 0),
                        0.0,
                    )
                    if futures_summary.get("unrealized_pnl") is not None:
                        summary_unrealized = _coerce_monitoring_float(
                            futures_summary.get("unrealized_pnl"), 0.0
                        )
                    break
        if summary_unrealized is not None:
            unrealized_pnl = summary_unrealized
        leverage = total_exposure / total_value if total_value > 0 else 0

        return {
            "total_exposure_usd": total_exposure,
            "unrealized_pnl": unrealized_pnl,
            "long_exposure": long_exposure,
            "short_exposure": short_exposure,
            "net_exposure": long_exposure - short_exposure,
            "leverage_estimate": leverage,
            "account_value": total_value,
        }

    def _analyze_concentration(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze position concentration across assets.

        Returns:
            Concentration metrics including:
            - num_positions: Number of open positions
            - largest_position_pct: Largest single position as % of portfolio
            - top_3_concentration: % in top 3 positions
            - diversification_score: 0-100 (higher = more diversified)
        """
        futures_positions, _ = self._extract_active_positions_from_portfolio(portfolio)
        total_value = _coerce_monitoring_float(portfolio.get("total_value_usd", 1), 1.0)
        if total_value <= 0:
            for pdata in (portfolio.get("platform_breakdowns") or {}).values():
                if isinstance(pdata, dict):
                    total_value = _coerce_monitoring_float(pdata.get("total_value_usd", 0.0), 0.0) or total_value

        if not futures_positions or total_value <= 0:
            return {
                "num_positions": 0,
                "largest_position_pct": 0,
                "top_3_concentration": 0,
                "diversification_score": 0,
            }

        # Calculate position sizes as % of portfolio and keep per-asset breakdown
        position_sizes = []
        asset_position_pct: Dict[str, float] = {}
        for pos in futures_positions:
            notional = _estimate_position_notional_usd(pos)
            if notional <= 0:
                continue
            pct = (notional / total_value) * 100
            position_sizes.append(pct)
            for asset_key in _position_asset_keys(pos):
                asset_position_pct[asset_key] = max(asset_position_pct.get(asset_key, 0.0), pct)

        position_sizes.sort(reverse=True)

        largest_pct = position_sizes[0] if position_sizes else 0
        top_3_pct = sum(position_sizes[:3])

        # Diversification score (simplified Herfindahl index)
        # Lower concentration = higher score
        herfindahl = sum(p**2 for p in position_sizes) / 10000
        diversification = max(0, 100 - (herfindahl * 100))

        return {
            "num_positions": len(futures_positions),
            "largest_position_pct": largest_pct,
            "top_3_concentration": top_3_pct,
            "diversification_score": diversification,
            "asset_position_pct": asset_position_pct,
        }

    def _get_recent_performance(
        self, asset_pair: Optional[str], lookback_hours: int
    ) -> Dict[str, Any]:
        """
        Get recent trade performance metrics.

        Returns:
            Recent performance including:
            - trades_count: Number of trades in lookback period
            - win_rate: % of profitable trades
            - avg_pnl: Average P&L per trade
            - total_pnl: Total P&L in period
        """
        if not self.metrics_collector:
            return {}

        try:
            # Get all metrics files
            metrics_dir = Path("data/trade_metrics")
            if not metrics_dir.exists():
                return {}

            cutoff_time = datetime.now(UTC) - timedelta(hours=lookback_hours)
            recent_trades = []

            for metric_file in metrics_dir.glob("trade_*.json"):
                try:
                    with open(metric_file, "r", encoding="utf-8") as f:
                        metrics = json.load(f)

                    # Check if within lookback period
                    entry_time_str = metrics.get("entry_time", "")
                    if entry_time_str.endswith("Z"):
                        entry_time_str = entry_time_str[:-1] + "+00:00"
                    entry_time = datetime.fromisoformat(entry_time_str)

                    if entry_time >= cutoff_time:
                        # Filter by asset if specified
                        if asset_pair:
                            product = metrics.get("product_id", "")
                            if asset_pair not in product:
                                continue

                        recent_trades.append(metrics)

                except Exception as e:
                    logger.debug(f"Error reading metric file: {e}")
                    continue

            if not recent_trades:
                return {"trades_count": 0, "lookback_hours": lookback_hours}

            # Calculate aggregate metrics
            profitable = sum(1 for t in recent_trades if t.get("realized_pnl", 0) > 0)
            total_pnl = sum(t.get("realized_pnl", 0) for t in recent_trades)

            return {
                "trades_count": len(recent_trades),
                "win_rate": (profitable / len(recent_trades)) * 100,
                "avg_pnl": total_pnl / len(recent_trades),
                "total_pnl": total_pnl,
                "lookback_hours": lookback_hours,
            }

        except Exception as e:
            logger.error(f"Error getting recent performance: {e}")
            return {}

    def get_portfolio_pnl_percentage(self) -> float:
        """
        Calculate the overall portfolio P&L as a percentage of the initial balance.
        This assumes that the `account_value` from `risk_metrics` (derived from
        `platform.get_portfolio_breakdown().get('total_value_usd')`) already reflects
        the current total equity, including both unrealized P&L of open positions
        and realized P&L from closed positions (if any are settled).

        Returns:
            Current overall portfolio P&L as a percentage.
        """
        if self.portfolio_initial_balance <= 0:
            return 0.0

        # Get current total value of the portfolio from the platform
        current_context = self.get_monitoring_context()
        current_portfolio_value = current_context.get("risk_metrics", {}).get(
            "account_value", 0.0
        )

        # Calculate P&L as a percentage of initial balance
        pnl_percentage = (
            current_portfolio_value - self.portfolio_initial_balance
        ) / self.portfolio_initial_balance

        return pnl_percentage

    def _format_pulse_summary(self, pulse: Dict[str, Any]) -> str:
        """
        Format multi-timeframe pulse data into LLM-friendly text.

        Converts technical indicators (RSI, MACD, Bollinger Bands, ADX, ATR)
        into natural language descriptions for AI decision making.

        Args:
            pulse: Multi-timeframe pulse dict from TradeMonitor.get_latest_market_context()

        Returns:
            Formatted string describing multi-timeframe technical analysis
        """
        if not pulse or not pulse.get("timeframes"):
            return ""

        lines = ["\n=== MULTI-TIMEFRAME TECHNICAL ANALYSIS ==="]

        # Pulse metadata
        pulse_age = pulse.get("age_seconds", 0)
        lines.append(f"Pulse Age: {pulse_age:.0f}s ago (refreshes every 5 min)")

        timeframes = pulse.get("timeframes", {})
        sorted_tfs = sorted(
            timeframes.keys(),
            key=lambda x: {
                "1m": 1,
                "5m": 5,
                "15m": 15,
                "1h": 60,
                "4h": 240,
                "1d": 1440,
                "daily": 1440,
            }.get(x, 999),
        )

        for tf in sorted_tfs:
            data = timeframes[tf]
            lines.append(f"\n[{tf.upper()} Timeframe]")

            # Trend analysis
            trend = data.get("trend", "UNKNOWN")
            rsi = data.get("rsi")
            signal_strength = data.get("signal_strength", 0)

            lines.append(
                f"  Trend: {trend} (Signal Strength: {signal_strength:.0f}/100)"
            )

            # RSI
            if rsi is not None:
                if rsi > 70:
                    rsi_text = f"OVERBOUGHT ({rsi:.1f})"
                elif rsi < 30:
                    rsi_text = f"OVERSOLD ({rsi:.1f})"
                else:
                    rsi_text = f"NEUTRAL ({rsi:.1f})"
                lines.append(f"  RSI: {rsi_text}")

            # MACD
            macd_data = data.get("macd", {})
            if macd_data:
                macd_val = macd_data.get("macd", 0)
                signal_val = macd_data.get("signal", 0)
                histogram = macd_data.get("histogram", 0)

                if histogram > 0:
                    macd_text = "BULLISH (histogram positive)"
                elif histogram < 0:
                    macd_text = "BEARISH (histogram negative)"
                else:
                    macd_text = "NEUTRAL"
                lines.append(
                    f"  MACD: {macd_text} | "
                    f"MACD={macd_val:.2f}, Signal={signal_val:.2f}"
                )

            # Bollinger Bands
            bbands = data.get("bollinger_bands", {})
            if bbands:
                percent_b = bbands.get("percent_b")
                if percent_b is not None:
                    if percent_b > 1.0:
                        bb_text = "Above upper band (overbought zone)"
                    elif percent_b < 0.0:
                        bb_text = "Below lower band (oversold zone)"
                    elif percent_b > 0.8:
                        bb_text = "Near upper band (resistance)"
                    elif percent_b < 0.2:
                        bb_text = "Near lower band (support)"
                    else:
                        bb_text = "Middle range (neutral)"
                    lines.append(f"  Bollinger Bands: {bb_text} (%B={percent_b:.2f})")

            # ADX (trend strength)
            adx_data = data.get("adx", {})
            if adx_data:
                adx_val = adx_data.get("adx", 0)
                plus_di = adx_data.get("plus_di", 0)
                minus_di = adx_data.get("minus_di", 0)

                if adx_val > 25:
                    adx_text = "STRONG TREND"
                elif adx_val > 20:
                    adx_text = "Developing trend"
                else:
                    adx_text = "Weak/ranging"

                direction = "+DI dominant" if plus_di > minus_di else "-DI dominant"
                lines.append(f"  ADX: {adx_text} ({adx_val:.1f}) | {direction}")

            # Volatility
            volatility = data.get("volatility", "unknown")
            atr = data.get("atr")
            if volatility != "unknown":
                vol_text = volatility.upper()
                if atr:
                    vol_text += f" (ATR={atr:.2f})"
                lines.append(f"  Volatility: {vol_text}")

        # Cross-timeframe alignment
        lines.append("\n[Cross-Timeframe Alignment]")
        trend_counts = {"UPTREND": 0, "DOWNTREND": 0, "RANGING": 0}
        for tf_data in timeframes.values():
            trend = tf_data.get("trend", "UNKNOWN")
            if "UPTREND" in trend:
                trend_counts["UPTREND"] += 1
            elif "DOWNTREND" in trend:
                trend_counts["DOWNTREND"] += 1
            else:
                trend_counts["RANGING"] += 1

        total_tfs = len(timeframes)
        if trend_counts["UPTREND"] >= total_tfs * 0.6:
            alignment = "BULLISH ALIGNMENT - Multiple timeframes confirm uptrend"
        elif trend_counts["DOWNTREND"] >= total_tfs * 0.6:
            alignment = "BEARISH ALIGNMENT - Multiple timeframes confirm downtrend"
        else:
            alignment = "MIXED SIGNALS - Timeframes show conflicting trends"

        lines.append(f"  {alignment}")
        lines.append(
            f"  Breakdown: {trend_counts['UPTREND']} up, "
            f"{trend_counts['DOWNTREND']} down, {trend_counts['RANGING']} ranging"
        )

        lines.append("=" * 42 + "\n")

        return "\n".join(lines)

    def format_for_ai_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format monitoring context for inclusion in AI prompts.

        Args:
            context: Monitoring context from get_monitoring_context()

        Returns:
            Formatted string for AI prompt injection
        """
        if not context.get("has_monitoring_data"):
            return "\nNo active trading positions currently.\n"

        lines = ["\n=== LIVE TRADING CONTEXT ==="]

        # Position-awareness directives should appear before raw data so they don't
        # get lost in the middle of a long prompt.
        active_pos = context.get("active_positions", {})
        futures = active_pos.get("futures", [])
        slots_available = int(_coerce_monitoring_float(context.get("slots_available"), 0))
        active_trades = int(_coerce_monitoring_float(context.get("active_trades_count"), 0))

        if futures:
            lines.extend([
                "",
                "=== POSITION AWARENESS DIRECTIVES ===",
                "- Respect live position context before proposing any action.",
                "- HOLD = maintain current exposure when the thesis is intact.",
                "- REDUCE_* / CLOSE_* = trim or fully exit exposure when risk, invalidation, or adverse momentum dominates.",
                "- OPEN_* = initiate new exposure only when slots are available, confidence is strong, and risk is justified.",
                "- ADD_* = scale an existing same-side position only when conviction and risk budget clearly justify it.",
                "- Explicitly weigh confidence, risk, and active exposure in your recommendation.",
            ])
            if slots_available <= 0:
                lines.append("- Monitoring capacity is full, so do NOT recommend OPEN_* actions until a slot opens.")
            else:
                lines.append(
                    f"- {slots_available} monitoring slot(s) remain; OPEN_* actions are allowed only with high confidence and clear risk control."
                )

        # Active positions summary
        if futures:
            lines.append(f"\nActive Positions: {len(futures)}")
            for pos in futures:
                side = pos.get("side", "UNKNOWN")
                product = pos.get("product_id", "N/A")
                contracts = _coerce_monitoring_float(
                    pos.get("contracts", pos.get("number_of_contracts", 0))
                )
                entry = _coerce_monitoring_float(
                    pos.get("entry_price", pos.get("avg_entry_price", 0))
                )
                current = _coerce_monitoring_float(pos.get("current_price", 0))
                pnl = _coerce_monitoring_float(pos.get("unrealized_pnl", 0))

                pnl_sign = "+" if pnl >= 0 else ""
                lines.append(
                    f"  • {side} {product}: {contracts:.2f} contracts "
                    f"@ ${entry:.2f} (current ${current:.2f}) "
                    f"| P&L: {pnl_sign}${pnl:.2f}"
                )
        else:
            lines.append("\nNo active positions")

        # Risk metrics
        risk = context.get("risk_metrics", {})
        if risk:
            lines.append("\nRisk Exposure:")
            lines.append(
                f"  • Total Exposure: ${_coerce_monitoring_float(risk.get('total_exposure_usd', 0)):,.2f}"
            )
            lines.append(
                f"  • Unrealized P&L: ${_coerce_monitoring_float(risk.get('unrealized_pnl', 0)):,.2f}"
            )
            lines.append(
                f"  • Leverage: {_coerce_monitoring_float(risk.get('leverage_estimate', 0)):.2f}x"
            )
            lines.append(
                f"  • Net Exposure: ${_coerce_monitoring_float(risk.get('net_exposure', 0)):,.2f}"
            )

        # Position concentration
        conc = context.get("position_concentration", {})
        if conc and conc.get("num_positions", 0) > 0:
            lines.append("\nPosition Concentration:")
            lines.append(
                f"  • Largest Position: "
                f"{_coerce_monitoring_float(conc.get('largest_position_pct', 0)):.1f}% of portfolio"
            )
            lines.append(
                f"  • Diversification Score: "
                f"{_coerce_monitoring_float(conc.get('diversification_score', 0)):.0f}/100"
            )

        # Active trade slots
        if context.get("max_concurrent_trades"):
            lines.append(
                f"\nMonitoring Capacity: "
                f"{active_trades}/"
                f"{int(_coerce_monitoring_float(context.get('max_concurrent_trades', 0), 0))} slots used "
                f"({slots_available} available)"
            )

        # Recent performance
        perf = context.get("recent_performance", {})
        if perf.get("trades_count", 0) > 0:
            lines.append(
                f"\nRecent Performance " f"({perf.get('lookback_hours', 24)}h):"
            )
            lines.append(
                f"  • Trades: {perf.get('trades_count', 0)} "
                f"| Win Rate: {_coerce_monitoring_float(perf.get('win_rate', 0)):.1f}%"
            )
            lines.append(
                f"  • Total P&L: ${_coerce_monitoring_float(perf.get('total_pnl', 0)):,.2f} "
                f"| Avg: ${_coerce_monitoring_float(perf.get('avg_pnl', 0)):.2f}"
            )

        lines.append("=" * 30 + "\n")

        # Multi-timeframe pulse (if available)
        pulse = context.get("multi_timeframe_pulse")
        if pulse:
            pulse_text = self._format_pulse_summary(pulse)
            if pulse_text:
                lines.append(pulse_text)

        return "\n".join(lines)
