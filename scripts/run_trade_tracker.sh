#!/bin/sh
# Trade Tracker Monitor (THR-221)
# Runs every 5 minutes to detect position closes

set -e

echo "Starting Trade Tracker Monitor..."
echo "Poll interval: 5 minutes (300s)"
echo "Purpose: Detect position closes and record trade outcomes"
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
  
  echo "[$TIMESTAMP] Trade Tracker Check #$ITERATION"
  
  # Run track-trades command
  if python -m finance_feedback_engine.cli.main track-trades 2>&1 | tee /tmp/trade_tracker_last.log; then
    echo "  ✓ Track trades completed successfully"
  else
    EXIT_CODE=$?
    echo "  ✗ Track trades failed (exit code: $EXIT_CODE)"
    echo "  → Data may be stale - will retry in 5 minutes"
  fi
  
  echo "  → Next check in 5 minutes"
  echo ""
  
  sleep 300
done
