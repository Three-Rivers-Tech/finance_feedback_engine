#!/usr/bin/env bash
# Simple wrapper to run the todos collector. Exits non-zero if any High priority items found.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3 || echo python)"
"$PYTHON" "$ROOT/scripts/collect_todos.py"
JSON="$ROOT/developer_markers.json"
if [ -f "$JSON" ]; then
  high_count=$(jq '[.[] | select(.priority=="High")] | length' "$JSON")
  echo "High priority TODOs: $high_count"
  if [ "$high_count" -gt 0 ]; then
    echo "Found high priority TODOs. Inspect docs/todo_report.md or developer_markers.json"
    exit 1
  fi
fi
