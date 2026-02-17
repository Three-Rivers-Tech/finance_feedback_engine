#!/usr/bin/env bash
# Create Linear ticket for QA work
# Usage: ./scripts/create_linear_ticket.sh "Ticket Title" "Ticket Description" [priority]

set -euo pipefail

# Configuration
LINEAR_API_KEY=$(security find-generic-password -a openclaw -s linear-api-key -w)
TEAM_ID="a75d0448-7d6a-4c06-81b7-1fe622dc7e25"  # THR team
STATE_IN_PROGRESS="6515d5db-3c44-4b42-bcb7-d8d67bfdd843"

# Parse arguments
TITLE="${1:-}"
DESCRIPTION="${2:-}"
PRIORITY="${3:-1}"  # 1 = High, 2 = Medium, 3 = Low, 4 = Urgent

if [ -z "$TITLE" ]; then
    echo "Usage: $0 \"Ticket Title\" \"Ticket Description\" [priority]"
    echo "Priority: 1=High (default), 2=Medium, 3=Low, 4=Urgent"
    exit 1
fi

if [ -z "$DESCRIPTION" ]; then
    DESCRIPTION="$TITLE"
fi

# Create GraphQL query
QUERY=$(cat <<EOF
{
  "query": "mutation IssueCreate(\$input: IssueCreateInput!) { issueCreate(input: \$input) { success issue { id identifier title url } } }",
  "variables": {
    "input": {
      "teamId": "$TEAM_ID",
      "title": "$TITLE",
      "description": "$DESCRIPTION",
      "priority": $PRIORITY,
      "stateId": "$STATE_IN_PROGRESS"
    }
  }
}
EOF
)

# Create ticket
echo "Creating Linear ticket..."
RESPONSE=$(curl -s -X POST https://api.linear.app/graphql \
  -H "Authorization: $LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$QUERY")

# Parse response
IDENTIFIER=$(echo "$RESPONSE" | jq -r '.data.issueCreate.issue.identifier')
URL=$(echo "$RESPONSE" | jq -r '.data.issueCreate.issue.url')

if [ "$IDENTIFIER" != "null" ]; then
    echo "✅ Created ticket: $IDENTIFIER"
    echo "📎 URL: $URL"
else
    echo "❌ Failed to create ticket"
    echo "$RESPONSE" | jq .
    exit 1
fi
