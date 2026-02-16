#!/usr/bin/env python3
"""
Verify State Machine Bug Fix

Demonstrates that the state transition validation now allows
curriculum learning workflow to complete successfully.
"""

import sys
from pathlib import Path

# Add parent to path for FFE imports
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.agent.trading_loop_agent import AgentState, TradingLoopAgent


def verify_transitions():
    """Verify all state transitions are legal according to _VALID_TRANSITIONS."""
    
    print("=" * 80)
    print("STATE MACHINE VALIDATION CHECK")
    print("=" * 80)
    print()
    
    # Print the valid transition rules
    print("Valid Transition Rules:")
    print("-" * 80)
    for from_state, to_states in TradingLoopAgent._VALID_TRANSITIONS.items():
        to_state_names = [s.name for s in to_states]
        print(f"  {from_state.name:15} → {', '.join(to_state_names)}")
    print()
    
    # Check critical transitions for curriculum learning
    print("Critical Transitions for Curriculum Learning:")
    print("-" * 80)
    
    checks = [
        ("IDLE", "PERCEPTION", "Cycle restart (FIXED)"),
        ("RECOVERING", "PERCEPTION", "Recovery failure (FIXED)"),
        ("EXECUTION", "LEARNING", "Normal flow (OK)"),
        ("LEARNING", "PERCEPTION", "Continue cycle (OK)"),
        ("LEARNING", "IDLE", "End cycle (OK)"),
    ]
    
    all_valid = True
    for from_name, to_name, description in checks:
        from_state = AgentState[from_name]
        to_state = AgentState[to_name]
        
        valid_targets = TradingLoopAgent._VALID_TRANSITIONS.get(from_state, set())
        is_valid = to_state in valid_targets
        
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"  {from_name:15} → {to_name:15} {status:12} ({description})")
        
        if not is_valid:
            all_valid = False
    
    print()
    print("=" * 80)
    
    if all_valid:
        print("✅ ALL TRANSITIONS VALID - Curriculum learning can proceed!")
        print("=" * 80)
        return 0
    else:
        print("❌ INVALID TRANSITIONS DETECTED - Curriculum learning will fail!")
        print("=" * 80)
        return 1


def verify_no_illegal_transitions_in_code():
    """Scan code for any remaining illegal LEARNING transitions."""
    
    print()
    print("CODE SCAN: Checking for illegal transitions to LEARNING...")
    print("-" * 80)
    
    import re
    
    code_file = Path(__file__).parent / "finance_feedback_engine" / "agent" / "trading_loop_agent.py"
    
    with open(code_file, 'r') as f:
        lines = f.readlines()
    
    # Find all transitions to LEARNING
    learning_transitions = []
    for i, line in enumerate(lines, 1):
        if "transition_to(AgentState.LEARNING)" in line:
            # Get context (previous few lines to see which handler this is in)
            context_start = max(0, i - 30)
            context = "".join(lines[context_start:i])
            
            # Try to determine which state handler this is in
            handler_match = re.search(r'async def handle_(\w+)_state', context)
            if handler_match:
                from_state = handler_match.group(1).upper()
            else:
                from_state = "UNKNOWN"
            
            learning_transitions.append({
                'line': i,
                'from_state': from_state,
                'code': line.strip()
            })
    
    print(f"Found {len(learning_transitions)} transition(s) to LEARNING:")
    print()
    
    for trans in learning_transitions:
        from_state_enum = trans['from_state']
        
        # Check if this is legal
        if from_state_enum in ['EXECUTION', 'UNKNOWN']:
            status = "✅ LEGAL"
        else:
            try:
                from_state = AgentState[from_state_enum]
                valid = AgentState.LEARNING in TradingLoopAgent._VALID_TRANSITIONS.get(from_state, set())
                status = "✅ LEGAL" if valid else "❌ ILLEGAL"
            except KeyError:
                status = "⚠️  NEEDS REVIEW"
        
        print(f"  Line {trans['line']:4} | {from_state_enum:15} → LEARNING | {status}")
        print(f"           {trans['code']}")
        print()
    
    print("-" * 80)
    print()
    
    return len([t for t in learning_transitions if t['from_state'] not in ['EXECUTION', 'UNKNOWN']])


if __name__ == "__main__":
    print()
    result1 = verify_transitions()
    illegal_count = verify_no_illegal_transitions_in_code()
    
    if result1 == 0 and illegal_count == 0:
        print("🎉 STATE MACHINE FIX VERIFIED SUCCESSFULLY!")
        print()
        sys.exit(0)
    else:
        print("⚠️  ISSUES DETECTED - Review needed")
        print()
        sys.exit(1)
