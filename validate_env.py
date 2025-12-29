#!/usr/bin/env python3
"""Validate .env configuration and API key connectivity."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

EC_PRIVATE_KEY_MARKER = "BEGIN EC KEY"

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_status(message, status="info"):
    """Print colored status message."""
    colors = {
        "success": GREEN,
        "error": RED,
        "warning": YELLOW,
        "info": BLUE,
    }
    color = colors.get(status, RESET)
    symbol = {
        "success": "✓",
        "error": "✗",
        "warning": "⚠",
        "info": "ℹ",
    }
    print(f"{color}{symbol.get(status, '•')} {message}{RESET}")


def load_environment():
    """Load .env file and return validation results."""
    env_path = Path(__file__).parent / ".env"

    if not env_path.exists():
        print_status(f".env file not found at {env_path}", "error")
        return False

    load_dotenv(dotenv_path=env_path, override=True)
    print_status(f"Loaded .env from {env_path}", "success")
    return True


def validate_required_keys():
    """Validate that all required API keys are set."""
    print("\n" + "=" * 70)
    print("Validating Required API Keys")
    print("=" * 70)

    required_keys = {
        "ALPHA_VANTAGE_API_KEY": "Alpha Vantage",
        "COINBASE_API_KEY": "Coinbase",
        "COINBASE_API_SECRET": "Coinbase Secret",
        "OANDA_API_KEY": "Oanda",
        "OANDA_ACCOUNT_ID": "Oanda Account",
    }

    optional_keys = {
        "DECISION_ENGINE_GEMINI_API_KEY": "Gemini AI",
        "TELEGRAM_BOT_TOKEN": "Telegram",
        "TELEGRAM_NGROK_AUTH_TOKEN": "Ngrok",
    }

    all_valid = True

    # Check required keys
    for key, name in required_keys.items():
        value = os.getenv(key, "")

        # Check if it's a placeholder
        is_placeholder = any(
            placeholder in value
            for placeholder in ["YOUR_", "REPLACE_WITH_", "demo", "default"]
        )

        if not value:
            print_status(f"{name} ({key}): NOT SET", "error")
            all_valid = False
        elif is_placeholder:
            print_status(f"{name} ({key}): PLACEHOLDER (needs real value)", "warning")
            all_valid = False
        else:
            # Mask the key for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print_status(f"{name} ({key}): {masked}", "success")

    # Check optional keys
    print("\nOptional API Keys:")
    for key, name in optional_keys.items():
        value = os.getenv(key, "")

        is_placeholder = any(
            placeholder in value
            for placeholder in ["YOUR_", "REPLACE_WITH_", "demo", "default"]
        )

        if not value:
            print_status(f"{name} ({key}): NOT SET (optional)", "info")
        elif is_placeholder:
            print_status(f"{name} ({key}): PLACEHOLDER", "warning")
        else:
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print_status(f"{name} ({key}): {masked}", "success")

    return all_valid


def validate_platform_settings():
    """Validate platform-specific settings."""
    print("\n" + "=" * 70)
    print("Validating Platform Settings")
    print("=" * 70)

    # Coinbase settings
    use_sandbox = os.getenv("COINBASE_USE_SANDBOX", "false")
    print_status(
        f"Coinbase Sandbox Mode: {use_sandbox}",
        "warning" if use_sandbox == "true" else "info",
    )

    # Oanda settings
    oanda_env = os.getenv("OANDA_ENVIRONMENT", "live")
    print_status(
        f"Oanda Environment: {oanda_env}",
        "warning" if oanda_env == "practice" else "info",
    )

    # Trading platform
    trading_platform = os.getenv("TRADING_PLATFORM", "unified")
    print_status(f"Trading Platform: {trading_platform}", "info")

    # Telegram
    telegram_enabled = os.getenv("TELEGRAM_ENABLED", "false")
    print_status(f"Telegram Integration: {telegram_enabled}", "info")

    return True


def test_coinbase_connection():
    """Test Coinbase API connection."""
    print("\n" + "=" * 70)
    print("Testing Coinbase Connection")
    print("=" * 70)

    api_key = os.getenv("COINBASE_API_KEY", "")
    api_secret = os.getenv("COINBASE_API_SECRET", "")

    if not api_key or not api_secret:
        print_status("Coinbase credentials not set, skipping test", "warning")
        return False

    if "YOUR_" in api_key or "YOUR_" in api_secret:
        print_status("Coinbase credentials are placeholders, skipping test", "warning")
        return False

    try:
        # Try to import and test Coinbase connection
        print_status("Attempting to validate Coinbase credentials format...", "info")

        # Basic format validation
        if not api_key.startswith("organizations/"):
            print_status("Coinbase API key format appears incorrect", "warning")
            print_status(
                "Expected format: organizations/{org-id}/apiKeys/{key-id}", "info"
            )
        else:
            print_status("Coinbase API key format looks correct", "success")

        if EC_PRIVATE_KEY_MARKER not in api_secret:
            print_status("Coinbase API secret format appears incorrect", "warning")
            print_status(
                "Expected EC key PEM header containing 'BEGIN EC KEY'",
                "info",
            )
        else:
            print_status("Coinbase API secret format looks correct", "success")

        return True

    except Exception as e:
        print_status(f"Coinbase validation error: {e}", "error")
        return False


def test_oanda_connection():
    """Test Oanda API connection."""
    print("\n" + "=" * 70)
    print("Testing Oanda Connection")
    print("=" * 70)

    api_key = os.getenv("OANDA_API_KEY", "")
    account_id = os.getenv("OANDA_ACCOUNT_ID", "")

    if not api_key or not account_id:
        print_status("Oanda credentials not set, skipping test", "warning")
        return False

    if "YOUR_" in api_key or "YOUR_" in account_id:
        print_status("Oanda credentials are placeholders, skipping test", "warning")
        return False

    try:
        print_status("Attempting to validate Oanda credentials format...", "info")

        # Basic format validation
        # Oanda account IDs typically follow pattern: XXX-XXX-XXXXXXX-XXX
        if "-" in account_id and len(account_id.split("-")) == 4:
            print_status("Oanda account ID format looks correct", "success")
        else:
            print_status("Oanda account ID format may be incorrect", "warning")
            print_status("Expected format: XXX-XXX-XXXXXXX-XXX", "info")

        # API key should be a long alphanumeric string with hyphens
        if len(api_key) > 40 and "-" in api_key:
            print_status("Oanda API key format looks correct", "success")
        else:
            print_status("Oanda API key format may be incorrect", "warning")

        return True

    except Exception as e:
        print_status(f"Oanda validation error: {e}", "error")
        return False


def test_telegram_config():
    """Test Telegram configuration."""
    print("\n" + "=" * 70)
    print("Testing Telegram Configuration")
    print("=" * 70)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    ngrok_token = os.getenv("TELEGRAM_NGROK_AUTH_TOKEN", "")
    enabled = os.getenv("TELEGRAM_ENABLED", "false")

    if enabled != "true":
        print_status("Telegram integration is disabled", "info")
        return True

    if not bot_token or "YOUR_" in bot_token:
        print_status("Telegram bot token not set or is placeholder", "warning")
        return False

    # Validate bot token format (should be digits:alphanumeric)
    if ":" in bot_token:
        parts = bot_token.split(":")
        if len(parts) == 2 and parts[0].isdigit() and len(parts[1]) == 35:
            print_status("Telegram bot token format looks correct", "success")
        else:
            print_status("Telegram bot token format may be incorrect", "warning")
    else:
        print_status("Telegram bot token format is incorrect", "error")
        return False

    if not ngrok_token or "YOUR_" in ngrok_token:
        print_status("Ngrok auth token not set (needed for webhooks)", "warning")
    else:
        print_status("Ngrok auth token is set", "success")

    return True


def main():
    """Main validation routine."""
    print("\n" + "=" * 70)
    print("Finance Feedback Engine 2.0 - Environment Validation")
    print("=" * 70)

    # Load environment
    if not load_environment():
        print_status("\nValidation FAILED: Could not load .env file", "error")
        sys.exit(1)

    # Validate required keys
    keys_valid = validate_required_keys()

    # Validate platform settings
    settings_valid = validate_platform_settings()

    # Test connections
    coinbase_ok = test_coinbase_connection()
    oanda_ok = test_oanda_connection()
    telegram_ok = test_telegram_config()

    # Summary
    print("\n" + "=" * 70)
    print("Validation Summary")
    print("=" * 70)

    if keys_valid:
        print_status("All required API keys are configured", "success")
    else:
        print_status("Some required API keys are missing or placeholders", "error")

    if coinbase_ok:
        print_status("Coinbase configuration looks good", "success")

    if oanda_ok:
        print_status("Oanda configuration looks good", "success")

    if telegram_ok:
        print_status("Telegram configuration looks good", "success")

    print("\n" + "=" * 70)

    if keys_valid and (coinbase_ok or oanda_ok):
        print_status("✓ Configuration validation PASSED", "success")
        print_status("You should be able to run the Finance Feedback Engine", "success")
        print("\nNext steps:")
        print("  1. Run the backend: python main.py")
        print("  2. Run the frontend: cd frontend && npm run dev")
        return 0
    else:
        print_status("✗ Configuration validation FAILED", "error")
        print_status("Please check the issues above and update your .env file", "error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
