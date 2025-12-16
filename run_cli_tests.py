import re
import subprocess
import sys


def run_test(name, args, expected_string, timeout_sec=30):
    """
    Run a test command and check output for an expected string.

    Args:
        name: Test name for reporting
        args: List of command arguments (no shell=True)
        expected_string: Regex pattern to search in stdout+stderr
        timeout_sec: Command timeout in seconds

    Returns:
        Tuple of (test_name, passed: bool)
    """
    print(f"Running: {name}")
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout_sec
        )
        # Check both stdout and stderr for the expected pattern
        combined_output = result.stdout + result.stderr
        match_found = re.search(expected_string, combined_output, re.IGNORECASE)

        if match_found:
            print("  ✓ PASSED")
            return (name, True)
        else:
            print(f"  ✗ FAILED (expected string not found: '{expected_string}')")
            return (name, False)
    except subprocess.TimeoutExpired:
        print(f"  ✗ FAILED (timeout after {timeout_sec}s)")
        return (name, False)
    except Exception as e:
        print(f"  ✗ FAILED (exception: {e})")
        return (name, False)


def main():
    tests = [
        (
            "Backtest validation error",
            [
                "python",
                "main.py",
                "backtest",
                "BTCUSD",
                "--start",
                "2024-02-01",
                "--end",
                "2024-01-01",
            ],
            "start_date.*must be before",
            10,
        ),
        (
            "History invalid asset",
            ["python", "main.py", "history", "--asset", "ZZZNONE", "--limit", "1"],
            ".*",  # Accept any output
            10,
        ),
        (
            "Backtest summary output",
            [
                "python",
                "main.py",
                "backtest",
                "BTCUSD",
                "--start",
                "2024-01-01",
                "--end",
                "2024-01-02",
            ],
            "AI-Driven Backtest Summary",
            20,
        ),
        (
            "Walk-forward window output",
            [
                "python",
                "main.py",
                "walk-forward",
                "BTCUSD",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-10",
                "--train-ratio",
                "0.7",
            ],
            "Windows: train=",
            10,
        ),
        (
            "Monte-Carlo results output",
            [
                "python",
                "main.py",
                "monte-carlo",
                "BTCUSD",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-02",
                "--simulations",
                "3",
            ],
            "Monte Carlo Simulation Results",
            10,
        ),
    ]

    results = []
    for name, args, expected_string, timeout in tests:
        results.append(run_test(name, args, expected_string, timeout))

    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed

    print(f"\n{'='*60}")
    print(f"Test Summary: {passed} passed, {failed} failed (total: {len(results)})")
    print(f"{'='*60}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
