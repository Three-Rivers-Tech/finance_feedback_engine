# GitHub Workflows - Quick Reference

## What Changed (TL;DR)

✅ **Removed:** Backup workflow (we're poor, no S3)  
✅ **Fixed:** Tests now fail properly (removed continue-on-error abuse)  
✅ **Fixed:** Health checks are more reliable  
✅ **Fixed:** Security scans only run when images exist  
✅ **Fixed:** Environment variables set consistently  

## Current Workflows Status

| Workflow | Status | Runs On |
|----------|--------|---------|
| CI | ✅ Fixed | Every push/PR |
| Staging Tests | ✅ Fixed | Push to main/develop, PRs |
| Performance Testing | ✅ Fixed | Push to main, PRs, weekly schedule |
| Security Scanning | ✅ Working | Push to main, PRs, daily |
| Docker Build/Push | ✅ Fixed | Push to main/develop, tags |
| Monitoring | ✅ Working | Push to main, 6-hour schedule |
| Release Automation | ⏳ In progress | On tags |
| Backup Automation | ❌ Removed | N/A |

## Error Handling Rules (Important!)

### ✅ Use `continue-on-error: true` for:
- Optional services (Ollama model downloads)
- Informational checks (linting, formatting)
- Experimental features

### ✅ Use `if: always()` for:
- Uploading logs/artifacts
- Cleanup steps
- Status reporting

### ❌ NEVER use `continue-on-error` for:
- Unit tests
- Integration tests
- Critical service health checks

## Common Patterns

### Pattern 1: Running Tests Properly
```yaml
- name: Run tests
  id: tests
  run: pytest ...  # No continue-on-error!

- name: Upload logs
  if: always()  # Still runs if tests fail
  uses: actions/upload-artifact@v4

- name: Fail if tests failed
  if: steps.tests.outcome != 'success'
  run: exit 1
```

### Pattern 2: Optional Service
```yaml
- name: Pull Ollama model (optional)
  continue-on-error: true  # OK - truly optional
  run: ollama pull model
```

### Pattern 3: Conditional Workflow
```yaml
if: github.event_name == 'push' || github.event_name == 'workflow_dispatch'
# Only runs on pushes and manual triggers, not PRs
```

## Debugging Failed Workflows

1. **Check workflow run in GitHub Actions tab**
2. **Look for actual error, not masked by continue-on-error**
3. **Check service logs in artifacts** (uploaded even on failure)
4. **Verify environment variables** (should have ENVIRONMENT=ci)
5. **Health check issues?** Check docker-compose.test.yml healthcheck config

## Files Modified

- `.github/workflows/ci.yml` - Added ENVIRONMENT var, improved status check
- `.github/workflows/staging.yml` - Better health checks, removed masking
- `.github/workflows/performance-testing.yml` - Added ENVIRONMENT var
- `.github/workflows/docker-build-push.yml` - Fixed security scan conditions
- `.github/workflows/backup-automation.yml` - DELETED (RIP 🪦)

## Documentation

- `WORKFLOW_FIXES_SUMMARY.md` - Detailed changes
- `GITHUB_WORKFLOWS_ANALYSIS.md` - Full research and best practices

## Need Help?

- **Workflow failing?** Check if it's a real failure (not masked by continue-on-error)
- **Tests not running?** Check ENVIRONMENT variable is set
- **Health checks timing out?** Check docker-compose.test.yml start_period values
- **Security scan failing?** It now only runs on pushes, not PRs

---

**Updated:** 2026-01-02  
**Next Review:** After observing 5-10 workflow runs
