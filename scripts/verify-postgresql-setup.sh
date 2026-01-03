#!/bin/bash
# ============================================================================
# PostgreSQL + Docker Deployment Verification Script
# ============================================================================
# Quick sanity check that all components are properly configured
# ============================================================================

set -e

echo "🔍 Verifying PostgreSQL + Docker deployment setup..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

# Test function
test_file() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $description (missing: $file)"
        ((FAIL++))
    fi
}

test_syntax() {
    local file=$1
    local description=$2

    if python -m py_compile "$file" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $description"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $description (syntax error)"
        ((FAIL++))
    fi
}

test_yaml() {
    local file=$1
    local description=$2

    if python -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $description"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $description (YAML error)"
        ((FAIL++))
    fi
}

test_docker_compose() {
    local file=$1
    local description=$2

    if docker-compose -f "$file" config > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $description"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $description (docker-compose error)"
        ((FAIL++))
    fi
}

echo "📋 Files & Configuration:"
test_file "finance_feedback_engine/database.py" "SQLAlchemy database layer"
test_file "alembic/env.py" "Alembic environment configuration"
test_file "alembic.ini" "Alembic configuration file"
test_file "scripts/init-db.sql" "PostgreSQL initialization script"
test_file "scripts/backup-database.sh" "Database backup script"
test_file "scripts/restore-database.sh" "Database restore script"
test_file "docs/POSTGRESQL_DEPLOYMENT.md" "PostgreSQL deployment documentation"
test_file ".env.example" "Environment variables template"
test_file ".env.production.example" "Production environment template"
test_file ".env.test.example" "Test environment template"

echo ""
echo "🐍 Python Syntax:"
test_syntax "finance_feedback_engine/database.py" "database.py syntax"
test_syntax "alembic/env.py" "alembic/env.py syntax"
test_syntax "finance_feedback_engine/api/app.py" "app.py syntax"
test_syntax "finance_feedback_engine/api/health_checks.py" "health_checks.py syntax"
test_syntax "alembic/versions/001_initial_auth_schema.py" "Migration 001 syntax"
test_syntax "alembic/versions/002_decision_cache_schema.py" "Migration 002 syntax"
test_syntax "alembic/versions/003_portfolio_memory_schema.py" "Migration 003 syntax"
test_syntax "alembic/versions/004_add_indexes.py" "Migration 004 syntax"

echo ""
echo "📝 YAML Configuration:"
test_yaml "config/config.yaml" "config.yaml YAML syntax"
test_yaml "docker-compose.yml" "docker-compose.yml YAML syntax"
test_yaml "docker-compose.test.yml" "docker-compose.test.yml YAML syntax"

echo ""
echo "🐳 Docker Compose:"
test_docker_compose "docker-compose.yml" "docker-compose.yml validation"
test_docker_compose "docker-compose.test.yml" "docker-compose.test.yml validation"

echo ""
echo "🔑 Environment Variables:"
if grep -q "DATABASE_URL" .env.example; then
    echo -e "${GREEN}✓${NC} .env.example has DATABASE_URL"
    ((PASS++))
else
    echo -e "${RED}✗${NC} .env.example missing DATABASE_URL"
    ((FAIL++))
fi

if grep -q "DB_POOL_SIZE" .env.example; then
    echo -e "${GREEN}✓${NC} .env.example has DB_POOL_SIZE"
    ((PASS++))
else
    echo -e "${RED}✗${NC} .env.example missing DB_POOL_SIZE"
    ((FAIL++))
fi

if grep -q "DATABASE_URL" .env.production.example; then
    echo -e "${GREEN}✓${NC} .env.production.example has DATABASE_URL"
    ((PASS++))
else
    echo -e "${RED}✗${NC} .env.production.example missing DATABASE_URL"
    ((FAIL++))
fi

if grep -q "DATABASE_URL" .env.test.example; then
    echo -e "${GREEN}✓${NC} .env.test.example has DATABASE_URL"
    ((PASS++))
else
    echo -e "${RED}✗${NC} .env.test.example missing DATABASE_URL"
    ((FAIL++))
fi

echo ""
echo "📊 Summary:"
echo -e "  ${GREEN}Passed: $PASS${NC}"
echo -e "  ${RED}Failed: $FAIL${NC}"

if [ $FAIL -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All checks passed! PostgreSQL deployment is ready.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. cp .env.example .env"
    echo "  2. Edit .env with your PostgreSQL password and API keys"
    echo "  3. docker-compose up -d"
    echo "  4. curl http://localhost:8000/ready  # Check readiness"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}❌ Some checks failed. Please review the errors above.${NC}"
    exit 1
fi
