#!/usr/bin/env python3
"""
Real-time monitor for backtest progress and memory persistence.

Shows:
- Current backtest day
- Memory files accumulated
- Provider decisions being made
- Portfolio value progression
"""

import tempfile
import time
from datetime import datetime
from pathlib import Path


def monitor_backtest_progress():
    """Monitor Q1 backtest in real-time."""

    memory_dir = Path("data/memory")
    memory_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print("BACKTEST PROGRESS MONITOR")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Memory directory: {memory_dir.absolute()}")
    print("")

    last_outcome_count = 0

    while True:
        try:
            # Count accumulated memories
            outcome_files = list(memory_dir.glob("outcome_*.json"))
            snapshot_files = list(memory_dir.glob("snapshot_*.json"))
            vectors_file = memory_dir / "vectors.pkl"

            # Check if backtest log exists in a temporary location
            log_file = Path(tempfile.gettempdir()) / "q1_backtest.log"
            if not log_file.exists():
                print("Waiting for backtest to start...")
                time.sleep(2)
                continue

            # Get recent log lines
            with open(log_file, "r") as f:
                lines = f.readlines()

            # Find current processing info
            current_date = None
            current_asset = None
            for line in lines[-100:]:  # Check last 100 lines
                if "Processing" in line and "(" in line:
                    # Extract date from processing line
                    try:
                        parts = line.split("Processing")
                        if len(parts) > 1:
                            current_date = parts[1].strip().split()[0]
                    except (IndexError, ValueError):
                        pass

                if "Generating decision for" in line:
                    try:
                        current_asset = line.split("for")[-1].strip().split()[0]
                    except (IndexError, ValueError):
                        pass

            # Display status
            if len(outcome_files) != last_outcome_count:
                print(f"\r[{datetime.now().strftime('%H:%M:%S')}] ", end="", flush=True)
                if current_date:
                    print(f"Date: {current_date} ", end="", flush=True)
                if current_asset:
                    print(f"| Asset: {current_asset} ", end="", flush=True)
                print(f"| Outcomes: {len(outcome_files)} ", end="", flush=True)
                print(
                    (
                        f"| Memory: {vectors_file.stat().st_size / 1024 / 1024:.2f} MB "
                        if vectors_file.exists()
                        else "| Memory: 0 MB "
                    ),
                    end="",
                    flush=True,
                )

                last_outcome_count = len(outcome_files)

            time.sleep(5)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            time.sleep(5)


if __name__ == "__main__":
    monitor_backtest_progress()
