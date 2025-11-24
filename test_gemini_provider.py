#!/usr/bin/env python3
"""Test Gemini CLI provider integration."""

import sys
from finance_feedback_engine.decision_engine.gemini_cli_provider import GeminiCLIProvider

def test_gemini_provider():
    """Test Gemini CLI provider initialization and basic query."""
    print("🔧 Testing Gemini CLI Provider Integration")
    print("=" * 60)
    
    # Test 1: Check if provider can be instantiated
    print("\n1. Initializing Gemini CLI provider...")
    try:
        provider = GeminiCLIProvider({'model_name': 'gemini-2.5-flash'})
        print("   ✅ Provider initialized successfully")
    except ValueError as e:
        print(f"   ⚠️  Provider initialization failed: {e}")
        print("\n   To install Gemini CLI:")
        print("   npm install -g @google/gemini-cli")
        print("\n   Authentication options:")
        print("   1. OAuth: Run 'gemini' and select 'Login with Google'")
        print("   2. API Key: export GEMINI_API_KEY='your-key'")
        print("      Get key from: https://aistudio.google.com/apikey")
        return False
    
    # Test 2: Test query with sample prompt
    print("\n2. Testing sample trading decision query...")
    prompt = """
    Analyze BTCUSD trading opportunity:
    - Current price: $45,000
    - 24h change: +5%
    - Volume: High
    
    Provide trading recommendation in JSON format:
    {"action": "BUY|SELL|HOLD", "confidence": 0-100, "reasoning": "brief explanation", "amount": 0}
    """
    
    try:
        result = provider.query(prompt)
        print(f"   ✅ Query successful")
        print(f"\n   Response:")
        print(f"   - Action: {result.get('action', 'N/A')}")
        print(f"   - Confidence: {result.get('confidence', 'N/A')}%")
        print(f"   - Reasoning: {result.get('reasoning', 'N/A')}")
        print(f"   - Amount: {result.get('amount', 'N/A')}")
        return True
    except Exception as e:
        print(f"   ❌ Query failed: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Finance Feedback Engine - Gemini CLI Provider Test")
    print("=" * 60)
    
    success = test_gemini_provider()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All tests passed!")
        print("\nYou can now use Gemini CLI provider:")
        print("  python main.py analyze BTCUSD --provider gemini")
    else:
        print("⚠️  Some tests failed - see output above")
        print("\nNext steps:")
        print("  1. Install: npm install -g @google/gemini-cli")
        print("  2. Authenticate with OAuth or API key")
        print("  3. Re-run this test")
    print("=" * 60 + "\n")
    
    sys.exit(0 if success else 1)
