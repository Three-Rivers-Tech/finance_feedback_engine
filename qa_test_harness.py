#!/usr/bin/env python3
"""
Finance Feedback Engine - CLI QA Test Harness

Systematically runs CLI commands and captures output for analysis.
Supports both automated testing and interactive exploratory testing.

Usage:
  python qa_test_harness.py [--output QA_RESULTS.json] [--verbose] [--command COMMAND] [--asset ASSET]
"""

import json
import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import argparse


class CLITestResult:
    """Represents the result of a single CLI command execution."""

    def __init__(
        self,
        command: str,
        args: List[str],
        flags: Dict[str, Any],
        expected_behavior: str,
        severity: str = "P0",
    ):
        self.command = command
        self.args = args
        self.flags = flags
        self.expected_behavior = expected_behavior
        self.severity = severity
        self.timestamp = datetime.now().isoformat()
        self.execution_time = 0.0
        self.exit_code = None
        self.stdout = ""
        self.stderr = ""
        self.result_status = "NOT_RUN"  # NOT_RUN, PASS, FAIL, ERROR
        self.notes = ""
        self.deviations = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dict for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "severity": self.severity,
            "command": self.command,
            "args": self.args,
            "flags": self.flags,
            "expected_behavior": self.expected_behavior,
            "execution_time_seconds": round(self.execution_time, 3),
            "exit_code": self.exit_code,
            "result_status": self.result_status,
            "stdout_preview": self.stdout[:500],  # First 500 chars
            "stderr_preview": self.stderr[:500],
            "notes": self.notes,
            "deviations": self.deviations,
        }


