#!/usr/bin/env python3
"""Test script for Finance Feedback Engine API."""

from finance_feedback_engine import FinanceFeedbackEngine

# Configuration
config = {
    'alpha_vantage_api_key': 'demo',
    'trading_platform': 'coinbase',
    'platform_credentials': {
        'api_key': 'test_key',
        'api_secret': 'test_secret'
    },
    'decision_engine': {
        'ai_provider': 'local',
        'model_name': 'default',
        'decision_threshold': 0.7
    },
    'persistence': {
        'storage_path': 'data/decisions'
    }
}

print("=" * 60)
print("Finance Feedback Engine 2.0 - Python API Test")
print("=" * 60)

# Initialize engine
print("\n1. Initializing engine...")
engine = FinanceFeedbackEngine(config)
print("✓ Engine initialized successfully")

# Analyze an asset
print("\n2. Analyzing BTCUSD...")
decision = engine.analyze_asset('BTCUSD')
print(f"   Asset: {decision['asset_pair']}")
print(f"   Action: {decision['action']}")
print(f"   Confidence: {decision['confidence']}%")
print(f"   Reasoning: {decision['reasoning']}")
print(f"   Price: ${decision['market_data']['close']:.2f}")

# Get balance
print("\n3. Getting account balance...")
balance = engine.get_balance()
for asset, amount in balance.items():
    print(f"   {asset}: {amount:,.2f}")

# View history
print("\n4. Viewing decision history...")
history = engine.get_decision_history(limit=3)
print(f"   Found {len(history)} decisions")
for i, d in enumerate(history, 1):
    print(f"   {i}. {d['asset_pair']}: {d['action']} ({d['confidence']}%)")

print("\n" + "=" * 60)
print("✓ All tests passed successfully!")
print("=" * 60)
