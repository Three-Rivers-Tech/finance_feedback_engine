#!/usr/bin/env python3
"""
Quick test to identify resource leak issues in the test suite.
This script tests the most problematic areas individually.
"""

import asyncio
import sys
import warnings
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Enable resource warnings
warnings.filterwarnings("error", category=ResourceWarning)


async def test_alpha_vantage_cleanup():
    """Test Alpha Vantage provider cleanup."""
    print("\n=== Testing Alpha Vantage Provider Cleanup ===")
    try:
        from finance_feedback_engine.data_providers.alpha_vantage_provider import (
            AlphaVantageProvider,
        )

        # Test 1: Basic initialization and cleanup
        print("Test 1: Basic init/cleanup...")
        provider = AlphaVantageProvider(api_key="test_key", is_backtest=True)
        await provider.close()
        print("✅ Basic cleanup passed")

        # Test 2: Context manager usage
        print("Test 2: Context manager...")
        async with AlphaVantageProvider(
            api_key="test_key", is_backtest=True
        ) as provider:
            pass  # Should auto-cleanup
        print("✅ Context manager cleanup passed")

        # Test 3: Multiple providers
        print("Test 3: Multiple providers...")
        providers = []
        for i in range(3):
            p = AlphaVantageProvider(api_key=f"test_key_{i}", is_backtest=True)
            providers.append(p)

        for p in providers:
            await p.close()
        print("✅ Multiple providers cleanup passed")

        return True

    except Exception as e:
        print(f"❌ Alpha Vantage cleanup failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_unified_provider_cleanup():
    """Test Unified Data Provider cleanup."""
    print("\n=== Testing Unified Data Provider Cleanup ===")
    try:
        from finance_feedback_engine.data_providers.unified_data_provider import (
            UnifiedDataProvider,
        )

        config = {
            "alpha_vantage_api_key": "test_av_key",
            "platform_credentials": {
                "coinbase": {"api_key": "test_cb_key", "api_secret": "test_cb_secret"},
                "oanda": {"api_key": "test_oanda_key", "account_id": "test_account"},
            },
        }

        print("Test 1: Basic init/cleanup...")
        provider = UnifiedDataProvider(config=config)

        # Check if it has alpha_vantage provider
        if hasattr(provider, "alpha_vantage") and provider.alpha_vantage:
            await provider.alpha_vantage.close()

        print("✅ Unified provider cleanup passed")
        return True

    except Exception as e:
        print(f"❌ Unified provider cleanup failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_conftest_fixtures():
    """Test conftest fixture cleanup."""
    print("\n=== Testing Conftest Fixtures ===")
    try:
        # Import conftest fixtures
        import tests.conftest as conftest

        print("Test 1: Checking fixture definitions...")
        # Check if fixtures are properly defined
        if hasattr(conftest, "alpha_vantage_provider"):
            print("  ✓ alpha_vantage_provider fixture found")
        if hasattr(conftest, "unified_data_provider"):
            print("  ✓ unified_data_provider fixture found")
        if hasattr(conftest, "configure_test_logging"):
            print("  ✓ configure_test_logging fixture found")

        print("✅ Conftest fixtures check passed")

        return True

    except Exception as e:
        print(f"❌ Conftest fixtures failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_logging_cleanup():
    """Test logging cleanup issues."""
    print("\n=== Testing Logging Cleanup ===")
    try:
        import logging

        # Get root logger
        root_logger = logging.getLogger()

        print(f"Active handlers: {len(root_logger.handlers)}")
        for i, handler in enumerate(root_logger.handlers):
            print(f"  Handler {i}: {type(handler).__name__}")
            if hasattr(handler, "baseFilename"):
                print(f"    File: {handler.baseFilename}")
            if hasattr(handler, "stream"):
                print(
                    f"    Stream closed: {handler.stream.closed if hasattr(handler.stream, 'closed') else 'N/A'}"
                )

        # Check for file handlers that might cause issues
        file_handlers = [
            h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
        ]
        if file_handlers:
            print(
                f"⚠️  Found {len(file_handlers)} file handlers that might cause issues"
            )
        else:
            print("✅ No problematic file handlers found")

        return True

    except Exception as e:
        print(f"❌ Logging check failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all resource leak tests."""
    print("=" * 60)
    print("RESOURCE LEAK DETECTION")
    print("=" * 60)

    results = []

    # Test each component
    results.append(("Alpha Vantage Cleanup", await test_alpha_vantage_cleanup()))
    results.append(("Unified Provider Cleanup", await test_unified_provider_cleanup()))
    results.append(("Conftest Fixtures", await test_conftest_fixtures()))
    results.append(("Logging Cleanup", test_logging_cleanup()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")

    print(f"\nTotal: {passed} passed, {failed} failed")

    if failed > 0:
        print("\n⚠️  Resource leaks detected! These need to be fixed.")
        return 1
    else:
        print("\n✅ No resource leaks detected!")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
