# TDD Workflow & Safety Gates

## Philosophy

**PRIORITY ONE: Code Stability**
- All new features MUST be behind feature flags
- Tests written BEFORE implementation (Red → Green → Refactor)
- Pre-commit hooks MUST pass (no bypass without logging)
- 70% minimum coverage enforced
- Cannot go backwards - incremental progress only

---

## Quality Gates

### 1. Pre-Commit Gates (Automatic on `git commit`)

**Formatting & Linting:**
- ✅ Black (code formatting)
- ✅ isort (import sorting)
- ✅ Flake8 (linting)
- ✅ Mypy (type hints - relaxed for now)

**Testing:**
- ✅ Pytest-fast (unit tests, no external services)
- ✅ Coverage check (70% minimum)

**If bypass needed:** Use `SKIP=hook-name git commit` - logged to GitHub

### 2. Pre-Push Gates (Recommended)

```bash
# Run full test suite before pushing
pytest tests/ --cov=finance_feedback_engine --cov-report=term-missing --cov-fail-under=70
```

### 3. CI/CD Gates (GitHub Actions)

- Full test suite (including slow/external_service tests)
- Coverage report uploaded to Codecov
- Integration tests
- Backtest validation

---

## TDD Cycle for New Features

### Step 1: Write Failing Test First (RED)

```python
# tests/test_enhanced_slippage.py
import pytest
from finance_feedback_engine.backtesting.backtester import Backtester

def test_realistic_slippage_crypto_major():
    """Test realistic slippage for major crypto pairs"""
    backtester = Backtester(config_path='config/config.test.mock.yaml')

    # Major crypto should have 2 bps spread
    slippage = backtester._calculate_realistic_slippage(
        asset_pair='BTCUSD',
        size=1000,
        timestamp=datetime(2024, 1, 1, 12, 0, 0)  # Normal hours
    )

    # Expected: 0.02% spread + 0.005% volume impact = 0.025%
    assert slippage == pytest.approx(0.00025, rel=1e-4)

def test_realistic_slippage_low_liquidity_hours():
    """Test 1.5x slippage multiplier during low liquidity hours"""
    backtester = Backtester(config_path='config/config.test.mock.yaml')

    # Low liquidity hours (2 AM)
    slippage = backtester._calculate_realistic_slippage(
        asset_pair='EURUSD',
        size=1000,
        timestamp=datetime(2024, 1, 1, 2, 0, 0)  # Low liquidity
    )

    # Expected: 0.01% * 1.5 + 0.005% = 0.02%
    assert slippage == pytest.approx(0.0002, rel=1e-4)
```

