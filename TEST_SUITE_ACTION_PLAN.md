# Test Suite Stabilization & Pre-commit Progressive Implementation Plan

## Current Status
- **Test Suite**: 1050 tests collected, 79 failing (82.9% pass rate)
- **Critical Issue**: Test suite crashes IDE due to resource leaks
- **Pre-commit**: Basic configuration exists, enhanced config available but not active

## Completed Actions

### 1. Created Safe Test Infrastructure
- ✅ `scripts/safe_test_runner.py` - Runs tests individually with timeout protection
- ✅ `scripts/test_resource_leak.py` - Identifies specific resource leak issues
- ✅ `TEST_FIX_TODO.md` - Tracks test fixing progress

### 2. Progressive Pre-commit Strategy
- ✅ `.pre-commit-config-progressive.yaml` - 4-phase gradual tightening approach
- ✅ `scripts/manage_precommit.py` - Automated pre-commit phase management

## Immediate Actions Required

### Phase 1: Fix Critical Resource Leaks (TODAY)

#### 1.1 Fix Alpha Vantage Provider Session Management
```python
# In finance_feedback_engine/data_providers/alpha_vantage_provider.py
# Add proper cleanup in __del__ method
def __del__(self):
    """Cleanup on garbage collection."""
    if hasattr(self, 'session') and self.session and self._owned_session:
        try:
            if not self.session.closed:
                # Create new event loop if needed for cleanup
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.session.close())
                except RuntimeError:
                    # Can't close in __del__, but we warned
                    pass
        except Exception:
            pass
```

#### 1.2 Update Test Fixtures in conftest.py
```python
# Ensure all async fixtures properly cleanup
@pytest.fixture
async def alpha_vantage_provider():
    provider = AlphaVantageProvider(api_key="test_key", is_backtest=True)
    try:
        yield provider
    finally:
        await provider.close()
        # Force cleanup of session
        if hasattr(provider, 'session') and provider.session:
            if not provider.session.closed:
                await provider.session.close()
```

#### 1.3 Add Test Isolation
```python
# Add to conftest.py
@pytest.fixture(autouse=True)
async def cleanup_aiohttp_sessions():
    """Force cleanup of any lingering aiohttp sessions after each test."""
    yield
    # Force garbage collection
    import gc
    gc.collect()
    
    # Close any unclosed sessions
    import aiohttp
    import asyncio
    
    # Get all ClientSession instances
    for obj in gc.get_objects():
        if isinstance(obj, aiohttp.ClientSession):
            if not obj.closed:
                try:
                    await obj.close()
                except Exception:
                    pass
```

### Phase 2: Run Safe Test Analysis (After Phase 1)

```bash
# 1. Run resource leak detection
python scripts/test_resource_leak.py

# 2. Run priority tests with safe runner
python scripts/safe_test_runner.py --mode priority --timeout 10

# 3. If stable, run all tests
python scripts/safe_test_runner.py --mode all --timeout 30
```

### Phase 3: Fix Failing Tests by Category

Based on TEST_FAILURE_ANALYSIS.md priorities:

1. **Data Provider Tests** (17 failures)
   - Fix mock responses to match current API formats
   - Ensure proper session cleanup
   - Update test expectations

2. **Decision Engine Tests** (15 failures)
   - Fix position sizing calculation tests
   - Update market analysis helper tests
   - Review configuration structure changes

3. **Ensemble System Tests** (10 failures)
   - Update error propagation expectations
   - Fix fallback tier tests
   - Review provider failure tracking

4. **Integration Tests** (10 failures)
   - Add proper Redis/ngrok mocking
   - Update platform error handling
   - Fix monitoring integration

### Phase 4: Implement Progressive Pre-commit

```bash
# Start with Phase 1 (formatting only)
python scripts/manage_precommit.py set-phase 1
pre-commit run --all-files  # Fix any formatting issues

# When stable, move to Phase 2 (add linting)
python scripts/manage_precommit.py set-phase 2
pre-commit run --all-files  # Fix linting issues

# Continue through phases as tests stabilize
python scripts/manage_precommit.py gradual  # Get recommendations
```

## Success Metrics

### Week 1 Goals
- [ ] No IDE crashes when running tests
- [ ] Resource leak tests pass
- [ ] Pre-commit Phase 1 active (formatting)
- [ ] 90% test pass rate

### Week 2 Goals
- [ ] All resource leaks fixed
- [ ] Pre-commit Phase 2 active (linting)
- [ ] 95% test pass rate
- [ ] CI pipeline runs without crashes

### Week 3 Goals
- [ ] 100% test pass rate
- [ ] Pre-commit Phase 3 active (security/types)
- [ ] Coverage > 70%
- [ ] No flaky tests

### Week 4 Goals
- [ ] Pre-commit Phase 4 active (test runner)
- [ ] Full CI/CD pipeline active
- [ ] Branch protection enabled
- [ ] Ready for production release

## Commands Reference

### Test Management
```bash
# Run safe test analysis
python scripts/safe_test_runner.py --mode priority

# Check resource leaks
python scripts/test_resource_leak.py

# Run specific test file safely
python scripts/safe_test_runner.py --mode single --test tests/test_api.py

# Generate test report
python scripts/safe_test_runner.py --mode all > test_run.log 2>&1
```

### Pre-commit Management
```bash
# Check current status
python scripts/manage_precommit.py status

# Set to specific phase
python scripts/manage_precommit.py set-phase 1

# Check for violations
python scripts/manage_precommit.py check

# Get recommendations
python scripts/manage_precommit.py gradual

# Run hooks manually
pre-commit run --all-files
```

### Monitoring Progress
```bash
# Check test count
pytest --collect-only -q | grep "test" | wc -l

# Check passing tests
pytest -v --tb=no | grep PASSED | wc -l

# Check resource warnings
pytest -W error::ResourceWarning --tb=short

# Generate coverage report
pytest --cov=finance_feedback_engine --cov-report=term-missing
```

## Risk Mitigation

1. **Backup before changes**: Always backup working code
2. **Test in isolation**: Use virtual environments
3. **Gradual rollout**: Don't enable all checks at once
4. **Developer communication**: Keep team informed of changes
5. **Rollback plan**: Keep previous configs accessible

## Next Immediate Steps

1. **WAIT** for current test runners to complete
2. **ANALYZE** results from safe_test_runner.py and test_resource_leak.py
3. **FIX** critical resource leaks identified
4. **RERUN** tests to verify fixes
5. **IMPLEMENT** Phase 1 pre-commit hooks
6. **DOCUMENT** any architectural changes needed

## Notes

- The test suite crashes are primarily due to unclosed aiohttp sessions
- The Alpha Vantage provider is the main culprit for resource leaks
- Pre-commit should be implemented gradually to avoid developer friction
- Focus on stability over strictness initially
- Once tests are stable, gradually increase pre-commit strictness

## Contact for Issues

If tests continue to crash after implementing these fixes:
1. Check for circular imports
2. Review async/await usage in tests
3. Ensure all fixtures have proper cleanup
4. Consider using pytest-asyncio fixtures
5. Check for global state modifications

---

**Last Updated**: [Current Date]
**Status**: In Progress - Waiting for test analysis to complete
