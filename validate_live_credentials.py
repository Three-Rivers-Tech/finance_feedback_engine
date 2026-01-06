#!/usr/bin/env python3
"""
Credential validator for live trading.
Validates all required keys WITHOUT logging sensitive values.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import logging
import os
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Credentials that must be checked for live trading
REQUIRED_FOR_LIVE = {
    'alpha_vantage': ['ALPHA_VANTAGE_API_KEY'],
    'coinbase': ['COINBASE_API_KEY', 'COINBASE_API_SECRET'],
    'oanda': ['OANDA_API_KEY', 'OANDA_ACCOUNT_ID'],
    'decision_engine': ['DECISION_ENGINE_AI_PROVIDER'],
}

OPTIONAL_FOR_LIVE = {
    'telegram': ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'],
    'monitoring': ['MONITORING_ENABLED'],
}

def mask_value(value: str, visible_chars: int = 4) -> str:
    """Mask sensitive values, showing only first N chars."""
    if not value or len(value) <= visible_chars:
        return '***'
    return value[:visible_chars] + '*' * (len(value) - visible_chars)

def validate_platform_config() -> Tuple[bool, List[str]]:
    """Validate trading platform configuration."""
    errors = []

    # Check main platform setting
    platform = os.getenv('TRADING_PLATFORM', 'unknown')
    logger.info(f"Trading Platform: {platform}")

    if platform != 'unified':
        errors.append(f"TRADING_PLATFORM should be 'unified' for multi-platform, got '{platform}'")

    # Check Coinbase for live
    if not os.getenv('COINBASE_USE_SANDBOX', 'true').lower() == 'false':
        errors.append("⚠️  COINBASE_USE_SANDBOX is not set to 'false' for live trading")
    else:
        logger.info("✓ Coinbase: LIVE (sandbox disabled)")

    # Check Oanda for live
    oanda_env = os.getenv('OANDA_ENVIRONMENT', 'practice').lower()
    if oanda_env != 'live':
        errors.append(f"⚠️  OANDA_ENVIRONMENT is '{oanda_env}', should be 'live' for live trading")
    else:
        logger.info("✓ Oanda: LIVE")

    return len(errors) == 0, errors

def validate_ai_provider() -> Tuple[bool, List[str]]:
    """Validate AI provider configuration."""
    errors = []

    provider = os.getenv('DECISION_ENGINE_AI_PROVIDER', 'unknown').lower()
    logger.info(f"AI Provider: {provider}")

    if provider == 'local':
        model = os.getenv('DECISION_ENGINE_MODEL_NAME', 'unknown')
        logger.info(f"✓ Local AI: {model}")
        logger.info("  → Ensure Ollama is running: docker-compose -f docker-compose.yml up ollama")
    elif provider == 'ensemble':
        logger.warning("⚠️  Ensemble mode detected - ensure all debate providers are configured")
    elif provider in ['gemini', 'codex', 'qwen']:
        key_var = f"DECISION_ENGINE_{provider.upper()}_API_KEY"
        if not os.getenv(key_var):
            errors.append(f"{key_var} required for {provider} provider")

    return len(errors) == 0, errors

def validate_required_credentials() -> Tuple[bool, List[str]]:
    """Check all required credentials are present."""
    errors = []
    missing = []

    for service, keys in REQUIRED_FOR_LIVE.items():
        logger.info(f"\n{service.upper()}:")

        for key in keys:
            value = os.getenv(key)

            if not value or value.startswith('YOUR_'):
                errors.append(f"  ✗ {key} is not set")
                missing.append(key)
            elif key.endswith('SECRET') or key.endswith('KEY'):
                masked = mask_value(value, visible_chars=6)
                logger.info(f"  ✓ {key}: {masked}")
            else:
                logger.info(f"  ✓ {key}: {value}")

    return len(errors) == 0, errors

def check_ollama_running():
    """Check if Ollama service is accessible. Returns tuple or None."""
    try:
        import requests
    except ImportError:
        return None, "⚠️  requests library not installed, skipping Ollama check"

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    try:
        response = requests.get(f"{ollama_host}/api/tags", timeout=3)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return True, f"✓ Ollama running with {len(models)} models"
        else:
            return False, f"✗ Ollama returned status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, f"✗ Cannot connect to Ollama at {ollama_host}"
    except requests.exceptions.Timeout:
        return False, f"✗ Ollama connection timeout at {ollama_host}"
    except Exception as e:
        return False, f"✗ Ollama check failed: {e}"

def main():
    print("\n" + "="*70)
    print(" LIVE TRADING CREDENTIALS VALIDATION")
    print("="*70)
    print("\n⚠️  LIVE CREDENTIALS DETECTED - Real money at stake")
    print("    This script validates your configuration WITHOUT logging keys\n")

    all_valid = True
    errors: List[str] = []

    # 1. Check required credentials
    print("\n[1/4] REQUIRED CREDENTIALS")
    print("-" * 70)
    valid, cred_errors = validate_required_credentials()
    all_valid = all_valid and valid
    errors.extend(cred_errors)

    # 2. Check platform configuration
    print("\n[2/4] PLATFORM CONFIGURATION")
    print("-" * 70)
    valid, platform_errors = validate_platform_config()
    all_valid = all_valid and valid
    errors.extend(platform_errors)

    # 3. Check AI provider
    print("\n[3/4] AI PROVIDER CONFIGURATION")
    print("-" * 70)
    valid, ai_errors = validate_ai_provider()
    all_valid = all_valid and valid
    errors.extend(ai_errors)

    # 4. Check Ollama (if local provider)
    print("\n[4/4] OLLAMA SERVICE")
    print("-" * 70)
    if os.getenv('DECISION_ENGINE_AI_PROVIDER', '').lower() == 'local':
        ollama_running, message = check_ollama_running()
        if ollama_running is None:
            logger.warning(message)
        elif ollama_running:
            logger.info(message)
        else:
            logger.error(message)
            all_valid = False
            errors.append(message)
    else:
        logger.info("Skipping Ollama check (not using local AI provider)")

    # Summary
    print("\n" + "="*70)
    print(" VALIDATION SUMMARY")
    print("="*70)

    if all_valid and not errors:
        print("\n✅ ALL CHECKS PASSED - Ready for live trading!\n")
        print("SAFETY CHECKS BEFORE EXECUTING:")
        print("  1. Run with --dry-run first to simulate trades")
        print("  2. Start with small position sizes (1-5%)")
        print("  3. Monitor the first few trades manually")
        print("  4. Set AGENT_AUTONOMOUS_ENABLED=true only after validation\n")
        print("Next step: python main.py run-agent --asset-pair BTCUSD --dry-run")
        return 0
    else:
        print("\n❌ VALIDATION FAILED\n")
        print("Issues found:")
        for error in errors:
            print(f"  - {error}")
        print("\nFix these issues before running live trading.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