**Run test:** `pytest tests/test_enhanced_slippage.py -v`
**Expected:** ❌ FAIL (method doesn't exist yet)

---

### Step 2: Implement Minimal Code (GREEN)

```python
# finance_feedback_engine/backtesting/backtester.py

def _calculate_realistic_slippage(self, asset_pair: str, size: float, timestamp: datetime) -> float:
    """
    Calculate realistic slippage based on asset type, size, and market hours.

    Args:
        asset_pair: Trading pair (e.g., 'BTCUSD', 'EURUSD')
        size: Order size in base currency
        timestamp: Timestamp for market hours check

    Returns:
        Slippage as decimal (e.g., 0.0002 = 0.02%)
    """
    # Bid-ask spread by asset type
    if asset_pair in ['BTCUSD', 'ETHUSD']:  # Major crypto
        spread = 0.0002  # 2 bps
    elif 'USD' in asset_pair:  # Forex majors
        spread = 0.0001  # 1 bp
    else:  # Exotic pairs
        spread = 0.0005  # 5 bps

    # Market hours liquidity adjustment
    hour = timestamp.hour
    if asset_pair.endswith('USD') and hour in [0, 1, 2, 20, 21, 22, 23]:
        spread *= 1.5  # Low liquidity hours

    # Tiered volume impact
    if size > 10000:
        volume_impact = 0.0003  # 3 bps for large orders
    elif size > 1000:
        volume_impact = 0.0001  # 1 bp for medium
    else:
        volume_impact = 0.00005  # 0.5 bps for small

    return spread + volume_impact
```

**Run test:** `pytest tests/test_enhanced_slippage.py -v`
**Expected:** ✅ PASS

---

### Step 3: Refactor & Add Feature Flag (REFACTOR)

```python
# config/config.yaml
features:
  enhanced_slippage_model: false  # OFF by default
  thompson_sampling_weights: false
  sentiment_veto: false
  rl_agent: false
  multi_agent_system: false
  paper_trading_mode: false

backtesting:
  slippage_model: "basic"  # or "realistic" when feature enabled
  fee_model: "simple"      # or "tiered" when feature enabled
```

```python
# finance_feedback_engine/backtesting/backtester.py

def _execute_trade(self, decision):
    """Execute trade with appropriate slippage model"""

    # Feature flag: Use enhanced slippage if enabled
    if self.config.get('features', {}).get('enhanced_slippage_model', False):
        slippage = self._calculate_realistic_slippage(
            decision['asset_pair'],
            decision['position_size'],
            self.current_timestamp
        )
    else:
        # Legacy basic slippage
        slippage = 0.0001  # 1 bp fixed

    # ... rest of execution logic
```

**Run full test suite:** `pytest tests/ -v`
**Expected:** ✅ ALL PASS (new feature doesn't break existing tests)

---

### Step 4: Integration Test

```python
# tests/test_slippage_integration.py

def test_backtester_with_enhanced_slippage():
    """Integration test: Backtest with enhanced slippage model"""
    config = load_config('config/config.test.mock.yaml')
    config['features']['enhanced_slippage_model'] = True
    config['backtesting']['slippage_model'] = 'realistic'

    backtester = Backtester(config=config)
    results = backtester.run(
        asset_pair='BTCUSD',
        start_date='2024-01-01',
        end_date='2024-01-31'
    )

    # Enhanced slippage should reduce returns slightly
    assert results['total_return'] < 0.15  # More realistic
    assert results['sharpe_ratio'] > 0  # Still profitable
    assert 'slippage_costs' in results
```

---

### Step 5: Documentation

```python
def _calculate_realistic_slippage(self, asset_pair: str, size: float, timestamp: datetime) -> float:
    """
    Calculate realistic slippage based on asset type, size, and market hours.

    Implements tiered slippage model with:
    - Bid-ask spread by asset class (crypto: 2 bps, forex major: 1 bp, exotic: 5 bps)
    - Market hours liquidity adjustment (1.5x during low liquidity)
    - Volume impact (tiered: small/medium/large orders)

    Feature flag: `features.enhanced_slippage_model` must be enabled

    Args:
        asset_pair: Trading pair (e.g., 'BTCUSD', 'EURUSD')
        size: Order size in base currency
        timestamp: Timestamp for market hours check

    Returns:
        Slippage as decimal (e.g., 0.0002 = 0.02%)

    Examples:
        >>> backtester._calculate_realistic_slippage('BTCUSD', 1000, datetime(2024,1,1,12,0))
        0.00025  # 2 bps spread + 0.5 bps volume = 2.5 bps

    References:
        - Plan: /home/cmp6510/.claude/plans/declarative-sprouting-balloon.md (Phase 1.1)
        - Research: Realistic slippage critical for live/backtest correlation
    """
```

---

## Feature Flag Pattern

### Configuration Structure

```yaml
# config/config.yaml
features:
  # Phase 1: Quick Wins
  enhanced_slippage_model: false
  thompson_sampling_weights: false

  # Phase 2: Medium-term
  sentiment_veto: false
  paper_trading_mode: false
  visual_reports: false

  # Phase 3: Advanced ML
  rl_agent: false
  multi_agent_system: false

  # Phase 4: Infrastructure
  parallel_backtesting: false
  limit_stop_orders: false
```

### Usage Pattern

```python
# finance_feedback_engine/decision_engine/ensemble_manager.py

class EnsembleDecisionManager:
    def __init__(self, config):
        self.config = config

        # Initialize Thompson Sampling only if feature enabled
        if self._is_feature_enabled('thompson_sampling_weights'):
            from .thompson_sampling import ThompsonSamplingWeightOptimizer
            self.weight_optimizer = ThompsonSamplingWeightOptimizer()
        else:
            self.weight_optimizer = None

    def _is_feature_enabled(self, feature_name: str) -> bool:
        """Check if feature flag is enabled"""
        return self.config.get('features', {}).get(feature_name, False)

    def aggregate_decisions(self, provider_decisions, market_regime='trending'):
        """Aggregate with optional Thompson Sampling"""

        if self.weight_optimizer and self._is_feature_enabled('thompson_sampling_weights'):
            # Use dynamic weights from Thompson Sampling
            weights = self.weight_optimizer.sample_weights(market_regime)
        else:
            # Legacy: Use static weights from config
            weights = self.config['ensemble']['provider_weights']

        # ... rest of aggregation logic
```

---

## Rollback Mechanism

### Gradual Rollout

```yaml
# config/config.local.yaml (user-specific)

# Week 1: Test enhanced slippage in backtesting only
features:
  enhanced_slippage_model: true

# Week 2: Add Thompson Sampling if slippage tests pass
features:
  enhanced_slippage_model: true
  thompson_sampling_weights: true

# Week 3: Enable in paper trading
mode: paper_trading
features:
  enhanced_slippage_model: true
  thompson_sampling_weights: true
  paper_trading_mode: true
```

### Rollback Script

```bash
#!/bin/bash
# scripts/rollback_feature.sh

FEATURE=$1

if [ -z "$FEATURE" ]; then
    echo "Usage: ./scripts/rollback_feature.sh <feature_name>"
    exit 1
fi

# Disable feature in config
python -c "
import yaml
with open('config/config.local.yaml', 'r') as f:
    config = yaml.safe_load(f)
config['features']['$FEATURE'] = False
with open('config/config.local.yaml', 'w') as f:
    yaml.safe_dump(config, f)
"

echo "✅ Rolled back feature: $FEATURE"
echo "Run backtest to validate: python main.py backtest BTCUSD --start-date 2024-01-01"
```

---

## Coverage Requirements

### Minimum Coverage: 70%

```bash
# Run with coverage
pytest tests/ \
  --cov=finance_feedback_engine \
  --cov-report=term-missing \
  --cov-report=html \
  --cov-fail-under=70
```

### New Code: 90% Coverage

```python
# All new features MUST have 90%+ coverage
# Use pytest-cov to check specific files

pytest tests/test_enhanced_slippage.py \
  --cov=finance_feedback_engine.backtesting.backtester \
  --cov-report=term-missing \
  --cov-fail-under=90
```

### Coverage Exemptions

```python
# Only exempt defensive error handling
def _calculate_realistic_slippage(self, asset_pair, size, timestamp):
    try:
        # Main logic
        return spread + volume_impact
    except Exception as e:  # pragma: no cover
        # Fallback to basic slippage
        logger.error(f"Slippage calculation failed: {e}")
        return 0.0001
```

---

## Agent Delegation Strategy

### Use TDD Agents for Features

```python
# Delegate to tdd-orchestrator for TDD workflow enforcement
# Example: Implementing Thompson Sampling

Task(
    subagent_type='tdd-workflows:tdd-orchestrator',
    description='Implement Thompson Sampling weight optimization',
    prompt='''
    Implement Thompson Sampling weight optimization for ensemble providers.

    CRITICAL: Follow TDD workflow:
    1. Write failing tests first (Red)
    2. Implement minimal code to pass (Green)
    3. Refactor with feature flag (Refactor)

    Requirements:
    - Feature flag: features.thompson_sampling_weights
    - 90%+ test coverage
    - Integration with EnsembleDecisionManager
    - Beta distribution for provider weights
    - Regime-based multipliers

    Files:
    - Tests: tests/decision_engine/test_thompson_sampling.py
    - Implementation: finance_feedback_engine/decision_engine/thompson_sampling.py
    - Integration: finance_feedback_engine/decision_engine/ensemble_manager.py

    Reference: /home/cmp6510/.claude/plans/declarative-sprouting-balloon.md (Phase 1.2)
    '''
)
```

### Use Code Review Agents After Implementation

```python
# Delegate to code-reviewer after feature complete
Task(
    subagent_type='code-review:code-review',
    description='Review Thompson Sampling implementation',
    prompt='''
    Review the Thompson Sampling weight optimization implementation.

    Focus on:
    - Test coverage (should be 90%+)
    - Feature flag integration (properly gated?)
    - Backward compatibility (no breaking changes?)
    - Performance implications (added latency?)
    - Security concerns (input validation?)

    Files to review:
    - tests/decision_engine/test_thompson_sampling.py
    - finance_feedback_engine/decision_engine/thompson_sampling.py
    - finance_feedback_engine/decision_engine/ensemble_manager.py
    '''
)
```

---

## Pre-Commit Bypass Protocol

### When to Bypass

**NEVER bypass unless:**
1. Emergency hotfix for production bug
2. Documentation-only changes
3. Test infrastructure changes (carefully)

### How to Bypass

```bash
# Bypass specific hook (logged automatically)
SKIP=pytest-fast git commit -m "docs: Update TDD workflow"

# Check bypass log
cat PRE_COMMIT_BYPASS_LOG.md
```

### Bypass Audit

All bypasses logged to `PRE_COMMIT_BYPASS_LOG.md`:
```markdown
## 2024-12-19 14:30:00
- Hook: pytest-fast
- Reason: Documentation update only
- Commit: abc123 "docs: Update TDD workflow"
- User: cmp6510
```

---

## Testing Pyramid

### Unit Tests (Fast, Isolated)
- Target: 70% coverage minimum
- Run on every commit (pre-commit hook)
- No external services (mock everything)
- Markers: `not slow and not external_service`

**Example:**
```python
@pytest.mark.unit
def test_thompson_sampling_beta_distribution():
    """Unit test: Beta distribution sampling"""
    optimizer = ThompsonSamplingWeightOptimizer()
    optimizer.provider_stats['local'] = {'alpha': 10, 'beta': 5}

    weights = optimizer.sample_weights()

    assert 'local' in weights
    assert 0 <= weights['local'] <= 1
    assert sum(weights.values()) == pytest.approx(1.0)
```

### Integration Tests (Medium Speed)
- Run before push
- Test multiple components together
- Mock only external APIs
- Markers: `not external_service`

**Example:**
```python
@pytest.mark.integration
def test_ensemble_with_thompson_sampling():
    """Integration test: Ensemble + Thompson Sampling"""
    config = load_config('config/config.test.mock.yaml')
    config['features']['thompson_sampling_weights'] = True

    engine = DecisionEngine(config)
    decision = engine.generate_decision('BTCUSD', market_data)

    assert 'ensemble_metadata' in decision
    assert 'thompson_sampling_weights' in decision['ensemble_metadata']
```

### E2E Tests (Slow, Full Stack)
- Run in CI/CD only
- Real external services (requires API keys)
- Markers: `slow` or `external_service`

**Example:**
```python
@pytest.mark.slow
@pytest.mark.external_service
def test_live_backtest_with_all_features():
    """E2E test: Full backtest with all Phase 1 features"""
    config = load_config('config/config.test.mock.yaml')
    config['features']['enhanced_slippage_model'] = True
    config['features']['thompson_sampling_weights'] = True

    backtester = Backtester(config)
    results = backtester.run('BTCUSD', '2024-01-01', '2024-01-31')

    assert results['sharpe_ratio'] > 1.5  # Phase 1 target
```

---

## Continuous Validation

### Daily Backtest (Automated)

```bash
# .github/workflows/daily-backtest.yml
# Runs nightly to catch regressions

- name: Daily Backtest Validation
  run: |
    python main.py backtest BTCUSD --start-date 2024-01-01 --end-date 2024-12-01
    python scripts/compare_performance.py --baseline data/baseline_results.json
```

### Performance Regression Detection

```python
# scripts/compare_performance.py

def check_regression(current_results, baseline_results):
    """Fail if performance degrades >5%"""

    current_sharpe = current_results['sharpe_ratio']
    baseline_sharpe = baseline_results['sharpe_ratio']

    degradation = (baseline_sharpe - current_sharpe) / baseline_sharpe

    if degradation > 0.05:  # >5% degradation
        raise RegressionError(
            f"Performance degraded by {degradation*100:.1f}%\n"
            f"Baseline Sharpe: {baseline_sharpe:.2f}\n"
            f"Current Sharpe: {current_sharpe:.2f}"
        )
```

---

## Summary Checklist

Before merging any feature:

- [ ] Tests written FIRST (Red → Green → Refactor)
- [ ] Feature flag implemented and documented
- [ ] 90%+ coverage for new code
- [ ] All pre-commit hooks pass
- [ ] Integration tests pass
- [ ] Backward compatibility verified (old config still works)
- [ ] Performance regression check passed
- [ ] Code review completed
- [ ] Documentation updated (CLAUDE.md, docstrings)
- [ ] Baseline backtest results saved for comparison

**Remember: We cannot afford to go backwards. Quality gates are non-negotiable.**
