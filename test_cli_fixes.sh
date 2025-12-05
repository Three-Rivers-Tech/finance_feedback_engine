#!/bin/bash
echo "=== Testing All QA Fixes ==="
echo ""

echo "1. Testing C2: Invalid date range rejection"
python main.py backtest BTCUSD --start 2024-02-01 --end 2024-01-01 2>&1 | grep -q "start_date.*must be before" && echo "✅ PASS" || echo "❌ FAIL"

echo "2. Testing M1: History empty results exit code 0"
python main.py history --asset ZZZNONE --limit 1 >/dev/null 2>&1 && echo "✅ PASS (exit 0)" || echo "❌ FAIL (exit non-zero)"

echo "3. Testing C1: Backtest runs without AttributeError"
timeout 20 python main.py backtest BTCUSD --start 2024-01-01 --end 2024-01-02 2>&1 | grep -q "AI-Driven Backtest Summary" && echo "✅ PASS" || echo "❌ FAIL"

echo "4. Testing walk-forward initialization"
timeout 10 python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-01-10 --train-ratio 0.7 2>&1 | grep -q "Windows: train=" && echo "✅ PASS" || echo "❌ FAIL"

echo "5. Testing monte-carlo initialization"
timeout 10 python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-01-02 --simulations 3 2>&1 | grep -q "Monte Carlo Simulation Results" && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "=== Test Summary Complete ==="
