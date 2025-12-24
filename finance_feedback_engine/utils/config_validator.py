"""
Configuration Validation System for Finance Feedback Engine 2.0

This module provides comprehensive validation for YAML configuration files,
including schema validation, security checks, and environment-specific rules.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Validation issue severity levels"""

    CRITICAL = "critical"  # Security vulnerabilities, exposed secrets
    HIGH = "high"  # Configuration errors that will cause failures
    MEDIUM = "medium"  # Suboptimal configurations
    LOW = "low"  # Style issues, recommendations
    INFO = "info"  # Informational messages


@dataclass
class ValidationIssue:
    """Represents a configuration validation issue"""

    severity: Severity
    rule: str
    message: str
    file_path: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Results from configuration validation"""

    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)

    def add_issue(
        self,
        severity: Severity,
        rule: str,
        message: str,
        file_path: str,
        line_number: Optional[int] = None,
        suggestion: Optional[str] = None,
    ):
        """Add a validation issue"""
        self.issues.append(
            ValidationIssue(
                severity=severity,
                rule=rule,
                message=message,
                file_path=file_path,
                line_number=line_number,
                suggestion=suggestion,
            )
        )
        # Mark as invalid if critical or high severity
        if severity in [Severity.CRITICAL, Severity.HIGH]:
            self.valid = False

    def get_critical_issues(self) -> List[ValidationIssue]:
        """Get all critical severity issues"""
        return [i for i in self.issues if i.severity == Severity.CRITICAL]

    def get_high_issues(self) -> List[ValidationIssue]:
        """Get all high severity issues"""
        return [i for i in self.issues if i.severity == Severity.HIGH]

    def has_errors(self) -> bool:
        """Check if there are any critical or high severity issues"""
        return len(self.get_critical_issues()) > 0 or len(self.get_high_issues()) > 0


class ConfigValidator:
    """
    Comprehensive configuration validator for Finance Feedback Engine 2.0

    Validates:
    - Schema correctness
    - Security issues (exposed secrets)
    - Environment-specific rules
    - Consistency across configs
    - Best practices
    """

    # Pattern to detect potential secrets (case-insensitive)
    SECRET_PATTERNS = {
        "api_key": r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?',
        "secret": r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?([a-zA-Z0-9\-_@#$%^&*]{8,})["\']?',
        "token": r'(?i)(token|auth[_-]?token)\s*[:=]\s*["\']?([a-zA-Z0-9\-_]{20,})["\']?',
        "telegram_token": r'(?i)(telegram[_-]?token|bot[_-]?token)\s*[:=]\s*["\']?(\d+:[A-Za-z0-9_-]{35})["\']?',
        "telegram_token_alt": r"\b\d+:[A-Za-z0-9_-]{35}\b",  # Telegram token pattern: digits:35chars
        "private_key": r"(?i)(BEGIN\s+(?:RSA|EC|OPENSSH)\s+PRIVATE\s+KEY)",
        "aws_access": r'(?i)(aws[_-]?access[_-]?key[_-]?id)\s*[:=]\s*["\']?(AKIA[0-9A-Z]{16})["\']?',
        "bearer_token": r"(?i)Bearer\s+[a-zA-Z0-9\-_\.]{20,}",
    }

    # Placeholder/example values that are safe
    SAFE_PLACEHOLDERS = {
        "YOUR_ALPHA_VANTAGE_API_KEY",
        "YOUR_COINBASE_API_KEY",
        "YOUR_COINBASE_API_SECRET",
        "YOUR_COINBASE_PASSPHRASE",
        "YOUR_OANDA_API_TOKEN",
        "YOUR_OANDA_ACCOUNT_ID",
        "demo",
        "default",
        "REPLACE_WITH_",
        "your_",
        "my_secret_key_123",  # Example from docs
    }

    # Environment-specific rules
    ENVIRONMENT_RULES = {
        "production": {
            "allow_debug": False,
            "require_https": True,
            "require_strong_passwords": True,
            "min_password_length": 16,
            "allow_sandbox": False,
            "allow_mock_platform": False,
        },
        "staging": {
            "allow_debug": False,
            "require_https": True,
            "require_strong_passwords": True,
            "min_password_length": 12,
            "allow_sandbox": True,
            "allow_mock_platform": False,
        },
        "development": {
            "allow_debug": True,
            "require_https": False,
            "require_strong_passwords": False,
            "min_password_length": 8,
            "allow_sandbox": True,
            "allow_mock_platform": True,
        },
        "test": {
            "allow_debug": True,
            "require_https": False,
            "require_strong_passwords": False,
            "min_password_length": 1,
            "allow_sandbox": True,
            "allow_mock_platform": True,
        },
    }

    def __init__(self, environment: str = "development"):
        """
        Initialize the configuration validator

        Args:
            environment: Target environment (production, staging, development, test)
        """
        self.environment = environment
        self.rules = self.ENVIRONMENT_RULES.get(
            environment, self.ENVIRONMENT_RULES["development"]
        )

    def validate_file(self, config_path: str) -> ValidationResult:
        """
        Validate a single configuration file

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            ValidationResult with all identified issues
        """
        result = ValidationResult(valid=True)

        try:
            resolved_path = Path(config_path).expanduser().resolve(strict=False)
        except Exception as e:
            result.add_issue(
                Severity.CRITICAL,
                "invalid_path",
                f"Invalid configuration path: {config_path} ({e})",
                config_path,
            )
            return result

        if not resolved_path.is_file():
            result.add_issue(
                Severity.CRITICAL,
                "file_not_found",
                f"Configuration file not found: {resolved_path}",
                str(resolved_path),
            )
            return result

        # Optional: enforce YAML extension
        if resolved_path.suffix not in {".yaml", ".yml"}:
            result.add_issue(
                Severity.HIGH,
                "invalid_extension",
                "Configuration file must be .yaml or .yml",
                str(resolved_path),
            )

        # Load and parse YAML
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                content = f.read()
                config = yaml.safe_load(content)
        except yaml.YAMLError as e:
            result.add_issue(
                Severity.CRITICAL,
                "yaml_parse_error",
                f"Failed to parse YAML: {str(e)}",
                str(resolved_path),
            )
            return result
        except Exception as e:
            result.add_issue(
                Severity.CRITICAL,
                "file_read_error",
                f"Failed to read file: {str(e)}",
                str(resolved_path),
            )
            return result

        # Run validation checks
        self._check_secrets(str(resolved_path), content, result)
        self._check_schema(config, str(resolved_path), result)
        self._check_environment_rules(config, str(resolved_path), result)
        self._check_best_practices(config, str(resolved_path), result)
        self._check_logging_configuration(config, str(resolved_path), result)
        self._check_env_var_naming(str(resolved_path), content, result)

        return result

    def _check_secrets(self, config_path: str, content: str, result: ValidationResult):
        """Check for exposed secrets in configuration content"""
        lines = content.split("\n")

        for pattern_name, pattern in self.SECRET_PATTERNS.items():
            for line_num, line in enumerate(lines, 1):
                # Skip comments
                if line.strip().startswith("#"):
                    continue

                matches = re.finditer(pattern, line)
                for match in matches:
                    # Extract the value (usually in group 2 for most patterns)
                    try:
                        value = (
                            match.group(2)
                            if len(match.groups()) >= 2
                            else match.group(0)
                        )
                    except Exception:
                        value = match.group(0)

                    # Check if it's a safe placeholder
                    is_safe = any(
                        placeholder.lower() in value.lower()
                        for placeholder in self.SAFE_PLACEHOLDERS
                    )

                    # Check if it's an environment variable reference
                    is_env_var = "${" in line or "$ENV" in line or value.startswith("$")

                    if not is_safe and not is_env_var:
                        result.add_issue(
                            Severity.CRITICAL,
                            "exposed_secret",
                            f"Potential exposed secret detected ({pattern_name}): {value[:20]}...",
                            config_path,
                            line_num,
                            "Use environment variables: ${ENV_VAR_NAME} instead of hardcoded values",
                        )

    def _check_env_var_naming(
        self, config_path: str, content: str, result: ValidationResult
    ):
        """
        Check for proper environment variable naming conventions.

        Validates:
        - Environment variables use hierarchical subsystem prefixes
        - No old-style placeholder patterns (bare UPPERCASE_NAMES without ${})
        - Proper ${ENV_VAR} syntax is used
        """
        lines = content.split("\n")

        # Pattern for old-style placeholders (UPPERCASE with no ${} wrapper)
        # But exclude YAML structural keywords and proper env var references
        old_placeholder_pattern = re.compile(r":\s+([A-Z][A-Z_0-9]+)\s*$")

        # Expected subsystem prefixes for hierarchical naming
        valid_prefixes = {
            "ALPHA_VANTAGE_",
            "TRADING_PLATFORM_",
            "COINBASE_",
            "OANDA_",
            "DECISION_ENGINE_",
            "ENSEMBLE_",
            "TWO_PHASE_",
            "MONITORING_",
            "PERSISTENCE_",
            "PORTFOLIO_MEMORY_",
            "TELEGRAM_",
            "BACKTESTING_",
            "SAFETY_",
            "CIRCUIT_BREAKER_",
            "SIGNAL_ONLY_",
            "LOGGING_",
            "AGENT_",
            "API_AUTH_",
            "API_TIMEOUT_",
            "BENCHMARK_",
            "REFACTORING_",
            "OPTIMIZATION_",
        }

        for line_num, line in enumerate(lines, 1):
            # Skip comments and empty lines
            if line.strip().startswith("#") or not line.strip():
                continue

            # Check for old-style placeholders (e.g., "autonomous_execution: AUTO_EXC")
            old_match = old_placeholder_pattern.search(line)
            if old_match:
                placeholder = old_match.group(1)
                # Ignore safe YAML values like "true", "false", "INFO", "balanced"
                if placeholder not in {
                    "TRUE",
                    "FALSE",
                    "INFO",
                    "DEBUG",
                    "WARNING",
                    "ERROR",
                }:
                    result.add_issue(
                        Severity.HIGH,
                        "old_placeholder_pattern",
                        f"Old-style placeholder detected: '{placeholder}' (should use ${{ENV_VAR}} syntax)",
                        config_path,
                        line_num,
                        f"Replace with: ${{{placeholder}}} or use proper hierarchical naming from .env.example",
                    )

            # Check env var references for proper naming (inside ${...})
            env_var_refs = re.findall(r"\$\{([^}]+)\}", line)
            for env_var in env_var_refs:
                # Extract base name (without :default syntax)
                base_name = env_var.split(":")[0].strip()

                # Check if it has a valid subsystem prefix
                has_valid_prefix = any(
                    base_name.startswith(prefix) for prefix in valid_prefixes
                )

                if not has_valid_prefix:
                    result.add_issue(
                        Severity.MEDIUM,
                        "missing_subsystem_prefix",
                        f"Environment variable '{base_name}' lacks subsystem prefix",
                        config_path,
                        line_num,
                        f"Use hierarchical naming (e.g., SUBSYSTEM_{base_name}) to avoid collisions. See .env.example for naming conventions.",
                    )

    def _check_schema(self, config: Dict, config_path: str, result: ValidationResult):
        """Validate configuration schema"""
        if not config:
            result.add_issue(
                Severity.HIGH,
                "empty_config",
                "Configuration file is empty",
                config_path,
            )
            return

        # Check required top-level keys
        required_keys = ["decision_engine", "persistence"]
        for key in required_keys:
            if key not in config:
                result.add_issue(
                    Severity.HIGH,
                    "missing_required_key",
                    f"Missing required configuration key: {key}",
                    config_path,
                    suggestion=f'Add "{key}:" section to your configuration',
                )

        # Validate decision_engine section
        if "decision_engine" in config:
            de = config["decision_engine"]
            if "ai_provider" not in de:
                result.add_issue(
                    Severity.HIGH,
                    "missing_ai_provider",
                    "Missing ai_provider in decision_engine configuration",
                    config_path,
                    suggestion='Add ai_provider: "local" (or cli, ensemble, etc.)',
                )

            # Validate threshold values
            if "decision_threshold" in de:
                threshold = de["decision_threshold"]
                if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                    result.add_issue(
                        Severity.MEDIUM,
                        "invalid_threshold",
                        f"decision_threshold must be between 0.0 and 1.0, got: {threshold}",
                        config_path,
                    )

        # Validate ensemble configuration if using ensemble provider
        if config.get("decision_engine", {}).get("ai_provider") == "ensemble":
            if "ensemble" not in config:
                result.add_issue(
                    Severity.HIGH,
                    "missing_ensemble_config",
                    "Using ensemble provider but ensemble configuration is missing",
                    config_path,
                    suggestion='Add "ensemble:" section with enabled_providers and provider_weights',
                )
            else:
                self._validate_ensemble_config(config["ensemble"], config_path, result)

    def _validate_ensemble_config(
        self, ensemble: Dict, config_path: str, result: ValidationResult
    ):
        """Validate ensemble-specific configuration"""
        # Check provider weights sum to 1.0
        if "provider_weights" in ensemble:
            weights = ensemble["provider_weights"]
            if isinstance(weights, dict):
                total_weight = sum(weights.values())
                if (
                    not 0.99 <= total_weight <= 1.01
                ):  # Allow small floating point errors
                    result.add_issue(
                        Severity.MEDIUM,
                        "invalid_weight_sum",
                        f"Provider weights should sum to 1.0, got: {total_weight:.4f}",
                        config_path,
                        suggestion="Adjust provider_weights to sum to exactly 1.0",
                    )

        # Check enabled_providers exist
        if "enabled_providers" not in ensemble:
            result.add_issue(
                Severity.HIGH,
                "missing_enabled_providers",
                "Ensemble configuration missing enabled_providers list",
                config_path,
            )

        # Validate agreement threshold
        if "agreement_threshold" in ensemble:
            threshold = ensemble["agreement_threshold"]
            if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                result.add_issue(
                    Severity.MEDIUM,
                    "invalid_agreement_threshold",
                    f"agreement_threshold must be between 0.0 and 1.0, got: {threshold}",
                    config_path,
                )

    def _check_environment_rules(
        self, config: Dict, config_path: str, result: ValidationResult
    ):
        """Check environment-specific validation rules"""
        # Check debug mode
        if not self.rules["allow_debug"]:
            # Check in decision_engine
            if config.get("decision_engine", {}).get("debug", False):
                result.add_issue(
                    Severity.CRITICAL,
                    "debug_in_production",
                    f"Debug mode is not allowed in {self.environment} environment",
                    config_path,
                    suggestion="Set debug: false or remove the debug setting",
                )

        # Check sandbox mode
        if not self.rules["allow_sandbox"]:
            if config.get("platform_credentials", {}).get("use_sandbox", False):
                result.add_issue(
                    Severity.HIGH,
                    "sandbox_in_production",
                    f"Sandbox mode is not allowed in {self.environment} environment",
                    config_path,
                    suggestion="Set use_sandbox: false",
                )

        # Check mock platform
        if not self.rules["allow_mock_platform"]:
            if config.get("trading_platform") == "mock":
                result.add_issue(
                    Severity.CRITICAL,
                    "mock_platform_in_production",
                    f"Mock platform is not allowed in {self.environment} environment",
                    config_path,
                    suggestion="Use a real trading platform (coinbase_advanced, oanda, etc.)",
                )

    def _check_best_practices(
        self, config: Dict, config_path: str, result: ValidationResult
    ):
        """Check configuration best practices"""
        # Check if API keys are using environment variables
        if "alpha_vantage_api_key" in config:
            api_key = config["alpha_vantage_api_key"]
            if isinstance(api_key, str) and not api_key.startswith("${"):
                # Check if it's a placeholder
                is_placeholder = any(ph in api_key for ph in self.SAFE_PLACEHOLDERS)
                if not is_placeholder:
                    result.add_issue(
                        Severity.CRITICAL,
                        "hardcoded_api_key",
                        "API key appears to be hardcoded instead of using environment variable",
                        config_path,
                        suggestion='Use: alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"',
                    )

        # Check persistence path
        if "persistence" in config and "storage_path" in config["persistence"]:
            storage_path = config["persistence"]["storage_path"]
            if isinstance(storage_path, str) and storage_path.startswith("/"):
                result.add_issue(
                    Severity.LOW,
                    "absolute_storage_path",
                    "Using absolute path for storage_path may cause portability issues",
                    config_path,
                    suggestion="Use relative path: data/decisions",
                )

        # Check for common typos in provider names
        if "ensemble" in config and "enabled_providers" in config["ensemble"]:
            valid_providers = {
                "local",
                "cli",
                "codex",
                "qwen",
                "gemini",
                "llama3.2:3b-instruct-fp16",
                "deepseek-r1:8b",
                "mistral:7b-instruct",
                "qwen2.5:7b-instruct",
                "gemma2:9b",
            }
            for provider in config["ensemble"]["enabled_providers"]:
                if isinstance(provider, str) and provider not in valid_providers:
                    # Check if it looks like a model name (contains colon)
                    if ":" not in provider and provider != "mock":
                        result.add_issue(
                            Severity.LOW,
                            "unknown_provider",
                            f"Unknown provider name: {provider}",
                            config_path,
                            suggestion=f'Valid providers: {", ".join(sorted(valid_providers))}',
                        )

    def _check_logging_configuration(
        self, config: Dict, config_path: str, result: ValidationResult
    ):
        """Check logging configuration for production environments"""
        # Check if logging is configured for production
        if self.environment == "production":
            logging_config = config.get("logging", {})

            # Check if console handler is disabled in production
            handlers = logging_config.get("handlers", {})
            if "console" in handlers:
                # Check if the console handler is for debugging only
                console_config = handlers["console"]
                if console_config.get("enabled", True) is True:
                    result.add_issue(
                        Severity.HIGH,
                        "console_logging_in_production",
                        "Console logging should be disabled in production environment",
                        config_path,
                        suggestion="Disable console logging in production to prevent sensitive data from being written to stdout",
                    )

            # Check for file-based logging in production
            has_file_handler = any(
                handler_type in handlers
                and "file" in str(handlers[handler_type]).lower()
                for handler_type in handlers
            )
            if not has_file_handler:
                result.add_issue(
                    Severity.MEDIUM,
                    "no_file_logging_in_production",
                    "Production environment should have file-based logging",
                    config_path,
                    suggestion="Configure file-based logging for persistent logs in production",
                )

            # Check log level is appropriate for production
            root_config = logging_config.get("root", {})
            log_level = root_config.get("level", "INFO")
            if log_level.upper() == "DEBUG":
                result.add_issue(
                    Severity.HIGH,
                    "debug_logging_in_production",
                    "DEBUG log level should not be used in production environment",
                    config_path,
                    suggestion="Set log level to INFO, WARNING, or ERROR for production",
                )


def validate_config_file(
    config_path: str, environment: str = "development"
) -> ValidationResult:
    """
    Convenience function to validate a configuration file

    Args:
        config_path: Path to the configuration file
        environment: Target environment (production, staging, development, test)

    Returns:
        ValidationResult with all identified issues
    """
    validator = ConfigValidator(environment=environment)
    return validator.validate_file(config_path)


def print_validation_results(result: ValidationResult, verbose: bool = True):
    """
    Print validation results in a human-readable format

    Args:
        result: ValidationResult to print
        verbose: If True, show all issues; if False, show only critical/high
    """
    if result.valid and not result.issues:
        print("✓ Configuration validation passed with no issues")
        return

    # Group issues by severity
    issues_by_severity = {}
    for issue in result.issues:
        if issue.severity not in issues_by_severity:
            issues_by_severity[issue.severity] = []
        issues_by_severity[issue.severity].append(issue)

    # Print summary
    total_issues = len(result.issues)
    critical_count = len(result.get_critical_issues())
    high_count = len(result.get_high_issues())

    print(f"\n{'='*70}")
    print("Configuration Validation Results")
    print(f"{'='*70}")
    print(f"Status: {'✗ FAILED' if not result.valid else '⚠ PASSED WITH WARNINGS'}")
    print(f"Total Issues: {total_issues}")
    print(f"  Critical: {critical_count}")
    print(f"  High: {high_count}")
    print(f"  Other: {total_issues - critical_count - high_count}")
    print(f"{'='*70}\n")

    # Print issues by severity
    severity_order = [
        Severity.CRITICAL,
        Severity.HIGH,
        Severity.MEDIUM,
        Severity.LOW,
        Severity.INFO,
    ]

    for severity in severity_order:
        if severity not in issues_by_severity:
            continue

        # Skip low/info in non-verbose mode
        if not verbose and severity in [Severity.LOW, Severity.INFO]:
            continue

        issues = issues_by_severity[severity]
        severity_icon = {
            Severity.CRITICAL: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🔵",
            Severity.INFO: "ℹ️",
        }

        print(
            f"{severity_icon[severity]} {severity.value.upper()} ({len(issues)} issues)"
        )
        print("-" * 70)

        for issue in issues:
            location = f"{issue.file_path}"
            if issue.line_number:
                location += f":{issue.line_number}"

            print(f"\n  Rule: {issue.rule}")
            print(f"  Location: {location}")
            print(f"  Message: {issue.message}")

            if issue.suggestion:
                print(f"  Suggestion: {issue.suggestion}")

        print()


if __name__ == "__main__":
    """CLI for configuration validation"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Validate Finance Feedback Engine configuration"
    )
    parser.add_argument("config_file", help="Path to configuration file")
    parser.add_argument(
        "--environment",
        "-e",
        default="development",
        choices=["production", "staging", "development", "test"],
        help="Target environment",
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

    args = parser.parse_args()

    # Run validation
    result = validate_config_file(args.config_file, args.environment)

    # Print results
    print_validation_results(result, verbose=args.verbose)

    # Exit with error code if requested and validation failed
    if args.exit_on_error and not result.valid:
        sys.exit(1)
