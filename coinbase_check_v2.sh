#!/usr/bin/env bash
# Direct Coinbase API check via curl with full paths

set -e

# Load environment
export $(grep -v '^#' .env | xargs)

TIMESTAMP=$(/bin/date +%s)
METHOD="GET"
PATH_API="/api/v3/brokerage/accounts"
MESSAGE="${TIMESTAMP}${METHOD}${PATH_API}"

# Generate HMAC SHA256 signature
SIGNATURE=$(/bin/echo -n "$MESSAGE" | /opt/homebrew/bin/openssl dgst -sha256 -hmac "$COINBASE_API_SECRET" | /usr/bin/awk '{print $2}')

echo "=== COINBASE PRODUCTION API CHECK ==="
echo "Checking: https://api.coinbase.com${PATH_API}"
echo ""

/usr/bin/curl -s -X GET "https://api.coinbase.com${PATH_API}" \
  -H "CB-ACCESS-KEY: $COINBASE_API_KEY" \
  -H "CB-ACCESS-SIGN: $SIGNATURE" \
  -H "CB-ACCESS-TIMESTAMP: $TIMESTAMP" \
  -H "Content-Type: application/json" | /opt/homebrew/bin/python3 -m json.tool 2>&1 | head -100
