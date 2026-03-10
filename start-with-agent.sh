#!/bin/sh
# FFE Startup Script - Auto-starts API and Trading Agent
set -e

echo "🚀 Starting Finance Feedback Engine API..."

# Start uvicorn in background
uvicorn finance_feedback_engine.api.app:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Wait for API to be healthy
echo "⏳ Waiting for API health check..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ API is healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ API failed to start"
    kill $UVICORN_PID 2>/dev/null || true
    exit 1
fi

# Get asset pairs from environment or use defaults
ASSET_PAIRS="${AGENT_ASSET_PAIRS:-BTCUSD,ETHUSD}"
echo "🎯 Asset pairs: $ASSET_PAIRS"

# Start the trading agent
echo "🤖 Starting trading agent..."
curl -sf -X POST http://localhost:8000/api/v1/bot/start \
    -H "Content-Type: application/json" \
    -d "{\"autonomous\": true, \"asset_pairs\": [\"$(echo $ASSET_PAIRS | sed 's/,/","/g')\"]}" || {
    echo "⚠️ Failed to start trading agent (may already be running)"
}

echo "✅ Trading agent started"
echo "📊 Bot is operational"

# Keep uvicorn running
wait $UVICORN_PID
