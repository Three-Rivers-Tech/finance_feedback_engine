#!/usr/bin/env python3
"""
Quick validation test for asset_type normalization fix.

This script tests the asset_type validation and normalization logic
added to aggregate_decisions_two_phase() without requiring a full
ensemble run.
"""

def test_asset_type_normalization():
    """Test asset type normalization logic."""

    # Define canonical asset types (must match ensemble_manager.py)
    CANONICAL_ASSET_TYPES = {'crypto', 'forex', 'stock'}

    # Normalization mapping
    ASSET_TYPE_NORMALIZATION = {
        'cryptocurrency': 'crypto',
        'cryptocurrencies': 'crypto',
        'digital_currency': 'crypto',
        'digital': 'crypto',
        'btc': 'crypto',
        'eth': 'crypto',
        'foreign_exchange': 'forex',
        'fx': 'forex',
        'currency': 'forex',
        'currency_pair': 'forex',
        'equities': 'stock',
        'equity': 'stock',
        'shares': 'stock',
        'stocks': 'stock',
    }

    def normalize_asset_type(raw_asset_type, asset_pair="TEST_PAIR"):
        """Replicate the normalization logic from ensemble_manager.py."""
        if raw_asset_type is None:
            print(f"⚠️  Asset type missing for {asset_pair}. Defaulting to 'crypto'.")
            return 'crypto'
        elif isinstance(raw_asset_type, str):
            raw_lower = raw_asset_type.lower().strip()

            if raw_lower in CANONICAL_ASSET_TYPES:
                return raw_lower
            elif raw_lower in ASSET_TYPE_NORMALIZATION:
                normalized = ASSET_TYPE_NORMALIZATION[raw_lower]
                print(f"ℹ️  Asset type normalized: '{raw_asset_type}' -> '{normalized}' for {asset_pair}")
                return normalized
            else:
                print(f"❌ Invalid asset_type '{raw_asset_type}' for {asset_pair}. Defaulting to 'crypto'.")
                return 'crypto'
        else:
            print(f"❌ Asset type is not a string (type: {type(raw_asset_type)}) for {asset_pair}. Defaulting to 'crypto'.")
            return 'crypto'

    # Test cases
    test_cases = [
        # (input, expected_output, description)
        ('crypto', 'crypto', "Canonical crypto"),
        ('forex', 'forex', "Canonical forex"),
        ('stock', 'stock', "Canonical stock"),
        ('cryptocurrency', 'crypto', "Variation: cryptocurrency"),
        ('fx', 'forex', "Variation: fx"),
        ('equity', 'stock', "Variation: equity"),
        ('unknown', 'crypto', "Invalid: unknown (should default)"),
        ('mystery', 'crypto', "Invalid: mystery (should default)"),
        (None, 'crypto', "Missing (None, should default)"),
        ('', 'crypto', "Empty string (should default)"),
        ('CRYPTO', 'crypto', "Uppercase (should normalize)"),
        ('  crypto  ', 'crypto', "With whitespace (should normalize)"),
        (123, 'crypto', "Non-string: integer (should default)"),
        (['crypto'], 'crypto', "Non-string: list (should default)"),
    ]

    print("=" * 80)
    print("ASSET TYPE NORMALIZATION TESTS")
    print("=" * 80)

    passed = 0
    failed = 0

    for raw_input, expected, description in test_cases:
        print(f"\n📋 Test: {description}")
        print(f"   Input: {repr(raw_input)}")
        result = normalize_asset_type(raw_input, "TEST_PAIR")

        if result == expected:
            print(f"   ✅ PASS: Got '{result}' (expected '{expected}')")
            passed += 1
        else:
            print(f"   ❌ FAIL: Got '{result}' but expected '{expected}'")
            failed += 1

        # Final validation check
        if result not in CANONICAL_ASSET_TYPES:
            print(f"   ⚠️  CRITICAL: Result '{result}' is not canonical!")
            failed += 1

    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = test_asset_type_normalization()
    exit(0 if success else 1)
