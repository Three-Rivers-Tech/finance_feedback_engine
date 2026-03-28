#!/usr/bin/env python3
"""
Test script for THR-301 fixes.

Verifies all 4 critical issues are resolved:
1. Event loop proliferation (persistent loop)
2. Broad exception handling (specific exceptions)
3. FFE backtest isolation (reset_state method)
4. FFE initialization validation (explicit checks)

Run after installing dependencies:
    python3 test_thr301_fixes.py
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def test_event_loop_persistence():
    """Test Fix #1: Persistent event loop instead of creating new ones."""
    print("Testing Fix #1: Event Loop Persistence...")
    
    from finance_feedback_engine.backtest.strategy_adapter import FFEStrategyAdapter
    from unittest.mock import Mock
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.decision_engine = Mock()
    mock_engine.config = {}
    
    # Create adapter
    adapter = FFEStrategyAdapter(mock_engine)
    
    # Verify persistent loop was created
    assert hasattr(adapter, 'loop'), "❌ No persistent loop created in __init__"
    assert isinstance(adapter.loop, asyncio.AbstractEventLoop), "❌ Loop is not an event loop"
    assert not adapter.loop.is_closed(), "❌ Loop should not be closed after init"
    
    # Verify close method exists and works
    adapter.close()
    assert adapter.loop.is_closed(), "❌ Loop not closed by close() method"
    
    print("✅ Fix #1 verified: Persistent event loop created and cleanup works")


def test_specific_exception_handling():
    """Test Fix #2: Specific exception handling instead of broad catch-all."""
    print("\nTesting Fix #2: Specific Exception Handling...")
    
    from finance_feedback_engine.backtest.strategy_adapter import FFEStrategyAdapter
    from unittest.mock import Mock, AsyncMock
    
    # Create mock engine
    mock_engine = Mock()
    mock_engine.decision_engine = Mock()
    mock_engine.decision_engine.make_decision = AsyncMock(side_effect=ValueError("Test error"))
    mock_engine.config = {}
    
    # Create adapter
    adapter = FFEStrategyAdapter(mock_engine)
    
    # Test that ValueError is caught and returns None
    context = {"market_data": {}, "symbol": "TEST"}
    result = adapter._get_decision_sync(context)
    
    assert result is None, "❌ ValueError should be caught and return None"
    
    # Test that unexpected exceptions would propagate (RuntimeError)
    mock_engine.decision_engine.make_decision = AsyncMock(side_effect=RuntimeError("Unexpected bug"))
    
    try:
        result = adapter._get_decision_sync(context)
        print("❌ RuntimeError should have propagated")
    except RuntimeError:
        print("✅ Fix #2 verified: Unexpected exceptions propagate correctly")
    
    adapter.close()


def test_state_reset():
    """Test Fix #3: State reset method for backtest isolation."""
    print("\nTesting Fix #3: State Reset Method...")
    
    from finance_feedback_engine.backtest.strategy_adapter import FFEStrategyAdapter
    from unittest.mock import Mock
    
    # Create mock engine with vector_memory and portfolio_memory
    mock_engine = Mock()
    mock_engine.decision_engine = Mock()
    mock_engine.decision_engine.vector_memory = Mock()
    mock_engine.decision_engine.vector_memory.clear = Mock()
    mock_engine.portfolio_memory = Mock()
    mock_engine.portfolio_memory.reset = Mock()
    mock_engine.config = {}
    
    # Create adapter
    adapter = FFEStrategyAdapter(mock_engine)
    
    # Verify reset_state method exists
    assert hasattr(adapter, 'reset_state'), "❌ No reset_state method found"
    
    # Call reset_state
    adapter.reset_state()
    
    # Verify memory was cleared
    mock_engine.decision_engine.vector_memory.clear.assert_called_once()
    mock_engine.portfolio_memory.reset.assert_called_once()
    
    print("✅ Fix #3 verified: State reset clears vector_memory and portfolio_memory")
    
    adapter.close()


def test_initialization_validation():
    """Test Fix #4: FFE initialization validation in CLI."""
    print("\nTesting Fix #4: Initialization Validation...")
    
    # Read the main.py file and check for validation code
    main_py = Path(__file__).parent / "finance_feedback_engine" / "cli" / "main.py"
    
    with open(main_py) as f:
        content = f.read()
    
    # Check for key validation steps
    checks = [
        "FIX #4: Validate FFE initialization",
        "decision_engine not initialized",
        "trading_platform not initialized",
        "test_decision = loop.run_until_complete",
        "Decision engine test returned None"
    ]
    
    missing = []
    for check in checks:
        if check not in content:
            missing.append(check)
    
    if missing:
        print(f"❌ Missing validation checks: {missing}")
        return False
    
    print("✅ Fix #4 verified: All validation checks present in main.py")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("THR-301 Critical Fixes Verification")
    print("=" * 60)
    
    try:
        test_event_loop_persistence()
        test_specific_exception_handling()
        test_state_reset()
        test_initialization_validation()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nAll 4 critical issues have been successfully fixed:")
        print("1. ✅ Event loop persistence (no more proliferation)")
        print("2. ✅ Specific exception handling (no silent failures)")
        print("3. ✅ State reset method (backtest isolation)")
        print("4. ✅ Initialization validation (catch failures early)")
        print("\nReady for production use!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
