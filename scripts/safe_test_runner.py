#!/usr/bin/env python3
"""
Safe Test Runner - Runs tests individually to identify crash-causing tests
without crashing the IDE or system.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class SafeTestRunner:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.results = []
        self.crash_tests = []
        self.resource_leak_tests = []
        self.passing_tests = []
        self.failing_tests = []

    def run_single_test(self, test_path: str) -> Dict[str, Any]:
        """Run a single test file with timeout and resource monitoring."""
        print(f"\n{'='*60}")
        print(f"Testing: {test_path}")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")

        result = {
            "test": test_path,
            "status": "unknown",
            "duration": 0,
            "errors": [],
            "warnings": [],
        }

        # Run test with timeout and capture output
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_path,
            "-v",
            "--tb=short",
            "--capture=no",
            "-W",
            "error::ResourceWarning",
            "--timeout",
            str(self.timeout),
            "--timeout-method=thread",
            "-p",
            "no:cacheprovider",  # Disable cache to avoid corruption
        ]

        start_time = time.time()
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 5,  # Extra buffer
            )

            duration = time.time() - start_time
            result["duration"] = duration

            # Check for resource warnings
            if "ResourceWarning" in process.stderr:
                result["warnings"].append("Resource leak detected")
                self.resource_leak_tests.append(test_path)

            # Check for unclosed sessions
            if "Unclosed" in process.stderr or "unclosed" in process.stderr:
                result["warnings"].append("Unclosed session detected")
                self.resource_leak_tests.append(test_path)

            # Check exit code
            if process.returncode == 0:
                result["status"] = "passed"
                self.passing_tests.append(test_path)
                print(f"✅ PASSED in {duration:.2f}s")
            else:
                result["status"] = "failed"
                self.failing_tests.append(test_path)
                print(f"❌ FAILED in {duration:.2f}s")

                # Extract error summary
                if "FAILED" in process.stdout:
                    lines = process.stdout.split("\n")
                    for line in lines:
                        if "FAILED" in line or "ERROR" in line:
                            result["errors"].append(line.strip())

        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["errors"].append(f"Test timed out after {self.timeout}s")
            self.crash_tests.append(test_path)
            print(f"⏱️ TIMEOUT after {self.timeout}s - Potential crash!")

        except Exception as e:
            result["status"] = "crash"
            result["errors"].append(str(e))
            self.crash_tests.append(test_path)
            print(f"💥 CRASH: {e}")

        self.results.append(result)
        return result

    def discover_test_files(self, test_dir: str = "tests") -> List[str]:
        """Discover all test files in the test directory."""
        test_files = []
        test_path = Path(test_dir)

        if test_path.exists():
            # Get all test files
            for file in test_path.rglob("test_*.py"):
                test_files.append(str(file))

            # Also include conftest.py files
            for file in test_path.rglob("conftest.py"):
                test_files.append(str(file))

        return sorted(test_files)

    def run_priority_tests(self):
        """Run high-priority tests that are likely causing crashes."""
        priority_tests = [
            "tests/conftest.py",
            "tests/test_data_providers_comprehensive.py",
            "tests/test_core_integration.py",
            "tests/test_api.py",
            "tests/test_ensemble_error_propagation.py",
            "tests/test_critical_fixes_integration.py",
        ]

        print("\n" + "=" * 60)
        print("RUNNING PRIORITY TESTS (Likely crash culprits)")
        print("=" * 60)

        for test in priority_tests:
            if os.path.exists(test):
                self.run_single_test(test)
                # Add delay between tests to allow cleanup
                time.sleep(2)

    def run_all_tests(self):
        """Run all tests one by one."""
        test_files = self.discover_test_files()

        print(f"\nFound {len(test_files)} test files")
        print("=" * 60)

        for i, test in enumerate(test_files, 1):
            print(f"\nProgress: {i}/{len(test_files)}")
            self.run_single_test(test)
            # Add delay between tests to allow cleanup
            time.sleep(1)

    def generate_report(self):
        """Generate a detailed report of test results."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "passed": len(self.passing_tests),
                "failed": len(self.failing_tests),
                "crashed": len(self.crash_tests),
                "resource_leaks": len(set(self.resource_leak_tests)),
            },
            "crash_tests": self.crash_tests,
            "resource_leak_tests": list(set(self.resource_leak_tests)),
            "details": self.results,
        }

        # Save JSON report
        with open("test_analysis_report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Generate markdown report
        self.generate_markdown_report(report)

        return report

    def generate_markdown_report(self, report: Dict[str, Any]):
        """Generate a markdown report."""
        md_content = f"""# Safe Test Runner Report

**Generated**: {report['timestamp']}

## Summary

- **Total Tests**: {report['summary']['total']}
- **Passed**: {report['summary']['passed']} ✅
- **Failed**: {report['summary']['failed']} ❌
- **Crashed/Timeout**: {report['summary']['crashed']} 💥
- **Resource Leaks**: {report['summary']['resource_leaks']} ⚠️

## Critical Issues

### Tests Causing Crashes/Timeouts
"""

        if report["crash_tests"]:
            for test in report["crash_tests"]:
                md_content += f"- `{test}`\n"
        else:
            md_content += "- None found ✅\n"

        md_content += "\n### Tests with Resource Leaks\n"

        if report["resource_leak_tests"]:
            for test in report["resource_leak_tests"]:
                md_content += f"- `{test}`\n"
        else:
            md_content += "- None found ✅\n"

        md_content += "\n## Detailed Results\n\n"

        # Group by status
        for status in ["crash", "timeout", "failed", "passed"]:
            tests = [r for r in report["details"] if r["status"] == status]
            if tests:
                md_content += f"\n### {status.upper()} ({len(tests)})\n\n"
                for test in tests[:10]:  # Show first 10
                    md_content += f"- `{test['test']}` ({test['duration']:.2f}s)\n"
                    if test["errors"]:
                        md_content += f"  - Error: {test['errors'][0][:100]}...\n"

        with open("SAFE_TEST_REPORT.md", "w") as f:
            f.write(md_content)

        print("\n" + "=" * 60)
        print("REPORT GENERATED")
        print("=" * 60)
        print("✅ JSON Report: test_analysis_report.json")
        print("✅ Markdown Report: SAFE_TEST_REPORT.md")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Safe Test Runner")
    parser.add_argument(
        "--mode",
        choices=["priority", "all", "single"],
        default="priority",
        help="Test mode: priority (high-risk tests), all (all tests), single (one test)",
    )
    parser.add_argument("--test", help="Specific test file to run (for single mode)")
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout per test in seconds (default: 30)",
    )

    args = parser.parse_args()

    runner = SafeTestRunner(timeout=args.timeout)

    try:
        if args.mode == "single" and args.test:
            runner.run_single_test(args.test)
        elif args.mode == "priority":
            runner.run_priority_tests()
        elif args.mode == "all":
            response = input("⚠️  This will run ALL tests. Continue? (y/n): ")
            if response.lower() == "y":
                runner.run_all_tests()
            else:
                print("Aborted.")
                return

        # Generate report
        report = runner.generate_report()

        # Print summary
        print("\n" + "=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)
        print(f"Total: {report['summary']['total']}")
        print(f"Passed: {report['summary']['passed']} ✅")
        print(f"Failed: {report['summary']['failed']} ❌")
        print(f"Crashed: {report['summary']['crashed']} 💥")
        print(f"Resource Leaks: {report['summary']['resource_leaks']} ⚠️")

        if report["crash_tests"]:
            print("\n⚠️  CRITICAL: Found tests that crash/timeout!")
            print("These tests need immediate attention:")
            for test in report["crash_tests"][:5]:
                print(f"  - {test}")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Generating partial report...")
        runner.generate_report()


if __name__ == "__main__":
    main()
