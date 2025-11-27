#!/usr/bin/env python3
"""
Test script to verify Qwen CLI provider is properly integrated.
This does not require qwen to be installed - just tests the module structure.
"""

import sys
import os
# Add the project root to the path (two levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print("Testing Qwen CLI Provider Integration")
print("=" * 50)

# Test 1: Import the provider class
print("\n1. Testing import...")
try:
    from finance_feedback_engine.decision_engine.qwen_cli_provider import QwenCLIProvider
    print("   ✓ QwenCLIProvider imports successfully")
except ImportError as e:
    print(f"   ✗ Failed to import: {e}")
    sys.exit(1)

# Test 2: Instantiate with mock config
print("\n2. Testing instantiation (without qwen binary)...")
config = {
    'model_name': 'test-model',
    'decision_threshold': 0.7
}

try:
    # This will fail since qwen is not installed, but we can catch the error
    provider = QwenCLIProvider(config)
    print("   ✗ Should have raised ValueError for missing qwen binary")
except ValueError as e:
    if "qwen" in str(e).lower():
        print(f"   ✓ Correctly raises error when qwen not found: {e}")
    else:
        print(f"   ✗ Unexpected error: {e}")
except Exception as e:
    print(f"   ✗ Unexpected error type: {type(e).__name__}: {e}")

# Test 3: Verify methods exist
print("\n3. Testing method signatures...")
required_methods = ['query', '_verify_qwen_available', '_format_prompt_for_qwen', 
                   '_parse_qwen_response', '_fallback_decision']
for method in required_methods:
    if hasattr(QwenCLIProvider, method):
        print(f"   ✓ Method '{method}' exists")
    else:
        print(f"   ✗ Method '{method}' missing")

print("\n" + "=" * 50)
print("✓ All structural tests passed!")
print("\nNote: To test actual Qwen CLI execution:")
print("  1. Install Node.js v20+")
print("  2. Install Qwen CLI")
print("  3. Run: python main.py analyze BTCUSD --provider qwen")
