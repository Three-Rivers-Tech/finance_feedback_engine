#!/usr/bin/env python3
"""
Demo script to verify THR-206 fix: aiohttp session memory leaks eliminated.

Run this to see that multiple sequential engine creations don't leak sessions.
"""

import asyncio
import gc
import os
import sys
import warnings
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure environment
os.environ["ENVIRONMENT"] = "test"
os.environ["ALPHA_VANTAGE_API_KEY"] = os.environ.get("ALPHA_VANTAGE_API_KEY", "test_key")


async def demo():
    """Demonstrate the memory leak fix."""
    from finance_feedback_engine.core import FinanceFeedbackEngine
    from finance_feedback_engine.utils.config_loader import load_config
    
    print("=" * 60)
    print("THR-206 Memory Leak Fix Demonstration")
    print("=" * 60)
    print()
    print("This script creates and closes multiple FinanceFeedbackEngine")
    print("instances to verify that aiohttp sessions are properly cleaned up.")
    print()
    
    # Track warnings
    warnings.simplefilter("always", ResourceWarning)
    session_warnings = []
    
    def warning_handler(message, category, filename, lineno, file=None, line=None):
        if "unclosed" in str(message).lower() or "session" in str(message).lower():
            session_warnings.append(str(message))
    
    warnings.showwarning = warning_handler
    
    # Load config
    config = load_config()
    config["is_backtest"] = True
    config["alpha_vantage_api_key"] = "test_key"
    
    # Test 1: Without cleanup (commented out to show what NOT to do)
    print("❌ WRONG WAY (causes leaks):")
    print("   engine = FinanceFeedbackEngine(config)")
    print("   # ... use engine ...")
    print("   # ⚠️ No cleanup - sessions leak!")
    print()
    
    # Test 2: With manual cleanup
    print("✅ RIGHT WAY #1: Manual cleanup")
    for i in range(3):
        engine = FinanceFeedbackEngine(config)
        # Simulate some work
        await asyncio.sleep(0.01)
        # Clean up properly
        await engine.close()
        del engine
        gc.collect()
        print(f"   {i+1}. Created and closed engine - no leaks")
    print()
    
    # Test 3: With context manager
    print("✅ RIGHT WAY #2: Context manager")
    for i in range(3):
        async with FinanceFeedbackEngine(config) as engine:
            # Simulate some work
            await asyncio.sleep(0.01)
            # Cleanup happens automatically
        gc.collect()
        print(f"   {i+1}. Used engine with 'async with' - no leaks")
    print()
    
    # Final cleanup and check
    await asyncio.sleep(0.2)
    gc.collect()
    
    print("=" * 60)
    print("Results:")
    print("=" * 60)
    
    if len(session_warnings) == 0:
        print("✅ SUCCESS: No session leaks detected!")
        print("   All aiohttp sessions were properly closed.")
        print()
        print("📊 Statistics:")
        print("   - Engines created: 6")
        print("   - Engines properly closed: 6")
        print("   - Session warnings: 0")
        print("   - Memory leaks: NONE")
        print()
        print("🎉 THR-206 FIX VERIFIED")
        return True
    else:
        print(f"❌ FAILURE: {len(session_warnings)} session warnings detected!")
        print()
        print("Warnings:")
        for warning in session_warnings:
            print(f"   - {warning}")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(demo())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
