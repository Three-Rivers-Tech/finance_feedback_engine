"""
Debate mode decision manager.

Implements debate-style decision making with:
- Bullish provider argument
- Bearish provider argument
- Judge provider decision
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
from copy import deepcopy


logger = logging.getLogger(__name__)


class DebateManager:
    """
    Manages debate-style decision making with multiple providers taking different roles.
    """

    def __init__(self, debate_providers: Dict[str, str], enabled: bool = False):
        """
        Initialize debate manager.

        Args:
            debate_providers: Dictionary mapping roles to provider names
            enabled: Whether debate mode is active
        """
        self.debate_providers = debate_providers
        self.enabled = enabled

    def synthesize_debate_decision(
        self,
        bull_case: Dict[str, Any],
        bear_case: Dict[str, Any],
        judge_decision: Dict[str, Any],
        failed_debate_providers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Synthesize debate decisions from bull, bear, and judge providers.

        Args:
            bull_case: Decision from bullish provider
            bear_case: Decision from bearish provider
            judge_decision: Final decision from judge provider
            failed_debate_providers: List of provider names that failed

        Returns:
            Synthesized decision with debate metadata
        """
        # Validate all inputs
        failed_debate_providers = failed_debate_providers or []
        final_decision = deepcopy(judge_decision)

        # Add debate-specific metadata
        final_decision['debate_metadata'] = {
            'bull_case': bull_case,
            'bear_case': bear_case,
            'judge_reasoning': judge_decision.get('reasoning', ''),
            'debate_providers': self.debate_providers,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Add ensemble metadata for consistency
        failed_roles = [role for role, provider in self.debate_providers.items() if provider in failed_debate_providers]
        providers_used = [p for p in self.debate_providers.values() if p not in failed_debate_providers]
        num_total = len(self.debate_providers)
        num_active = len(providers_used)
        failure_rate = len(failed_debate_providers) / num_total if num_total > 0 else 0.0

        provider_decisions = {}
        if 'bull' not in failed_roles:
            provider_decisions[self.debate_providers['bull']] = bull_case
        if 'bear' not in failed_roles:
            provider_decisions[self.debate_providers['bear']] = bear_case
        if 'judge' not in failed_roles:
            provider_decisions[self.debate_providers['judge']] = judge_decision

        final_decision['ensemble_metadata'] = {
            'providers_used': providers_used,
            'providers_failed': failed_debate_providers,
            'num_active': num_active,
            'num_total': num_total,
            'failure_rate': failure_rate,
            'original_weights': {},
            'adjusted_weights': {},
            'weight_adjustment_applied': False,
            'voting_strategy': 'debate',
            'fallback_tier': 'none',
            'provider_decisions': provider_decisions,
            'agreement_score': 1.0,  # Judge makes final decision
            'confidence_variance': 0.0,
            'confidence_adjusted': False,
            'local_priority_applied': False,
            'local_models_used': [],
            'debate_mode': True,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(
            f"Debate decision: {final_decision['action']} "
            f"({final_decision['confidence']}%) - "
            f"Judge: {self.debate_providers['judge']}"
        )

        return final_decision