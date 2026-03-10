#!/bin/sh
set -eu

cleanup() {
    if [ -n "${UVICORN_PID:-}" ]; then
        kill "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi
}
trap cleanup INT TERM EXIT

echo "🗄️ Running database migrations..."
alembic upgrade head

echo "🚀 Starting Finance Feedback Engine API..."
uvicorn finance_feedback_engine.api.app:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

echo "⏳ Waiting for API health check..."
MAX_RETRIES=${API_HEALTH_MAX_RETRIES:-30}
RETRY_DELAY=${API_HEALTH_RETRY_DELAY_SECONDS:-2}
RETRY_COUNT=0
while [ "$RETRY_COUNT" -lt "$MAX_RETRIES" ]; do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ API is healthy"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep "$RETRY_DELAY"
done
if [ "$RETRY_COUNT" -eq "$MAX_RETRIES" ]; then
    echo "❌ API failed to start"
    exit 1
fi

ASSET_PAIRS="${AGENT_ASSET_PAIRS:-BTCUSD,ETHUSD}"
ASSET_PAIRS_JSON=$(printf '%s' "$ASSET_PAIRS" | python3 -c 'import json,sys; pairs=[p.strip().upper() for p in sys.stdin.read().split(",") if p.strip()]; print(json.dumps(pairs or ["BTCUSD","ETHUSD"]))')
echo "🎯 Asset pairs: $ASSET_PAIRS"
echo "🤖 Starting trading agent..."
if ! curl -sf -X POST http://localhost:8000/api/v1/bot/start -H "Content-Type: application/json" -d "{\"autonomous\": true, \"asset_pairs\": ${ASSET_PAIRS_JSON}}"; then
    echo "⚠️ Failed to start trading agent (may already be running)"
else
    echo
    echo "✅ Trading agent started"
fi

echo "📊 Bot is operational"
wait "$UVICORN_PID"
