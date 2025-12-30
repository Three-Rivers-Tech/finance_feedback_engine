"""
Prompt Templates for LLM Pair Evaluation.

Templates for querying LLM ensemble to evaluate and vote on trading pair candidates.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


PAIR_EVALUATION_PROMPT = """You are an expert quantitative analyst evaluating trading pair candidates for selection.

**Current Portfolio Context:**
{portfolio_context}

**Candidate Pairs (with statistical scores):**
{candidates_table}

**Your Task:**
For each candidate pair, provide:
1. **Vote**: STRONG_BUY | BUY | NEUTRAL | AVOID
2. **Confidence**: 0-100 (higher = more confident)
3. **Reasoning**: 2-3 sentences focusing on:
   - Statistical profile interpretation (Sortino, correlation, volatility)
   - Market regime fit
   - Diversification value
   - Risk factors or concerns

**Market Context:**
- Current Regime: {current_regime}
- Recent Performance: {recent_pnl} ({win_rate}% win rate over last {trade_count} trades)
- Active Positions: {active_positions}

**Selection Constraints:**
- Need to select {available_slots} new pair(s)
- Avoid pairs highly correlated with active positions (>0.7)
- Prioritize risk-adjusted returns (Sortino) over raw volatility
- Consider diversification to reduce portfolio concentration risk

**Important Guidelines:**
- STRONG_BUY: Exceptional risk-adjusted returns, excellent diversification, stable volatility
- BUY: Good candidate with solid metrics, worth considering
- NEUTRAL: Acceptable but not compelling, use as backup option
- AVOID: Poor metrics, high correlation, excessive volatility, or fundamental concerns

**Output Format (JSON):**
{{
  "BTCUSD": {{
    "vote": "STRONG_BUY",
    "confidence": 85,
    "reasoning": "Excellent Sortino ratio (2.1) indicates strong risk-adjusted returns with minimal downside. Low correlation (0.15) with current forex positions provides diversification. GARCH forecast shows stable volatility regime, reducing tail risk."
  }},
  "ETHUSD": {{
    "vote": "BUY",
    "confidence": 70,
    "reasoning": "Solid Sortino (1.6) with moderate volatility. Correlation (0.65) with BTCUSD is acceptable but not ideal for diversification. Consider as secondary option if top choices unavailable."
  }}
}}

Evaluate all {candidate_count} candidate pairs and provide your votes.
"""


PAIR_DESCRIPTION_PROMPT = """You are an expert quantitative analyst explaining trading pair selections.

**Selected Pairs:**
{selected_pairs}

**Statistical Scores:**
{statistical_scores}

**LLM Votes:**
{llm_votes}

**Your Task:**
Generate a concise summary (3-5 sentences) explaining why these specific pairs were selected for trading.

Focus on:
- Key strengths of the selected pairs (risk-adjusted returns, diversification, stability)
- How they complement each other as a portfolio
- Any notable market conditions or regime factors
- Overall portfolio construction logic

**Output Format:**
A clear, professional paragraph suitable for logging or reporting.

