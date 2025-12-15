#!/usr/bin/env python3
"""Debug config loading for unified platform."""

import yaml
import sys
from pathlib import Path

# Load config files in order
config_files = [
    "config/config.yaml",
    "config/config.local.yaml"
]

final_config = {}

for config_file in config_files:
    path = Path(config_file)
    if path.exists():
        print(f"✓ Loading {config_file}...")
        with open(path) as f:
            content = yaml.safe_load(f)
            if content:
                final_config.update(content)
    else:
        print(f"✗ {config_file} not found")

# Check critical settings
print("\n=== Trading Platform Config ===")
print(f"trading_platform: {final_config.get('trading_platform')}")

print("\n=== Platforms List ===")
platforms = final_config.get('platforms', [])
print(f"Number of platforms: {len(platforms)}")

for i, platform_config in enumerate(platforms):
    print(f"\nPlatform {i + 1}:")
    if isinstance(platform_config, dict):
        name = platform_config.get('name')
        creds = platform_config.get('credentials', {})
        print(f"  name: {name}")
        print(f"  credentials keys: {list(creds.keys())}")

        if name == 'coinbase_advanced':
            print(f"    api_key present: {'api_key' in creds}")
            print(f"    api_secret present: {'api_secret' in creds}")
            print(f"    use_sandbox: {creds.get('use_sandbox')}")
            if 'api_key' in creds:
                key = str(creds['api_key'])[:50]
                print(f"    api_key preview: {key}...")
        elif name == 'oanda':
            print(f"    api_key present: {'api_key' in creds}")
            print(f"    account_id: {creds.get('account_id')}")
            print(f"    environment: {creds.get('environment')}")
    else:
        print(f"  Invalid type: {type(platform_config)}")

print("\n=== Unified Credentials Transform ===")
# Simulate what core.py does
unified_credentials = {}
for platform_config in platforms:
    if not isinstance(platform_config, dict):
        print(f"Skipping non-dict: {platform_config}")
        continue

    platform_key = platform_config.get('name', '').lower()
    platform_creds = platform_config.get('credentials', {})

    if not platform_key or not isinstance(platform_key, str):
        print(f"Skipping invalid name: {platform_config}")
        continue

    if not isinstance(platform_creds, dict):
        print(f"Skipping non-dict credentials for {platform_key}")
        continue

    # Normalize key names
    if platform_key in ['coinbase', 'coinbase_advanced']:
        unified_credentials['coinbase'] = platform_creds
        print(f"✓ Added coinbase (from {platform_key})")
    elif platform_key == 'oanda':
        unified_credentials['oanda'] = platform_creds
        print(f"✓ Added oanda")
    else:
        print(f"Unknown platform: {platform_key}")

print(f"\nFinal unified_credentials keys: {list(unified_credentials.keys())}")
for key, creds in unified_credentials.items():
    print(f"  {key}: {list(creds.keys())}")
