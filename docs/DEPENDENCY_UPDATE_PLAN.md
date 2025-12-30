# Dependency Update Plan - Q1 2026 Sprint 1
# Finance Feedback Engine 2.0

**Sprint:** Week 1-2 of Q1 2026
**Effort:** 40 hours
**Priority:** HIGH
**Status:** 🚀 READY TO START

---

## Pre-Update Checklist

- [x] Backup created: `requirements-backup-20251229.txt`
- [ ] Test baseline documented
- [ ] Git branch created: `tech-debt/q1-dependency-updates`
- [ ] Team notified of update sprint

---

## Dependency Update Batches

### Batch 1: Critical Security Updates (Day 1-3, 18 hours)

#### 1.1 coinbase-advanced-py (1.7.0 → 1.8.2) - 8 hours

**Risk:** HIGH - Potential API breaking changes
**Impact Files:**
- `finance_feedback_engine/trading_platforms/coinbase_platform.py`
- `finance_feedback_engine/data_providers/coinbase_data.py`
- `finance_feedback_engine/data_providers/coinbase_data_refactored.py`

**Update Command:**
```bash
pip install --upgrade coinbase-advanced-py==1.8.2
```

**Breaking Changes to Check:**
1. Authentication API changes
2. Order placement parameter changes
3. WebSocket connection updates
4. Market data endpoint changes
5. Error response format changes

**Test Commands:**
```bash
# Unit tests
pytest tests/trading_platforms/test_coinbase_platform.py -v

# Integration tests (requires credentials)
pytest tests/integration/test_coinbase_integration.py -v -m external_service

# Manual API test
python -c "
from coinbase_advanced import coinbase_client
from finance_feedback_engine.trading_platforms import CoinbasePlatform
platform = CoinbasePlatform()
balance = platform.get_balance()
print(f'Balance check: {balance}')
"
```

**Migration Tasks:**
- [ ] Review SDK changelog: https://github.com/coinbase/coinbase-advanced-py/releases
- [ ] Update authentication if changed
- [ ] Update order placement calls
- [ ] Update market data fetching
- [ ] Fix any test failures
- [ ] Update documentation

**Rollback Plan:**
```bash
pip install coinbase-advanced-py==1.7.0
```

---

#### 1.2 fastapi (0.125.0 → 0.128.0) - 4 hours

**Risk:** MEDIUM - Security patches, minor API changes
**Impact Files:**
- `finance_feedback_engine/api/app.py`
- `finance_feedback_engine/api/routes.py`
- `finance_feedback_engine/api/bot_control.py`
- `finance_feedback_engine/api/optimization.py`

**Update Command:**
```bash
pip install --upgrade fastapi==0.128.0 uvicorn[standard]
```

**Breaking Changes to Check:**
1. Pydantic V2 compatibility
2. Dependency injection changes
3. Response model updates
4. WebSocket handling changes

**Test Commands:**
```bash
# API tests
pytest tests/test_api_endpoints.py -v
pytest tests/test_bot_control_auth.py -v

# Start server and manual test
uvicorn finance_feedback_engine.api.app:app --reload &
SERVER_PID=$!
sleep 5

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/balance
curl -X POST http://localhost:8000/api/bot/start

kill $SERVER_PID
```

**Migration Tasks:**
- [ ] Review FastAPI changelog
- [ ] Test Pydantic model compatibility
- [ ] Update dependency injection if needed
- [ ] Fix any deprecation warnings
- [ ] Update OpenAPI docs

---

#### 1.3 numpy (2.2.6 → 2.4.0) - 6 hours

**Risk:** MEDIUM - Breaking changes in 2.3+
**Impact:** Wide - Used in 40+ files
**Affected Modules:**
- Decision engine calculations
- Backtesting simulations
- Risk analytics
- Data providers

**Update Command:**
```bash
pip install --upgrade "numpy==2.4.0"
```

**Breaking Changes to Check:**
1. `np.float_` → `np.float64` (deprecated in 2.3)
2. Array scalar behavior changes
3. Random number generator updates
4. String array changes

**Test Commands:**
```bash
# Numpy compatibility tests
pytest tests/test_numpy_compatibility.py -v

# Data provider tests
pytest tests/test_data_providers_comprehensive.py -v

# Backtesting tests (heavy numpy usage)
pytest tests/backtesting/ -v

# Check for deprecation warnings
python -W default::DeprecationWarning -m pytest tests/ 2>&1 | grep -i numpy
```

**Migration Tasks:**
- [ ] Find and replace `np.float_` with `np.float64`
- [ ] Update random seed usage if needed
- [ ] Check scipy compatibility
- [ ] Check pandas compatibility
- [ ] Fix deprecation warnings

