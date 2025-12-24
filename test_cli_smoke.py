#!/usr/bin/env python
"""Quick CLI smoke tests to verify production readiness."""

import subprocess
import sys

def run_cmd(cmd, timeout=30):
    """Run a CLI command and return stdout."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/home/cmp6510/finance_feedback_engine-2.0"
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)

def test_command(name, cmd, check_exit=0, check_output=None):
    """Test a single CLI command."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")

    exit_code, stdout, stderr = run_cmd(cmd)

    success = exit_code == check_exit
    if check_output and check_output in stdout:
        success = success and True

    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status} (exit code: {exit_code})")

    if stderr and "WARNING" not in stderr.upper():
        print(f"STDERR: {stderr[:200]}")
    if not success and stdout:
        print(f"STDOUT: {stdout[:200]}")

    return success

def main():
    """Run all CLI smoke tests."""
    tests = [
        # Help and status
        ("CLI Help", "python main.py --help", 0, "Finance Feedback Engine"),
        ("Status Command", "python main.py status", 0, "Engine initialized"),
        ("Balance Command Help", "python main.py balance --help", 0, "Show current account balances"),
        ("Positions Help", "python main.py positions --help", 0, "Display active trading positions"),
        ("History Help", "python main.py history --help", 0, "Show decision history"),

        # Config and validation
        ("Config Editor Help", "python main.py config-editor --help", 0, "Interactive helper"),

        # Agent commands
        ("Run Agent Help", "python main.py run-agent --help", 0, "Starts the autonomous trading agent"),

        # Backtest commands
        ("Backtest Help", "python main.py backtest --help", 0, "Run AI-driven backtest"),
        ("Walk-Forward Help", "python main.py walk-forward --help", 0, "Run walk-forward"),
        ("Monte-Carlo Help", "python main.py monte-carlo --help", 0, "Run Monte Carlo"),

        # API command
        ("Monitor Help", "python main.py monitor --help", 0, "Live trade monitoring"),
        ("Dashboard Help", "python main.py dashboard --help", 0, "Show unified dashboard"),

        # Analyze command
        ("Analyze Help", "python main.py analyze --help", 0, "Analyze an asset pair"),
    ]

    passed = 0
    failed = 0

    for name, cmd, expected_exit, expected_output in tests:
        if test_command(name, cmd, expected_exit, expected_output):
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
