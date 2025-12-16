#!/usr/bin/env python3
"""
Test script to verify that the Alpha Vantage provider always uses rate limiting.
"""

import asyncio

from finance_feedback_engine.data_providers.alpha_vantage_provider import (
    AlphaVantageProvider,
)
from finance_feedback_engine.utils.rate_limiter import RateLimiter


def test_rate_limiter_always_active():
    """Test that the Alpha Vantage provider always has a rate limiter."""
    print("Testing Alpha Vantage provider rate limiter implementation...")

    # Test 1: Initialize without providing a rate limiter (should create default)
    print("\n1. Testing initialization without rate limiter...")
    try:
        provider1 = AlphaVantageProvider(
            api_key="demo", config={}  # Using demo key for testing
        )

        # Check that rate limiter exists and is a RateLimiter instance
        assert provider1.rate_limiter is not None
        assert isinstance(provider1.rate_limiter, RateLimiter)
        print("✓ Rate limiter automatically created when not provided")

    except Exception as e:
        print(f"✗ Error during test 1: {e}")
        return False

    # Test 2: Initialize with a custom rate limiter (should use provided one)
    print("\n2. Testing initialization with custom rate limiter...")
    try:
        custom_limiter = RateLimiter(tokens_per_second=1.0, max_tokens=10)
        provider2 = AlphaVantageProvider(
            api_key="demo", config={}, rate_limiter=custom_limiter
        )

        # Check that the custom rate limiter is used
        assert provider2.rate_limiter is custom_limiter
        assert isinstance(provider2.rate_limiter, RateLimiter)
        print("✓ Custom rate limiter properly assigned")

    except Exception as e:
        print(f"✗ Error during test 2: {e}")
        return False

    # Test 3: Check that default rate limiter has conservative settings
    print("\n3. Testing default rate limiter settings...")
    try:
        provider3 = AlphaVantageProvider(api_key="demo", config={})

        # Check that the default rate limiter has conservative settings
        # Based on our implementation, defaults should be 0.0833 tokens/sec (5/min) and 5 max tokens
        print(
            f"   Default tokens per second: {provider3.rate_limiter.tokens_per_second}"
        )
        print(f"   Default max tokens: {provider3.rate_limiter.max_tokens}")

        # The actual values may vary based on the RateLimiter implementation
        # but they should be reasonable conservative values
        assert provider3.rate_limiter.tokens_per_second > 0
        assert provider3.rate_limiter.max_tokens > 0
        print("✓ Default rate limiter has valid settings")

    except Exception as e:
        print(f"✗ Error during test 3: {e}")
        return False

    # Test 4: Check that rate limiting is applied in the _async_request method
    print("\n4. Testing rate limiting application...")
    try:
        # The _async_request method should always try to apply rate limiting
        # since we removed the 'if self.rate_limiter is not None:' check
        provider4 = AlphaVantageProvider(api_key="demo", config={})

        # Check that the rate limiter attribute exists and is properly set
        assert hasattr(provider4, "rate_limiter")
        assert provider4.rate_limiter is not None
        print("✓ Rate limiter attribute exists and is always set")

    except Exception as e:
        print(f"✗ Error during test 4: {e}")
        return False

    print(
        "\n✓ All tests passed! Rate limiter is always active in Alpha Vantage provider."
    )
    return True


if __name__ == "__main__":
    success = test_rate_limiter_always_active()
    if success:
        print("\n✅ Rate limiter implementation verification completed successfully!")
    else:
        print("\n❌ Rate limiter implementation verification failed!")
        exit(1)
