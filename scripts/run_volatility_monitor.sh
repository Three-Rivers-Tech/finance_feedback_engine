#!/bin/sh
# Volatility Monitor (THR-210)
# Runs every 60 seconds to check for ±5% P&L moves

set -e

echo "Starting Volatility Monitor..."
echo "Poll interval: 60 seconds"
echo "Alert threshold: ±5% unrealized P&L"
echo "Spam prevention: 1-hour cooldown per position"
echo ""

# Wait for database to be ready
echo "Waiting for database connection..."
until python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}').close()" 2>/dev/null; do
  echo "Database not ready, waiting..."
  sleep 5
done
echo "Database connected!"
echo ""

# Main monitoring loop
ITERATION=0
while true; do
  ITERATION=$((ITERATION + 1))
  TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
  
  echo "[$TIMESTAMP] Volatility Check #$ITERATION"
  
  # Run volatility check
  OUTPUT=$(python -m finance_feedback_engine.cli.main check-volatility 2>&1) || {
    EXIT_CODE=$?
    echo "  ✗ Volatility check failed (exit code: $EXIT_CODE)"
    echo "  → Data Stale - API error detected"
    echo "$OUTPUT" | grep -E "(Data Stale|Error)" || true
    echo "  → Will retry in 60 seconds"
    echo ""
    sleep 60
    continue
  }
  
  # Check if alert was triggered
  if echo "$OUTPUT" | grep -q "VOLATILITY ALERT"; then
    echo "  ⚠️  HIGH VOLATILITY DETECTED"
    echo "$OUTPUT" | grep -A 5 "VOLATILITY ALERT"
    # TODO: Send Telegram notification here
  else
    echo "  ✓ No high volatility (all positions < 5%)"
  fi
  
  echo "  → Next check in 60 seconds"
  echo ""
  
  sleep 60
done
