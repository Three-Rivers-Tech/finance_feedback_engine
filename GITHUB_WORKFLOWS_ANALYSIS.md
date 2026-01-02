# GitHub Workflows Analysis & Recommendations

**Date:** 2026-01-02  
**Status:** Multiple workflows failing  
**Goal:** Apply industry best practices from GitHub repos and web sources

## Current State Overview

### Failing Workflows (from recent runs)
1. **Backup Automation** - ❌ Failure
2. **Staging Environment Tests** - ❌ Failure  
3. **Performance Testing** - ❌ Failure
4. **Build and Push Docker Images** - ❌ Failure
5. **Security Scanning** - ⚠️ Intermittent failures
6. **CI** - ⚠️ Some failures
7. **Release Automation** - ⏳ In progress

### Passing Workflows
- ✅ Monitoring & Alerting
- ✅ Security Scanning (recent runs)

---

## Research Findings: Industry Best Practices

### 1. Error Handling & Conditional Execution

Based on research from Ken Muse, KodeKloud, and Stack Overflow discussions:

**Key Principles:**
- **`continue-on-error: true`** - Use ONLY for non-critical steps where failures should be ignored
  - Sets step.outcome but doesn't fail the job
  - Can mask real failures if overused
  - Good for: optional services (Ollama), experimental features, reporting steps

- **`if: always()`** - Better for cleanup/artifact steps that must run after failure
  - Still marks job as failed if earlier steps failed
  - Good for: log collection, artifact upload, cleanup
  - Consider `if: success() || failure()` to exclude cancelled runs

**Sources:**
- https://www.kenmuse.com/blog/how-to-handle-step-and-job-errors-in-github-actions/
- https://notes.kodekloud.com/docs/GitHub-Actions/Continuous-Integration-with-GitHub-Actions/Using-continue-on-error-expression
- https://stackoverflow.com/questions/58858429/how-to-run-a-github-actions-step-even-if-the-previous-step-fails-while-still-f

### 2. Docker Compose Health Checks

Research from Docker Compose documentation and GitHub marketplace:

**Critical Pattern:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s  # Important for slow-starting services
```

**Use dedicated health check action:**
```yaml
- name: Wait for services
  uses: jaracogmbh/docker-compose-health-check-action@v1.0.0
  with:
    compose-file: "docker-compose.test.yml"
    max-retries: 30
    retry-interval: 10
    skip-exited: "true"  # Skip init containers
    skip-no-healthcheck: "true"  # Skip optional services
```

**Sources:**
- https://github.com/marketplace/actions/docker-compose-health-check
- https://www.tvaidyan.com/2025/02/13/health-checks-in-docker-compose-a-practical-guide/
- https://docs.docker.com/guides/gha/

### 3. Python CI/CD Best Practices

From GitHub official docs and industry tutorials:

**Matrix Testing:**
```yaml
strategy:
  matrix:
    python-version: [3.9, 3.10, 3.11, 3.12, 3.13]
    os: [ubuntu-latest, macos-latest]  # If needed
  fail-fast: false  # Continue testing other versions
```

**Coverage Enforcement:**
```yaml
- name: Run tests with coverage
  run: |
    pytest --cov=src \
      --cov-report=xml \
      --cov-report=html \
      --cov-report=term-missing \
      --cov-fail-under=70 \
      -v
```

**Caching Strategy:**
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: ${{ matrix.python-version }}
    cache: 'pip'  # Built-in pip caching
    cache-dependency-path: |
      requirements.txt
      requirements-dev.txt
```

**Sources:**
- https://docs.github.com/en/actions/tutorials/build-and-test-code/python
- https://pytest-with-eric.com/integrations/pytest-github-actions/
- https://realpython.com/github-actions-python/

---

## Specific Issues Found

