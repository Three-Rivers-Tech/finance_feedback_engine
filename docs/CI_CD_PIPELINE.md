# CI/CD Pipeline Documentation

## Overview

The CI/CD pipeline has been cleaned up and streamlined to focus on **relevant and useful checks** that actually prevent bugs and security issues from reaching production.

## Active Workflows

### 1. CI (`.github/workflows/ci.yml`)
**Purpose:** Primary continuous integration checks on all PRs and main branch  
**Triggers:** Push to main, all pull requests  
**Jobs:**
- **Pre-commit Checks** - Runs the same checks as local pre-commit hooks
  - Code formatting (black, isort)
  - Linting (flake8)
  - Type checking (mypy)
  - Security (bandit)
  - Secret detection (prevent-secrets)
- **Tests & Coverage** - Runs test suite with 70% coverage requirement
- **Security Scan** - Bandit security analysis
- **CI Success** - Combined status check for branch protection

**Why This Approach:**
- Aligns CI with local development (pre-commit hooks)
- Developers see the same checks locally as in CI
- Fails fast on actual problems
- No `continue-on-error` - checks must pass

### 2. Security Scanning (`.github/workflows/security-scan.yml`)
**Purpose:** Comprehensive security scanning  
**Triggers:** Push to main, PRs to main, daily at 2 AM UTC, manual  
**Jobs:**
- **Dependency Scan** - pip-audit for known CVEs
- **Code Security** - Bandit for code vulnerabilities
- **Secret Detection** - TruffleHog + prevent-secrets.py
- **Security Summary** - Combined status

**Why This Approach:**
- No `continue-on-error` - security issues must be fixed
- Runs daily to catch newly-discovered vulnerabilities
- Comprehensive but focused checks

### 3. Build & Deployment Workflows
**Active:**
- `build-ci-image.yml` - Builds CI container image
- `docker-build-push.yml` - Builds and pushes Docker images
- `deploy.yml` - Deployment automation
- `release.yml` - Release automation

**Status:** These are specialized workflows that remain as-is.

### 4. Monitoring (`.github/workflows/monitoring.yml`)
**Purpose:** Monitoring and alerting setup  
**Status:** Kept for production monitoring

### 5. Gemini AI Workflows
**Purpose:** AI-powered code review and issue triage  
**Active:**
- `gemini-review.yml` - AI code review on PRs
- `gemini-triage.yml` - AI issue triage
- `gemini-dispatch.yml` - Gemini workflow dispatcher
- `gemini-invoke.yml` - Gemini invocation handler
- `gemini-scheduled-triage.yml` - Scheduled AI triage

**Status:** Kept for AI assistance features

## Disabled/Archived Workflows

### Disabled (renamed to .disabled)
- `ci-enhanced.yml.disabled` - Overly complex, duplicated ci.yml
  - Reason: 473 lines, excessive `continue-on-error`, duplicated checks
  - Replacement: Consolidated into simplified ci.yml

### Archived (renamed to .old)
- `ci.yml.old` - Previous CI configuration
- `security-scan.yml.old` - Previous security scan with `continue-on-error`

## Key Improvements

### 1. ✅ Aligned with Pre-commit Hooks
CI now runs the exact same checks as local pre-commit hooks:
```yaml
# In CI
- name: Run pre-commit hooks
  run: SKIP=pytest-fast pre-commit run --all-files

# Locally
pre-commit run --all-files
```

### 2. ✅ No More continue-on-error
**Before:** Many checks had `continue-on-error: true`, making them useless  
**After:** All checks must pass - failures are meaningful

### 3. ✅ Simplified and Focused
**Before:** 473-line ci-enhanced.yml with matrix testing, multiple continue-on-error  
**After:** 180-line ci.yml focused on essential checks

### 4. ✅ Clear Job Separation
- Code quality (linting, formatting)
- Tests (with coverage)
- Security (bandit, secrets, dependencies)

### 5. ✅ Better Status Reporting
Combined status checks for branch protection:
- `ci-success` job aggregates all CI checks
- `security-summary` job aggregates all security checks

## Workflow Triggers

| Workflow | Push to Main | PRs | Schedule | Manual |
|----------|--------------|-----|----------|--------|
| CI | ✅ | ✅ | ❌ | ✅ |
| Security Scan | ✅ | ✅ (to main) | ✅ Daily | ✅ |
| Deploy | ✅ | ❌ | ❌ | ✅ |
| Release | Tags | ❌ | ❌ | ✅ |
| Monitoring | ✅ | ❌ | ❌ | ✅ |

## Branch Protection Recommendations

Set up branch protection rules for `main`:
- Require status checks: `CI Success`
- Require status checks: `Security Summary`
- Require review from code owners
- No force pushes
- No deletions

## Running Workflows Locally

### Pre-commit checks (matches CI)
```bash
# Install hooks
./scripts/setup-hooks.sh

# Run all checks
pre-commit run --all-files

# This matches what CI runs!
```

### Tests
```bash
pytest -m "not external_service and not slow" \
  --cov=finance_feedback_engine \
  --cov-fail-under=70 \
  -v
```

### Security scan
```bash
# Bandit
bandit -c pyproject.toml -r finance_feedback_engine/ -ll

# Secret detection
python .pre-commit-hooks/prevent-secrets.py

# Dependency audit
pip-audit --desc
```

## CI/CD Best Practices Applied

1. **Fail Fast** - No continue-on-error on critical checks
2. **Consistency** - CI matches local development (pre-commit)
3. **Clarity** - Clear job names and purposes
4. **Efficiency** - Caching for faster runs
5. **Observability** - GitHub Step Summaries for results
6. **Security** - Multiple layers of security scanning

## Maintenance

### Adding New Checks
1. Add to `.pre-commit-config.yaml` first
2. Test locally with `pre-commit run --all-files`
3. CI will automatically pick it up

### Updating Dependencies
1. Update `requirements-dev.txt`
2. CI will test with new versions
3. Security scan will check for vulnerabilities

### Troubleshooting Failed Workflows
1. Check GitHub Actions tab for detailed logs
2. Run the same check locally (it should match CI)
3. Fix issues and push again

## Migration Notes

### For Developers
- No changes needed! CI now matches your local pre-commit hooks
- Run `./scripts/setup-hooks.sh` if you haven't already

### For CI/CD Maintainers
- Old workflows archived with `.old` or `.disabled` extension
- Can be safely deleted after 30 days if no issues arise
- New workflows are simpler and more maintainable

## Support

For issues or questions:
- CI/CD pipeline: See this document
- Pre-commit hooks: See `docs/PRE_COMMIT_GUIDE.md`
- Security scanning: See `docs/SECURITY.md`

---

**Last Updated:** December 2025  
**Version:** 2.0  
**Maintainer:** DevOps Team
