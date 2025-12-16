#!/usr/bin/env python3
"""
Test script to verify atomic writes with file locking in PortfolioMemoryEngine.
"""

import json
import tempfile
import threading
import time
from pathlib import Path

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine


def test_concurrent_writes():
    """Test that concurrent writes don't corrupt the memory file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        memory_file = Path(temp_dir) / "test_memory.json"

        # Create a basic config
        config = {
            "portfolio_memory": {
                "enabled": True,
                "max_memory_size": 100,
                "learning_rate": 0.1,
                "context_window": 20,
            },
            "persistence": {"storage_path": str(temp_dir)},
        }

        # Create decision data for multiple trades
        decisions = []
        for i in range(10):
            decisions.append(
                {
                    "id": f"test_trade_{i}",
                    "asset_pair": "BTCUSD",
                    "action": "BUY",
                    "entry_price": 50000.0 + i * 100,
                    "position_size": 0.1,
                    "confidence": 80 + i,
                    "reasoning": f"Test trade {i}",
                    "timestamp": f"2024-12-04T10:0{i}:00Z",
                    "ai_provider": "test_provider",
                }
            )

        def write_trade(decision, exit_price):
            """Function to record a trade and save to disk."""
            engine = PortfolioMemoryEngine(config)
            outcome = engine.record_trade_outcome(
                decision,
                exit_price=exit_price,
                exit_timestamp=f"2024-12-04T11:0{i}:00Z",
            )
            # Save to the specific file
            engine.save_to_disk(str(memory_file))
            print(f"Completed trade {decision['id']}")

        # Create threads for concurrent writes
        threads = []
        for i, decision in enumerate(decisions):
            thread = threading.Thread(
                target=write_trade, args=(decision, 51000.0 + i * 100)
            )
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        print(f"All threads completed. Checking file: {memory_file}")

        # Verify the file can be read back without corruption
        if memory_file.exists():
            try:
                with open(memory_file, "r") as f:
                    data = json.load(f)
                print("File read successfully - no corruption detected")
                print(f"File contains {len(data.get('trade_history', []))} trades")
                return True
            except json.JSONDecodeError as e:
                print(f"File corruption detected: {e}")
                return False
        else:
            print("File does not exist after concurrent writes")
            return False


def test_atomic_write_function():
    """Test the atomic write function directly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "test_atomic.json"

        engine = PortfolioMemoryEngine(
            {
                "persistence": {"storage_path": str(temp_dir)},
            }
        )

        # Test data
        test_data = {"test": "data", "timestamp": time.time()}

        try:
            engine._atomic_write_file(test_file, test_data)
            print("Atomic write function test passed")

            # Verify the file was written correctly
            with open(test_file, "r") as f:
                read_data = json.load(f)

            if read_data == test_data:
                print("Data integrity verified")
                return True
            else:
                print("Data integrity check failed")
                return False

        except Exception as e:
            print(f"Atomic write function test failed: {e}")
            return False


if __name__ == "__main__":
    print("Testing atomic writes with file locking...")

    print("\n1. Testing atomic write function:")
    atomic_test_result = test_atomic_write_function()

    print("\n2. Testing concurrent writes:")
    concurrent_test_result = test_concurrent_writes()

    print("\nResults:")
    print(f"Atomic write function: {'PASS' if atomic_test_result else 'FAIL'}")
    print(f"Concurrent writes: {'PASS' if concurrent_test_result else 'FAIL'}")

    if atomic_test_result and concurrent_test_result:
        print(
            "\nAll tests passed! Atomic writes with file locking are working correctly."
        )
    else:
        print("\nSome tests failed. Please review the implementation.")
