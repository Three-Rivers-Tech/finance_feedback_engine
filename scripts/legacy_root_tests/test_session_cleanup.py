#!/usr/bin/env python3
"""Test script to verify aiohttp session cleanup (THR-206)."""

import asyncio
import gc
import os
import sys
import warnings
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

# Configure environment
os.environ["ENVIRONMENT"] = "test"
os.environ["ALPHA_VANTAGE_API_KEY"] = os.environ.get("ALPHA_VANTAGE_API_KEY", "test_key")


async def test_session_cleanup():
    """Test that engine properly cleans up aiohttp sessions."""
    from finance_feedback_engine.core import FinanceFeedbackEngine
    from finance_feedback_engine.utils.config_loader import load_config
    
    print("🧪 Testing session cleanup...")
    
    # Load config
    config = load_config()
    config["is_backtest"] = True  # Disable live trading
    config["alpha_vantage_api_key"] = "test_key"
    
    # Track warnings
    warnings.simplefilter("always", ResourceWarning)
    warning_count = 0
    
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        nonlocal warning_count
        if "unclosed" in str(message).lower() or "session" in str(message).lower():
            warning_count += 1
            print(f"⚠️  Warning: {message}")
    
    warnings.showwarning = warning_handler
    
    # Test 1: Engine with manual close
    print("\n📋 Test 1: Manual close()")
    engine1 = FinanceFeedbackEngine(config)
    await engine1.close()
    del engine1
    gc.collect()
    await asyncio.sleep(0.1)  # Give time for cleanup
    
    # Test 2: Engine with context manager
    print("\n📋 Test 2: Async context manager")
    async with FinanceFeedbackEngine(config) as engine2:
        pass
    del engine2
    gc.collect()
    await asyncio.sleep(0.1)
    
    # Test 3: Multiple sequential engines (simulating CLI commands)
    print("\n📋 Test 3: Sequential engine instances (like CLI commands)")
    for i in range(3):
        engine = FinanceFeedbackEngine(config)
        # Simulate some work
        await asyncio.sleep(0.01)
        await engine.close()
        del engine
        gc.collect()
    
    await asyncio.sleep(0.2)  # Give time for cleanup
    
    # Final garbage collection
    gc.collect()
    await asyncio.sleep(0.1)
    
    print(f"\n{'✅' if warning_count == 0 else '❌'} Test complete: {warning_count} session warnings")
    
    return warning_count == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(test_session_cleanup())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