### Issue 1: Backup Automation Workflow
**Problem:** Requires AWS secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BACKUP_BUCKET`)  
**Evidence:** Line 144-146, 232-234 in backup-automation.yml  
**Impact:** Fails on scheduled runs and manual dispatch

**Recommendation:**
```yaml
- name: Upload to cloud storage
  if: |
    (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch') &&
    secrets.AWS_ACCESS_KEY_ID != '' &&
    secrets.AWS_SECRET_ACCESS_KEY != ''
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    # ... rest
```

Add fallback to artifacts-only mode if AWS not configured.

### Issue 2: Staging Workflow Docker Compose
**Problem:** Complex health check logic with manual polling  
**Current:** Lines 60-106 in staging.yml use bash loops and timeouts  
**Better:** Use dedicated health check action

**Recommendation:**
```yaml
- name: Start services
  run: docker compose -f ${{ env.COMPOSE_FILE }} up -d

- name: Wait for all services to be healthy
  uses: jaracogmbh/docker-compose-health-check-action@v1.0.0
  with:
    compose-file: ${{ env.COMPOSE_FILE }}
    max-retries: 60
    retry-interval: 5
    skip-exited: "true"
    skip-no-healthcheck: "true"
```

Ensure all services in `docker-compose.test.yml` have proper healthchecks defined.

### Issue 3: Performance Testing Environment Variable
**Problem:** `ENVIRONMENT: ci` is required but not set in load-test job  
**Current:** Line 215 sets it, but other jobs don't  
**Impact:** Application may fail to start or use wrong config

**Recommendation:**
Add to workflow-level `env:` section:
```yaml
env:
  PYTHON_VERSION: '3.13'
  ENVIRONMENT: ci  # Add this
```

### Issue 4: Conditional Step Patterns
**Current Issues:**
- `continue-on-error: true` used inconsistently
- Some critical steps marked as continue-on-error (integration tests at line 144-162 in staging.yml)
- Output checking pattern is verbose

**Recommended Pattern:**
```yaml
# For optional services (Ollama)
- name: Pull Ollama model (optional)
  continue-on-error: true
  run: |
    docker compose exec -T ollama ollama pull llama3.2:3b-instruct-fp16

# For critical tests that need cleanup
- name: Run integration tests
  id: tests
  run: |
    pytest --cov=... -v
  # Don't use continue-on-error

- name: Upload logs
  if: always()  # Run even if tests fail
  uses: actions/upload-artifact@v4

- name: Check test results
  if: always()
  run: |
    if [ "${{ steps.tests.outcome }}" != "success" ]; then
      echo "Tests failed"
      exit 1
    fi
```

### Issue 5: Docker Build Push Workflow
**Problem:** Security scan depends on latest tag but images may not exist on PRs  
**Current:** Line 153 pulls `:latest` but PRs don't push  
**Impact:** Security scan fails on PRs

**Recommendation:**
```yaml
security-scan:
  needs: [build-backend, build-frontend]
  if: github.event_name != 'pull_request'  # Already present, good
  # But also need to handle image tags properly

  - name: Set image tag
    id: tag
    run: |
      if [ "${{ github.event_name }}" == "pull_request" ]; then
        echo "tag=pr-${{ github.event.number }}" >> $GITHUB_OUTPUT
      else
        echo "tag=latest" >> $GITHUB_OUTPUT
      fi

  - name: Pull image
    run: |
      docker pull ${{ env.REGISTRY }}/${{ github.repository }}-${{ matrix.image }}:${{ steps.tag.outputs.tag }}
```

Or simplify: only run security scan on pushes to main/develop.

### Issue 6: Workflow Dependencies & Job Status
**Problem:** Summary jobs don't handle skipped dependencies correctly  
**Current:** Multiple summary jobs check `result == 'success'`  
**Issue:** If a job is skipped, result is 'skipped' not 'success'

**Recommendation:**
```yaml
- name: Check all jobs
  run: |
    # Account for skipped jobs
    if [ "${{ needs.pre-commit.result }}" == "success" ] && \
       [ "${{ needs.test.result }}" == "success" ] && \
       ([ "${{ needs.security.result }}" == "success" ] || [ "${{ needs.security.result }}" == "skipped" ]); then
      echo "✅ All required CI checks passed"
      exit 0
    fi
    echo "❌ CI checks failed"
    exit 1
```

---

## Recommended Action Plan

### Phase 1: Critical Fixes (Do Now)

1. **Fix Backup Workflow**
   - Add AWS secrets check before cloud operations
   - Make cloud backup optional with artifact fallback
   - Document required secrets in README

2. **Fix Staging Health Checks**
   - Replace manual polling with `docker-compose-health-check-action`
   - Ensure all services in docker-compose.test.yml have healthchecks
   - Add `start_period` to slow-starting services (Backend, Ollama)

3. **Fix Performance Testing**
   - Add `ENVIRONMENT: ci` to workflow-level env
   - Verify all jobs that start services have this set

4. **Fix Docker Build Security Scan**
   - Only run on pushes to main/develop/tags (not PRs)
   - Already has `if: github.event_name != 'pull_request'` but ensure images exist

### Phase 2: Improvements (Soon)

1. **Standardize Error Handling**
   - Review all `continue-on-error` usage
   - Replace with `if: always()` where appropriate
   - Document which steps are critical vs optional

2. **Add Matrix Testing to CI**
   - Test multiple Python versions (3.11, 3.12, 3.13)
   - Use `fail-fast: false` to see all results

3. **Improve Caching**
   - Add pip caching to all jobs
   - Use Docker layer caching in all build jobs
   - Cache pre-commit hooks

4. **Add Workflow Validation**
   - Use `actionlint` in pre-commit or as CI step
   - Validate workflow syntax before pushing

### Phase 3: Enhancements (Later)

1. **Add Reusable Workflows**
   - Extract common patterns (setup Python, install deps)
   - Create composite actions for repeated steps

2. **Improve Monitoring**
   - Add workflow run time tracking
   - Alert on consistent failures
   - Track flaky tests

3. **Security Hardening**
   - Use explicit action versions (not @main)
   - Pin action SHAs for security-critical workflows
   - Review secret usage and permissions

---

## Example Fixes

### Fix 1: Staging Workflow Health Checks

**Before:**
```yaml
- name: Wait for Backend to be healthy
  run: |
    timeout 120 bash -c 'until docker compose -f ${{ env.COMPOSE_FILE }} ps | grep backend | grep -q healthy; do sleep 3; done' || {
      echo "Backend failed to become healthy"
      docker compose -f ${{ env.COMPOSE_FILE }} logs backend
      exit 1
    }
```

**After:**
```yaml
- name: Start all services
  run: docker compose -f ${{ env.COMPOSE_FILE }} up -d

- name: Wait for services to be healthy
  uses: jaracogmbh/docker-compose-health-check-action@v1.0.0
  with:
    compose-file: ${{ env.COMPOSE_FILE }}
    max-retries: 60
    retry-interval: 5
    skip-exited: "true"
    skip-no-healthcheck: "true"

- name: Show service status on failure
  if: failure()
  run: |
    docker compose -f ${{ env.COMPOSE_FILE }} ps
    docker compose -f ${{ env.COMPOSE_FILE }} logs
```

### Fix 2: Backup Workflow Conditional Cloud Upload

**Before:**
```yaml
- name: Upload to cloud storage
  if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    # ... fails if secrets not set
```

**After:**
```yaml
- name: Check cloud backup availability
  id: cloud-check
  run: |
    if [ -n "${{ secrets.AWS_ACCESS_KEY_ID }}" ] && [ -n "${{ secrets.AWS_SECRET_ACCESS_KEY }}" ]; then
      echo "available=true" >> $GITHUB_OUTPUT
    else
      echo "available=false" >> $GITHUB_OUTPUT
      echo "⚠️ AWS credentials not configured - backup will only be saved to artifacts"
    fi

- name: Upload to cloud storage
  if: |
    steps.cloud-check.outputs.available == 'true' &&
    (github.event_name == 'schedule' || github.event_name == 'workflow_dispatch')
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
  run: |
    # ... upload code
```

### Fix 3: Test Error Handling Pattern

**Before:**
```yaml
- name: Run integration tests in container
  id: integration-tests
  continue-on-error: true  # ❌ Hides failures
  run: |
    docker compose exec -T backend pytest ...
```

**After:**
```yaml
- name: Run integration tests in container
  id: integration-tests
  run: |
    docker compose -f ${{ env.COMPOSE_FILE }} exec -T backend \
      pytest -m "not external_service and not slow" \
        --cov=finance_feedback_engine \
        --cov-report=xml:/app/coverage.xml \
        --cov-fail-under=70 \
        -v

- name: Extract coverage (runs even on test failure)
  if: always()
  run: |
    docker cp ffe-backend-test:/app/coverage.xml ./coverage.xml || \
      echo '<?xml version="1.0" ?><coverage version="7.0" />' > ./coverage.xml

- name: Upload logs (runs even on test failure)
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: test-logs
    path: logs/

# Job fails if tests fail (no masking with continue-on-error)
```

---

## Additional Resources

### GitHub Actions Documentation
- [Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Context and expression syntax](https://docs.github.com/en/actions/learn-github-actions/contexts)

### Best Practice Articles
- [Pytest with GitHub Actions](https://pytest-with-eric.com/integrations/pytest-github-actions/)
- [Docker Compose Health Checks](https://compose-it.top/posts/docker-compose-health-checks)
- [GitHub Actions Error Handling](https://www.kenmuse.com/blog/how-to-handle-step-and-job-errors-in-github-actions/)
- [CI/CD with Docker and GitHub Actions](https://codezup.com/scalable-ci-cd-pipelines-with-docker-and-github-actions/)

### Marketplace Actions
- [Docker Compose Health Check](https://github.com/marketplace/actions/docker-compose-health-check)
- [Codecov Action](https://github.com/marketplace/actions/codecov)
- [Trivy Security Scanner](https://github.com/marketplace/actions/aqua-security-trivy)

---

## Summary

**Key Takeaways:**
1. Use `continue-on-error: true` sparingly - only for truly optional steps
2. Use `if: always()` for cleanup/artifact upload that must run after failure
3. Use dedicated health check actions instead of manual bash loops
4. Always check for required secrets before using them
5. Account for skipped jobs in summary steps
6. Add proper environment variables at workflow level
7. Test across multiple Python versions with matrix strategy
8. Cache aggressively (pip, Docker layers, pre-commit)

**Immediate Actions:**
- Fix AWS secrets check in backup workflow
- Replace manual health checks with action
- Add ENVIRONMENT var to performance workflow
- Review all continue-on-error usage

**Measure Success:**
- Workflow failure rate decreases
- Clearer failure reasons in logs
- Faster workflow execution (with caching)
- No masked failures from continue-on-error abuse
