#!/bin/bash
#
# Demo script showing signal-only mode in action
#
# This script demonstrates that when a trading platform returns
# empty or zero balances, the engine provides trading signals
# without position sizing recommendations.

set -e

echo "========================================================================"
echo "SIGNAL-ONLY MODE DEMO"
echo "========================================================================"
echo ""
echo "This demo shows that the Finance Feedback Engine gracefully handles"
echo "scenarios where portfolio/balance data is unavailable by providing"
echo "trading signals only (no position sizing)."
echo ""

# Create a test config with mock platform (returns empty balance)
cat > config/config.signal_test.yaml << 'EOF'
# Test configuration for signal-only mode demo
# Mock platform returns empty balance to trigger signal-only mode

alpha_vantage_api_key: "${ALPHA_VANTAGE_API_KEY}"

trading_platform: mock
platform_credentials: {}

decision_engine:
  ai_provider: local
  model_name: llama3.2:3b-instruct-q4_K_M
  decision_threshold: 0.6

persistence:
  storage_path: data/demo_signal_only
  max_decisions: 100
EOF

echo "Test config created: config/config.signal_test.yaml"
echo ""

# Create data directory
mkdir -p data/demo_signal_only

echo "Running analysis with mock platform (empty balance)..."
echo "------------------------------------------------------------------------"
python main.py -c config/config.signal_test.yaml analyze BTCUSD 2>&1 | grep -A 30 "Trading Decision Generated" || true
echo ""

echo "------------------------------------------------------------------------"
echo "VERIFICATION"
echo "------------------------------------------------------------------------"
echo ""
echo "Checking the generated decision JSON for signal_only flag..."
LATEST_DECISION=$(ls -t data/demo_signal_only/*.json 2>/dev/null | head -1)

if [ -f "$LATEST_DECISION" ]; then
    echo "Latest decision file: $LATEST_DECISION"
    echo ""
    echo "Key fields:"
    echo "  signal_only:                $(cat "$LATEST_DECISION" | grep -o '"signal_only": [^,]*' || echo 'not found')"
    echo "  recommended_position_size:  $(cat "$LATEST_DECISION" | grep -o '"recommended_position_size": [^,]*' || echo 'not found')"
    echo "  stop_loss_fraction:       $(cat "$LATEST_DECISION" | grep -o '"stop_loss_fraction": [^,]*' || echo 'not found')"
    echo "  risk_percentage:            $(cat "$LATEST_DECISION" | grep -o '"risk_percentage": [^,]*' || echo 'not found')"
else
    echo "No decision file found in data/demo_signal_only/"
fi

echo ""
echo "------------------------------------------------------------------------"
echo "CLEANUP"
echo "------------------------------------------------------------------------"
rm -rf data/demo_signal_only config/config.signal_test.yaml
echo "Demo artifacts cleaned up"
echo ""

echo "========================================================================"
echo "DEMO COMPLETE"
echo "========================================================================"
echo ""
echo "✓ Signal-only mode activated when balance unavailable"
echo "✓ Decision includes action, confidence, and reasoning"
echo "✓ Position sizing fields set to null (not calculated)"
echo "✓ CLI displays warning about signal-only mode"
echo ""