class CLITestHarness:
    """Main test harness for CLI command execution and analysis."""

    def __init__(self, config_path: Optional[str] = None, verbose: bool = False):
        self.config_path = config_path or "config/config.test.mock.yaml"
        self.verbose = verbose
        self.results: List[CLITestResult] = []
        self.project_root = Path(__file__).parent
        self.test_start_time = datetime.now()

    def run_command(
        self, command: str, args: List[str], flags: Dict[str, Any]
    ) -> Tuple[int, str, str, float]:
        """
        Execute a CLI command and capture output.

        Args:
            command: CLI command (e.g., "analyze")
            args: Positional arguments
            flags: Flags/options dict

        Returns:
            (exit_code, stdout, stderr, execution_time)
        """
        # Build command line
        cmd_parts = [sys.executable, "main.py", "-c", self.config_path, command]
        cmd_parts.extend(args)

        # Add flags
        for flag_name, flag_value in flags.items():
            if flag_value is True:
                cmd_parts.append(f"--{flag_name}")
            elif flag_value is not False and flag_value is not None:
                cmd_parts.append(f"--{flag_name}")
                cmd_parts.append(str(flag_value))

        if self.verbose:
            print(f"[EXECUTE] {' '.join(cmd_parts)}")

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd_parts,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            elapsed = time.time() - start_time
            return result.returncode, result.stdout, result.stderr, elapsed
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return -1, "", "TIMEOUT after 30 seconds", elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            return -1, "", str(e), elapsed

    def test_command(
        self,
        command: str,
        args: List[str],
        flags: Dict[str, Any],
        expected_behavior: str,
        severity: str = "P0",
        should_pass: bool = True,
    ) -> CLITestResult:
        """
        Execute and assess a single CLI command test.

        Args:
            command: CLI command to test
            args: Positional arguments
            flags: Flag options
            expected_behavior: Description of expected behavior
            severity: Priority level (P0/P1/P2)
            should_pass: Whether command should succeed (exit_code == 0)

        Returns:
            CLITestResult with captured output and assessment
        """
        result = CLITestResult(command, args, flags, expected_behavior, severity)

        # Execute
        exit_code, stdout, stderr, elapsed = self.run_command(command, args, flags)
        result.exit_code = exit_code
        result.stdout = stdout
        result.stderr = stderr
        result.execution_time = elapsed

        # Assess
        if should_pass:
            if exit_code == 0:
                result.result_status = "PASS"
            else:
                result.result_status = "FAIL"
                result.deviations.append(f"Expected success, got exit code {exit_code}")
        else:
            if exit_code != 0:
                result.result_status = "PASS"  # Expected to fail
            else:
                result.result_status = "FAIL"
                result.deviations.append("Expected failure, but succeeded")

        self.results.append(result)
        return result

    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary statistics from all test results."""
        if not self.results:
            return {}

        total = len(self.results)
        passed = sum(1 for r in self.results if r.result_status == "PASS")
        failed = sum(1 for r in self.results if r.result_status == "FAIL")
        errors = sum(1 for r in self.results if r.result_status == "ERROR")

        by_severity = {}
        for severity in ["P0", "P1", "P2"]:
            sev_results = [r for r in self.results if r.severity == severity]
            if sev_results:
                by_severity[severity] = {
                    "total": len(sev_results),
                    "passed": sum(1 for r in sev_results if r.result_status == "PASS"),
                    "failed": sum(1 for r in sev_results if r.result_status == "FAIL"),
                }

        all_deviations = []
        for result in self.results:
            if result.deviations:
                all_deviations.append(
                    {
                        "command": result.command,
                        "args": result.args,
                        "deviations": result.deviations,
                    }
                )

        return {
            "test_run_date": self.test_start_time.isoformat(),
            "config_used": self.config_path,
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": round(100 * passed / total, 1) if total > 0 else 0,
            "by_severity": by_severity,
            "deviations_found": len(all_deviations),
            "deviation_details": all_deviations,
        }

    def save_results(self, output_file: str) -> None:
        """Save test results to JSON file."""
        summary = self.generate_summary_report()
        results_data = {
            "summary": summary,
            "detailed_results": [r.to_dict() for r in self.results],
        }

        output_path = self.project_root / output_file
        with open(output_path, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\n✓ Results saved to {output_path}")

    def print_summary(self) -> None:
        """Print summary to console."""
        summary = self.generate_summary_report()

        if not summary:
            print("No tests run yet.")
            return

        print("\n" + "=" * 70)
        print("QA TEST SUMMARY".center(70))
        print("=" * 70)
        print(f"Test Date: {summary['test_run_date']}")
        print(f"Config: {summary['config_used']}")
        print(f"\nTotal Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']} ✓")
        print(f"Failed: {summary['failed']} ✗")
        print(f"Errors: {summary['errors']} ⚠")
        print(f"Pass Rate: {summary['pass_rate']}%")

        if summary["by_severity"]:
            print("\nBy Severity:")
            for severity, stats in summary["by_severity"].items():
                print(
                    f"  {severity}: {stats['passed']}/{stats['total']} passed"
                )

        if summary["deviation_details"]:
            print(f"\n⚠ Deviations Found: {summary['deviations_found']}")
            for dev in summary["deviation_details"][:5]:  # Show first 5
                print(f"  - {dev['command']} {' '.join(dev['args'])}")
                for d in dev["deviations"]:
                    print(f"    → {d}")

        print("=" * 70)


# ============================================================================
# TEST SUITE DEFINITIONS
# ============================================================================


def define_core_command_tests() -> List[Tuple[str, List[str], Dict, str, str]]:
    """Define P0 (core command) tests."""
    return [
        # ANALYZE command tests
        (
            "analyze",
            ["BTCUSD"],
            {"provider": "local"},
            "Should return decision with BUY/SELL/HOLD action",
            "P0",
        ),
        (
            "analyze",
            ["btc-usd"],
            {"provider": "local"},
            "Should normalize asset pair format",
            "P0",
        ),
        (
            "analyze",
            ["BTCUSD"],
            {"provider": "ensemble"},
            "Should aggregate multiple providers",
            "P0",
        ),
        (
            "analyze",
            ["BTCUSD"],
            {"provider": "invalid"},
            "Should fail with invalid provider",
            "P0",
        ),
        # BACKTEST command tests
        (
            "backtest",
            ["BTCUSD"],
            {
                "start": "2024-01-01",
                "end": "2024-01-31",
            },
            "Should backtest and return metrics",
            "P0",
        ),
        (
            "backtest",
            ["BTCUSD"],
            {
                "start": "2024-01-31",
                "end": "2024-01-01",
            },
            "Should fail with invalid date range",
            "P0",
        ),
        (
            "balance",
            [],
            {},
            "Should return platform balance",
            "P0",
        ),
        (
            "status",
            [],
            {},
            "Should display platform and provider status",
            "P0",
        ),
    ]


def define_workflow_tests() -> List[Tuple[str, List[str], Dict, str, str]]:
    """Define P1 (workflow) tests."""
    return [
        (
            "history",
            [],
            {"limit": "10"},
            "Should show decision history",
            "P1",
        ),
        (
            "history",
            [],
            {"asset": "BTCUSD", "limit": "5"},
            "Should filter history by asset",
            "P1",
        ),
        (
            "history",
            [],
            {"asset": "INVALID", "limit": "10"},
            "Should show empty history for invalid asset",
            "P1",
        ),
        (
            "dashboard",
            [],
            {},
            "Should display portfolio dashboard",
            "P1",
        ),
        (
            "wipe-decisions",
            [],
            {"confirm": True},
            "Should wipe decisions with confirmation",
            "P1",
        ),
    ]


def define_utility_tests() -> List[Tuple[str, List[str], Dict, str, str]]:
    """Define P2 (utility/advanced) tests."""
    return [
        (
            "install-deps",
            [],
            {},
            "Should show dependency status",
            "P2",
        ),
        (
            "walk-forward",
            ["BTCUSD"],
            {
                "start-date": "2024-01-01",
                "end-date": "2024-01-31",
                "train-ratio": "0.7",
            },
            "Should run walk-forward analysis",
            "P2",
        ),
        (
            "monte-carlo",
            ["BTCUSD"],
            {
                "start-date": "2024-01-01",
                "end-date": "2024-01-31",
                "simulations": "10",
            },
            "Should run monte-carlo simulation",
            "P2",
        ),
        (
            "learning-report",
            [],
            {},
            "Should generate learning report",
            "P2",
        ),
    ]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Finance Feedback Engine - CLI QA Test Harness"
    )
    parser.add_argument(
        "--config",
        default="config/config.test.mock.yaml",
        help="Config file to use (default: config.test.mock.yaml)",
    )
    parser.add_argument(
        "--output",
        default="qa_results.json",
        help="Output JSON file for results (default: qa_results.json)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--command",
        help="Run only specific command (e.g., 'analyze')",
    )
    parser.add_argument(
        "--level",
        choices=["P0", "P1", "P2"],
        help="Run only tests of specified level",
    )

    args = parser.parse_args()

    # Initialize harness
    harness = CLITestHarness(config_path=args.config, verbose=args.verbose)

    # Define test suite
    test_cases = []
    test_cases.extend(define_core_command_tests())
    test_cases.extend(define_workflow_tests())
    test_cases.extend(define_utility_tests())

    # Filter tests if needed
    if args.command:
        test_cases = [t for t in test_cases if t[0] == args.command]
    if args.level:
        test_cases = [t for t in test_cases if t[4] == args.level]

    print(f"Running {len(test_cases)} test(s)...")

    # Execute tests
    for command, cmd_args, flags, expected, severity in test_cases:
        should_pass = "fail" not in expected.lower() and "invalid" not in expected.lower()
        result = harness.test_command(
            command, cmd_args, flags, expected, severity, should_pass=should_pass
        )

        status_symbol = "✓" if result.result_status == "PASS" else "✗"
        print(
            f"{status_symbol} {command} {' '.join(cmd_args)}: {result.result_status} ({result.execution_time:.2f}s)"
        )

    # Save and display results
    harness.save_results(args.output)
    harness.print_summary()


if __name__ == "__main__":
    main()
