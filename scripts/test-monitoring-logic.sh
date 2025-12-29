#!/bin/bash
# Test script to simulate monitoring workflow behavior locally
# This helps verify the logic before running in GitHub Actions

set -e

echo "🔍 Monitoring Workflow Test Simulation"
echo "======================================="
echo ""

# Test 1: Skip check with example.com URL
echo "Test 1: Production URL with example.com (should skip)"
PROD_URL="https://api.example.com"

if [[ "$PROD_URL" == *"example.com"* ]]; then
    echo "✅ PASS: Correctly skipped example.com URL"
    HTTP_CODE="SKIPPED"
else
    echo "❌ FAIL: Should have skipped example.com URL"
    exit 1
fi

echo ""

# Test 2: Skip check with staging.example.com
echo "Test 2: Staging URL with staging.example.com (should skip)"
STAGING_URL="https://staging.example.com"

if [[ "$STAGING_URL" == *"example.com"* ]]; then
    echo "✅ PASS: Correctly skipped staging.example.com URL"
    STAGING_CODE="SKIPPED"
else
    echo "❌ FAIL: Should have skipped staging.example.com URL"
    exit 1
fi

echo ""

# Test 3: Alert condition check for production branch
echo "Test 3: Alert conditions (should create alert only on main/production)"
BRANCH="main"
PROD_CHECK_OUTCOME="failure"
HTTP_CODE="500"

if [[ "$PROD_CHECK_OUTCOME" == "failure" ]] && \
   [[ "$HTTP_CODE" != "SKIPPED" ]] && \
   [[ "$BRANCH" == "main" || "$BRANCH" == "production" ]]; then
    echo "✅ PASS: Would create alert on main branch with failure"
else
    echo "❌ FAIL: Should create alert on main with failure"
    exit 1
fi

echo ""

# Test 4: No alert on feature branch
echo "Test 4: Feature branch failure (should NOT create alert)"
BRANCH="feature/test"
PROD_CHECK_OUTCOME="failure"
HTTP_CODE="500"

if [[ "$PROD_CHECK_OUTCOME" == "failure" ]] && \
   [[ "$HTTP_CODE" != "SKIPPED" ]] && \
   [[ "$BRANCH" == "main" || "$BRANCH" == "production" ]]; then
    echo "❌ FAIL: Should NOT create alert on feature branch"
    exit 1
else
    echo "✅ PASS: Correctly skipped alert on feature branch"
fi

echo ""

# Test 5: No alert when check is skipped
echo "Test 5: Skipped check (should NOT create alert)"
BRANCH="main"
PROD_CHECK_OUTCOME="failure"
HTTP_CODE="SKIPPED"

if [[ "$PROD_CHECK_OUTCOME" == "failure" ]] && \
   [[ "$HTTP_CODE" != "SKIPPED" ]] && \
   [[ "$BRANCH" == "main" || "$BRANCH" == "production" ]]; then
    echo "❌ FAIL: Should NOT create alert when check is skipped"
    exit 1
else
    echo "✅ PASS: Correctly skipped alert when check was skipped"
fi

echo ""
echo "======================================="
echo "✅ All tests passed!"
echo ""
echo "Summary:"
echo "- Health checks skip when using example.com URLs"
echo "- Alerts only created on main/production branches"
echo "- Alerts only created when check actually fails (not skipped)"
echo "- Feature branch failures don't trigger alerts"
