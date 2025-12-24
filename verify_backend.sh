#!/bin/bash

echo "Checking Backend & Observability Structure..."
echo ""

files=(
  "docker-compose.yml"
  "observability/prometheus/prometheus.yml"
  "observability/grafana/provisioning/datasources/prometheus.yml"
  "observability/grafana/provisioning/dashboards/dashboards.yml"
  "observability/grafana/dashboards/trading-metrics.json"
  "observability/README.md"
  "finance_feedback_engine/api/app.py"
  "finance_feedback_engine/api/routes.py"
  "finance_feedback_engine/api/bot_control.py"
  "finance_feedback_engine/api/dependencies.py"
  "finance_feedback_engine/api/optimization.py"
  "FRONTEND_COMPLETE.md"
)

missing=0
for file in "${files[@]}"; do
  if [ -f "$file" ]; then
    echo "✅ $file"
  else
    echo "❌ MISSING: $file"
    missing=$((missing + 1))
  fi
done

echo ""
if [ $missing -eq 0 ]; then
  echo "✅ All ${#files[@]} backend/observability files present!"
else
  echo "❌ $missing files missing!"
  exit 1
fi