**Search and Replace:**
```bash
# Find np.float_ usage
grep -r "np\.float_" finance_feedback_engine/ --include="*.py"

# Automated replacement (review first!)
find finance_feedback_engine/ -name "*.py" -exec sed -i 's/np\.float_/np.float64/g' {} \;
```

---

### Batch 2: ML/Performance Updates (Day 4-5, 10 hours)

#### 2.1 mlflow (3.8.0 → 3.8.1) - 2 hours

**Risk:** LOW - Bug fixes only
**Impact Files:**
- `finance_feedback_engine/optimization/optuna_optimizer.py`
- `finance_feedback_engine/monitoring/model_performance_monitor.py`

**Update Command:**
```bash
pip install --upgrade mlflow==3.8.1 mlflow-skinny==3.8.1 mlflow-tracing==3.8.1
```

**Test Commands:**
```bash
pytest tests/optimization/test_optuna_optimizer.py -v
pytest tests/test_model_performance_monitor.py -v
```

---

#### 2.2 numba (0.61.2 → 0.63.1) - 4 hours

**Risk:** MEDIUM - Performance improvements, potential compilation changes
**Impact Files:**
- `finance_feedback_engine/data_providers/timeframe_aggregator.py`
- `finance_feedback_engine/pair_selection/statistical/garch_volatility.py`

**Update Command:**
```bash
pip install --upgrade numba==0.63.1 llvmlite==0.46.0
```

**Test Commands:**
```bash
pytest tests/test_timeframe_aggregator_indicators.py -v
pytest tests/pair_selection/test_garch_volatility.py -v
```

**Migration Tasks:**
- [ ] Check JIT compilation warnings
- [ ] Verify performance improvements
- [ ] Update type annotations if needed

---

#### 2.3 antlr4-python3-runtime (4.9.3 → 4.13.2) - 2 hours

**Risk:** LOW - Dependency of other tools
**Impact:** Minimal - Used by parsing libraries

**Update Command:**
```bash
pip install --upgrade antlr4-python3-runtime==4.13.2
```

**Test Commands:**
```bash
# Verify no regressions
pytest tests/ -k "not external_service" -x
```

---

#### 2.4 flufl.lock (8.2.0 → 9.0.0) - 2 hours

**Risk:** LOW - May have API changes
**Impact:** File locking utilities

**Update Command:**
```bash
pip install --upgrade "flufl.lock>=9.0.0"
```

**Breaking Changes to Check:**
- Context manager API
- Lock timeout behavior

**Test Commands:**
```bash
pytest tests/test_portfolio_memory_persistence.py -v
pytest tests/test_decision_store.py -v
```

---

### Batch 3: Maintenance Updates (Day 6, 8 hours)

**Low-risk batch update:**
```bash
pip install --upgrade \
  celery==5.6.1 \
  coverage==7.13.1 \
  kombu==5.6.2 \
  librt==0.7.5 \
  nodeenv==1.10.0 \
  psutil==7.2.1
```

**Test Commands:**
```bash
# Full test suite
pytest tests/ -v --cov=finance_feedback_engine

# Verify coverage tool
coverage report
```

---

### Batch 4: Additional Updates (Day 7, 4 hours)

**Remaining packages:**
```bash
pip list --outdated --format=json | python -c "
import json, sys
data = json.load(sys.stdin)
for pkg in data:
    if pkg['name'] not in ['antlr4-python3-runtime', 'celery', 'coinbase-advanced-py',
                           'coverage', 'fastapi', 'flufl.lock', 'kombu', 'librt',
                           'llvmlite', 'mlflow', 'mlflow-skinny', 'mlflow-tracing',
                           'nodeenv', 'numba', 'numpy', 'psutil']:
        print(f\"{pkg['name']}=={pkg['latest_version']}\")
"
```

---

## Integration Testing (Day 8-9, 8 hours)

### Test Suite Execution

```bash
# 1. Full test suite with coverage
pytest tests/ -v --cov=finance_feedback_engine --cov-report=html --cov-report=term

# Expected results:
# - Tests passing: ≥1184
# - Tests xfailed: ≤17
# - Coverage: ≥9.81%
# - New failures: 0

# 2. Type checking
mypy finance_feedback_engine/core.py
mypy finance_feedback_engine/risk/gatekeeper.py
mypy finance_feedback_engine/trading_platforms/platform_factory.py

# 3. Security audit
pip-audit --fix
bandit -r finance_feedback_engine/ -f json -o bandit_post_update.json

# 4. Deprecation warnings audit
python -W default::DeprecationWarning -m pytest tests/ -v 2>&1 | tee deprecation_warnings.log
grep -i "deprecat" deprecation_warnings.log

# 5. Performance regression tests
pytest tests/test_phase2_performance_benchmarks.py -v --benchmark-only

# 6. Integration tests with external services (if credentials available)
pytest tests/ -v -m external_service
```

### Smoke Tests

