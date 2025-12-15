#!/usr/bin/env python3
"""Test Coinbase authentication and diagnose 401 errors."""

import sys
import json
from coinbase.rest import RESTClient

# Your credentials
API_KEY = "REDACTED_COINBASE_KEY_ID_2"
API_SECRET = """-----BEGIN EC PRIVATE KEY REDACTED-----
REDACTED_KEY_MATERIAL
REDACTED_KEY_MATERIAL
REDACTED_KEY_MATERIAL
-----END EC PRIVATE KEY REDACTED-----
"""

print("="*60)
print("Coinbase CDP API Authentication Test")
print("="*60)
print(f"\nAPI Key: {API_KEY[:80]}...")
print(f"Key Type: {'CDP Format (organizations/.../)' if API_KEY.startswith('organizations/') else 'Legacy'}")
print(f"Secret Format: EC PRIVATE KEY\n")

try:
    # Initialize client
    print("Step 1: Initializing REST client...")
    client = RESTClient(
        api_key=API_KEY,
        api_secret=API_SECRET
    )
    print("✓ Client initialized successfully\n")

    # Try to make an API call
    print("Step 2: Testing API call (GET /accounts)...")
    response = client.get_accounts()
    print(f"✓ Success! Found {len(response.accounts)} accounts")

    for account in response.accounts:
        print(f"  - {account.name}: {account.available_balance.value} {account.available_balance.currency}")

except Exception as e:
    print(f"✗ Error: {e}\n")

    # Try to extract more details
    if hasattr(e, 'response'):
        print("Response details:")
        print(f"  Status Code: {e.response.status_code}")
        print(f"  Headers: {dict(e.response.headers)}")
        try:
            error_body = e.response.json()
            print(f"  Body: {json.dumps(error_body, indent=2)}")
        except:
            print(f"  Body (text): {e.response.text}")

    print("\nPossible issues:")
    print("  1. API key has been revoked or expired")
    print("  2. API key lacks required permissions:")
    print("     - wallet:accounts:read")
    print("     - wallet:trades:read")
    print("     - wallet:orders:read")
    print("  3. API key is for wrong environment (production vs sandbox)")
    print("  4. API key organization doesn't match")
    print("\nSolution:")
    print("  1. Go to: https://portal.cdp.coinbase.com/access/api")
    print("  2. Create new API key with required permissions")
    print("  3. Update config/config.local.yaml with new credentials")

    sys.exit(1)

print("\n" + "="*60)
print("✓ Authentication test passed!")
print("="*60)
