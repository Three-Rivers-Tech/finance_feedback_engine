#!/usr/bin/env python3
"""
Pre-commit Hook Management Script
Helps gradually tighten pre-commit hooks without disrupting development.
"""

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path



class PreCommitManager:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.configs = {
            "minimal": ".pre-commit-config-progressive.yaml",
            "current": ".pre-commit-config.yaml",
            "enhanced": ".pre-commit-config-enhanced.yaml",
        }

    def get_current_phase(self):
        """Determine current pre-commit phase based on active config."""
        current_config_path = self.root_dir / ".pre-commit-config.yaml"

        if not current_config_path.exists():
            return "none", "No pre-commit config found"

        with open(current_config_path) as f:
            content = f.read()

        # Check for phase indicators
        if "PHASE 1: ESSENTIAL CHECKS ONLY" in content:
            if "# # Basic Python linting" in content:
                return "phase1", "Phase 1: Essential checks only (formatting)"
            elif "# Security scanning" in content:
                return "phase2", "Phase 2: Basic linting enabled"
            elif "# Run critical tests" in content:
                return "phase3", "Phase 3: Security & type checks enabled"
            else:
                return "phase4", "Phase 4: Test runner enabled"
        elif "Enhanced Pre-commit Hooks Configuration" in content:
            return "enhanced", "Full enhanced configuration active"
        else:
            return "custom", "Custom configuration"

    def backup_current(self):
        """Backup current pre-commit config."""
        current = self.root_dir / ".pre-commit-config.yaml"
        if current.exists():
            backup_name = f".pre-commit-config.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
            backup_path = self.root_dir / backup_name
            shutil.copy2(current, backup_path)
            print(f"✅ Backed up current config to {backup_name}")
            return backup_path
        return None

    def set_phase(self, phase: int):
        """Set pre-commit to a specific phase."""
        if phase < 1 or phase > 4:
            print("❌ Invalid phase. Must be 1-4")
            return False

        # Backup current
        self.backup_current()

        # Copy progressive config
        progressive = self.root_dir / self.configs["minimal"]
        current = self.root_dir / ".pre-commit-config.yaml"

        with open(progressive) as f:
            lines = f.readlines()

        # Uncomment appropriate phases
        new_lines = []
        in_phase = 0
        for line in lines:
            if "PHASE 2:" in line:
                in_phase = 2
            elif "PHASE 3:" in line:
                in_phase = 3
            elif "PHASE 4:" in line:
                in_phase = 4
            elif "LOCAL HOOKS" in line or "Configuration" in line:
                in_phase = 0

            # Uncomment if in active phase
            if in_phase > 0 and in_phase <= phase:
                if line.strip().startswith("# ") and not line.strip().startswith("# ="):
                    line = line.replace("# ", "", 1)

            new_lines.append(line)

        with open(current, "w") as f:
            f.writelines(new_lines)

        print(f"✅ Set pre-commit to Phase {phase}")

        # Reinstall hooks
        self.install_hooks()
        return True

    def install_hooks(self):
        """Install pre-commit hooks."""
        try:
            subprocess.run(["pre-commit", "install"], check=True, capture_output=True)
            print("✅ Pre-commit hooks installed")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install hooks: {e}")
            return False

    def run_hooks(self, all_files=False):
        """Run pre-commit hooks."""
        cmd = ["pre-commit", "run"]
        if all_files:
            cmd.append("--all-files")

        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode == 0

    def check_violations(self):
        """Check for violations without modifying files."""
        print("\n🔍 Checking for pre-commit violations...")

        # Run with --all-files but don't modify
        result = subprocess.run(
            ["pre-commit", "run", "--all-files", "--show-diff-on-failure"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print("✅ No violations found!")
            return True
        else:
            print("⚠️  Violations found:")
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return False

    def status(self):
        """Show current pre-commit status."""
        print("\n" + "=" * 60)
        print("PRE-COMMIT STATUS")
        print("=" * 60)

        phase, description = self.get_current_phase()
        print(f"\nCurrent Phase: {description}")

        # Check if hooks are installed
        git_hooks = self.root_dir / ".git/hooks/pre-commit"
        if git_hooks.exists():
            print("✅ Hooks installed")
        else:
            print("❌ Hooks not installed (run: pre-commit install)")

        # List available configs
        print("\nAvailable Configurations:")
        for name, path in self.configs.items():
            full_path = self.root_dir / path
            if full_path.exists():
                print(f"  - {name}: {path}")

        # Show recent violations
        print("\nChecking current violations...")
        self.check_violations()

    def gradual_tighten(self):
        """Gradually tighten pre-commit hooks based on test results."""
        print("\n" + "=" * 60)
        print("GRADUAL TIGHTENING ANALYSIS")
        print("=" * 60)

        phase, description = self.get_current_phase()
        print(f"\nCurrent: {description}")

        # Check if we can move to next phase
        if phase == "none":
            print("\n📝 Recommendation: Start with Phase 1")
            print("  - Basic formatting (Black, isort)")
            print("  - File hygiene (trailing whitespace, EOF)")
            print("  - Security (detect private keys)")
            print("\nRun: python scripts/manage_precommit.py set-phase 1")

        elif phase == "phase1":
            print("\n📝 Checking readiness for Phase 2...")
            # Check if formatting is stable
            if self.check_violations():
                print("✅ Ready for Phase 2: Add basic linting")
                print("\nRun: python scripts/manage_precommit.py set-phase 2")
            else:
                print("❌ Fix Phase 1 violations first")

        elif phase == "phase2":
            print("\n📝 Checking readiness for Phase 3...")
            if self.check_violations():
                print("✅ Ready for Phase 3: Add security & type checks")
                print("\nRun: python scripts/manage_precommit.py set-phase 3")
            else:
                print("❌ Fix Phase 2 violations first")

        elif phase == "phase3":
            print("\n📝 Checking readiness for Phase 4...")
            # Check if tests are passing
            print("Checking test status...")
            test_result = subprocess.run(
                ["python", "-m", "pytest", "--co", "-q"], capture_output=True
            )
            if test_result.returncode == 0:
                print("✅ Tests collected successfully")
                print("✅ Ready for Phase 4: Add test runner")
                print("\nRun: python scripts/manage_precommit.py set-phase 4")
            else:
                print("❌ Fix test collection issues first")

        elif phase == "phase4":
            print("\n✅ All phases active!")
            print("Consider moving to enhanced config when ready:")
            print("  cp .pre-commit-config-enhanced.yaml .pre-commit-config.yaml")

        else:
            print("\n⚠️  Custom configuration detected")


def main():
    parser = argparse.ArgumentParser(
        description="Manage pre-commit hooks progressively"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Status command
    subparsers.add_parser("status", help="Show current pre-commit status")

    # Set phase command
    set_phase_parser = subparsers.add_parser("set-phase", help="Set pre-commit phase")
    set_phase_parser.add_argument(
        "phase", type=int, choices=[1, 2, 3, 4], help="Phase number (1-4)"
    )

    # Check command
    subparsers.add_parser("check", help="Check for violations")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run pre-commit hooks")
    run_parser.add_argument("--all", action="store_true", help="Run on all files")

    # Gradual command
    subparsers.add_parser("gradual", help="Analyze and recommend next steps")

    # Install command
    subparsers.add_parser("install", help="Install pre-commit hooks")

    args = parser.parse_args()

    manager = PreCommitManager()

    if args.command == "status":
        manager.status()
    elif args.command == "set-phase":
        manager.set_phase(args.phase)
    elif args.command == "check":
        manager.check_violations()
    elif args.command == "run":
        manager.run_hooks(all_files=args.all)
    elif args.command == "gradual":
        manager.gradual_tighten()
    elif args.command == "install":
        manager.install_hooks()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
