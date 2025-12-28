#!/bin/bash
# Finance Feedback Engine - Deployment Verification Script
# Tests all critical components of the stack

set -e

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

# Test counter
passed=0
failed=0

# 1. Frontend
echo -e "\n${YELLOW}[1/8]${NC} Frontend (React SPA)"
if test_endpoint "Frontend HTML" "http://localhost" "<!doctype html>"; then
    ((passed++))
else
    ((failed++))
fi

if test_endpoint "Frontend Assets" "http://localhost/assets/" ""; then
    ((passed++))
else
    ((failed++))
fi

# 2. Backend API
echo -e "\n${YELLOW}[2/8]${NC} Backend API"
if test_endpoint "Health Check" "http://localhost:8000/health" '"status":"healthy"'; then
    ((passed++))
else
    ((failed++))
fi

if test_endpoint "API Docs" "http://localhost:8000/docs" "Swagger UI"; then
    ((passed++))
else
    ((failed++))
fi

# 3. API Endpoints
echo -e "\n${YELLOW}[3/8]${NC} API Endpoints"
if test_endpoint "Bot Status" "http://localhost:8000/api/v1/bot/status" '"state"'; then
    ((passed++))
else
    ((failed++))
fi

if test_endpoint "System Status" "http://localhost:8000/api/v1/status" '"balance"'; then
    ((passed++))
else
    ((failed++))
fi

# 4. Nginx Proxy
echo -e "\n${YELLOW}[4/8]${NC} Nginx API Proxy"
if test_endpoint "Frontend → Backend Proxy" "http://localhost/api/v1/status" '"balance"'; then
    ((passed++))
else
    ((failed++))
fi

# 5. Prometheus
echo -e "\n${YELLOW}[5/8]${NC} Prometheus Metrics"
if test_endpoint "Prometheus UI" "http://localhost:9090" "Prometheus"; then
    ((passed++))
else
    ((failed++))
fi

if test_endpoint "Metrics Endpoint" "http://localhost:8000/metrics" "# HELP"; then
    ((passed++))
else
    ((failed++))
fi

# 6. Grafana
echo -e "\n${YELLOW}[6/8]${NC} Grafana Monitoring"
if test_endpoint "Grafana UI" "http://localhost:3001" "Grafana"; then
    ((passed++))
else
    ((failed++))
fi

# 7. Docker Services
echo -e "\n${YELLOW}[7/8]${NC} Docker Services"
echo -n "Checking running containers... "
running_containers=$(docker-compose ps | grep -c "Up" || true)
expected_containers=4  # backend, frontend, prometheus, grafana

if [ "$running_containers" -ge "$expected_containers" ]; then
    echo -e "${GREEN}✅ OK ($running_containers containers)${NC}"
    ((passed++))
else
    echo -e "${RED}❌ FAILED (Only $running_containers/$expected_containers running)${NC}"
    ((failed++))
fi

# 8. GPU Access
echo -e "\n${YELLOW}[8/8]${NC} GPU & LLM Setup"
echo -n "Checking GPU access... "
if docker exec ffe-backend nvidia-smi > /dev/null 2>&1; then
    gpu_name=$(docker exec ffe-backend nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null)
    echo -e "${GREEN}✅ OK ($gpu_name)${NC}"
    ((passed++))
else
    echo -e "${YELLOW}⚠️  GPU not accessible${NC}"
    ((failed++))
fi

echo -n "Checking Ollama connection... "
if docker exec ffe-backend curl -sf http://host.docker.internal:11434/api/version > /dev/null 2>&1; then
    ollama_version=$(curl -sf http://localhost:11434/api/version 2>/dev/null | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✅ OK (v${ollama_version})${NC}"
    ((passed++))
else
    echo -e "${YELLOW}⚠️  Ollama not reachable${NC}"
    echo "  Make sure Ollama is running on host: ollama serve"
    ((failed++))
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
