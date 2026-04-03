#!/bin/bash
# FFE Telegram Monitor — polls bot status, alerts on position/PnL/state changes.
# Secrets loaded from .ffe-monitor.env (chmod 600, git-ignored).
# State persisted in .ffe-monitor-state.json (git-ignored).
#
# Usage: ./ffe-monitor.sh           # normal run (alert on changes)
#        ./ffe-monitor.sh --force   # force send current status
#        ./ffe-monitor.sh --test    # send test ping

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.ffe-monitor.env"
STATE_FILE="${SCRIPT_DIR}/.ffe-monitor-state.json"
SSH_TIMEOUT=10

# ---------------------------------------------------------------------------
# Load secrets
# ---------------------------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: Missing env file: $ENV_FILE"
    echo "Create it with:"
    echo "  FFE_TG_BOT_TOKEN=<your-bot-token>"
    echo "  FFE_TG_CHAT_ID=<your-chat-id>"
    echo "  FFE_SSH_HOST=<hostname>"
    exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

BOT_TOKEN="${FFE_TG_BOT_TOKEN:?Missing FFE_TG_BOT_TOKEN in $ENV_FILE}"
CHAT_ID="${FFE_TG_CHAT_ID:?Missing FFE_TG_CHAT_ID in $ENV_FILE}"
FFE_HOST="${FFE_SSH_HOST:-gpu-laptop}"
FFE_URL="http://localhost:8000/api/v1/bot/status"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
send_telegram() {
    local msg="$1"
    curl -sf --max-time 10 -X POST \
        "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        -d chat_id="${CHAT_ID}" \
        -d parse_mode="HTML" \
        -d text="${msg}" \
        -d disable_web_page_preview=true > /dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# Handle --test / --force flags
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--test" ]]; then
    send_telegram "🤖 <b>FFE Monitor</b> — test ping at $(date '+%H:%M %Z')"
    echo "Test message sent"
    exit 0
fi

FORCE_SEND=false
if [[ "${1:-}" == "--force" ]]; then
    FORCE_SEND=true
fi

# ---------------------------------------------------------------------------
# Fetch current status from FFE via SSH
# ---------------------------------------------------------------------------
CURRENT=$(ssh -o ConnectTimeout=$SSH_TIMEOUT -o BatchMode=yes \
    "$FFE_HOST" "curl -sf --max-time 8 $FFE_URL" 2>/dev/null) || {
    send_telegram "🔴 <b>FFE ALERT</b>: Cannot reach backend on ${FFE_HOST}"
    exit 1
}

# Validate we got valid JSON
if ! echo "$CURRENT" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    send_telegram "🔴 <b>FFE ALERT</b>: Backend returned invalid JSON"
    exit 1
fi

# ---------------------------------------------------------------------------
# Parse all fields in a single python3 call (no shell injection)
# ---------------------------------------------------------------------------
PARSED=$(echo "$CURRENT" | python3 -c "
import json, sys

d = json.load(sys.stdin)
cb = d.get('portfolio', {}).get('platform_breakdowns', {}).get('coinbase', {})
fs = cb.get('futures_summary', {})
positions = cb.get('futures_positions', [])

# Position fingerprint (sorted, pipe-delimited)
parts = []
for p in positions:
    pid = p.get('product_id', '?')
    side = p.get('side', '?')
    qty = p.get('number_of_contracts', '?')
    pnl = p.get('unrealized_pnl', '0')
    parts.append(f'{pid} {side} {qty}x PnL:{pnl}')
pos_key = '|'.join(sorted(parts)) if parts else 'FLAT'

# Emit tab-separated fields (safe, no injection)
fields = [
    f'{d.get(\"portfolio\", {}).get(\"total_value_usd\", 0):.2f}',
    pos_key,
    f'{fs.get(\"buying_power\", 0):.2f}',
    f'{fs.get(\"daily_realized_pnl\", 0):.2f}',
    str(int(d.get('uptime_seconds', 0))),
    d.get('state', 'unknown'),
    str(len(positions)),
    f'{fs.get(\"unrealized_pnl\", 0):.2f}',
]
print('\t'.join(fields))
" 2>/dev/null) || {
    send_telegram "🔴 <b>FFE ALERT</b>: Failed to parse bot status JSON"
    exit 1
}

# Split tab-separated fields
IFS=$'\t' read -r NOW_PORTFOLIO NOW_POSITIONS NOW_BUYING_POWER NOW_DAILY_PNL \
    NOW_UPTIME NOW_STATE NOW_POS_COUNT NOW_UNREALIZED <<< "$PARSED"

# ---------------------------------------------------------------------------
# Load previous state (single python3 call)
# ---------------------------------------------------------------------------
if [[ -f "$STATE_FILE" ]]; then
    PREV=$(python3 -c "
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print('\t'.join([
        d.get('positions', 'NONE'),
        d.get('daily_pnl', '0'),
        d.get('state', 'unknown'),
        d.get('portfolio', '0'),
    ]))
except Exception:
    print('NONE\t0\tunknown\t0')
" "$STATE_FILE" 2>/dev/null) || PREV="NONE	0	unknown	0"
    IFS=$'\t' read -r PREV_POSITIONS PREV_DAILY_PNL PREV_STATE PREV_PORTFOLIO <<< "$PREV"
else
    PREV_POSITIONS="NONE"
    PREV_DAILY_PNL="0"
    PREV_STATE="unknown"
    PREV_PORTFOLIO="0"
fi

# ---------------------------------------------------------------------------
# Save current state (proper JSON serialization, no shell interpolation)
# ---------------------------------------------------------------------------
python3 -c "
import json, sys
state = {
    'positions': sys.argv[1],
    'daily_pnl': sys.argv[2],
    'state': sys.argv[3],
    'portfolio': sys.argv[4],
    'buying_power': sys.argv[5],
    'pos_count': sys.argv[6],
}
with open(sys.argv[7], 'w') as f:
    json.dump(state, f, indent=2)
" "$NOW_POSITIONS" "$NOW_DAILY_PNL" "$NOW_STATE" "$NOW_PORTFOLIO" \
  "$NOW_BUYING_POWER" "$NOW_POS_COUNT" "$STATE_FILE"

# ---------------------------------------------------------------------------
# Determine what changed
# ---------------------------------------------------------------------------
ALERTS=""

# Position change
if [[ "$NOW_POSITIONS" != "$PREV_POSITIONS" ]]; then
    if [[ "$NOW_POSITIONS" == "FLAT" ]]; then
        ALERTS="${ALERTS}📭 <b>Positions closed</b> → now flat\n"
    elif [[ "$PREV_POSITIONS" == "FLAT" || "$PREV_POSITIONS" == "NONE" ]]; then
        ALERTS="${ALERTS}📊 <b>New position:</b> ${NOW_POSITIONS//|/, }\n"
    else
        ALERTS="${ALERTS}📊 <b>Position change:</b> ${NOW_POSITIONS//|/, }\n"
    fi
fi

# Daily PnL shift > $5
PNL_SHIFTED=$(python3 -c "
a, b = float('${NOW_DAILY_PNL}'), float('${PREV_DAILY_PNL}')
print('yes' if abs(a - b) > 5.0 else 'no')
" 2>/dev/null || echo "no")
if [[ "$PNL_SHIFTED" == "yes" ]]; then
    ALERTS="${ALERTS}💰 <b>Daily PnL:</b> \$${NOW_DAILY_PNL} (was \$${PREV_DAILY_PNL})\n"
fi

# Agent state change
if [[ "$NOW_STATE" != "$PREV_STATE" && "$PREV_STATE" != "unknown" ]]; then
    ALERTS="${ALERTS}⚠️ <b>Agent state:</b> ${PREV_STATE} → ${NOW_STATE}\n"
fi

# Restart detected
if [[ "$NOW_UPTIME" -lt 300 && "$PREV_STATE" != "unknown" ]]; then
    ALERTS="${ALERTS}🔄 <b>Restart detected</b> (uptime: ${NOW_UPTIME}s)\n"
fi

# ---------------------------------------------------------------------------
# Send alert (or force-send full status)
# ---------------------------------------------------------------------------
if [[ -n "$ALERTS" || "$FORCE_SEND" == "true" ]]; then
    UPTIME_H=$((NOW_UPTIME / 3600))
    UPTIME_M=$(( (NOW_UPTIME % 3600) / 60))

    if [[ -z "$ALERTS" ]]; then
        ALERTS="ℹ️ <b>Scheduled status check</b>\n"
    fi

    MSG=$(printf "🤖 <b>FFE Status</b>\n\n%b\n📈 Portfolio: \$%s\n💵 Buying Power: \$%s\n📉 Unrealized: \$%s\n📊 Daily PnL: \$%s\n⏱ Uptime: %dh %dm\n🔧 Positions: %s" \
        "$ALERTS" "$NOW_PORTFOLIO" "$NOW_BUYING_POWER" "$NOW_UNREALIZED" \
        "$NOW_DAILY_PNL" "$UPTIME_H" "$UPTIME_M" "$NOW_POS_COUNT")

    send_telegram "$MSG"
    echo "Alert sent"
else
    echo "No changes detected"
fi