Example:
"Selected BTCUSD, EURUSD, and GBPJPY based on strong risk-adjusted returns (Sortino >1.5) and low inter-pair correlation (<0.4). BTCUSD leads with exceptional volatility-adjusted performance in the current trending regime. EURUSD and GBPJPY provide forex diversification while maintaining stable GARCH volatility forecasts. This combination balances crypto and forex exposure with minimal concentration risk."
"""


def build_pair_evaluation_prompt(
    candidates: Dict[str, float],
    candidate_metrics: Dict[str, Dict[str, any]],
    portfolio_context: Dict[str, Any],
    available_slots: int,
) -> str:
    """
    Build context-rich prompt for LLM pair evaluation.

    Args:
        candidates: Dict mapping pair to composite statistical score {pair: score}
        candidate_metrics: Dict mapping pair to detailed metrics
            {
                pair: {
                    'sortino': SortinoScore,
                    'correlation': CorrelationScore,
                    'garch': GARCHForecast,
                    'composite': float
                }
            }
        portfolio_context: Portfolio and market context from PortfolioMemory
        available_slots: Number of pairs to select

    Returns:
        Formatted prompt string ready for LLM
    """
    # Build candidates table
    candidates_table = _format_candidates_table(candidates, candidate_metrics)

    # Format portfolio context
    portfolio_summary = _format_portfolio_context(portfolio_context)

    # Extract market context
    current_regime = portfolio_context.get("current_regime", "unknown")
    recent_pnl = portfolio_context.get("total_pnl", 0.0)
    win_rate = portfolio_context.get("win_rate", 0.0)
    trade_count = portfolio_context.get("total_trades", 0)
    active_positions = portfolio_context.get("active_pairs", [])

    # Fill template
    return PAIR_EVALUATION_PROMPT.format(
        portfolio_context=portfolio_summary,
        candidates_table=candidates_table,
        current_regime=current_regime,
        recent_pnl=f"${recent_pnl:.2f}",
        win_rate=f"{win_rate:.1f}",
        trade_count=trade_count,
        active_positions=", ".join(active_positions) if active_positions else "None",
        available_slots=available_slots,
        candidate_count=len(candidates),
    )


def build_pair_description_prompt(
    selected_pairs: List[str],
    statistical_scores: Dict[str, float],
    llm_votes: Dict[str, Dict[str, any]],
) -> str:
    """
    Build prompt for generating selection reasoning.

    Args:
        selected_pairs: List of selected pair names
        statistical_scores: Dict mapping pair to composite score
        llm_votes: Dict mapping pair to LLM vote details

    Returns:
        Formatted prompt string ready for LLM
    """
    # Format selected pairs with scores
    pairs_summary = _format_selected_pairs_summary(
        selected_pairs, statistical_scores, llm_votes
    )

    # Format statistical scores
    scores_summary = _format_scores_summary(selected_pairs, statistical_scores)

    # Format LLM votes
    votes_summary = _format_votes_summary(selected_pairs, llm_votes)

    return PAIR_DESCRIPTION_PROMPT.format(
        selected_pairs=pairs_summary,
        statistical_scores=scores_summary,
        llm_votes=votes_summary,
    )


def _format_candidates_table(
    candidates: Dict[str, float], candidate_metrics: Dict[str, Dict[str, any]]
) -> str:
    """
    Format candidates into a readable table.

    Args:
        candidates: {pair: composite_score}
        candidate_metrics: {pair: {sortino, correlation, garch, composite}}

    Returns:
        Formatted table string
    """
    # Sort by composite score (descending)
    sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)

    lines = []
    lines.append("| Pair | Composite | Sortino | Correlation | Volatility | Details |")
    lines.append("|------|-----------|---------|-------------|------------|---------|")

    for pair, composite_score in sorted_candidates:
        metrics = candidate_metrics.get(pair, {})

        # Extract metric details
        sortino = metrics.get("sortino")
        correlation = metrics.get("correlation")
        garch = metrics.get("garch")

        sortino_val = f"{sortino.composite_score:.2f}" if sortino else "N/A"
        corr_val = f"{correlation.diversification_score:.2f}" if correlation else "N/A"
        vol_val = f"{garch.forecasted_vol:.2%}" if garch else "N/A"

        # Generate details string
        details = []
        if sortino:
            details.append(f"Returns: {sortino.mean_return:.2%}")
        if garch:
            details.append(f"Regime: {garch.volatility_regime}")
        if correlation and correlation.max_correlation > 0.7:
            details.append(f"⚠️ High corr: {correlation.max_correlation:.2f}")

        details_str = ", ".join(details) if details else "-"

        lines.append(
            f"| {pair} | {composite_score:.3f} | {sortino_val} | "
            f"{corr_val} | {vol_val} | {details_str} |"
        )

    return "\n".join(lines)


def _format_portfolio_context(portfolio_context: Dict[str, Any]) -> str:
    """Format portfolio context into readable summary."""
    lines = []

    def _to_percent(value: float) -> float:
        """Normalize win rate to percentage regardless of fraction/percent input."""
        return value * 100 if value <= 1 else value

    # Market regime
    regime = portfolio_context.get("current_regime", "unknown")
    lines.append(f"- Market Regime: {regime.upper()}")

    # Performance by regime
    regime_perf = portfolio_context.get("regime_performance", {})
    if regime_perf:
        lines.append("- Regime Performance:")
        for regime_name, stats in regime_perf.items():
            win_rate = _to_percent(stats.get("win_rate", 0))
            avg_pnl = stats.get("avg_pnl", 0)
            lines.append(
                f"  - {regime_name}: {win_rate:.1f}% WR, ${avg_pnl:.2f} avg P&L"
            )

    # Active positions
    active_pairs = portfolio_context.get("active_pairs", [])
    if active_pairs:
        lines.append(f"- Active Positions: {', '.join(active_pairs)}")
    else:
        lines.append("- Active Positions: None (fresh portfolio)")

    # Recent performance
    total_pnl = portfolio_context.get("total_pnl", 0)
    win_rate = _to_percent(portfolio_context.get("win_rate", 0))
    lines.append(f"- Recent P&L: ${total_pnl:.2f} ({win_rate:.1f}% win rate)")

    return "\n".join(lines)


def _format_selected_pairs_summary(
    selected_pairs: List[str],
    statistical_scores: Dict[str, float],
    llm_votes: Dict[str, Dict[str, any]],
) -> str:
    """Format selected pairs with brief summary."""
    lines = []

    for pair in selected_pairs:
        score = statistical_scores.get(pair, 0.0)
        vote = llm_votes.get(pair, {})
        vote_type = vote.get("vote", "N/A")
        confidence = vote.get("confidence", 0)

        lines.append(
            f"- {pair}: Score {score:.3f}, Vote: {vote_type} ({confidence}% confidence)"
        )

    return "\n".join(lines)


def _format_scores_summary(
    selected_pairs: List[str], statistical_scores: Dict[str, float]
) -> str:
    """Format statistical scores summary."""
    lines = []

    for pair in selected_pairs:
        score = statistical_scores.get(pair, 0.0)
        lines.append(f"- {pair}: {score:.3f}")

    return "\n".join(lines)


def _format_votes_summary(
    selected_pairs: List[str], llm_votes: Dict[str, Dict[str, any]]
) -> str:
    """Format LLM votes summary."""
    lines = []

    for pair in selected_pairs:
        vote = llm_votes.get(pair, {})
        vote_type = vote.get("vote", "N/A")
        confidence = vote.get("confidence", 0)
        reasoning = vote.get("reasoning", "No reasoning provided")

        lines.append(f"- {pair}: {vote_type} ({confidence}%)")
        lines.append(f"  Reasoning: {reasoning}")

    return "\n".join(lines)
