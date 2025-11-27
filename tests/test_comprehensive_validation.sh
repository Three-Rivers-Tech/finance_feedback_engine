#!/bin/bash
# Comprehensive test of asset pair validation

echo "========================================"
echo "Asset Pair Validation - Comprehensive Test"
echo "========================================"
echo ""

echo "Test 1: CLI with various formats"
echo "--------------------------------"
formats=("btcusd" "BTC-USD" "btc_usd" "eur-usd" "EUR_USD")
for format in "${formats[@]}"; do
    echo -n "Testing: $format ... "
    output=$(python3 main.py analyze "$format" --provider local 2>&1 | grep "Analyzing")
    if [[ $output == *"Analyzing"* ]]; then
        echo "✓ $(echo "$output" | grep -o "Analyzing [A-Z]*")"
    else
        echo "✗ Failed"
    fi
done

echo ""
echo "Test 2: Python API validation function"
echo "---------------------------------------"
python3 -c "
from finance_feedback_engine.utils.validation import standardize_asset_pair

tests = [
    ('btc-usd', 'BTCUSD'),
    ('eur_usd', 'EURUSD'),
    ('ETH/USD', 'ETHUSD'),
    ('gbp jpy', 'GBPJPY'),
]

for input_val, expected in tests:
    result = standardize_asset_pair(input_val)
    status = '✓' if result == expected else '✗'
    print(f'{status} {input_val:15} -> {result:10} (expected: {expected})')
"

echo ""
echo "Test 3: Unit test suite"
echo "-----------------------"
python3 test_asset_pair_validation.py | tail -2

echo ""
echo "========================================"
echo "All validation tests complete!"
echo "========================================"
