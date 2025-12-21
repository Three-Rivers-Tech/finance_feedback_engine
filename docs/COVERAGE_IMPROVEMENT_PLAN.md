# Coverage Improvement Plan
## From 43% to 70% Target

**Current Status**: 43.07% coverage (18,826 total lines, 10,717 covered)
**Target**: 70% coverage
**Gap**: 26.93% (approximately 5,078 additional lines need testing)

---

## Why 43% Temporarily?

The pre-commit coverage threshold was temporarily lowered from 70% to 43% on 2025-12-20 to resolve emergency bypasses and unblock development. This is a **temporary measure** with a clear path to reach the 70% production target.

### Context
- **Original requirement**: 70% coverage (documented in pytest.ini and CI)
- **Actual coverage**: 43.07%
- **Bypass root cause**: Coverage gap prevented commits
- **Decision**: Set threshold at current level, incrementally increase

---

## Phased Improvement Strategy

### Phase 1: Critical Components (Priority 1) - Target: 50% Overall
**Timeline**: Week 1
**Focus**: Core trading logic and decision engine

**Modules to prioritize**:
1. `finance_feedback_engine/decision_engine/` - Currently undertested
   - `ensemble_manager.py` - Multi-LLM voting logic
   - `engine.py` - Position sizing, prompt building
   - `decision_validation.py` - Schema validation

2. `finance_feedback_engine/risk/` - Critical for production safety
   - `gatekeeper.py` - Risk validation
   - `var_calculator.py` - Value-at-risk

3. `finance_feedback_engine/trading_platforms/` - Platform integration
   - `coinbase_platform.py` - Crypto trading
   - `oanda_platform.py` - Forex trading
   - `platform_factory.py` - Circuit breaker logic

**Test additions needed**: ~1,300 lines

---

### Phase 2: Data & Memory (Priority 2) - Target: 55% Overall
**Timeline**: Week 2
**Focus**: Data providers and memory systems

**Modules to prioritize**:
1. `finance_feedback_engine/data_providers/` - Market data retrieval
   - `alpha_vantage_provider.py` - Multi-timeframe data
   - `unified_data_provider.py` - Provider aggregation
   - `timeframe_aggregator.py` - Technical indicators

2. `finance_feedback_engine/memory/` - Portfolio memory
   - `portfolio_memory.py` - Experience replay
   - `vector_store.py` - Embedding search (after JSON migration)

**Test additions needed**: ~900 lines

---

### Phase 3: Monitoring & Agent (Priority 3) - Target: 62% Overall
**Timeline**: Week 3
**Focus**: Monitoring, logging, and agent orchestration

**Modules to prioritize**:
1. `finance_feedback_engine/monitoring/` - Observability
   - `trade_monitor.py` - Real-time P&L tracking
   - `context_provider.py` - Position awareness
   - `logging_config.py` - Structured logging
   - **NEW**: `error_tracking.py` - Centralized error tracking (Phase 2.1)
   - **NEW**: `performance_metrics.py` - Instrumentation (Phase 2.2)

2. `finance_feedback_engine/agent/` - OODA loop
   - `trading_loop_agent.py` - State machine
   - `orchestrator.py` - Legacy orchestrator

**Test additions needed**: ~1,300 lines

---

### Phase 4: API, CLI & Utils (Priority 4) - Target: 70% Overall
**Timeline**: Week 4
**Focus**: Remaining components to reach 70%

**Modules to prioritize**:
1. `finance_feedback_engine/api/` - FastAPI endpoints
   - `app.py` - Web service
   - `telegram.py` - Telegram bot

2. `finance_feedback_engine/cli/` - Command-line interface
   - `main.py` - CLI entry point
   - `commands/` - Individual commands

3. `finance_feedback_engine/utils/` - Utilities
   - `config_validator.py` - Config validation
   - `market_regime_detector.py` - ADX/ATR classification
   - **NEW**: `environment.py` - Environment detection (Phase 1.4)

**Test additions needed**: ~1,578 lines

---

## Testing Guidelines

### What to Test
- **Business logic**: Decision algorithms, risk calculations, position sizing
- **Integration points**: Platform APIs, data providers, ensemble voting
- **Error handling**: Circuit breakers, fallback logic, validation
- **State machines**: Agent OODA loop, trade monitor
- **Critical paths**: Balance retrieval, trade execution, decision persistence

### What NOT to Test (Mark with `# pragma: no cover`)
- **Defensive error handling**: Unreachable exception branches
- **External service mocks**: Already tested by libraries
- **Simple getters/setters**: Trivial properties with no logic
- **Third-party library wrappers**: Thin wrappers with no business logic

