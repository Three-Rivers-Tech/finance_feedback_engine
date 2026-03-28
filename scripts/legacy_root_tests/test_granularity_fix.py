#!/usr/bin/env python3
"""Test script to verify 4h→6h granularity mapping fix."""

from finance_feedback_engine.data_providers.coinbase_data import CoinbaseDataProvider

def test_granularity_mapping():
    """Test that 4h granularity is correctly mapped to 6h (21600s)."""
    provider = CoinbaseDataProvider()
    
    # Test 4h mapping
    assert provider.GRANULARITIES["4h"] == 21600, "4h should map to 21600s (6h)"
    assert provider.GRANULARITIES["6h"] == 21600, "6h should map to 21600s"
    assert provider.GRANULARITIES["FOUR_HOUR"] == 21600, "FOUR_HOUR should map to 21600s"
    assert provider.GRANULARITIES["SIX_HOUR"] == 21600, "SIX_HOUR should map to 21600s"
    
    # Test enum mapping
    assert provider.GRANULARITY_ENUMS["4h"] == "SIX_HOUR", "4h enum should map to SIX_HOUR"
    assert provider.GRANULARITY_ENUMS["6h"] == "SIX_HOUR", "6h enum should map to SIX_HOUR"
    assert provider.GRANULARITY_ENUMS["FOUR_HOUR"] == "SIX_HOUR", "FOUR_HOUR enum should map to SIX_HOUR"
    assert provider.GRANULARITY_ENUMS["SIX_HOUR"] == "SIX_HOUR", "SIX_HOUR enum should map to SIX_HOUR"
    
    # Test that Coinbase API will receive correct granularity name
    granularity_seconds = provider.GRANULARITIES["4h"]
    assert granularity_seconds == 21600, f"Expected 21600, got {granularity_seconds}"
    
    print("✅ All granularity mapping tests passed!")
    print("\n📋 Summary:")
    print("- 4h granularity now maps to 21600 seconds (6h)")
    print("- Coinbase API will receive 'SIX_HOUR' instead of 'FOUR_HOUR' or '14400'")
    print("- This fixes the 'Unsupported granularity: 4h' error")
    print("\n🔄 Next steps:")
    print("1. Rebuild Docker image: docker build -t finance-feedback-engine:latest .")
    print("2. Restart container: docker restart ffe-backend")
    print("3. Monitor logs for successful candle fetches")

if __name__ == "__main__":
    test_granularity_mapping()
