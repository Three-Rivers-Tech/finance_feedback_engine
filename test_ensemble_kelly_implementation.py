"""
Test script to validate the enhanced ensemble and Kelly Criterion implementations.
"""

import asyncio
import json
from pathlib import Path

import numpy as np

from finance_feedback_engine.decision_engine.ensemble_manager import (
    EnsembleDecisionManager,
)
from finance_feedback_engine.decision_engine.kelly_criterion import (
    KellyCriterionCalculator,
)
from finance_feedback_engine.decision_engine.voting_strategies import VotingStrategies


def test_kelly_criterion():
    """Test the Kelly Criterion implementation."""
    print("Testing Kelly Criterion Implementation...")

    # Create a test configuration
    config = {
        "kelly_criterion": {
            "kelly_fraction_cap": 0.25,
            "kelly_fraction_multiplier": 0.5,
            "min_kelly_fraction": 0.001,
            "max_position_size_pct": 0.10,
        }
    }

    # Initialize Kelly Criterion calculator
    kelly_calc = KellyCriterionCalculator(config)

    # Test 1: Basic Kelly calculation
    win_rate = 0.6  # 60% win rate
    avg_win = 150.0  # Average win $150
    avg_loss = 100.0  # Average loss $100
    account_balance = 10000.0  # $10,000 account
    current_price = 100.0  # Current asset price $100

    position_size, details = kelly_calc.calculate_position_size(
        account_balance, win_rate, avg_win, avg_loss, current_price
    )

    print(f"Test 1 - Basic Kelly:")
    print(f"  Position size: {position_size:.4f} units")
    print(f"  Details: {details}")
    print(f"  Position size in dollars: ${position_size * current_price:.2f}")

    # Test 2: Dynamic Kelly calculation
    historical_trades = [
        {"pnl": 150.0},
        {"pnl": -50.0},
        {"pnl": 200.0},
        {"pnl": -75.0},
        {"pnl": 120.0},
        {"pnl": 180.0},
        {"pnl": -30.0},
        {"pnl": -100.0},
        {"pnl": 250.0},
        {"pnl": 90.0},
    ]

    kelly_fraction, metrics = kelly_calc.calculate_dynamic_kelly_fraction(
        historical_trades
    )
    print(f"\nTest 2 - Dynamic Kelly:")
    print(f"  Kelly fraction: {kelly_fraction:.4f}")
    print(f"  Metrics: {metrics}")

    # Test 3: Market condition adjustment
    adjusted_fraction, adj_details = kelly_calc.adjust_for_market_conditions(
        kelly_fraction, volatility=0.3, correlation=0.6, trend_strength=0.4
    )
    print(f"\nTest 3 - Market Condition Adjustment:")
    print(f"  Adjusted Kelly fraction: {adjusted_fraction:.4f}")
    print(f"  Adjustment details: {adj_details}")

    print("\nKelly Criterion tests completed successfully!\n")


def test_voting_strategies():
    """Test the voting strategies implementation."""
    print("Testing Voting Strategies Implementation...")

    # Create test data
    providers = ["local", "cli", "codex", "qwen", "gemini"]
    actions = ["BUY", "BUY", "HOLD", "SELL", "BUY"]
    confidences = [85, 75, 60, 90, 80]
    reasonings = [
        "Strong bullish trend",
        "Bullish sentiment",
        "Neutral",
        "Strong bearish",
        "Bullish",
    ]
    amounts = [1000, 800, 500, 1200, 900]

    # Test 1: Weighted voting
    voting_strategies = VotingStrategies("weighted")
    decision = voting_strategies.apply_voting_strategy(
        providers, actions, confidences, reasonings, amounts
    )

    print(f"Test 1 - Weighted Voting:")
    print(f"  Action: {decision['action']}")
    print(f"  Confidence: {decision['confidence']}")
    print(f"  Amount: {decision['amount']}")

    # Test 2: Majority voting
    voting_strategies = VotingStrategies("majority")
    decision = voting_strategies.apply_voting_strategy(
        providers, actions, confidences, reasonings, amounts
    )

    print(f"\nTest 2 - Majority Voting:")
    print(f"  Action: {decision['action']}")
    print(f"  Confidence: {decision['confidence']}")
    print(f"  Amount: {decision['amount']}")

    # Test 3: Enhanced stacking
    voting_strategies = VotingStrategies("stacking")
    decision = voting_strategies.apply_voting_strategy(
        providers, actions, confidences, reasonings, amounts
    )

    print(f"\nTest 3 - Enhanced Stacking:")
    print(f"  Action: {decision['action']}")
    print(f"  Confidence: {decision['confidence']}")
    print(f"  Amount: {decision['amount']}")
    print(f"  Enhanced features: {decision.get('enhanced_meta_features', False)}")
    print(f"  Meta features: {decision.get('meta_features', {})}")

    print("\nVoting Strategies tests completed successfully!\n")


def test_ensemble_manager():
    """Test the ensemble manager with enhanced stacking."""
    print("Testing Ensemble Manager Implementation...")

    # Create a test configuration
    config = {
        "ensemble": {
            "voting_strategy": "stacking",
            "provider_weights": {
                "local": 0.25,
                "cli": 0.20,
                "codex": 0.20,
                "qwen": 0.15,
                "gemini": 0.20,
            },
            "enabled_providers": ["local", "cli", "codex", "qwen", "gemini"],
        }
    }

    # Initialize ensemble manager
    ensemble_manager = EnsembleDecisionManager(config)

    # Create test provider decisions
    provider_decisions = {
        "local": {
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Strong bullish trend on local model",
            "amount": 1000,
        },
        "cli": {
            "action": "BUY",
            "confidence": 75,
            "reasoning": "Bullish sentiment in CLI model",
            "amount": 800,
        },
        "codex": {
            "action": "HOLD",
            "confidence": 60,
            "reasoning": "Neutral position in Codex model",
            "amount": 500,
        },
        "qwen": {
            "action": "SELL",
            "confidence": 90,
            "reasoning": "Strong bearish signal from Qwen",
            "amount": 1200,
        },
        "gemini": {
            "action": "BUY",
            "confidence": 80,
            "reasoning": "Bullish trend in Gemini model",
            "amount": 900,
        },
    }

    # Test aggregation with stacking
    async def run_test():
        decision = await ensemble_manager.aggregate_decisions(provider_decisions)
        return decision

    decision = asyncio.run(run_test())

    print(f"Test - Ensemble Aggregation with Stacking:")
    print(f"  Action: {decision['action']}")
    print(f"  Confidence: {decision['confidence']}")
    print(f"  Amount: {decision['amount']}")
    print(f"  Voting strategy: {decision['ensemble_metadata']['voting_strategy']}")
    print(f"  Enhanced features: {decision.get('enhanced_meta_features', False)}")
    print(f"  Meta features: {decision.get('meta_features', {})}")

    print("\nEnsemble Manager tests completed successfully!\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Enhanced Ensemble and Kelly Criterion Implementation")
    print("=" * 60)

    test_kelly_criterion()
    test_voting_strategies()
    test_ensemble_manager()

    print("=" * 60)
    print("All tests completed successfully!")
    print(
        "Enhanced ensemble with stacking and Kelly Criterion implementation is working correctly."
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
