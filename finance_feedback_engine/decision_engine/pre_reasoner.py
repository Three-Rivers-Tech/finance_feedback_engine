"""Pre-reasoning layer for FFE decision pipeline.

Generates a structured market brief before debate mode, enabling:
1. Focused context for bull/bear/judge (replaces raw data dump)
2. No-op gating (skip debate when nothing is actionable)
3. Reduced LLM token usage (compressed brief vs full prompt)

Safety features (from architecture reviews — Claude + GPT 5.4):
- Separate consecutive_skips vs cycles_since_last_debate counters
- Confidence floor on skip decisions
- Volatility/volume spike escalation (regime novelty)
- Recent position close forces debate
- Portfolio drawdown awareness
- Hard timeout on LLM call (20s default)
- Enum validation + numeric clamping on all parsed fields
- Shadow counterfactual logging for skip quality measurement
- Rationale quality check

Track E1 — see docs/plans/FFE_EFFICIENCY_ROADMAP_2026-04-04.md
"""

import logging
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Valid enum values for validation
_VALID_REGIMES = {"trending_up", "trending_down", "ranging", "volatile", "dead", "unknown"}
_VALID_MOMENTUM = {"bullish", "bearish", "neutral", "mixed"}
_VALID_DATA_QUALITY = {"good", "degraded", "stale"}
_VALID_VOLUME = {"high", "normal", "low", "thin"}

# Safety defaults
DEFAULT_MAX_CONSECUTIVE_SKIPS = 3
DEFAULT_FORCED_DEBATE_INTERVAL = 3  # cycles_since_last_debate, not consecutive
DEFAULT_PRE_REASON_TIMEOUT_S = 20
DEFAULT_CONFIDENCE_FLOOR = 40  # Below this → force debate
DEFAULT_VOLATILITY_CEILING = 90  # Above this → force debate (regime novelty)
DEFAULT_RECENT_CLOSE_WINDOW_S = 300  # 5 min after close → force debate
DEFAULT_MIN_REASONING_LENGTH = 20  # Chars — below this → force debate
DEFAULT_DATA_DEGRADED_AGE_S = 300  # 5 min → degraded
DEFAULT_DATA_STALE_AGE_S = 900  # 15 min → stale


