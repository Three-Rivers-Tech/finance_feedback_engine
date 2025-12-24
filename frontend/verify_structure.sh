#!/bin/bash

echo "Checking Frontend File Structure..."
echo ""

files=(
  "src/App.tsx"
  "src/main.tsx"
  "src/index.css"
  "src/api/client.ts"
  "src/api/types.ts"
  "src/api/hooks/usePolling.ts"
  "src/api/hooks/useAgentStatus.ts"
  "src/api/hooks/usePortfolio.ts"
  "src/api/hooks/usePositions.ts"
  "src/api/hooks/useDecisions.ts"
  "src/api/hooks/useHealth.ts"
  "src/stores/authStore.ts"
  "src/services/formatters.ts"
  "src/utils/constants.ts"
  "src/components/common/Card.tsx"
  "src/components/common/Button.tsx"
  "src/components/common/MetricCard.tsx"
  "src/components/common/Badge.tsx"
  "src/components/common/Spinner.tsx"
  "src/components/layout/AppLayout.tsx"
  "src/components/layout/Header.tsx"
  "src/components/layout/Sidebar.tsx"
  "src/components/dashboard/PortfolioOverview.tsx"
  "src/components/dashboard/PositionsTable.tsx"
  "src/components/dashboard/RecentDecisions.tsx"
  "src/components/agent/AgentStatusDisplay.tsx"
  "src/components/agent/AgentControlPanel.tsx"
  "src/components/agent/CircuitBreakerStatus.tsx"
  "src/pages/Dashboard.tsx"
  "src/pages/AgentControl.tsx"
  "src/pages/Analytics.tsx"
  "src/pages/Optimization.tsx"
  ".env"
  "package.json"
  "vite.config.ts"
  "tailwind.config.js"
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
  echo "✅ All ${#files[@]} critical files present!"
else
  echo "❌ $missing files missing!"
  exit 1
fi
