#!/usr/bin/env python3
"""
Quick Start Example for Finance Feedback Engine 2.0

This example demonstrates the basic usage of the Finance Feedback Engine.
"""

import os

from finance_feedback_engine import FinanceFeedbackEngine


def main():
    print("=" * 70)
    print("Finance Feedback Engine 2.0 - Quick Start Example")
    print("=" * 70)

    # Example configuration
    # In production, load from config file or environment variables
    config = {
        "alpha_vantage_api_key": os.getenv("ALPHA_VANTAGE_API_KEY", "demo"),
        "trading_platform": "coinbase",
        "platform_credentials": {
            "api_key": os.getenv("COINBASE_API_KEY", "demo_key"),
            "api_secret": os.getenv("COINBASE_API_SECRET", "demo_secret"),
        },
        "decision_engine": {"ai_provider": "local", "decision_threshold": 0.7},
        "persistence": {"storage_path": "data/decisions"},
    }

    # Initialize the engine
    print("\n1. Initializing Finance Feedback Engine...")
    engine = FinanceFeedbackEngine(config)
    print("   ✓ Engine initialized successfully\n")

    # Example 1: Analyze Bitcoin
    print("2. Analyzing BTCUSD (Bitcoin)...")
    decision = engine.analyze_asset("BTCUSD")
    print(f"   Asset: {decision['asset_pair']}")
    print(f"   Recommendation: {decision['action']}")
    print(f"   Confidence: {decision['confidence']}%")
    print(f"   Reasoning: {decision['reasoning']}")
    print(f"   Current Price: ${decision['market_data']['close']:,.2f}\n")

    # Example 2: Check account balance
    print("3. Checking account balance...")
    balance = engine.get_balance()
    for asset, amount in balance.items():
        print(f"   {asset}: {amount:,.2f}")
    print()

    # Example 3: View decision history
    print("4. Viewing recent decision history...")
    history = engine.get_decision_history(limit=3)
    print(f"   Found {len(history)} recent decisions:")
    for i, d in enumerate(history, 1):
        timestamp = d["timestamp"].split("T")[1][:8]
        print(
            f"   {i}. [{timestamp}] {d['asset_pair']}: {d['action']} ({d['confidence']}%)"
        )
    print()

    # Example 4: Analyze a forex pair
    print("5. Analyzing EURUSD (Forex)...")
    decision = engine.analyze_asset("EURUSD")
    print(f"   Asset: {decision['asset_pair']}")
    print(f"   Recommendation: {decision['action']}")
    print(f"   Confidence: {decision['confidence']}%")
    print(f"   Current Price: ${decision['market_data']['close']:.4f}\n")

    print("=" * 70)
    print("✓ Quick Start Complete!")
    print("=" * 70)
    print("\nNext Steps:")
    print("  • Set up your Alpha Vantage API key")
    print("  • Configure your trading platform credentials")
    print("  • Customize the decision engine settings")
    print("  • Run: python main.py --help for CLI commands")
    print("  • Read USAGE.md for detailed documentation")
    print()


if __name__ == "__main__":
    main()
