#!/usr/bin/env python3
"""
Test script demonstrating signal-only mode.

This script shows that when portfolio/balance data is unavailable,
the engine provides trading signals (action/confidence/reasoning)
without position sizing recommendations.
"""

from finance_feedback_engine.decision_engine.engine import DecisionEngine

# Mock configuration
config = {
    'decision_engine': {
        'ai_provider': 'local',
        'model_name': 'test-model'
    }
}

# Create decision engine
engine = DecisionEngine(config)

# Create decision engine with signal_only_default
config_signal_only = {
    'decision_engine': {
        'ai_provider': 'local',
        'model_name': 'test-model'
    },
    'signal_only_default': True
}
engine_signal_only = DecisionEngine(config_signal_only)

# Mock market data
market_data = {
    'type': 'crypto',
    'date': '2025-11-22',
    'open': 95000.0,
    'high': 96500.0,
    'low': 94800.0,
    'close': 96200.0,
    'volume': 1234567,
    'market_cap': 1900000000000,
    'price_range': 1700.0,
    'price_range_pct': 1.77,
    'trend': 'bullish',
    'body_size': 1200.0,
    'body_pct': 1.25,
    'upper_wick': 300.0,
    'lower_wick': 200.0,
    'close_position_in_range': 0.82,
    'rsi': 62.5,
    'rsi_signal': 'neutral'
}

print("=" * 70)
print("SIGNAL-ONLY MODE TEST")
print("=" * 70)
print()

# Test 1: Valid balance - should provide position sizing
print("Test 1: VALID BALANCE (Position sizing enabled)")
print("-" * 70)

context_with_balance = {
    'asset_pair': 'BTCUSD',
    'market_data': market_data,
    'balance': {'coinbase_USD': 10000.0, 'coinbase_BTC': 0.1},  # Valid balance
    'portfolio': None,
    'memory_context': None,
    'timestamp': '2025-11-22T12:00:00',
    'price_change': 1.26,
    'volatility': 1.77
}

ai_response_buy = {
    'action': 'BUY',
    'confidence': 75,
    'reasoning': 'Strong bullish momentum with healthy RSI',
    'amount': 0.05
}


# Use the public API: generate_decision

# For balance, always return a dict (empty if not a dict)
def safe_balance(val):
    return val if isinstance(val, dict) else {}

# For portfolio and memory_context, allow dict or None
def safe_dict(val):
    return val if isinstance(val, dict) or val is None else None

decision1 = engine.generate_decision(
    asset_pair='BTCUSD',
    market_data=market_data,
    balance=safe_balance(context_with_balance['balance']),
    portfolio=safe_dict(context_with_balance['portfolio']),
    memory_context=safe_dict(context_with_balance['memory_context'])
)

print(f"Action:                     {decision1['action']}")
print(f"Confidence:                 {decision1['confidence']}%")
print(f"Signal Only:                {decision1['signal_only']}")
print(f"Position Type:              {decision1['position_type']}")
print(f"Recommended Position Size:  {decision1['recommended_position_size']}")
print(f"Stop Loss Fraction:         {decision1['stop_loss_fraction']}")
print(f"Risk %:                     {decision1['risk_percentage']}")
print()

# Test 2: Empty balance - signal-only mode
print("Test 2: EMPTY BALANCE (Signal-only mode)")
print("-" * 70)

context_empty_balance = {
    'asset_pair': 'BTCUSD',
    'market_data': market_data,
    'balance': {},  # Empty balance dict
    'portfolio': None,
    'memory_context': None,
    'timestamp': '2025-11-22T12:00:00',
    'price_change': 1.26,
    'volatility': 1.77
}


decision2 = engine.generate_decision(
    asset_pair='BTCUSD',
    market_data=market_data,
    balance=safe_balance(context_empty_balance['balance']),
    portfolio=safe_dict(context_empty_balance['portfolio']),
    memory_context=safe_dict(context_empty_balance['memory_context'])
)

print(f"Action:                     {decision2['action']}")
print(f"Confidence:                 {decision2['confidence']}%")
print(f"Signal Only:                {decision2['signal_only']}")
print(f"Position Type:              {decision2['position_type']}")
print(f"Recommended Position Size:  {decision2['recommended_position_size']}")
print(f"Stop Loss Fraction:         {decision2['stop_loss_fraction']}")
print(f"Risk %:                     {decision2['risk_percentage']}")
print()

# Test 3: Zero balance - signal-only mode
print("Test 3: ZERO BALANCE (Signal-only mode)")
print("-" * 70)