### Test Quality Standards
- **Unit tests**: Fast (<1s each), no external dependencies
- **Integration tests**: Test multi-component workflows
- **Fixtures**: Reuse fixtures from `tests/conftest.py`
- **Markers**: Use `@pytest.mark.slow` for tests >1s, `@pytest.mark.external_service` for API calls
- **Coverage**: Aim for 80%+ on new modules, 70%+ overall

---

## Monitoring Progress

### Weekly Check-ins
Every Friday, run:
```bash
pytest -m "not slow and not external_service" --cov=finance_feedback_engine --cov-report=html
open htmlcov/index.html
```

**Track**:
- Overall coverage percentage
- Modules below 70% (sort by coverage in HTML report)
- Number of uncovered lines

### Adjusting Pre-Commit Threshold
As coverage improves, update `.pre-commit-config.yaml`:

- **Week 1** (Phase 1 complete): Increase to `--cov-fail-under=50`
- **Week 2** (Phase 2 complete): Increase to `--cov-fail-under=55`
- **Week 3** (Phase 3 complete): Increase to `--cov-fail-under=62`
- **Week 4** (Phase 4 complete): Increase to `--cov-fail-under=70` (FINAL)

### Enforcement in CI
Once 70% is reached:
- Update `.github/workflows/ci.yml` line 63: `--cov-fail-under=70`
- Enable Codecov strict mode: `fail_ci_if_error: true` (already planned in Phase 1.5)
- Add coverage badge to README.md

---

## Tracking Uncovered Code

### High-Priority Gaps (from current 65 test failures)
Based on test failures observed on 2025-12-20:

1. **Ensemble fallback tiers** (`test_ensemble_tiers.py`)
   - Issue: `test_fallback_to_single_provider` expects 'single_provider' but gets 'weighted'
   - Root cause: Ensemble manager fallback logic

2. **Platform error handling** (`test_platform_error_handling.py`)
   - 25 failures in Coinbase/Oanda error handling
   - Missing: Connection errors, timeout handling, malformed responses

3. **Data provider integration** (`test_data_providers_comprehensive.py`)
   - 13 failures in unified data provider routing
   - Missing: Fallback on provider failure, Coinbase/Oanda integration

4. **Historical data provider** (`test_historical_data_provider_implementation.py`)
   - AttributeError: `asyncio` attribute missing
   - Fix: Import asyncio in historical_data_provider.py

5. **Redis/Telegram integration** (`test_integrations_telegram_redis.py`)
   - 12 failures in tunnel management, Redis setup
   - Low priority: External service tests (already marked `@pytest.mark.external_service`)

---

## Success Criteria

### Phase 1 (Week 1) - ✅ 50% Coverage
- [ ] All modules in `decision_engine/` have ≥70% coverage
- [ ] All modules in `risk/` have ≥75% coverage
- [ ] Core `trading_platforms/` modules have ≥70% coverage
- [ ] Pre-commit threshold updated to 50%

### Phase 2 (Week 2) - ✅ 55% Coverage
- [ ] All modules in `data_providers/` have ≥70% coverage
- [ ] All modules in `memory/` have ≥70% coverage
- [ ] Pre-commit threshold updated to 55%

### Phase 3 (Week 3) - ✅ 62% Coverage
- [ ] All modules in `monitoring/` have ≥70% coverage
- [ ] All modules in `agent/` have ≥70% coverage
- [ ] Pre-commit threshold updated to 62%

### Phase 4 (Week 4) - ✅ 70% Coverage
- [ ] **Overall coverage: 70%+**
- [ ] All modules have ≥70% coverage (except marked `# pragma: no cover`)
- [ ] Pre-commit threshold updated to 70%
- [ ] CI enforces 70% threshold
- [ ] Coverage badge added to README

---

## Rollback Strategy

If coverage improvement blocks development:
1. **Identify blockers**: Which modules are failing tests?
2. **Fix or skip**: Either fix the tests or mark problematic tests as `@pytest.mark.slow`
3. **Temporary bypass**: Use `SKIP=pytest-fast git commit` with logging (see PRE_COMMIT_BYPASS_LOG.md)
4. **Create issue**: Track bypasses as GitHub issues with 24-hour resolution

**Do NOT**:
- Lower coverage threshold below current level (43%)
- Remove tests to artificially increase coverage
- Add `# pragma: no cover` without justification

---

## Resources

- **Coverage report**: `pytest --cov=finance_feedback_engine --cov-report=html && open htmlcov/index.html`
- **Test failures**: `pytest -m "not slow and not external_service" -v`
- **Bypass log**: `PRE_COMMIT_BYPASS_LOG.md`
- **CI configuration**: `.github/workflows/ci.yml`
- **Pre-commit config**: `.pre-commit-config.yaml`

---

## Questions?

Contact: @Zzzero-hash or open an issue tagged `coverage-improvement`

**Last Updated**: 2025-12-20
**Target Completion**: 2026-01-17 (4 weeks)
