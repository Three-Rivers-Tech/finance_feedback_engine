"""
Ensemble Voter for Pair Selection.

Integrates with existing EnsembleDecisionManager to query LLM providers
and aggregate their votes on trading pair candidates.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .prompt_templates import (
    build_pair_evaluation_prompt,
    build_pair_description_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class EnsembleVote:
    """
    Ensemble vote result for a trading pair.

    Attributes:
        vote: Categorical vote (STRONG_BUY, BUY, NEUTRAL, AVOID)
        confidence: Confidence level 0-100
        provider_votes: Individual votes from each provider {provider: vote}
        reasoning: Aggregated reasoning from providers
        vote_score: Numeric score for ranking (-1 to 2)
    """
    vote: str
    confidence: int
    provider_votes: Dict[str, str]
    reasoning: str
    vote_score: float


class PairEnsembleVoter:
    """
    Integrate with EnsembleDecisionManager for pair voting.

    Reuses existing ensemble infrastructure:
    - Weighted voting based on provider performance
    - Thompson Sampling weight optimization
    - Multi-provider consensus building
    """

    # Vote to numeric score mapping
    VOTE_SCORES = {
        "STRONG_BUY": 2.0,
        "BUY": 1.0,
        "NEUTRAL": 0.0,
        "AVOID": -1.0
    }

    def __init__(self, ai_decision_manager):
        """
        Initialize Pair Ensemble Voter.

        Args:
            ai_decision_manager: AIDecisionManager instance from decision engine
                                (has query_ai method for provider interaction)
        """
        self.ai_manager = ai_decision_manager
        logger.info("PairEnsembleVoter initialized")

    async def get_ensemble_votes(
        self,
        candidates: Dict[str, float],
        candidate_metrics: Dict[str, Dict[str, any]],
        market_context: Dict[str, Any],
        available_slots: int,
        enabled_providers: Optional[List[str]] = None
    ) -> Dict[str, EnsembleVote]:
        """
        Query LLM ensemble for pair evaluation votes.

        Args:
            candidates: Dict mapping pair to composite statistical score
            candidate_metrics: Detailed metrics for each candidate
            market_context: Portfolio and market context
            available_slots: Number of pairs to select
            enabled_providers: List of providers to query (None = all enabled)

        Returns:
            Dict mapping pair to EnsembleVote with aggregated consensus
        """
        logger.info(
            f"Querying ensemble for {len(candidates)} candidates "
            f"(selecting {available_slots})"
        )

        # Build evaluation prompt
        prompt = build_pair_evaluation_prompt(
            candidates=candidates,
            candidate_metrics=candidate_metrics,
            portfolio_context=market_context,
            available_slots=available_slots
        )

        # Query providers
        provider_responses = await self._query_providers(
            prompt=prompt,
            enabled_providers=enabled_providers
        )

        if not provider_responses:
            logger.warning("No provider responses received, using neutral votes")
            return self._generate_neutral_votes(list(candidates.keys()))

        # Aggregate votes across providers
        aggregated_votes = self._aggregate_provider_votes(
            provider_responses=provider_responses,
            candidate_pairs=list(candidates.keys())
        )

        logger.info(
            f"Ensemble voting complete: {len(aggregated_votes)} pairs evaluated"
        )

        return aggregated_votes

    async def generate_selection_reasoning(
        self,
        selected_pairs: List[str],
        statistical_scores: Dict[str, float],
        llm_votes: Dict[str, EnsembleVote],
        enabled_providers: Optional[List[str]] = None
    ) -> str:
        """
        Generate human-readable reasoning for pair selections.

        Args:
            selected_pairs: List of selected pair names
            statistical_scores: Composite scores for selected pairs
            llm_votes: LLM votes for selected pairs
            enabled_providers: List of providers to use (None = first available)

        Returns:
            Concise paragraph explaining the selections
        """
        logger.info(f"Generating selection reasoning for {len(selected_pairs)} pairs")

        # Build description prompt
        llm_votes_dict = {
            pair: {
                'vote': vote.vote,
                'confidence': vote.confidence,
                'reasoning': vote.reasoning
            }
            for pair, vote in llm_votes.items()
        }

        prompt = build_pair_description_prompt(
            selected_pairs=selected_pairs,
            statistical_scores=statistical_scores,
            llm_votes=llm_votes_dict
        )

        # Query single provider for description (use first enabled)
        if enabled_providers is None:
            enabled_providers = self._get_enabled_providers()

        if not enabled_providers:
            return self._generate_fallback_description(
                selected_pairs,
                statistical_scores
            )

        # Use first available provider
        provider = enabled_providers[0]

        try:
            response = await self._query_single_provider(
                provider=provider,
                prompt=prompt
            )

            # Extract text from response
            reasoning = self._extract_text_from_response(response)

            logger.info(
                f"Generated selection reasoning ({len(reasoning)} chars) "
                f"using provider: {provider}"
            )

            return reasoning

        except Exception as e:
            logger.warning(
                f"Failed to generate reasoning with {provider}: {e}. "
                "Using fallback."
            )
            return self._generate_fallback_description(
                selected_pairs,
                statistical_scores
            )

    async def _query_providers(
        self,
        prompt: str,
        enabled_providers: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Query multiple LLM providers in parallel.

        Args:
            prompt: Evaluation prompt
            enabled_providers: Providers to query (None = all enabled)

        Returns:
            Dict mapping provider name to parsed response
        """
        if enabled_providers is None:
            enabled_providers = self._get_enabled_providers()

        if not enabled_providers:
            logger.warning("No enabled providers found")
            return {}

        provider_responses = {}

        for provider in enabled_providers:
            try:
                response = await self._query_single_provider(
                    provider=provider,
                    prompt=prompt
                )

                # Parse JSON response
                parsed = self._parse_provider_response(response, provider)

                if parsed:
                    provider_responses[provider] = parsed
                    logger.debug(
                        f"Provider '{provider}' evaluated "
                        f"{len(parsed)} pairs"
                    )

            except Exception as e:
                logger.warning(
                    f"Provider '{provider}' failed pair evaluation: {e}"
                )

        return provider_responses

    async def _query_single_provider(
        self,
        provider: str,
        prompt: str
    ) -> str:
        """
        Query a single LLM provider.

        Args:
            provider: Provider name ('local', 'qwen', 'gemini', etc.)
            prompt: Prompt text

        Returns:
            Raw response text from provider
        """
        # Use AI decision manager's query_ai method
        # This handles the provider-specific API calls
        response = await self.ai_manager.query_ai(
            prompt=prompt,
            provider=provider
        )

        return response

    def _parse_provider_response(
        self,
        response: str,
        provider: str
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        Parse JSON response from provider.

        Expected format:
        {
            "BTCUSD": {
                "vote": "STRONG_BUY",
                "confidence": 85,
                "reasoning": "..."
            },
            ...
        }

        Args:
            response: Raw response text
            provider: Provider name (for logging)

        Returns:
            Parsed dict or None if parsing fails
        """
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            json_str = response.strip()

            # Remove markdown code fences if present
            if json_str.startswith("```json"):
                json_str = json_str[7:]  # Remove ```json
            if json_str.startswith("```"):
                json_str = json_str[3:]  # Remove ```
            if json_str.endswith("```"):
                json_str = json_str[:-3]  # Remove trailing ```

            json_str = json_str.strip()

            # Parse JSON
            parsed = json.loads(json_str)

            return parsed

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from provider '{provider}': {e}\n"
                f"Response preview: {response[:200]}..."
            )
            return None

    def _aggregate_provider_votes(
        self,
        provider_responses: Dict[str, Dict[str, Any]],
        candidate_pairs: List[str]
    ) -> Dict[str, EnsembleVote]:
        """
        Aggregate votes across providers using weighted voting.

        Args:
            provider_responses: {provider: {pair: {vote, confidence, reasoning}}}
            candidate_pairs: List of all candidate pairs

        Returns:
            {pair: EnsembleVote}
        """
        aggregated = {}

        for pair in candidate_pairs:
            # Collect votes from providers
            votes = []
            confidences = []
            reasonings = []
            provider_votes = {}

            for provider, response in provider_responses.items():
                pair_eval = response.get(pair, {})

                if not pair_eval:
                    continue

                vote = pair_eval.get('vote', 'NEUTRAL')
                confidence = pair_eval.get('confidence', 50)
                reasoning = pair_eval.get('reasoning', '')

                votes.append(vote)
                confidences.append(confidence)
                reasonings.append(f"[{provider}] {reasoning}")
                provider_votes[provider] = vote

            if not votes:
                # No votes for this pair - use neutral
                aggregated[pair] = EnsembleVote(
                    vote='NEUTRAL',
                    confidence=50,
                    provider_votes={},
                    reasoning='No provider votes received',
                    vote_score=0.0
                )
                continue

            # Calculate weighted vote scores
            vote_scores = []
            for vote, conf in zip(votes, confidences):
                score = self.VOTE_SCORES.get(vote, 0.0)
                # Weight by confidence (0-100 → 0-1)
                weighted_score = score * (conf / 100.0)
                vote_scores.append(weighted_score)

            # Average weighted score
            avg_score = sum(vote_scores) / len(vote_scores)

            # Map score back to categorical vote
            final_vote = self._score_to_vote(avg_score)

            # Average confidence
            final_confidence = int(sum(confidences) / len(confidences))

            # Combine reasonings
            combined_reasoning = " | ".join(reasonings[:3])  # Limit to 3

            aggregated[pair] = EnsembleVote(
                vote=final_vote,
                confidence=final_confidence,
                provider_votes=provider_votes,
                reasoning=combined_reasoning,
                vote_score=avg_score
            )

        return aggregated

    def _score_to_vote(self, score: float) -> str:
        """Map numeric score to categorical vote."""
        if score >= 1.5:
            return "STRONG_BUY"
        elif score >= 0.5:
            return "BUY"
        elif score >= -0.5:
            return "NEUTRAL"
        else:
            return "AVOID"

    def _get_enabled_providers(self) -> List[str]:
        """
        Get list of enabled providers from AI manager.

        Queries the AI manager for the list of currently enabled providers.
        Falls back to a default list if the manager doesn't have the attribute.

        Returns:
            List of enabled provider names (e.g., ['local', 'gemini', 'qwen'])
        """
        # Try to query AI manager for enabled providers
        if self.ai_manager and hasattr(self.ai_manager, 'enabled_providers'):
            providers = self.ai_manager.enabled_providers
            if providers and isinstance(providers, list):
                logger.debug(f"Using enabled providers from AI manager: {providers}")
                return providers

        # Fallback to common providers if not available
        logger.debug("AI manager doesn't have enabled_providers, using fallback list")
        return ['local', 'qwen', 'gemini', 'cli']

    def _generate_neutral_votes(
        self,
        candidate_pairs: List[str]
    ) -> Dict[str, EnsembleVote]:
        """Generate neutral votes as fallback."""
        return {
            pair: EnsembleVote(
                vote='NEUTRAL',
                confidence=50,
                provider_votes={},
                reasoning='No LLM responses available',
                vote_score=0.0
            )
            for pair in candidate_pairs
        }

    def _generate_fallback_description(
        self,
        selected_pairs: List[str],
        statistical_scores: Dict[str, float]
    ) -> str:
        """Generate simple fallback description without LLM."""
        avg_score = sum(
            statistical_scores.get(pair, 0.0)
            for pair in selected_pairs
        ) / len(selected_pairs) if selected_pairs else 0.0

        pairs_str = ", ".join(selected_pairs)

        return (
            f"Selected {len(selected_pairs)} pairs ({pairs_str}) "
            f"with average statistical score of {avg_score:.3f}. "
            f"Selections based on quantitative metrics including Sortino ratio, "
            f"portfolio correlation, and GARCH volatility forecasting."
        )

    def _extract_text_from_response(self, response: str) -> str:
        """Extract clean text from LLM response."""
        # Remove markdown formatting if present
        text = response.strip()

        # Remove code fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines if they're code fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        return text