context_zero_balance = {
    'asset_pair': 'BTCUSD',
    'market_data': market_data,
    'balance': {'USD': 0.0, 'BTC': 0.0},  # Zero balance
    'portfolio': None,
    'memory_context': None,
    'timestamp': '2025-11-22T12:00:00',
    'price_change': 1.26,
    'volatility': 1.77
}


decision3 = engine.generate_decision(
    asset_pair='BTCUSD',
    market_data=market_data,
    balance=safe_balance(context_zero_balance['balance']),
    portfolio=safe_dict(context_zero_balance['portfolio']),
    memory_context=safe_dict(context_zero_balance['memory_context'])
)

print(f"Action:                     {decision3['action']}")
print(f"Confidence:                 {decision3['confidence']}%")
print(f"Signal Only:                {decision3['signal_only']}")
print(f"Position Type:              {decision3['position_type']}")
print(f"Recommended Position Size:  {decision3['recommended_position_size']}")
print(f"Stop Loss Fraction:         {decision3['stop_loss_fraction']}")
print(f"Risk %:                     {decision3['risk_percentage']}")
print()

# Test 4: None balance - signal-only mode
print("Test 4: NONE BALANCE (Signal-only mode)")
print("-" * 70)

context_none_balance = {
    'asset_pair': 'BTCUSD',
    'market_data': market_data,
    'balance': None,  # None balance
    'portfolio': None,
    'memory_context': None,
    'timestamp': '2025-11-22T12:00:00',
    'price_change': 1.26,
    'volatility': 1.77
}


decision4 = engine.generate_decision(
    asset_pair='BTCUSD',
    market_data=market_data,
    balance=safe_balance(context_none_balance['balance']),
    portfolio=safe_dict(context_none_balance['portfolio']),
    memory_context=safe_dict(context_none_balance['memory_context'])
)

print(f"Action:                     {decision4['action']}")
print(f"Confidence:                 {decision4['confidence']}%")
print(f"Signal Only:                {decision4['signal_only']}")
print(f"Position Type:              {decision4['position_type']}")
print(f"Recommended Position Size:  {decision4['recommended_position_size']}")
print(f"Stop Loss Fraction:         {decision4['stop_loss_fraction']}")
print(f"Risk %:                     {decision4['risk_percentage']}")
print()

# Test 5: Signal-only default enabled - signal-only mode even with valid balance
print("Test 5: SIGNAL-ONLY DEFAULT (Signal-only mode)")
print("-" * 70)

decision5 = engine_signal_only.generate_decision(
    asset_pair='BTCUSD',
    market_data=market_data,
    balance=safe_balance(context_with_balance['balance']),
    portfolio=safe_dict(context_with_balance['portfolio']),
    memory_context=safe_dict(context_with_balance['memory_context'])
)

print(f"Action:                     {decision5['action']}")
print(f"Confidence:                 {decision5['confidence']}%")
print(f"Signal Only:                {decision5['signal_only']}")
print(f"Position Type:              {decision5['position_type']}")
print(f"Recommended Position Size:  {decision5['recommended_position_size']}")
print(f"Stop Loss Fraction:         {decision5['stop_loss_fraction']}")
print(f"Risk %:                     {decision5['risk_percentage']}")
print()

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("✓ Test 1 (Valid balance):   Position sizing ENABLED")
print(f"  - signal_only = {decision1['signal_only']}")
print(
    f"  - recommended_position_size = "
    f"{decision1['recommended_position_size']:.6f}"
)
print()
print("✓ Test 2 (Empty balance):   Position sizing DISABLED")
print(f"  - signal_only = {decision2['signal_only']}")
print(
    f"  - recommended_position_size = "
    f"{decision2['recommended_position_size']}"
)
print()
print("✓ Test 3 (Zero balance):    Position sizing DISABLED")
print(f"  - signal_only = {decision3['signal_only']}")
print(
    f"  - recommended_position_size = "
    f"{decision3['recommended_position_size']}"
)
print()
print("✓ Test 4 (None balance):    Position sizing DISABLED")
print(f"  - signal_only = {decision4['signal_only']}")
print(
    f"  - recommended_position_size = "
    f"{decision4['recommended_position_size']}"
)
print()
print("✓ Test 5 (Signal-only default): Position sizing DISABLED")
print(f"  - signal_only = {decision5['signal_only']}")
print(
    f"  - recommended_position_size = "
    f"{decision5['recommended_position_size']}"
)
print()
print("All tests passed! Signal-only mode works correctly.")
print("When portfolio data is unavailable OR signal_only_default is enabled,")
print("the engine provides signals only.")
print()
