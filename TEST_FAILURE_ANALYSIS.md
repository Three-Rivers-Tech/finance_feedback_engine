# Test Failure Analysis & Fix Plan

**Date:** 2025-01-XX
**Total Tests:** 1050 collected
**Status:** 79 failed, 870 passed, 98 skipped, 3 errors

## Summary

The test suite is mostly functional (82.9% pass rate), but there are several categories of failures that need to be addressed:

### Failure Categories

1. **Logging/Resource Cleanup Issues** (Most Common)
   - Unclosed aiohttp client sessions
   - "I/O operation on closed file" errors
   - Impact: 40+ tests affected by logging errors

2. **Data Provider Tests** (17 failures)
   - Alpha Vantage provider tests
   - Coinbase/Oanda provider tests
   - Unified provider routing tests

3. **Decision Engine Tests** (15 failures)
   - Position sizing calculation tests
   - Market analysis helper tests
   - Configuration tests

4. **Ensemble System Tests** (10 failures)
   - Error propagation tests
   - Fallback tier tests
   - Provider failure tracking

5. **Integration Tests** (10 failures)
   - Redis/Telegram integration
   - Platform error handling
   - Monitoring integration

6. **Utility Tests** (7 failures)
   - Data freshness validation
   - Risk context fields

## Priority 1: Fix Logging/Resource Cleanup (CRITICAL)

### Issue: Unclosed aiohttp Sessions

**Root Cause:** aiohttp ClientSession objects not being properly closed in tests

**Affected Files:**
- `finance_feedback_engine/data_providers/alpha_vantage_provider.py`
- Test files using async HTTP clients

**Fix Strategy:**
```python
# Add proper session management
class AlphaVantageProvider:
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def close(self):
        """Explicitly close the session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
```

**Test Fixture Fix:**
```python
# In conftest.py or test files
@pytest.fixture
async def alpha_vantage_provider():
    provider = AlphaVantageProvider(api_key="test_key")
    yield provider
    await provider.close()  # Ensure cleanup
```

## Priority 2: Fix Data Provider Tests (HIGH)

### Failing Tests:
1. `test_get_market_data_success` - Alpha Vantage
2. `test_circuit_breaker_opens_on_failures` - Alpha Vantage
3. `test_get_comprehensive_market_data` - Alpha Vantage
4. `test_initialization` - Coinbase
5. `test_get_candles` - Coinbase/Oanda
6. `test_get_portfolio` - Coinbase
7. `test_get_account_summary` - Oanda

**Common Issue:** Tests likely failing due to:
- Missing mock responses
- Incorrect API response format expectations
- Session management issues

**Fix Approach:**
1. Review and update mock responses to match current API formats
2. Add proper async context managers
3. Ensure all HTTP sessions are closed

## Priority 3: Fix Decision Engine Tests (HIGH)

### Failing Tests:
1. `test_normal_mode_with_valid_balance_buy/sell` - Position sizing
2. `test_hold_without_position_no_sizing` - Position sizing
3. `test_calculate_price_change_*` - Market analysis
4. `test_calculate_volatility*` - Market analysis
5. `test_config_nested_structure` - Configuration
6. `test_ensemble_decision_mocked` - Ensemble integration

**Root Cause:** Likely changes in function signatures or return value formats

**Investigation Needed:**
- Check if `calculate_position_sizing_params` function signature changed
- Verify market analysis helper functions exist and have correct signatures
- Review configuration structure changes

## Priority 4: Fix Ensemble Error Propagation (MEDIUM)

### Failing Tests (10 tests):
- `test_ensemble_tracks_local_exception_as_failure`
- `test_ensemble_tracks_multiple_provider_failures`
- `test_ensemble_all_providers_fail_raises_error`
- `test_single_local_provider_returns_fallback_*`
- `test_local_priority_*`
- `test_weights_adjust_when_provider_fails`
- `test_weighted_voting_falls_back_to_majority_on_insufficient_providers`

**Issue:** Tests expect specific error propagation behavior that may have changed

**Fix Strategy:**
1. Review ensemble manager error handling logic
2. Update tests to match current error propagation behavior
3. Ensure fallback tiers work as expected

## Priority 5: Fix Integration Tests (MEDIUM)

### Redis/Telegram Tests (8 failures):
- `test_ensure_running_already_running`
- `test_ensure_running_docker_fallback`
- `test_is_redis_running_true`
- `test_start_ngrok_tunnel`
- `test_install_ngrok_if_missing`
- `test_get_tunnel_url_returns_url`
- `test_stop_tunnel`
- `test_custom_domain_scaffold`

**Issue:** External service dependencies (Redis, ngrok) not properly mocked

**Fix Strategy:**
1. Add proper mocking for Redis connection checks
2. Mock ngrok subprocess calls
3. Ensure tests don't require actual external services

