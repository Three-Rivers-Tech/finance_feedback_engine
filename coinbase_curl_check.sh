#!/bin/bash
# Direct Coinbase API check via curl

source .env

TIMESTAMP=$(date +%s)
METHOD="GET"
PATH="/api/v3/brokerage/accounts"
MESSAGE="${TIMESTAMP}${METHOD}${PATH}"

# Generate HMAC SHA256 signature
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$COINBASE_API_SECRET" | awk '{print $2}')

echo "=== COINBASE API CHECK ==="
echo "Timestamp: $TIMESTAMP"
echo "Path: $PATH"
echo ""

curl -s -X GET "https://api.coinbase.com${PATH}" \
  -H "CB-ACCESS-KEY: $COINBASE_API_KEY" \
  -H "CB-ACCESS-SIGN: $SIGNATURE" \
  -H "CB-ACCESS-TIMESTAMP: $TIMESTAMP" \
  -H "Content-Type: application/json" | python3 -m json.tool
