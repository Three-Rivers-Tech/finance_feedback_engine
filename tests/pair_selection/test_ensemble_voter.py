"""
Unit tests for PairEnsembleVoter.

Tests LLM ensemble voting integration for pair evaluation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from finance_feedback_engine.pair_selection.llm.ensemble_voter import (
    EnsembleVote,
    PairEnsembleVoter,
)


class TestPairEnsembleVoter:
    """Test suite for PairEnsembleVoter."""

    @pytest.fixture
    def mock_ai_manager(self):
        """Create mock AIDecisionManager."""
        manager = MagicMock()
        manager.query_ai = AsyncMock()
        return manager

    @pytest.fixture
    def voter(self, mock_ai_manager):
        """Create PairEnsembleVoter instance."""
        return PairEnsembleVoter(ai_decision_manager=mock_ai_manager)

    @pytest.mark.asyncio
    async def test_get_ensemble_votes_single_provider(self, voter, mock_ai_manager):
        """Test ensemble voting with single provider."""
        mock_ai_manager.query_ai.return_value = """
        {
            "BTCUSD": {
                "vote": "STRONG_BUY",
                "confidence": 90,
                "reasoning": "Excellent Sortino ratio"
            }
        }
        """

        candidates = {"BTCUSD": 0.85}

        votes = await voter.get_ensemble_votes(
            candidates=candidates,
            candidate_metrics={},
            market_context={},
            available_slots=1,
            enabled_providers=["local"],
        )

        assert isinstance(votes, dict)
        assert "BTCUSD" in votes

        btc_vote = votes["BTCUSD"]
        assert isinstance(btc_vote, EnsembleVote)
        assert btc_vote.vote == "STRONG_BUY"
        assert btc_vote.confidence == 90

    @pytest.mark.asyncio
    async def test_parse_provider_response_json_extraction(self, voter):
        """Test JSON extraction from markdown code blocks."""
        response_with_fence = """```json
        {
            "BTCUSD": {"vote": "BUY", "confidence": 80, "reasoning": "Good"}
        }
        ```"""

        parsed = voter._parse_provider_response(response_with_fence, "local")

        assert parsed is not None
        assert "BTCUSD" in parsed
        assert parsed["BTCUSD"]["vote"] == "BUY"

    def test_ensemble_vote_dataclass(self):
        """Test EnsembleVote dataclass structure."""
        vote = EnsembleVote(
            vote="STRONG_BUY",
            confidence=90,
            provider_votes={"local": "STRONG_BUY", "qwen": "BUY"},
            reasoning="Excellent metrics",
            vote_score=2.0,
        )

        assert vote.vote == "STRONG_BUY"
        assert vote.confidence == 90
        assert len(vote.provider_votes) == 2
        assert vote.vote_score == 2.0

    def test_score_to_vote_with_default_thresholds(self, mock_ai_manager):
        """Test _score_to_vote uses DEFAULT_VOTE_THRESHOLDS when config not provided."""
        voter = PairEnsembleVoter(ai_decision_manager=mock_ai_manager)

        # Test various scores with default thresholds
        assert voter._score_to_vote(2.0) == "STRONG_BUY"
        assert voter._score_to_vote(1.5) == "STRONG_BUY"
        assert voter._score_to_vote(1.0) == "BUY"
        assert voter._score_to_vote(0.5) == "BUY"
        assert voter._score_to_vote(0.0) == "NEUTRAL"
        assert voter._score_to_vote(-0.5) == "NEUTRAL"
        assert voter._score_to_vote(-1.0) == "AVOID"

    def test_score_to_vote_with_custom_config(self, mock_ai_manager):
        """Test _score_to_vote uses custom thresholds from provided config."""
        custom_config = {
            "ensemble": {
                "vote_thresholds": {
                    "strong_buy": 2.0,
                    "buy": 1.0,
                    "neutral": 0.0,
                }
            }
        }
        voter = PairEnsembleVoter(ai_decision_manager=mock_ai_manager, config=custom_config)

        # Test with custom thresholds
        assert voter._score_to_vote(2.5) == "STRONG_BUY"
        assert voter._score_to_vote(2.0) == "STRONG_BUY"
        assert voter._score_to_vote(1.5) == "BUY"
        assert voter._score_to_vote(1.0) == "BUY"
        assert voter._score_to_vote(0.5) == "NEUTRAL"
        assert voter._score_to_vote(0.0) == "NEUTRAL"
        assert voter._score_to_vote(-0.5) == "AVOID"

    def test_config_fallback_from_ai_manager(self, mock_ai_manager):
        """Test config is loaded from ai_manager if available."""
        ai_manager_config = {
            "ensemble": {
                "vote_thresholds": {
                    "strong_buy": 1.75,
                    "buy": 0.75,
                    "neutral": -0.25,
                }
            }
        }
        mock_ai_manager.config = ai_manager_config

        voter = PairEnsembleVoter(ai_decision_manager=mock_ai_manager)

        # Verify config was loaded from ai_manager
        assert voter.config == ai_manager_config
        assert voter._score_to_vote(1.75) == "STRONG_BUY"
        assert voter._score_to_vote(0.75) == "BUY"

