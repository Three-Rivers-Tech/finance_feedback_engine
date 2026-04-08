#!/bin/bash
# Finance Feedback Engine - Deployment Verification Script
# Tests all critical components of the stack

set -e

VERIFY_FRONTEND=${VERIFY_FRONTEND:-0}

if docker compose version >/dev/null 2>&1; then
    COMPOSE_BIN="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_BIN="docker-compose"
else
    echo -e "${RED}❌ Docker Compose not found${NC}"
    exit 1
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}Finance Feedback Engine - Deployment Check${NC}"
echo -e "${GREEN}===========================================${NC}"
echo ""

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local expected=$3

    echo -n "Testing $name... "

    if response=$(curl -sf "$url" 2>&1); then
        if [[ -z "$expected" ]] || echo "$response" | grep -q "$expected"; then
            echo -e "${GREEN}✅ OK${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  Response unexpected${NC}"
            echo "  Expected: $expected"
            echo "  Got: $(echo $response | head -c 100)"
            return 1
        fi
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "  Error: $response"
        return 1
    fi
}


SPINE_LOOKBACK_MIN=${SPINE_LOOKBACK_MIN:-120}

verify_spine_health() {
    local lookback_min=${SPINE_LOOKBACK_MIN}
    local log_file
    log_file=$(mktemp)
    $COMPOSE_BIN logs --since="${lookback_min}m" backend 2>/dev/null > "$log_file" || true

    local output
    if output=$(LOOKBACK_MIN="$lookback_min" BACKEND_LOG_PATH="$log_file" python3 - <<'PY'
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

lookback_min = int(os.environ.get("LOOKBACK_MIN", "120"))
log_path = os.environ.get("BACKEND_LOG_PATH")
log_text = Path(log_path).read_text() if log_path and Path(log_path).exists() else ""
cutoff = datetime.now(timezone.utc) - timedelta(minutes=lookback_min)
base = Path("data/decisions")

valid_judge = []
valid_pre = []
hollow = []


def parse_ts(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def recent_enough(path, payload):
    ts = parse_ts(payload.get("timestamp"))
    if ts is None:
        ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts >= cutoff

for candidate in sorted(base.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:80]:
    try:
        payload = json.loads(candidate.read_text())
    except Exception:
        continue
    if not recent_enough(candidate, payload):
        continue

    origin = payload.get("decision_origin")
    regime = payload.get("market_regime")
    filtered = payload.get("filtered_reason_code")
    pre_skipped = bool(payload.get("pre_reason_skipped"))
    has_ensemble = bool(payload.get("ensemble_metadata"))
    has_pre_reasoning = bool(payload.get("pre_reasoning"))

    if filtered == "NO_DECISION_PAYLOAD" or not origin or not regime:
        hollow.append(f"artifact:{candidate.name}: origin={origin} regime={regime} filtered={filtered}")
        continue

    if origin == "judge" and has_ensemble:
        valid_judge.append(candidate.name)
    if origin == "pre_reasoner" and pre_skipped and has_pre_reasoning:
        valid_pre.append(candidate.name)

for raw_line in log_text.splitlines():
    line = raw_line.strip()
    if "CORE post-generate shape" not in line and "CORE pre-save shape" not in line:
        continue
    origin = None
    regime = None
    filtered = None
    has_ensemble = None
    has_pre_reasoning = None
    try:
        if "origin=" in line:
            origin = line.split("origin=", 1)[1].split()[0]
        if "regime=" in line:
            regime = line.split("regime=", 1)[1].split()[0]
        if "filtered=" in line:
            filtered = line.split("filtered=", 1)[1].split()[0]
        if "has_ensemble=" in line:
            has_ensemble = line.split("has_ensemble=", 1)[1].split()[0]
        if "has_pre_reasoning=" in line:
            has_pre_reasoning = line.split("has_pre_reasoning=", 1)[1].split()[0]
    except Exception:
        pass

    if filtered == "NO_DECISION_PAYLOAD" or origin in {None, "None", "null"} or regime in {None, "None", "null"}:
        hollow.append(f"log:{line[-180:]}")
        continue

    if origin == "judge" and has_ensemble == "True":
        valid_judge.append("log")
    if origin == "pre_reasoner" and has_pre_reasoning == "True":
        valid_pre.append("log")

if hollow:
    print("Fresh hollow decision outputs detected:")
    for item in hollow[:10]:
        print(f"  - {item}")
    raise SystemExit(1)

if not valid_judge and not valid_pre:
    print("No fresh spine-valid judge or pre-reason decisions found.")
    raise SystemExit(1)

print(
    "Fresh spine-valid outputs found: "
    f"judge={len(valid_judge)} pre_reason={len(valid_pre)} lookback_min={lookback_min}"
)
PY
); then
        echo -e "${GREEN}✅ OK${NC}"
        echo "$output" | sed 's/^/  /'
        rm -f "$log_file"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "$output" | sed 's/^/  /'
        rm -f "$log_file"
        return 1
    fi
}

# Test counter
passed=0
failed=0

# 1. Frontend
echo -e "\n${YELLOW}[1/9]${NC} Frontend (React SPA)"
if test_endpoint "Frontend HTML" "http://localhost" "<!doctype html>"; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

if test_endpoint "Frontend Assets" "http://localhost/assets/" ""; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# 2. Backend API
echo -e "\n${YELLOW}[2/9]${NC} Backend API"
if test_endpoint "Health Check" "http://localhost:8000/health" '"status":"healthy"'; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

if test_endpoint "API Docs" "http://localhost:8000/docs" "Swagger UI"; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# 3. API Endpoints
echo -e "\n${YELLOW}[3/9]${NC} API Endpoints"
if test_endpoint "Bot Status" "http://localhost:8000/api/v1/bot/status" '"state"'; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

if test_endpoint "System Status" "http://localhost:8000/api/v1/status" '"balance"'; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# 4. Nginx Proxy
echo -e "\n${YELLOW}[4/9]${NC} Nginx API Proxy"
if test_endpoint "Frontend → Backend Proxy" "http://localhost/api/v1/status" '"balance"'; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# 5. Prometheus
echo -e "\n${YELLOW}[5/9]${NC} Prometheus Metrics"
if test_endpoint "Prometheus UI" "http://localhost:9090" "Prometheus"; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

if test_endpoint "Metrics Endpoint" "http://localhost:8000/metrics" "# HELP"; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# 6. Grafana
echo -e "\n${YELLOW}[6/9]${NC} Grafana Monitoring"
if test_endpoint "Grafana UI" "http://localhost:3001" "Grafana"; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# 7. Docker Services
echo -e "\n${YELLOW}[7/9]${NC} Docker Services"
echo -n "Checking running containers... "
running_containers=$($COMPOSE_BIN ps | grep -c "Up" || true)
expected_containers=3  # backend, prometheus, grafana (frontend optional)
if [ "$VERIFY_FRONTEND" = "1" ]; then
    expected_containers=4  # backend, frontend, prometheus, grafana
fi

if [ "$running_containers" -ge "$expected_containers" ]; then
    echo -e "${GREEN}✅ OK ($running_containers containers)${NC}"
    passed=$((passed + 1))
else
    echo -e "${RED}❌ FAILED (Only $running_containers/$expected_containers running)${NC}"
    failed=$((failed + 1))
fi

# 8. GPU Access
echo -e "\n${YELLOW}[8/9]${NC} GPU & LLM Setup"
echo -n "Checking GPU access... "
if docker exec ffe-backend nvidia-smi > /dev/null 2>&1; then
    gpu_name=$(docker exec ffe-backend nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)
    echo -e "${GREEN}✅ OK ($gpu_name)${NC}"
    passed=$((passed + 1))
else
    echo -e "${YELLOW}⚠️  GPU not accessible${NC}"
    failed=$((failed + 1))
fi

echo -n "Checking Ollama connection... "
if docker exec ffe-backend curl -sf http://host.docker.internal:11434/api/version > /dev/null 2>&1; then
    ollama_version=$(curl -sf http://localhost:11434/api/version 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✅ OK (v${ollama_version})${NC}"
    passed=$((passed + 1))
else
    echo -e "${YELLOW}⚠️  Ollama not reachable${NC}"
    echo "  Make sure Ollama is running on host: ollama serve"
    failed=$((failed + 1))
fi


# 9. Decision Spine Health
echo -e "\n${YELLOW}[9/9]${NC} Decision Spine Health"
echo -n "Checking fresh spine-valid outputs... "
if verify_spine_health; then
    passed=$((passed + 1))
else
    failed=$((failed + 1))
fi

# Summary
echo ""
echo -e "${GREEN}===========================================${NC}"
echo -e "${GREEN}Summary${NC}"
echo -e "${GREEN}===========================================${NC}"
echo -e "Passed: ${GREEN}$passed${NC}"
echo -e "Failed: ${RED}$failed${NC}"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Deployment is ready.${NC}"
    if [ "$VERIFY_FRONTEND" != "1" ]; then
        echo -e "${YELLOW}Frontend verification was skipped (VERIFY_FRONTEND=0).${NC}"
    fi
    echo ""
    echo -e "${GREEN}Access URLs:${NC}"
    echo "  Frontend:  http://localhost"
    echo "  API Docs:  http://localhost:8000/docs"
    echo "  Grafana:   http://localhost:3001 (admin/admin)"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Open http://localhost to access the dashboard"
    echo "  2. Start the bot from the Agent Control panel"
    echo "  3. Monitor performance in Grafana"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please review the errors above.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  - View logs: docker-compose logs -f"
    echo "  - Check status: ./scripts/deploy.sh production status"
    echo "  - Restart: ./scripts/deploy.sh production restart"
    echo ""
    exit 1
fi