@dataclass(frozen=True)
class MarketBrief:
    """Structured output from the pre-reasoning step."""

    regime: str
    regime_confidence: int  # 0-100
    key_support: float
    key_resistance: float
    current_price: float
    momentum: str
    momentum_detail: str
    volatility_percentile: float  # 0-100
    volume_context: str  # "high", "normal", "low", "thin"
    has_position: bool
    position_side: Optional[str]
    position_pnl: Optional[float]
    position_entry: Optional[float]
    actionable: bool
    skip_reason: Optional[str]
    key_question: str
    data_quality: str
    data_timestamp: float
    reasoning: str

    def to_prompt_section(self) -> str:
        """Format as a concise prompt section for debate providers."""
        lines = [
            "MARKET BRIEF (Pre-Analysis Summary)",
            "=" * 40,
            f"Regime: {self.regime.upper()} (confidence: {self.regime_confidence}%)",
            f"Momentum: {self.momentum} — {self.momentum_detail}",
            f"Volatility: {self.volatility_percentile:.0f}th percentile | Volume: {self.volume_context}",
            f"Price: ${self.current_price:,.2f} (support: ${self.key_support:,.2f}, resistance: ${self.key_resistance:,.2f})",
            f"Data Quality: {self.data_quality}",
        ]
        if self.has_position:
            pnl_str = f"${self.position_pnl:+.2f}" if self.position_pnl is not None else "unknown"
            lines.append(f"Open Position: {self.position_side} from ${self.position_entry:,.2f} (PnL: {pnl_str})")
        lines.append(f"")
        lines.append(f"KEY QUESTION: {self.key_question}")
        lines.append(f"")
        lines.append(f"Analysis: {self.reasoning}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PreReasonGatekeeper:
    """Tracks skip state and enforces safety limits on no-op gating.

    Safety controls (from GPT 5.4 review):
    1. consecutive_skips: max before forced debate (flash crash protection)
    2. cycles_since_last_debate: periodic heartbeat (separate counter)
    3. confidence_floor: low-certainty skip → force debate
    4. volatility_ceiling: regime novelty → force debate
    5. recent_close_window: force debate shortly after position close
    6. data_quality: degraded/stale → force debate
    7. rationale_quality: too-short reasoning → force debate
    8. position_open: always force debate
    """

    def __init__(
        self,
        max_consecutive_skips: int = DEFAULT_MAX_CONSECUTIVE_SKIPS,
        forced_debate_interval: int = DEFAULT_FORCED_DEBATE_INTERVAL,
        confidence_floor: int = DEFAULT_CONFIDENCE_FLOOR,
        volatility_ceiling: float = DEFAULT_VOLATILITY_CEILING,
        recent_close_window_s: float = DEFAULT_RECENT_CLOSE_WINDOW_S,
        min_reasoning_length: int = DEFAULT_MIN_REASONING_LENGTH,
    ):
        self.max_consecutive_skips = max_consecutive_skips
        self.forced_debate_interval = forced_debate_interval
        self.confidence_floor = confidence_floor
        self.volatility_ceiling = volatility_ceiling
        self.recent_close_window_s = recent_close_window_s
        self.min_reasoning_length = min_reasoning_length

        # Separate counters (GPT 5.4 finding #1)
        self._consecutive_skips = 0
        self._cycles_since_last_debate = 0
        self._total_skips = 0
        self._total_debates = 0
        self._last_forced_reason: Optional[str] = None
        self._last_position_close_time: Optional[float] = None

        # Shadow counterfactual tracking (GPT 5.4 finding #6)
        self._shadow_skip_count = 0
        self._shadow_would_have_debated = 0

    def record_position_close(self) -> None:
        """Record that a position was recently closed."""
        self._last_position_close_time = time.time()

    def should_force_debate(
        self,
        brief: "MarketBrief",
        portfolio_drawdown_pct: Optional[float] = None,
        daily_loss_pct: Optional[float] = None,
    ) -> tuple[bool, Optional[str]]:
        """Check if debate should be forced despite brief saying not actionable.

        Returns:
            (force_debate, reason)
        """
        # If brief says actionable, no forcing needed
        if brief.actionable:
            self._consecutive_skips = 0
            return False, None

        # --- Hard forces (always override skip) ---

        # 1. Position open → always debate
        if brief.has_position:
            self._consecutive_skips = 0
            return True, "position_open"

        # 2. Recent position close (GPT 5.4 finding #4)
        if self._last_position_close_time is not None:
            elapsed = time.time() - self._last_position_close_time
            if elapsed < self.recent_close_window_s:
                return True, f"recent_close ({elapsed:.0f}s ago, window={self.recent_close_window_s}s)"

        # 3. Consecutive skip limit (flash crash protection)
        if self._consecutive_skips >= self.max_consecutive_skips:
            reason = f"consecutive_skip_limit ({self._consecutive_skips}/{self.max_consecutive_skips})"
            self._last_forced_reason = reason
            self._consecutive_skips = 0
            return True, reason

        # 4. Periodic heartbeat (separate counter — GPT 5.4 finding #1)
        if self._cycles_since_last_debate >= self.forced_debate_interval:
            reason = f"heartbeat ({self._cycles_since_last_debate} cycles since last debate)"
            self._last_forced_reason = reason
            return True, reason

        # 5. Data quality degraded/stale → force
        if brief.data_quality in ("degraded", "stale"):
            return True, f"data_quality_{brief.data_quality}"

        # 6. Confidence floor (GPT 5.4 finding #2)
        if brief.regime_confidence < self.confidence_floor:
            return True, f"low_confidence ({brief.regime_confidence} < {self.confidence_floor})"

        # 7. Volatility ceiling / regime novelty (GPT 5.4 finding #3)
        if brief.volatility_percentile > self.volatility_ceiling:
            return True, f"volatility_spike ({brief.volatility_percentile:.0f}th pctl > {self.volatility_ceiling})"

        # 8. Volume anomaly (thin liquidity is dangerous)
        if brief.volume_context == "thin":
            return True, "thin_liquidity"

        # 9. Rationale quality check (GPT 5.4 finding #7)
        if len(brief.reasoning.strip()) < self.min_reasoning_length:
            return True, f"weak_rationale (len={len(brief.reasoning.strip())})"

        # 10. Portfolio drawdown awareness (GPT 5.4 finding #5)
        if portfolio_drawdown_pct is not None and portfolio_drawdown_pct > 10.0:
            return True, f"portfolio_drawdown ({portfolio_drawdown_pct:.1f}%)"
        if daily_loss_pct is not None and daily_loss_pct > 5.0:
            return True, f"daily_loss_limit ({daily_loss_pct:.1f}%)"

        # OK to skip
        return False, None

    def record_skip(self) -> None:
        """Record that a cycle was skipped."""
        self._consecutive_skips += 1
        self._cycles_since_last_debate += 1
        self._total_skips += 1
        self._shadow_skip_count += 1

    def record_debate(self) -> None:
        """Record that a full debate ran."""
        self._consecutive_skips = 0
        self._cycles_since_last_debate = 0
        self._total_debates += 1

    def record_shadow_counterfactual(self) -> None:
        """Record that a skipped cycle would have produced a different result.
        Call this when post-hoc analysis shows the skip missed an opportunity."""
        self._shadow_would_have_debated += 1

    @property
    def skip_stats(self) -> Dict[str, Any]:
        return {
            "consecutive_skips": self._consecutive_skips,
            "cycles_since_last_debate": self._cycles_since_last_debate,
            "total_skips": self._total_skips,
            "total_debates": self._total_debates,
            "last_forced_reason": self._last_forced_reason,
            "shadow_skip_count": self._shadow_skip_count,
            "shadow_would_have_debated": self._shadow_would_have_debated,
        }


def build_pre_reason_prompt(
    market_data: Dict[str, Any],
    position_state: Optional[Dict[str, Any]] = None,
    memory_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the pre-reasoning prompt from market data and position context."""
    price = market_data.get("close", 0)
    high = market_data.get("high", 0)
    low = market_data.get("low", 0)
    rsi = market_data.get("rsi", "N/A")
    trend = market_data.get("trend", "neutral")
    volume = market_data.get("volume", 0)
    volatility = market_data.get("volatility", "N/A")

    mtf = market_data.get("multi_timeframe_trend", {})
    mtf_consensus = mtf.get("consensus", "unknown")
    mtf_score = mtf.get("score", 0)
    timeframes = mtf.get("timeframes", {})
    tf_summary = ", ".join(
        f"{tf}: {td.get('direction', '?')}"
        for tf, td in sorted(timeframes.items())
        if td.get("direction", "unknown") != "unknown"
    )

    pos_section = "No open position."
    if position_state and position_state.get("has_position"):
        side = position_state.get("side", "?")
        entry = position_state.get("entry_price", 0)
        pnl = position_state.get("unrealized_pnl", 0)
        contracts = position_state.get("contracts", 0)
        pos_section = f"Open {side} {contracts} contracts @ ${entry:,.2f} (PnL: ${pnl:+.2f})"

    perf_section = ""
    if memory_context:
        recent_pnl = memory_context.get("realized_pnl", None)
        win_rate = memory_context.get("win_rate", None)
        streak = memory_context.get("current_streak", {})
        if recent_pnl is not None:
            perf_section = f"\nRecent Performance: PnL ${recent_pnl:+.2f}, Win Rate: {win_rate:.0f}%"
            if streak:
                perf_section += f", {streak.get('streak_type', '')} streak: {streak.get('streak_count', 0)}"

    # Keep the pre-reason prompt compact so the raw local model can decide
    # quickly. Missing secondary fields are safely defaulted by the parser.
    prompt = f"""You are a fast market triage analyst. Return ONLY compact valid JSON.

MARKET:
price=${price:,.2f}, high=${high:,.2f}, low=${low:,.2f}, rsi={rsi}, trend={trend}, volume={volume:,.0f}, volatility={volatility}
multi_tf={mtf_consensus}, score={mtf_score:.1f}, directions={tf_summary or 'none'}
position={pos_section}{perf_section}

TASK:
Decide if there is a clear actionable setup right now or if the trading council should be skipped.
- If the market is dead/ranging with no catalyst and no position, set actionable=false.
- If there is a position that needs attention or a clear directional setup, set actionable=true.
- Keep reasoning very short.
- Keep key_question short.

Return ONLY valid JSON with these keys:
{{"regime": "trending_up|trending_down|ranging|volatile|dead",
  "regime_confidence": 0-100,
  "momentum": "bullish|bearish|neutral|mixed",
  "volatility_percentile": 0-100,
  "volume_context": "high|normal|low|thin",
  "actionable": true/false,
  "skip_reason": "short string" or null,
  "key_question": "short string",
  "reasoning": "one short sentence"
}}"""

    return prompt


def _validate_enum(value: str, valid_set: set, default: str) -> str:
    cleaned = str(value).strip().lower()
    return cleaned if cleaned in valid_set else default


def _clamp(value: float, lo: float, hi: float) -> float:
    if not math.isfinite(value):
        return lo
    return max(lo, min(hi, value))


def _compute_data_quality(data_timestamp_resolved: float) -> str:
    """Compute data quality deterministically from data age.

    Thresholds:
    - < 5 min old -> good
    - 5-15 min old -> degraded
    - > 15 min old -> stale
    """
    age_s = time.time() - data_timestamp_resolved
    if age_s > DEFAULT_DATA_STALE_AGE_S:
        return "stale"
    if age_s > DEFAULT_DATA_DEGRADED_AGE_S:
        return "degraded"
    return "good"


def parse_pre_reason_response(
    response: Dict[str, Any],
    current_price: float,
    position_state: Optional[Dict[str, Any]] = None,
    data_timestamp: Optional[float] = None,
) -> MarketBrief:
    """Parse LLM response into a MarketBrief with enum validation and safe defaults."""

    def _get(key: str, default: Any = None) -> Any:
        val = response.get(key, default)
        return val if val is not None else default

    has_position = bool(position_state and position_state.get("has_position"))

    regime = _validate_enum(str(_get("regime", "unknown")), _VALID_REGIMES, "unknown")
    momentum = _validate_enum(str(_get("momentum", "neutral")), _VALID_MOMENTUM, "neutral")
    # Ignore LLM data_quality — compute deterministically from data age
    resolved_timestamp = data_timestamp if data_timestamp is not None else time.time()
    data_quality = _compute_data_quality(resolved_timestamp)
    volume_context = _validate_enum(str(_get("volume_context", "normal")), _VALID_VOLUME, "normal")

    regime_confidence = int(_clamp(float(_get("regime_confidence", 50)), 0, 100))
    volatility_percentile = _clamp(float(_get("volatility_percentile", 50)), 0, 100)

    return MarketBrief(
        regime=regime,
        regime_confidence=regime_confidence,
        key_support=float(_get("key_support", current_price * 0.98)),
        key_resistance=float(_get("key_resistance", current_price * 1.02)),
        current_price=current_price,
        momentum=momentum,
        momentum_detail=str(_get("momentum_detail", "No clear momentum signal")),
        volatility_percentile=volatility_percentile,
        volume_context=volume_context,
        has_position=has_position,
        position_side=position_state.get("side") if has_position else None,
        position_pnl=position_state.get("unrealized_pnl") if has_position else None,
        position_entry=position_state.get("entry_price") if has_position else None,
        actionable=bool(_get("actionable", True)),
        skip_reason=_get("skip_reason"),
        key_question=str(_get("key_question", "What is the best action right now?")),
        data_quality=data_quality,
        data_timestamp=resolved_timestamp,
        reasoning=str(_get("reasoning", "Pre-reasoning analysis unavailable")),
    )