### Platform Error Handling Tests (9 failures):
- Various Coinbase/Oanda error simulation tests
- Mock platform error simulation tests

**Issue:** Error handling behavior may have changed or mocks are outdated

## Priority 6: Fix Utility Tests (LOW)

### Data Freshness Tests (6 failures):
- Stock intraday/daily threshold tests
- Timeframe validation tests

**Issue:** Likely datetime handling or threshold calculation changes

## Detailed Fix Plan

### Phase 1: Resource Cleanup (Day 1)
**Estimated Time:** 4 hours

1. **Add async context managers to all providers**
   - [ ] AlphaVantageProvider
   - [ ] CoinbaseDataProvider
   - [ ] OandaDataProvider
   - [ ] UnifiedDataProvider

2. **Update test fixtures**
   - [ ] Add proper cleanup in conftest.py
   - [ ] Ensure all async fixtures close resources

3. **Fix logging errors**
   - [ ] Add proper file handle management
   - [ ] Ensure loggers are closed before test teardown

### Phase 2: Data Provider Tests (Day 1-2)
**Estimated Time:** 6 hours

1. **Review and fix Alpha Vantage tests**
   - [ ] Update mock responses
   - [ ] Fix circuit breaker test expectations
   - [ ] Ensure proper session management

2. **Review and fix Coinbase/Oanda tests**
   - [ ] Update API response mocks
   - [ ] Fix initialization tests
   - [ ] Update error handling expectations

3. **Fix UnifiedDataProvider routing tests**
   - [ ] Review routing logic
   - [ ] Update test expectations
   - [ ] Fix fallback behavior tests

### Phase 3: Decision Engine Tests (Day 2)
**Estimated Time:** 4 hours

1. **Fix position sizing tests**
   - [ ] Review function signature changes
   - [ ] Update test expectations
   - [ ] Fix parameter passing

2. **Fix market analysis tests**
   - [ ] Verify helper functions exist
   - [ ] Update calculation expectations
   - [ ] Fix edge case handling

3. **Fix configuration tests**
   - [ ] Review config structure changes
   - [ ] Update test expectations
   - [ ] Fix nested structure tests

### Phase 4: Ensemble Tests (Day 3)
**Estimated Time:** 4 hours

1. **Fix error propagation tests**
   - [ ] Review error handling logic
   - [ ] Update test expectations
   - [ ] Fix fallback behavior tests

2. **Fix fallback tier tests**
   - [ ] Review tier logic
   - [ ] Update test expectations
   - [ ] Fix provider failure tests

### Phase 5: Integration Tests (Day 3-4)
**Estimated Time:** 6 hours

1. **Fix Redis/Telegram tests**
   - [ ] Add proper mocking
   - [ ] Remove external dependencies
   - [ ] Fix subprocess mocks

2. **Fix platform error handling tests**
   - [ ] Review error handling changes
   - [ ] Update mock behaviors
   - [ ] Fix error simulation tests

### Phase 6: Utility Tests (Day 4)
**Estimated Time:** 2 hours

1. **Fix data freshness tests**
   - [ ] Review datetime handling
   - [ ] Update threshold calculations
   - [ ] Fix timeframe validation

## Testing Strategy

### After Each Phase:
1. Run affected test suite
2. Verify no new failures introduced
3. Check for resource leaks
4. Update documentation

### Final Validation:
```bash
# Run full test suite
pytest -v --tb=short

# Check for resource leaks
pytest -v --tb=short -W error::ResourceWarning

# Generate coverage report
pytest --cov=finance_feedback_engine --cov-report=html --cov-report=term-missing

# Run specific test categories
pytest tests/test_data_providers_comprehensive.py -v
pytest tests/test_decision_engine_*.py -v
pytest tests/test_ensemble_*.py -v
```

## Success Criteria

- [ ] All 1050 tests passing (or documented as expected skips)
- [ ] No resource warnings or unclosed session errors
- [ ] Test coverage ≥ 70%
- [ ] All critical paths tested
- [ ] No flaky tests (run 10 times successfully)

## Estimated Total Time

- **Phase 1:** 4 hours (Resource cleanup)
- **Phase 2:** 6 hours (Data providers)
- **Phase 3:** 4 hours (Decision engine)
- **Phase 4:** 4 hours (Ensemble)
- **Phase 5:** 6 hours (Integration)
- **Phase 6:** 2 hours (Utilities)
- **Testing/Validation:** 4 hours

**Total:** ~30 hours (4 working days)

## Next Steps

1. Start with Phase 1 (resource cleanup) as it affects many tests
2. Move to Phase 2 (data providers) as these are critical path
3. Continue through phases in order
4. Run full test suite after each phase
5. Document any architectural changes needed
