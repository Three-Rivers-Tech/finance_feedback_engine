"""Credential validation utility to catch configuration errors at startup."""

import logging
import sys
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def validate_credentials(config: Dict[str, Any]) -> None:
    """
    Validate that configuration doesn't contain placeholder values.

    Fails fast if placeholder credentials like 'YOUR_API_KEY' are detected,
    preventing silent failures during live trading.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If placeholder credentials are detected
    """
    errors: List[str] = []

    # Check Alpha Vantage API key
    alpha_vantage_key = config.get("alpha_vantage_api_key", "")
    if isinstance(alpha_vantage_key, str) and alpha_vantage_key.startswith("YOUR_"):
        errors.append(
            "❌ Alpha Vantage API key is a placeholder: "
            f"'{alpha_vantage_key}'\n"
            "   Get your free API key at: https://www.alphavantage.co/support/#api-key\n"
            "   Set via environment variable: export ALPHA_VANTAGE_API_KEY=your_actual_key"
        )

    # Check platform credentials
    platform_creds = config.get("platform_credentials", {})
    if isinstance(platform_creds, dict):
        # Check Coinbase credentials
        api_key = platform_creds.get("api_key", "")
        if isinstance(api_key, str) and api_key.startswith("YOUR_"):
            errors.append(
                "❌ Coinbase API key is a placeholder: "
                f"'{api_key}'\n"
                "   Get credentials at: https://www.coinbase.com/settings/api\n"
                "   Set via environment variable: export COINBASE_API_KEY=your_actual_key"
            )

        api_secret = platform_creds.get("api_secret", "")
        if isinstance(api_secret, str) and api_secret.startswith("YOUR_"):
            errors.append(
                "❌ Coinbase API secret is a placeholder: "
                f"'{api_secret}'\n"
                "   Set via environment variable: export COINBASE_API_SECRET=your_actual_secret"
            )

        # Check Oanda credentials
        oanda_token = platform_creds.get("api_key", "")
        account_id = platform_creds.get("account_id", "")

        if isinstance(oanda_token, str) and oanda_token.startswith("YOUR_"):
            errors.append(
                "❌ Oanda API token is a placeholder: "
                f"'{oanda_token}'\n"
                "   Get credentials at: https://www.oanda.com/\n"
                "   Set via environment variable: export OANDA_API_TOKEN=your_actual_token"
            )

        # Only check Oanda if it's likely being used (account_id present)
        if isinstance(account_id, str) and account_id.startswith("YOUR_"):
            errors.append(
                "❌ Oanda account ID is a placeholder: "
                f"'{account_id}'\n"
                "   Get credentials at: https://www.oanda.com/\n"
                "   Set via environment variable: export OANDA_ACCOUNT_ID=your_actual_id"
            )

    # Check multi-platform mode
    platforms = config.get("platforms", [])
    for idx, platform in enumerate(platforms):
        if not isinstance(platform, dict):
            continue

        platform_name = platform.get("name", f"platform_{idx}")
        creds = platform.get("credentials", {})

        for key, value in creds.items():
            if isinstance(value, str) and value.startswith("YOUR_"):
                errors.append(
                    f"❌ Platform '{platform_name}' has placeholder credential: "
                    f"{key}='{value}'\n"
                    "   Configure actual credentials in config.local.yaml or environment variables"
                )

    # If errors found, print to console and fail
    if errors:
        print("\n" + "=" * 80, file=sys.stderr)
        print("⚠️  CONFIGURATION ERROR: Placeholder Credentials Detected", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("\nThe following configuration issues must be fixed:\n", file=sys.stderr)

        for error in errors:
            print(f"{error}\n", file=sys.stderr)

        print("=" * 80, file=sys.stderr)
        print("📝 Quick Fix:", file=sys.stderr)
        print("   1. Copy .env.example to .env", file=sys.stderr)
        print("   2. Fill in your actual API keys in .env", file=sys.stderr)
        print("   3. Restart the application", file=sys.stderr)
        print("=" * 80 + "\n", file=sys.stderr)

        raise ValueError(
            "Configuration contains placeholder credentials. "
            "Replace 'YOUR_*' values with actual API keys. "
            f"Found {len(errors)} issue(s)."
        )

    logger.debug("✅ Credential validation passed")
