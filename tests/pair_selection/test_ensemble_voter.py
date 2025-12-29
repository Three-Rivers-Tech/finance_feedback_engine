"""
Unit tests for PairEnsembleVoter.

Tests LLM ensemble voting integration for pair evaluation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from finance_feedback_engine.pair_selection.llm.ensemble_voter import (
    PairEnsembleVoter,
    EnsembleVote,
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
        mock_ai_manager.query_ai.return_value = '''
        {
            "BTCUSD": {
                "vote": "STRONG_BUY",
                "confidence": 90,
                "reasoning": "Excellent Sortino ratio"
            }
        }
        '''

        candidates = {'BTCUSD': 0.85}
        
        votes = await voter.get_ensemble_votes(
            candidates=candidates,
            candidate_metrics={},
            market_context={},
            available_slots=1,
            enabled_providers=['local']
        )

        assert isinstance(votes, dict)
        assert 'BTCUSD' in votes

        btc_vote = votes['BTCUSD']
        assert isinstance(btc_vote, EnsembleVote)
        assert btc_vote.vote == 'STRONG_BUY'
        assert btc_vote.confidence == 90

    @pytest.mark.asyncio
    async def test_parse_provider_response_json_extraction(self, voter):
        """Test JSON extraction from markdown code blocks."""
        response_with_fence = '''```json
        {
            "BTCUSD": {"vote": "BUY", "confidence": 80, "reasoning": "Good"}
        }
        ```'''

        parsed = voter._parse_provider_response(response_with_fence, 'local')
        
        assert parsed is not None
        assert 'BTCUSD' in parsed
        assert parsed['BTCUSD']['vote'] == 'BUY'

    def test_ensemble_vote_dataclass(self):
        """Test EnsembleVote dataclass structure."""
        vote = EnsembleVote(
            vote='STRONG_BUY',
            confidence=90,
            provider_votes={'local': 'STRONG_BUY', 'qwen': 'BUY'},
            reasoning='Excellent metrics',
            vote_score=2.0
        )

        assert vote.vote == 'STRONG_BUY'
        assert vote.confidence == 90
        assert len(vote.provider_votes) == 2
        assert vote.vote_score == 2.0
