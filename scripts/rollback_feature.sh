#!/bin/bash
# scripts/rollback_feature.sh
# Safely disable a feature flag and validate system still works

set -e

FEATURE=$1
CONFIG_FILE="${2:-config/config.local.yaml}"

if [ -z "$FEATURE" ]; then
    echo "Usage: ./scripts/rollback_feature.sh <feature_name> [config_file]"
    echo ""
    echo "Available features:"
    echo "  - enhanced_slippage_model"
    echo "  - thompson_sampling_weights"
    echo "  - sentiment_veto"
    echo "  - paper_trading_mode"
    echo "  - visual_reports"
    echo "  - rl_agent"
    echo "  - multi_agent_system"
    echo "  - parallel_backtesting"
    echo "  - limit_stop_orders"
    exit 1
fi

echo "🔄 Rolling back feature: $FEATURE"
echo "📝 Config file: $CONFIG_FILE"

# Backup current config
BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$CONFIG_FILE" "$BACKUP_FILE"
echo "✅ Backed up config to: $BACKUP_FILE"

# Disable feature using Python
python3 << EOF
import yaml
from pathlib import Path

config_path = Path('$CONFIG_FILE')

# Load config (create if doesn't exist)
if config_path.exists():
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}
else:
    config = {}

# Ensure features section exists
if 'features' not in config:
    config['features'] = {}

# Disable the feature
config['features']['$FEATURE'] = False

# Write back
with open(config_path, 'w') as f:
    yaml.safe_dump(config, f, default_flow_style=False)

print(f"✅ Disabled feature: $FEATURE")
EOF

echo ""
echo "🧪 Running validation tests..."

# Run quick test suite to verify rollback didn't break anything
if pytest -m "not slow and not external_service" -v --tb=short --maxfail=5; then
    echo ""
    echo "✅ Rollback successful! All tests pass."
    echo ""
    echo "Next steps:"
    echo "  1. Review what went wrong: git log, error logs"
    echo "  2. Fix the issue in a separate branch"
    echo "  3. Re-enable feature after fixing"
    echo ""
    echo "Backup config saved at: $BACKUP_FILE"
else
    echo ""
    echo "❌ Tests failed after rollback!"
    echo "🔧 Restoring from backup..."
    cp "$BACKUP_FILE" "$CONFIG_FILE"
    echo "⚠️  Config restored. Please investigate manually."
    exit 1
fi
