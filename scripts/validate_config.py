#!/usr/bin/env python3
"""
Configuration Validation CLI

Provides a simple command-line interface for validating Finance Feedback Engine
configuration files. Can be integrated into CI/CD pipelines.

Usage:
    python scripts/validate_config.py config/config.yaml --environment production
    python scripts/validate_config.py --all
    python scripts/validate_config.py --check-secrets
"""

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import validator module directly without importing the main package
import importlib.util

validator_path = (
    Path(__file__).parent.parent
    / "finance_feedback_engine"
    / "utils"
    / "config_validator.py"
)
spec = importlib.util.spec_from_file_location("config_validator", validator_path)
config_validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_validator)

validate_config_file = config_validator.validate_config_file
print_validation_results = config_validator.print_validation_results
ConfigValidator = config_validator.ConfigValidator
Severity = config_validator.Severity


def validate_all_configs() -> Tuple[bool, List[str]]:
    """
    Validate all configuration files in the config directory

    Returns:
        (all_valid, failed_configs) tuple
    """
    config_dir = Path("config")
    config_files = [
        ("config/config.yaml", "production"),
        ("config/config.test.mock.yaml", "test"),
        ("config/config.backtest.yaml", "development"),
    ]

    # Add example configs
    if (config_dir / "examples").exists():
        for example_file in (config_dir / "examples").glob("*.yaml"):
            config_files.append((str(example_file), "development"))

    all_valid = True
    failed_configs = []

    print("=" * 70)
    print("Validating All Configuration Files")
    print("=" * 70)
    print()

    for config_path, env in config_files:
        if not Path(config_path).exists():
            print(f"⚠️  Skipping {config_path} (not found)")
            continue

        print(f"Checking: {config_path} (environment: {env})")
        print("-" * 70)

        result = validate_config_file(config_path, environment=env)

        if not result.valid:
            all_valid = False
            failed_configs.append(config_path)
            print(f"❌ FAILED - {len(result.issues)} issues found")

            # Show critical issues immediately
            critical = result.get_critical_issues()
            if critical:
                print(f"\n  Critical Issues ({len(critical)}):")
                for issue in critical[:3]:  # Show first 3
                    print(f"    • {issue.message}")
                if len(critical) > 3:
                    print(f"    ... and {len(critical) - 3} more")
        else:
            issue_count = len(result.issues)
            if issue_count > 0:
                print(f"⚠️  PASSED with {issue_count} warnings")
            else:
                print(f"✅ PASSED - No issues")

        print()

    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print(
        f"Total configs checked: {len([c for c, _ in config_files if Path(c).exists()])}"
    )
    print(
        f"Passed: {len([c for c, _ in config_files if Path(c).exists()]) - len(failed_configs)}"
    )
    print(f"Failed: {len(failed_configs)}")

    if failed_configs:
        print("\nFailed configurations:")
        for config in failed_configs:
            print(f"  - {config}")

    return all_valid, failed_configs


def check_for_secrets() -> bool:
    """
    Check all configuration files for exposed secrets

    Returns:
        True if no secrets found, False otherwise
    """
    import subprocess

    print("=" * 70)
    print("Checking for Exposed Secrets")
    print("=" * 70)
    print()

    hook_path = Path(".pre-commit-hooks/prevent-secrets.py")

    if not hook_path.exists():
        print(f"❌ Secret detection hook not found: {hook_path}")
        print("   Run configuration validation setup first")
        return False

    try:
        result = subprocess.run(
            ["python", str(hook_path)], capture_output=True, text=True
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Error running secret detection: {e}")
        return False


def validate_single_config(
    config_path: str, environment: str, verbose: bool = True
) -> bool:
    """
    Validate a single configuration file

    Args:
        config_path: Path to configuration file
        environment: Target environment
        verbose: Show all issues or just critical/high

    Returns:
        True if valid, False otherwise
    """
    result = validate_config_file(config_path, environment=environment)
    print_validation_results(result, verbose=verbose)
    return result.valid


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Validate Finance Feedback Engine configuration files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single config for production
  %(prog)s config/config.yaml --environment production

  # Validate all configs
  %(prog)s --all

  # Check for exposed secrets
  %(prog)s --check-secrets

  # Validate with verbose output
  %(prog)s config/config.yaml -e development --verbose

  # Exit with error code on validation failure (for CI/CD)
  %(prog)s config/config.yaml -e production --exit-on-error
        """,
    )

    parser.add_argument(
        "config_file", nargs="?", help="Path to configuration file to validate"
    )

    parser.add_argument(
        "--environment",
        "-e",
        default="development",
        choices=["production", "staging", "development", "test"],
        help="Target environment (default: development)",
    )

    parser.add_argument(
        "--all", action="store_true", help="Validate all configuration files"
    )

    parser.add_argument(
        "--check-secrets",
        action="store_true",
        help="Check for exposed secrets in all files",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all issues including low severity",
    )

    parser.add_argument(
        "--exit-on-error",
        action="store_true",
        help="Exit with code 1 if validation fails",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (only show pass/fail)",
    )

    args = parser.parse_args()

    # Determine what to do
    if args.all:
        all_valid, failed = validate_all_configs()
        if args.exit_on_error and not all_valid:
            sys.exit(1)
        sys.exit(0 if all_valid else 1)

    elif args.check_secrets:
        secrets_ok = check_for_secrets()
        if args.exit_on_error and not secrets_ok:
            sys.exit(1)
        sys.exit(0 if secrets_ok else 1)

    elif args.config_file:
        is_valid = validate_single_config(
            args.config_file, args.environment, verbose=args.verbose
        )

        if args.exit_on_error and not is_valid:
            sys.exit(1)

        sys.exit(0 if is_valid else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
