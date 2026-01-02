# Test Coverage Improvement Plan

**Current Coverage:** 47.6% (11,047/22,035 lines)  
**Goal:** 70%+ coverage  
**Gap:** ~5,000 lines need testing

## Priority 1: Critical Infrastructure (0% coverage)

### High-Impact Modules
1. **redis_manager.py** (200 lines, 0%) - Critical for approvals/caching
2. **live_dashboard.py** (270 lines, 0%) - CLI dashboard
3. **dashboard_aggregator.py** (186 lines, 0%) - Dashboard data
4. **deployment/orchestrator.py** (181 lines, 0%) - Deployment logic
5. **api/health.py** (0%) - Health check endpoint

## Priority 2: Large Modules with Low Coverage

### API Layer (27-38% coverage, ~900 lines)
1. **api/routes.py** (398 lines, 27.0%) - Main API routes
2. **api/bot_control.py** (394 lines, 22.0%) - Telegram bot control

### Trading Platforms (37-48% coverage, ~800 lines)
1. **coinbase_platform.py** (434 lines, 37.1%) - Coinbase trading
2. **oanda_platform.py** (335 lines, 47.4%) - Oanda trading

### Backtesting (11-49% coverage, ~900 lines)
1. **portfolio_backtester.py** (353 lines, 11.0%) - Main backtester
2. **performance_analyzer.py** (278 lines, 33.4%) - Analytics
3. **enhanced_risk_analyzer.py** (176 lines, 48.8%) - Risk analysis

### Decision Engine (5-39% coverage, ~700 lines)
1. **two_phase_aggregator.py** (191 lines, 5.2%) - Pair selection
2. **ai_decision_manager.py** (216 lines, 31.0%) - AI decisions
3. **local_llm_provider.py** (279 lines, 38.8%) - Local LLM

### Monitoring (42% coverage, 287 lines)
1. **trade_monitor.py** (287 lines, 41.9%) - Trade monitoring

### CLI (0-48% coverage, ~800 lines)
1. **cli/main.py** (329 lines, 48.7%) - Main CLI
2. **cli/backtest_formatter.py** (210 lines, 32.0%) - Formatting
3. **cli/formatters/pulse_formatter.py** (184 lines, 26.3%) - Pulse display

## Test Strategy

### Phase 1: Quick Wins (Target: +10% coverage)
- Add tests for 0% coverage modules
- Focus on happy paths and basic functionality
- Use existing mocks and fixtures

### Phase 2: API & Platform Coverage (Target: +8% coverage)
- Comprehensive API endpoint tests
- Platform integration tests with mocks
- Error handling and edge cases

### Phase 3: Backtesting & Decision Engine (Target: +7% coverage)
- Backtester with synthetic data
- Decision engine with multiple scenarios
- Performance analyzer validation

### Phase 4: Monitoring & CLI (Target: +5% coverage)
- Trade monitor lifecycle tests
- CLI command tests
- Dashboard rendering tests

## Test Infrastructure Needed

### Missing Test Utilities
1. **API test fixtures** - FastAPI test client setup
2. **Redis mocks** - For testing redis_manager
3. **Dashboard fixtures** - Mock portfolio data
4. **Backtester fixtures** - Historical data samples
5. **Platform mocks** - Enhanced Coinbase/Oanda mocks

### Existing Assets (Reuse These!)
- `tests/conftest.py` - Basic fixtures
- `tests/mocks/` - Mock implementations
- `tests/fixtures/` - Test data
- `tests/integration/` - Integration test patterns

## Implementation Order

### Week 1: Infrastructure (Estimated +10% coverage)
1. ✅ redis_manager tests
2. ✅ health endpoint tests
3. ✅ dashboard_aggregator tests
4. ✅ orchestrator tests

### Week 2: API Layer (Estimated +8% coverage)
1. ✅ api/routes comprehensive tests
2. ✅ api/bot_control tests
3. ✅ Error handling tests
4. ✅ Authentication/authorization tests

### Week 3: Platforms & Backtesting (Estimated +10% coverage)
1. ✅ coinbase_platform edge cases
2. ✅ oanda_platform edge cases
3. ✅ portfolio_backtester scenarios
4. ✅ performance_analyzer validation

### Week 4: Decision Engine & Monitoring (Estimated +7% coverage)
1. ✅ two_phase_aggregator tests
2. ✅ ai_decision_manager scenarios
3. ✅ trade_monitor lifecycle
4. ✅ local_llm_provider tests

## Success Metrics

- **Coverage target:** 70%+ (currently 47.6%)
- **All critical modules:** >50% coverage
- **API routes:** >80% coverage
- **Trading platforms:** >70% coverage
- **Zero 0% coverage modules**

## Testing Best Practices

### DO:
✅ Test happy paths first, then edge cases
✅ Use mocks for external services (APIs, databases, LLMs)
✅ Test error handling explicitly
✅ Use parametrized tests for multiple scenarios
✅ Keep tests fast (<1s each)
✅ Use meaningful test names (test_should_xxx_when_yyy)

### DON'T:
❌ Test external services directly (use mocks)
❌ Make tests depend on each other
❌ Hard-code sensitive data
❌ Skip testing error paths
❌ Write tests that are flaky

## Quick Wins (Start Here!)

These can be done in 1-2 hours each:

1. **test_api_health.py** - Simple health check endpoint
2. **test_redis_manager_basic.py** - Basic Redis operations with fakeredis
3. **test_dashboard_aggregator_unit.py** - Data aggregation logic
4. **test_deployment_orchestrator_mock.py** - Orchestration with mocks

---

**Created:** 2026-01-02  
**Target Completion:** 4 weeks  
**Expected Final Coverage:** 70-75%
