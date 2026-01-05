"""
Security validation for Finance Feedback Engine startup.

Checks for common security issues:
- Plaintext credentials in config files
- Missing environment variables for sensitive data
- Insecure configuration settings
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Validates security posture of configuration and environment."""

    SENSITIVE_KEYS = [
        "api_key",
        "api_secret",
        "password",
        "secret",
        "token",
        "passphrase",
    ]

    PLACEHOLDER_PATTERNS = [
        "YOUR_",
        "REPLACE_",
        "CHANGE_",
        "<your",
        "example",
    ]

    def __init__(self):
        """Initialize security validator."""
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.infos: List[str] = []

    def validate_config_file(self, config_path: Path) -> bool:
        """
        Validate a configuration file for security issues.

        Args:
            config_path: Path to YAML config file

        Returns:
            True if valid, False if critical errors found
        """
        if not config_path.exists():
            return True  # No file to validate

        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to parse config file {config_path}: {e}")
            return False

        if not config:
            return True

        # Check for plaintext credentials
        self._check_plaintext_credentials(config, str(config_path))

        return len(self.errors) == 0

    def validate_environment(self) -> bool:
        """
        Validate environment variables for required secrets.

        Returns:
            True if all required vars set, False otherwise
        """
        required_for_trading = [
            ("ALPHA_VANTAGE_API_KEY", "Alpha Vantage API key for market data"),
        ]

        required_for_trading_platform = [
            ("COINBASE_API_KEY", "Coinbase API key (if using coinbase_advanced)"),
            ("COINBASE_API_SECRET", "Coinbase API secret (if using coinbase_advanced)"),
        ]

        # Check Alpha Vantage (required for all modes)
        for env_var, description in required_for_trading:
            if not os.getenv(env_var):
                self.warnings.append(
                    f"⚠️  {description} not set in environment ({env_var}). "
                    f"Create .env file from .env.example and populate with your credentials."
                )

        # Only warn about platform credentials if not using mock
        trading_platform = os.getenv("TRADING_PLATFORM", "coinbase_advanced")
        if trading_platform != "mock":
            for env_var, description in required_for_trading_platform:
                if not os.getenv(env_var):
                    self.warnings.append(
                        f"⚠️  {description} not set in environment ({env_var}). "
                        f"Required for trading platform '{trading_platform}'."
                    )

        return len(self.errors) == 0

    def _check_plaintext_credentials(
        self, config: Dict, config_file: str, path: str = ""
    ) -> None:
        """
        Recursively check config for plaintext credentials.

        Args:
            config: Configuration dict to check
            config_file: Name of config file being checked
            path: Current path in nested dict (for error messages)
        """
        if not isinstance(config, dict):
            return

        for key, value in config.items():
            current_path = f"{path}.{key}" if path else key

            # Check if this is a sensitive key
            is_sensitive = any(
                sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS
            )

            if is_sensitive and isinstance(value, str):
                # Check if value looks like a placeholder or example
                is_placeholder = any(
                    placeholder in value for placeholder in self.PLACEHOLDER_PATTERNS
                )
                is_env_var = value.startswith("${") and value.endswith("}")

                if is_placeholder:
                    self.infos.append(
                        f"ℹ️  Found placeholder credential in {config_file}:{current_path} = '{value}'. "
                        f"Set actual value via environment variable."
                    )

                elif not is_env_var and value != "":
                    # This looks like a real credential, not a placeholder or env var
                    self.errors.append(  # nosec B608 - False positive: this is error message formatting, not SQL
                        f"🚨 Found plaintext credential in {config_file}:{current_path}. "  # nosec B608
                        f"Update config.yaml to use ${{ENV_VAR_NAME}} format. "
                        f"Set actual credentials in .env file, not config files."
                    )

            # Recurse into nested dicts and lists
            elif isinstance(value, dict):
                self._check_plaintext_credentials(value, config_file, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._check_plaintext_credentials(
                            item, config_file, f"{current_path}[{i}]"
                        )

    def validate_all(self, config_path: Path) -> Tuple[bool, List[str]]:
        """
        Run all security validations.

        Args:
            config_path: Path to main config file

        Returns:
            Tuple of (is_valid, messages_list)
        """
        # Validate config file
        config_valid = self.validate_config_file(config_path)

        # Validate environment
        env_valid = self.validate_environment()

        # Log all messages
        all_valid = config_valid and env_valid

        messages = []

        # Log errors (critical)
        for error in self.errors:
            logger.error(error)
            messages.append(error)

        # Log warnings (advisory)
        for warning in self.warnings:
            logger.warning(warning)
            messages.append(warning)

        # Log info (optional)
        for info in self.infos:
            logger.info(info)

        return all_valid, messages


def validate_at_startup(config_path: Path, raise_on_error: bool = False) -> bool:
    """
    Run security validation at application startup.

    Args:
        config_path: Path to configuration file
        raise_on_error: If True, raise exception on critical errors

    Returns:
        True if validation passed, False otherwise

    Raises:
        RuntimeError: If raise_on_error=True and critical errors found
    """
    validator = SecurityValidator()
    is_valid, messages = validator.validate_all(config_path)

    if not is_valid and raise_on_error:
        error_count = len(validator.errors)
        raise RuntimeError(
            f"❌ Security validation failed with {error_count} critical error(s). "
            f"See logs above for details."
        )

    return is_valid


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.DEBUG)
    config_path = Path(".env")
    is_valid, messages = SecurityValidator().validate_all(config_path)
    print(f"\nValidation Result: {'✅ PASS' if is_valid else '❌ FAIL'}")
    if messages:
        print(f"Total Messages: {len(messages)}")
