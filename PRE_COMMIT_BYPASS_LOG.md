# Pre-Commit Bypass Log

This document tracks all instances where pre-commit hooks were bypassed using `SKIP=pre-commit` or similar mechanisms.

**Purpose**: Maintain accountability and ensure bypassed checks are resolved within 24 hours.

## Bypass Events

> Note: New entries are appended automatically when bypasses occur. Resolved bypasses should be marked with ✓ RESOLVED.

---

## Guidelines

### When to Use Bypass

Pre-commit bypasses should be **rare** and **justified**:
- Production hotfix requiring immediate deployment
- Critical bug discovered after commit
- External service unavailability blocking all tests (e.g., ollama down)

### How to Bypass

```bash
# Bypass all pre-commit hooks
SKIP=pre-commit git commit -m "Emergency fix for X"

# This will:
# 1. Log bypass to this file
# 2. Post GitHub PR comment with 24-hour deadline
# 3. Require post-commit fix within deadline
```

### Post-Bypass Action

1. **Within 24 hours**: Resolve the bypassed check
   - Run `pytest -m "not slow and not external_service"` locally
   - Fix any failures
   - Run `pre-commit run --all-files` to validate all hooks pass
   
2. **Amend or follow-up commit**: Include the fix
   - Document fix in commit message: `Fix bypassed pytest from abc123`
   - All hooks must pass
   - Mark entry below as ✓ RESOLVED

3. **No Extensions**: If fix can't complete within 24h, open an issue instead

## Resolved Bypasses ✓

(Entries marked complete move here for archive)

---

## Statistics

- **Total Bypasses**: 0
- **Resolved**: 0
- **Pending Resolution**: 0
- **Expired (Not Resolved)**: 0

## Emergency Contact

If bypass deadline will be missed:
1. Open a GitHub issue with details
2. Tag as `bypass-extension-request`
3. Update estimated resolution date

## 2025-12-19T15:28:01.387260
**Bypass Timestamp**: 2025-12-19T15:28:01.384170
**Commit**: b15866d
**Hooks Skipped**: pytest-fast,mypy
**Reason**: Emergency bypass
**Fix Deadline**: 2025-12-20T15:28:01.384170

---

## 2025-12-19T15:28:24.119957
**Bypass Timestamp**: 2025-12-19T15:28:24.117213
**Commit**: b15866d
**Hooks Skipped**: pytest-fast,mypy
**Reason**: Emergency bypass
**Fix Deadline**: 2025-12-20T15:28:24.117213

---

## 2025-12-19T15:29:25.904267
**Bypass Timestamp**: 2025-12-19T15:29:25.898773
**Commit**: b15866d
**Hooks Skipped**: pytest-fast,mypy
**Reason**: Emergency bypass
**Fix Deadline**: 2025-12-20T15:29:25.898773

---
