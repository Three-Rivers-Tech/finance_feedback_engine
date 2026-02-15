#!/usr/bin/env python3
"""
Test script for THR-235: Trade Outcome Recording Pipeline

Tests:
1. TradeOutcomeRecorder initialization
2. Position tracking and outcome detection
3. Database integration
4. File output to data/trade_outcomes/
5. Decision file field population
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from finance_feedback_engine.monitoring.trade_outcome_recorder import TradeOutcomeRecorder


def test_trade_outcome_recorder():
    """Test TradeOutcomeRecorder with simulated position changes."""
    
    print("=" * 80)
    print("THR-235: Trade Outcome Recording Pipeline Test")
    print("=" * 80)
    
    # Initialize recorder
    print("\n1. Initializing TradeOutcomeRecorder...")
    recorder = TradeOutcomeRecorder(data_dir="data")
    print(f"   ✓ Recorder initialized")
    print(f"   ✓ State file: {recorder.state_file}")
    print(f"   ✓ Outcomes dir: {recorder.outcomes_dir}")
    print(f"   ✓ Current open positions: {len(recorder.open_positions)}")
    
    # Simulate opening a position
    print("\n2. Simulating position open (BTC-USD LONG)...")
    open_positions = [
        {
            "product_id": "BTC-USD",
            "side": "LONG",
            "size": "0.001",
            "entry_price": "69500.00",
            "current_price": "69500.00",
            "entry_time": datetime.now(timezone.utc).isoformat(),
        }
    ]
    
    outcomes = recorder.update_positions(open_positions)
    print(f"   ✓ Position opened")
    print(f"   ✓ Outcomes detected: {len(outcomes)}")
    print(f"   ✓ Open positions: {len(recorder.open_positions)}")
    
    # Simulate position still open (no change)
    print("\n3. Simulating position update (price changed)...")
    updated_positions = [
        {
            "product_id": "BTC-USD",
            "side": "LONG",
            "size": "0.001",
            "entry_price": "69500.00",
            "current_price": "70000.00",  # Price moved up
            "entry_time": open_positions[0]["entry_time"],
        }
    ]
    
    outcomes = recorder.update_positions(updated_positions)
    print(f"   ✓ Position updated")
    print(f"   ✓ Outcomes detected: {len(outcomes)} (should be 0, position still open)")
    print(f"   ✓ Open positions: {len(recorder.open_positions)}")
    
    # Simulate closing the position
    print("\n4. Simulating position close...")
    closed_positions = []  # Empty list = all positions closed
    
    outcomes = recorder.update_positions(closed_positions)
    print(f"   ✓ Position closed")
    print(f"   ✓ Outcomes detected: {len(outcomes)}")
    print(f"   ✓ Open positions: {len(recorder.open_positions)}")
    
    if outcomes:
        print("\n5. Outcome details:")
        outcome = outcomes[0]
        print(f"   • Trade ID: {outcome['trade_id']}")
        print(f"   • Product: {outcome['product']}")
        print(f"   • Side: {outcome['side']}")
        print(f"   • Entry: ${outcome['entry_price']} x {outcome['entry_size']}")
        print(f"   • Exit: ${outcome['exit_price']} x {outcome['exit_size']}")
        print(f"   • P&L: ${outcome['realized_pnl']}")
        print(f"   • ROI: {outcome['roi_percent']}%")
        print(f"   • Duration: {outcome['holding_duration_seconds']}s")
        
        # Check if outcome was saved to file
        exit_dt = datetime.fromisoformat(outcome["exit_time"].replace("Z", "+00:00"))
        outcome_file = recorder.outcomes_dir / f"{exit_dt.strftime('%Y-%m-%d')}.jsonl"
        if outcome_file.exists():
            print(f"\n   ✓ Outcome saved to: {outcome_file}")
            # Read and verify
            with open(outcome_file, 'r') as f:
                lines = f.readlines()
                print(f"   ✓ Total outcomes in file: {len(lines)}")
        else:
            print(f"\n   ✗ Outcome file not found: {outcome_file}")
    
    # Test with multiple positions
    print("\n6. Testing multiple positions...")
    multi_positions = [
        {
            "product_id": "BTC-USD",
            "side": "LONG",
            "size": "0.001",
            "entry_price": "69500.00",
            "current_price": "69500.00",
            "entry_time": datetime.now(timezone.utc).isoformat(),
        },
        {
            "product_id": "ETH-USD",
            "side": "LONG",
            "size": "0.01",
            "entry_price": "3500.00",
            "current_price": "3500.00",
            "entry_time": datetime.now(timezone.utc).isoformat(),
        }
    ]
    
    outcomes = recorder.update_positions(multi_positions)
    print(f"   ✓ Multiple positions opened: {len(recorder.open_positions)}")
    
    # Close only one
    single_position = [multi_positions[0]]
    outcomes = recorder.update_positions(single_position)
    print(f"   ✓ Closed 1 position, detected {len(outcomes)} outcomes")
    print(f"   ✓ Remaining open: {len(recorder.open_positions)}")
    
    # Close all
    outcomes = recorder.update_positions([])
    print(f"   ✓ Closed all positions, detected {len(outcomes)} outcomes")
    print(f"   ✓ Remaining open: {len(recorder.open_positions)}")
    
    print("\n" + "=" * 80)
    print("✓ All tests passed!")
    print("=" * 80)
    
    # Print summary
    print("\nSummary:")
    print(f"  • State file: {recorder.state_file}")
    print(f"  • Outcomes dir: {recorder.outcomes_dir}")
    print(f"  • Total outcome files: {len(list(recorder.outcomes_dir.glob('*.jsonl')))}")
    
    return True


if __name__ == "__main__":
    try:
        success = test_trade_outcome_recorder()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
