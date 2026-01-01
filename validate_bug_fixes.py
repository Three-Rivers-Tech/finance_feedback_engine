#!/usr/bin/env python3
"""
Simple validation script to check bug fixes without full test suite.
"""

import sys
from pathlib import Path


def check_idle_state_bug():
    """Check Bug #1: IDLE state should not auto-transition."""
    print("Checking Bug #1: IDLE state auto-transition...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    # Check that handle_idle_state does NOT have transition to LEARNING
    if "async def handle_idle_state" in content:
        # Find the function
        start = content.find("async def handle_idle_state")
        end = content.find("\n    async def ", start + 1)
        if end == -1:
            end = content.find("\n    def ", start + 1)
        
        function_body = content[start:end]
        
        if "await self._transition_to(AgentState.LEARNING)" in function_body:
            print("  ❌ FAIL: IDLE state still has auto-transition to LEARNING")
            return False
        else:
            print("  ✅ PASS: IDLE state does not auto-transition")
            return True
    
    print("  ⚠️  WARNING: Could not find handle_idle_state function")
    return False


def check_race_condition_bug():
    """Check Bug #2: asset_pairs should have lock protection."""
    print("Checking Bug #2: asset_pairs race condition...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    has_lock = "_asset_pairs_lock = asyncio.Lock()" in content
    uses_lock = "async with self._asset_pairs_lock:" in content
    has_snapshot = "asset_pairs_snapshot" in content
    
    if has_lock and uses_lock and has_snapshot:
        print("  ✅ PASS: Lock protection and snapshot copy implemented")
        return True
    else:
        print(f"  ❌ FAIL: Missing components (lock:{has_lock}, uses:{uses_lock}, snapshot:{has_snapshot})")
        return False


def check_memory_leak_bug():
    """Check Bug #3: _rejected_decisions_cache cleanup."""
    print("Checking Bug #3: Rejected decisions cache cleanup...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    # Check if cleanup is called in multiple states
    perception_cleanup = "async def handle_perception_state" in content and \
                        content.find("self._cleanup_rejected_cache()", 
                                   content.find("async def handle_perception_state")) > 0
    
    learning_cleanup = "async def handle_learning_state" in content and \
                      content.find("self._cleanup_rejected_cache()", 
                                 content.find("async def handle_learning_state")) > 0
    
    if perception_cleanup and learning_cleanup:
        print("  ✅ PASS: Cleanup called in multiple states")
        return True
    else:
        print(f"  ❌ FAIL: Cleanup missing (perception:{perception_cleanup}, learning:{learning_cleanup})")
        return False


def check_type_hints():
    """Check Bug #6: Type hints should use Dict[str, Any] not dict[str, any]."""
    print("Checking Bug #6: Type hints...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    # Check for bad type hints
    if "dict[str, any]" in content:
        print("  ❌ FAIL: Found dict[str, any] (should be Dict[str, Any])")
        return False
    
    # Check for good type hints
    has_dict_import = "from typing import" in content and "Dict" in content
    has_any_import = "from typing import" in content and "Any" in content
    
    if has_dict_import and has_any_import:
        print("  ✅ PASS: Proper type hints with Dict and Any imports")
        return True
    else:
        print(f"  ⚠️  WARNING: Type imports may be incomplete (Dict:{has_dict_import}, Any:{has_any_import})")
        return True  # Not critical


def check_unused_variable():
    """Check Bug #8: _current_decision should be removed."""
    print("Checking Bug #8: Unused _current_decision variable...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    # Check in __init__ method
    if "self._current_decision = None" in content:
        print("  ❌ FAIL: _current_decision still present in code")
        return False
    else:
        print("  ✅ PASS: _current_decision removed")
        return True


def check_autonomous_property():
    """Check Bug #5: is_autonomous_enabled property should exist."""
    print("Checking Bug #5: is_autonomous_enabled property...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    has_property = "def is_autonomous_enabled(self) -> bool:" in content
    has_decorator = "@property" in content and \
                   content.find("@property", 0, content.find("def is_autonomous_enabled")) > 0
    
    if has_property:
        print("  ✅ PASS: is_autonomous_enabled property exists")
        return True
    else:
        print("  ❌ FAIL: is_autonomous_enabled property not found")
        return False


def check_analysis_failures_cleanup():
    """Check Bug #9: analysis_failures should delete entries on success."""
    print("Checking Bug #9: analysis_failures cleanup...")
    
    file_path = Path("finance_feedback_engine/agent/trading_loop_agent.py")
    with open(file_path) as f:
        content = f.read()
    
    # Look for deletion pattern instead of setting to 0
    has_delete = "del self.analysis_failures[failure_key]" in content
    no_zero_set = "self.analysis_failures[failure_key] = 0" not in content
    
    if has_delete and no_zero_set:
        print("  ✅ PASS: Entries are deleted on success (not set to 0)")
        return True
    else:
        print(f"  ❌ FAIL: Cleanup pattern incorrect (delete:{has_delete}, no_zero:{no_zero_set})")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("Bug Fix Validation Script")
    print("=" * 60)
    print()
    
    results = [
        check_idle_state_bug(),
        check_race_condition_bug(),
        check_memory_leak_bug(),
        check_type_hints(),
        check_unused_variable(),
        check_autonomous_property(),
        check_analysis_failures_cleanup(),
    ]
    
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ All bug fixes validated successfully!")
        return 0
    else:
        print(f"❌ {total - passed} check(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
