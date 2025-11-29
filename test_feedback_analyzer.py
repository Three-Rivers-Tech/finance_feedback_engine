#!/usr/bin/env python3
"""
Test script for the FeedbackAnalyzer class.
"""

from finance_feedback_engine.learning.feedback_analyzer import FeedbackAnalyzer


def test_feedback_analyzer():
    """Test the FeedbackAnalyzer implementation."""
    print("Testing FeedbackAnalyzer...")
    
    # Create an instance of FeedbackAnalyzer
    analyzer = FeedbackAnalyzer()
    
    # Test loading historical decisions
    print("\n1. Testing load_historical_decisions...")
    decisions = analyzer.load_historical_decisions()
    print(f"Loaded {len(decisions)} decisions")
    if decisions:
        print(f"Sample decision keys: {list(decisions[0].keys())[:10]}")
    
    # Test loading trade outcomes
    print("\n2. Testing load_trade_outcomes...")
    outcomes = analyzer.load_trade_outcomes()
    print(f"Loaded {len(outcomes)} trade outcomes")
    if outcomes:
        print(f"Sample outcome keys: {list(outcomes[0].keys())[:10]}")
    
    # Test calculate_provider_accuracy
    print("\n3. Testing calculate_provider_accuracy...")
    provider_metrics = analyzer.calculate_provider_accuracy(window_days=30)
    print(f"Provider metrics: {provider_metrics}")
    
    # Test generate_weight_adjustments
    print("\n4. Testing generate_weight_adjustments...")
    weight_adjustments = analyzer.generate_weight_adjustments()
    print(f"Weight adjustments: {weight_adjustments}")
    
    print("\nTest completed successfully!")


if __name__ == "__main__":
    test_feedback_analyzer()