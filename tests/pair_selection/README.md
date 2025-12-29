# Pair Selection Test Suite

Comprehensive test suite for the autonomous trading pair selection system.

## Overview

This test suite covers all components of the pair selection module, including:
- Statistical analyzers (Sortino, Correlation, GARCH)
- Metric aggregation
- Thompson Sampling optimization
- Outcome tracking
- LLM ensemble voting
- Pair universe caching
- End-to-end integration tests

## Test Structure

```
tests/pair_selection/
├── __init__.py
├── test_sortino_analyzer.py        # Sortino Ratio calculation
├── test_correlation_matrix.py      # Portfolio correlation analysis
├── test_garch_volatility.py        # GARCH volatility forecasting
├── test_metric_aggregator.py       # Metric combination
├── test_thompson_optimizer.py      # Thompson Sampling
├── test_outcome_tracker.py         # Selection outcome tracking
├── test_ensemble_voter.py          # LLM ensemble voting
├── test_pair_universe.py           # Pair universe caching
└── README.md                        # This file

tests/integration/
└── test_pair_selection_pipeline.py # End-to-end integration tests
```

## Running Tests

### Run All Pair Selection Tests

```bash
# From project root
pytest tests/pair_selection/ -v

# With coverage
pytest tests/pair_selection/ --cov=finance_feedback_engine.pair_selection --cov-report=html
```

### Run Individual Test Files

```bash
# Test Sortino analyzer
pytest tests/pair_selection/test_sortino_analyzer.py -v

# Test correlation matrix
pytest tests/pair_selection/test_correlation_matrix.py -v

# Test GARCH volatility
pytest tests/pair_selection/test_garch_volatility.py -v

# Test metric aggregator
pytest tests/pair_selection/test_metric_aggregator.py -v

# Test Thompson Sampling
pytest tests/pair_selection/test_thompson_optimizer.py -v

# Test outcome tracker
pytest tests/pair_selection/test_outcome_tracker.py -v

# Test ensemble voter
pytest tests/pair_selection/test_ensemble_voter.py -v

# Test pair universe cache
pytest tests/pair_selection/test_pair_universe.py -v
```

### Run Integration Tests

```bash
# Full pipeline integration test
pytest tests/integration/test_pair_selection_pipeline.py -v
```

### Run Specific Test Classes or Methods

```bash
# Run specific test class
pytest tests/pair_selection/test_sortino_analyzer.py::TestSortinoAnalyzer -v

# Run specific test method
pytest tests/pair_selection/test_sortino_analyzer.py::TestSortinoAnalyzer::test_calculate_sortino_positive_returns -v
```

## Test Categories

### Unit Tests

#### Statistical Analyzers
- **test_sortino_analyzer.py**: Tests Sortino Ratio calculation with various market scenarios (uptrend, downtrend, volatile, insufficient data)
- **test_correlation_matrix.py**: Tests portfolio correlation analysis and diversification scoring
- **test_garch_volatility.py**: Tests GARCH(1,1) volatility forecasting and regime classification

#### Metric Aggregation
- **test_metric_aggregator.py**: Tests weighted combination of statistical metrics using sigmoid normalization

#### Thompson Sampling
- **test_thompson_optimizer.py**: Tests Beta distribution sampling, weight optimization, and learning from outcomes

#### Tracking & Voting
- **test_outcome_tracker.py**: Tests selection history persistence and trade outcome linkage
- **test_ensemble_voter.py**: Tests LLM ensemble voting and response aggregation
- **test_pair_universe.py**: Tests TTL caching for discovered pairs

### Integration Tests

- **test_pair_selection_pipeline.py**: Tests complete 7-step selection pipeline with:
  - Universe discovery
  - Position locking
  - Statistical scoring
  - LLM voting
  - Thompson Sampling combination
  - Final selection
  - Reasoning generation

## Test Coverage

Target coverage: **>90%** for all pair selection modules

View coverage report:
```bash
pytest tests/pair_selection/ --cov=finance_feedback_engine.pair_selection --cov-report=html
open htmlcov/index.html  # View detailed coverage
```

## Dependencies

Required for testing:
- pytest
- pytest-asyncio (for async tests)
- pytest-mock (for mocking)
- arch (GARCH library)

Install test dependencies:
```bash
pip install pytest pytest-asyncio pytest-mock pytest-cov
```

## Test Fixtures

Common fixtures used across tests:
- `mock_data_provider`: Mock UnifiedDataProvider
- `mock_trade_monitor`: Mock TradeMonitor
- `mock_portfolio_memory`: Mock PortfolioMemoryEngine
- `mock_ai_decision_manager`: Mock AIDecisionManager
- `temp_stats_file`: Temporary file for Thompson stats
- `temp_storage_path`: Temporary directory for outcome tracker

## Writing New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<description_of_what_is_tested>`

### Example Test Structure
```python
import pytest
from unittest.mock import AsyncMock, MagicMock

class TestMyComponent:
    """Test suite for MyComponent."""

    @pytest.fixture
    def component(self):
        """Create component instance for testing."""
        return MyComponent(config={'param': 'value'})

    @pytest.mark.asyncio
    async def test_async_method(self, component):
        """Test async method behavior."""
        result = await component.async_method()
        assert result is not None

    def test_sync_method(self, component):
        """Test sync method behavior."""
        result = component.sync_method()
        assert result == expected_value
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Pair Selection Tests
  run: |
    pytest tests/pair_selection/ \
      --cov=finance_feedback_engine.pair_selection \
      --cov-report=xml \
      --cov-report=term-missing
```

## Troubleshooting

### Common Issues

**Issue**: Tests fail with `ModuleNotFoundError: No module named 'arch'`
```bash
# Solution: Install GARCH library
pip install arch
```

**Issue**: Async tests fail
```bash
# Solution: Ensure pytest-asyncio is installed
pip install pytest-asyncio
```

**Issue**: Mock-related errors
```bash
# Solution: Install pytest-mock
pip install pytest-mock
```

### Debugging Tests

Run with verbose output and print statements:
```bash
pytest tests/pair_selection/ -v -s
```

Run with pdb debugger on failure:
```bash
pytest tests/pair_selection/ --pdb
```

## Performance Benchmarks

Expected test execution times (approximate):
- Unit tests: ~10-20 seconds
- Integration tests: ~5-10 seconds
- Full suite: ~30 seconds

If tests are significantly slower, check for:
- Unnecessary network calls (should be mocked)
- Large data generation (use smaller datasets in tests)
- Missing @pytest.mark.asyncio decorators

## Validation Checklist

Before merging pair selection changes:
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage >90%
- [ ] No new warnings or deprecations
- [ ] Tests run in <60 seconds
- [ ] All mocks properly configured
- [ ] No actual API calls in tests
- [ ] Temporary files cleaned up

## Next Steps

After implementing new features:
1. Write unit tests for new components
2. Update integration tests if pipeline changed
3. Run full test suite
4. Check coverage report
5. Update this README if needed

## Contact

For questions about the test suite:
- Review test implementation patterns in existing tests
- Check pytest documentation: https://docs.pytest.org
- Review pytest-asyncio docs: https://pytest-asyncio.readthedocs.io
