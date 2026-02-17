#!/bin/bash
# FFE Monitoring Installation Verification Script
# Verifies all monitoring components are properly installed and functional

cd "$(dirname "$0")/../.."
source .venv/bin/activate

echo "════════════════════════════════════════════════════════════════"
echo "FFE Monitoring & Alerting - Installation Verification"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

# Test function
test_component() {
    local name=$1
    local command=$2
    
    echo -n "Testing $name... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}"
        ((FAILED++))
    fi
}

echo "1. File Structure Verification"
echo "────────────────────────────────────────────────────────────────"

# Check files exist
test_component "P&L Analytics Module" "[ -f finance_feedback_engine/monitoring/pnl_analytics.py ]"
test_component "Alert Manager Module" "[ -f finance_feedback_engine/monitoring/alert_manager.py ]"
test_component "Analytics CLI Commands" "[ -f finance_feedback_engine/cli/commands/analytics.py ]"
test_component "Alert Configuration" "[ -f config/alerts.yaml ]"
test_component "Daily Report Script" "[ -f scripts/monitoring/daily_report.py ]"
test_component "Weekly Report Script" "[ -f scripts/monitoring/weekly_report.py ]"
test_component "Position Monitor Script" "[ -f scripts/monitoring/position_monitor.py ]"
test_component "Grafana Dashboard Template" "[ -f config/grafana_dashboard_template.json ]"
test_component "Setup Documentation" "[ -f docs/monitoring/MONITORING_SETUP.md ]"
test_component "Runbook Documentation" "[ -f docs/monitoring/MONITORING_RUNBOOK.md ]"

echo ""
echo "2. Python Module Imports"
echo "────────────────────────────────────────────────────────────────"

test_component "Import pnl_analytics" "python -c 'from finance_feedback_engine.monitoring.pnl_analytics import PnLAnalytics'"
test_component "Import alert_manager" "python -c 'from finance_feedback_engine.monitoring.alert_manager import AlertManager'"
test_component "Import analytics commands" "python -c 'from finance_feedback_engine.cli.commands.analytics import daily_pnl'"

echo ""
echo "3. CLI Commands Registration"
echo "────────────────────────────────────────────────────────────────"

test_component "daily-pnl command" "python -m finance_feedback_engine.cli.main daily-pnl --help"
test_component "weekly-pnl command" "python -m finance_feedback_engine.cli.main weekly-pnl --help"
test_component "monthly-pnl command" "python -m finance_feedback_engine.cli.main monthly-pnl --help"
test_component "asset-breakdown command" "python -m finance_feedback_engine.cli.main asset-breakdown --help"
test_component "export-csv command" "python -m finance_feedback_engine.cli.main export-csv --help"

echo ""
echo "4. Dependencies Check"
echo "────────────────────────────────────────────────────────────────"

test_component "PyYAML" "python -c 'import yaml'"
test_component "requests" "python -c 'import requests'"
test_component "numpy" "python -c 'import numpy'"
test_component "click" "python -c 'import click'"
test_component "rich" "python -c 'from rich.console import Console'"

echo ""
echo "5. Functional Tests (Data Processing)"
echo "────────────────────────────────────────────────────────────────"

test_component "Load trade outcomes" "python -c '
from finance_feedback_engine.monitoring.pnl_analytics import PnLAnalytics
analytics = PnLAnalytics()
trades = analytics.load_trade_outcomes()
assert isinstance(trades, list), \"Trades must be a list\"
'"

test_component "Calculate metrics" "python -c '
from finance_feedback_engine.monitoring.pnl_analytics import PnLAnalytics
analytics = PnLAnalytics()
metrics = analytics.get_daily_summary()
assert \"total_trades\" in metrics, \"Metrics must include total_trades\"
'"

test_component "Load alert config" "python -c '
from finance_feedback_engine.monitoring.alert_manager import AlertManager
manager = AlertManager()
assert manager.config is not None, \"Alert config must load\"
'"

echo ""
echo "6. Script Executability"
echo "────────────────────────────────────────────────────────────────"

test_component "daily_report.py executable" "[ -x scripts/monitoring/daily_report.py ]"
test_component "weekly_report.py executable" "[ -x scripts/monitoring/weekly_report.py ]"
test_component "position_monitor.py executable" "[ -x scripts/monitoring/position_monitor.py ]"

echo ""
echo "7. Configuration Validation"
echo "────────────────────────────────────────────────────────────────"

test_component "alerts.yaml syntax" "python -c '
import yaml
with open(\"config/alerts.yaml\") as f:
    config = yaml.safe_load(f)
assert \"pnl_alerts\" in config, \"Alert config must have pnl_alerts\"
assert \"position_alerts\" in config, \"Alert config must have position_alerts\"
'"

test_component "Grafana JSON syntax" "python -c '
import json
with open(\"config/grafana_dashboard_template.json\") as f:
    dashboard = json.load(f)
assert \"dashboard\" in dashboard, \"Grafana config must have dashboard\"
'"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Verification Summary"
echo "════════════════════════════════════════════════════════════════"
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Monitoring system is ready.${NC}"
    echo ""
    echo "Next Steps:"
    echo "  1. Configure Telegram: Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env"
    echo "  2. Schedule cron jobs: See docs/monitoring/MONITORING_SETUP.md"
    echo "  3. Test alert delivery: Run 'ffe daily-pnl' and check Telegram"
    echo "  4. Import Grafana dashboard: Upload config/grafana_dashboard_template.json"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the errors above.${NC}"
    echo ""
    exit 1
fi