```bash
# CLI smoke tests
python main.py --help
python main.py balance
python main.py analyze BTCUSD --no-execute
python main.py analyze EURUSD --no-execute

# API smoke test
python -c "
from finance_feedback_engine import FinanceFeedbackEngine
engine = FinanceFeedbackEngine('config/config.yaml')
print('Engine initialized successfully')
"
```

---

## Documentation (Day 10, 4 hours)

### 1. Migration Notes

Create `docs/MIGRATION_NOTES_Q1.md`:

```markdown
# Migration Notes - Q1 2026 Dependency Updates

## Summary
Updated 22 packages from outdated versions to latest stable releases.

## Critical Changes

### coinbase-advanced-py (1.7.0 → 1.8.2)
- **Breaking:** Authentication API changed
- **Action:** Updated `CoinbasePlatform` initialization
- **Files:** `coinbase_platform.py`, `coinbase_data.py`

### numpy (2.2.6 → 2.4.0)
- **Breaking:** `np.float_` deprecated, use `np.float64`
- **Action:** Global search/replace in all files
- **Files:** 40+ files updated

### fastapi (0.125.0 → 0.128.0)
- **Change:** Enhanced Pydantic V2 support
- **Action:** Verified model compatibility
- **Files:** `api/app.py`, `api/routes.py`

## Testing
- All 1184+ tests passing
- Security vulnerabilities: 0
- Coverage: 9.81% (maintained)

## Rollback
If issues arise:
```bash
pip install -r requirements-backup-20251229.txt
```
```

### 2. Update CHANGELOG.md

```markdown
# Changelog

## [0.9.10] - 2026-01-15

### Security
- Updated 22 dependencies to latest secure versions
- Fixed 7 security vulnerabilities
- All dependencies now current

### Changed
- Updated coinbase-advanced-py to 1.8.2
- Updated fastapi to 0.128.0
- Updated numpy to 2.4.0
- Updated mlflow family to 3.8.1
- Updated numba to 0.63.1
- Replaced deprecated np.float_ with np.float64 across codebase

### Fixed
- Resolved compatibility issues with latest numpy
- Fixed deprecation warnings in data providers

### Testing
- Maintained 1184+ passing tests
- Coverage: 9.81%
```

### 3. Update pyproject.toml

```toml
[project]
version = "0.9.10"  # Bump version

dependencies = [
    # Updated dependencies
    "coinbase-advanced-py>=1.8.2",
    "fastapi>=0.128.0",
    "numpy>=2.2.0,<2.5.0",
    "mlflow>=3.8.1",
    "numba>=0.63.1",
    # ... rest of dependencies
]
```

---

## Rollback Procedures

### If Critical Issues Found

```bash
# 1. Revert to backup
pip uninstall -y -r requirements.txt
pip install -r requirements-backup-20251229.txt

# 2. Verify rollback
pytest tests/ -v
python main.py --help

# 3. Document issue
# Create issue in GitHub with:
# - Package that caused problem
# - Error messages
# - Steps to reproduce
```

### Selective Rollback (Single Package)

```bash
# Example: Rollback numpy only
pip install "numpy==2.2.6"

# Re-run affected tests
pytest tests/test_numpy_compatibility.py -v
```

---

## Success Criteria

### Must Pass Before Merge

- [ ] All tests passing (≥1184)
- [ ] No new test failures
- [ ] Coverage maintained (≥9.81%)
- [ ] Security vulnerabilities: 0
- [ ] Type checking passes on strict modules
- [ ] No critical deprecation warnings
- [ ] Smoke tests pass
- [ ] Performance regressions <10%

### Documentation Complete

- [ ] Migration notes written
- [ ] CHANGELOG updated
- [ ] pyproject.toml version bumped
- [ ] Breaking changes documented
- [ ] Rollback procedures tested

### Code Review Checklist

- [ ] All files reviewed
- [ ] Breaking changes approved
- [ ] Tests comprehensive
- [ ] Documentation clear
- [ ] Rollback plan validated

---

## Timeline

```yaml
Day_1: "coinbase-advanced-py update & testing"
Day_2: "fastapi update & testing"
Day_3: "numpy update & testing"
Day_4: "mlflow, numba updates"
Day_5: "antlr4, flufl.lock updates"
Day_6: "Batch maintenance updates"
Day_7: "Additional package updates"
Day_8: "Integration testing"
Day_9: "Security & performance testing"
Day_10: "Documentation & code review"
```

---

## Post-Update Monitoring

### Week 1 After Merge
- Monitor production logs for errors
- Track performance metrics
- Check error rates
- Review security scan results

### Week 2-4 After Merge
- Quarterly dependency review scheduled
- Document lessons learned
- Update CI/CD to prevent regressions

---

**Status:** 🚀 Ready to Execute
**Next Action:** Create feature branch and begin Batch 1 updates
**Owner:** Tech Debt Team
**Due Date:** 2026-01-15
