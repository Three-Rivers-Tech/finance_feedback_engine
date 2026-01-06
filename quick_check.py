#!/usr/bin/env python3
"""
Simple credential check - no dependencies on main codebase.
Just checks if .env has the right keys set.
"""

import os
import sys
from pathlib import Path

# Check if .env exists and load it
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    print("❌ .env file not found at", env_path)
    sys.exit(1)

# Load .env manually
env_vars = {}
try:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip().strip('"').strip("'")
except Exception as e:
    print(f"❌ Failed to read .env: {e}")
    sys.exit(1)

print("\n" + "="*80)
print("QUICK CREDENTIAL CHECK")
print("="*80)

required = {
    'ALPHA_VANTAGE_API_KEY': 'Alpha Vantage',
    'COINBASE_API_KEY': 'Coinbase API Key',
    'COINBASE_API_SECRET': 'Coinbase Secret',
    'OANDA_API_KEY': 'Oanda API Key',
    'OANDA_ACCOUNT_ID': 'Oanda Account ID',
}

missing = []
for key, desc in required.items():
    value = env_vars.get(key, "")
    if not value or value == "YOUR_" + key or "YOUR_" in value:
        print(f"  ✗ {desc:.<40} NOT SET")
        missing.append(key)
    else:
        # Show first 8 chars + mask
        masked = value[:8] + "*" * max(0, len(value) - 8) if len(value) > 8 else "***"
        print(f"  ✓ {desc:.<40} {masked}")

print("\nPlatform Configuration:")
platform = env_vars.get('TRADING_PLATFORM', 'unknown')
print(f"  Trading Platform: {platform}")

coinbase_sandbox = env_vars.get('COINBASE_USE_SANDBOX', 'true').lower()
print(f"  Coinbase Sandbox: {coinbase_sandbox}")
if coinbase_sandbox == 'false':
    print(f"    ✓ Set to LIVE")
else:
    print(f"    ✗ Should be 'false' for live trading")
    missing.append('COINBASE_USE_SANDBOX')

oanda_env = env_vars.get('OANDA_ENVIRONMENT', 'practice').lower()
print(f"  Oanda Environment: {oanda_env}")
if oanda_env == 'live':
    print(f"    ✓ Set to LIVE")
else:
    print(f"    ✗ Should be 'live' for live trading")
    missing.append('OANDA_ENVIRONMENT')

print("\nAI Provider:")
ai_provider = env_vars.get('DECISION_ENGINE_AI_PROVIDER', 'unknown')
print(f"  Provider: {ai_provider}")
if ai_provider.lower() == 'local':
    model = env_vars.get('DECISION_ENGINE_MODEL_NAME', 'unknown')
    print(f"  Model: {model}")

print("\n" + "="*80)
if not missing:
    print("✅ All credentials are set for live trading!")
    print("\nNext step: python validate_live_credentials.py")
    sys.exit(0)
else:
    print("❌ Missing or incorrect configuration:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)
