# Technical Debt Cleanup Plan - Finance Feedback Engine 2.0

**Created**: December 14, 2025
**Status**: 📋 Planning Phase
**Focus**: Code quality improvements, no new features

---

## Overview

This plan addresses technical debt accumulated in the Finance Feedback Engine codebase. Based on analysis of 164 Python files with 40,572 lines of production code, we've identified **20 high-impact cleanup tasks** that will improve code quality, maintainability, and developer experience.

**Goal**: Reduce technical debt from **210/1000** to **<100/1000** (Low to Very Low)

**Timeline**: 4-6 weeks (parallel work possible)

---

## Current State Metrics

| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| Bare exception handlers | 130 | <50 | 🔴 High |
| TODO comments | 254 | <50 | 🟡 Medium |
| FIXME comments | 31 | 0 | 🟡 Medium |
| Type: ignore comments | 325 | <100 | 🟠 Medium |
| Noqa suppressions | 259 | <100 | 🟠 Medium |
| Pragma: no cover | 144 | <80 | 🟢 Low |
| Test coverage | Unknown | ≥70% | 🔴 High |
| Circular imports | 0 | 0 | ✅ Done |
| Outdated dependencies | 0 | 0 | ✅ Done |

---

## Phase 1: Build Hygiene (Week 1) 🔴 CRITICAL

### 1.1 Clean Up Git Repository

**Problem**: Python cache files tracked in git (mypy cache, __pycache__)

**Impact**: Repository bloat, merge conflicts, inconsistent builds

**Tasks**:
```bash
# Remove cache files from git
git rm -r --cached .mypy_cache/
find . -type d -name "__pycache__" -exec git rm -r --cached {} +

# Commit cleanup
git commit -m "chore: Remove Python cache files from git"
```

**Files**: `.mypy_cache/`, all `__pycache__/` directories

**Effort**: 15 minutes

**Priority**: 🔴 High (prevents future issues)

---

### 1.2 Fix .gitignore Completeness

**Problem**: .gitignore doesn't prevent all cache files

**Current .gitignore issues**:
- ✅ Has `__pycache__/` (good)
- ✅ Has `.mypy_cache/` (good)
- ❌ Missing `.ruff_cache/`
- ❌ Missing `*.pyc` in root
- ❌ Missing `.pytest_cache/` subdirectories
- ❌ Missing data pipeline artifacts (watermarks, DLQ)

**Fix**:
```bash
# Add to .gitignore
echo "" >> .gitignore
echo "# Data pipeline artifacts" >> .gitignore
echo "data/watermarks/" >> .gitignore
echo "data/dlq/" >> .gitignore
echo "data/delta_lake/" >> .gitignore
echo "data/cache/" >> .gitignore
echo "" >> .gitignore
echo "# Additional Python artifacts" >> .gitignore
echo ".ruff_cache/" >> .gitignore
echo "*.pyc" >> .gitignore
```

**Effort**: 10 minutes

**Priority**: 🔴 High

---

### 1.3 Add Pre-Commit Hooks

**Problem**: No automated checks before commit (allows bad code to enter repo)

**Solution**: Install pre-commit framework with hooks

**Configuration** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ["--max-line-length=88", "--extend-ignore=E203,W503"]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
        args: ["--ignore-missing-imports"]

  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/ --maxfail=1 -q
        language: system
        pass_filenames: false
        always_run: true
```

**Installation**:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files  # Initial run
```

**Effort**: 1 hour (setup + fix initial issues)

**Priority**: 🔴 High (prevents future debt)

---

## Phase 2: Error Handling Improvements (Week 1-2) 🔴 CRITICAL

### 2.1 Create Comprehensive Exception Hierarchy

**Problem**: 130 bare `except Exception` handlers mask real errors

**Current state** (from TECHNICAL_DEBT_ANALYSIS.md):
```python
# Anti-pattern (67 files)
try:
    risky_operation()
except Exception as e:  # Too broad!
    logger.warning(f"Operation failed: {e}")
    # Masks OOM, network, permission errors
```

**Solution**: Create specific exception types in `finance_feedback_engine/exceptions.py`

**New exception hierarchy**:
```python
# finance_feedback_engine/exceptions.py

class FFEBaseError(Exception):
    """Base exception for all FFE errors."""
    pass

# Client-side errors (4xx equivalent)
class FFEBadRequestError(FFEBaseError):
    """Invalid user input or configuration."""
    pass

class AssetPairValidationError(FFEBadRequestError):
    """Invalid asset pair format."""
    pass

class ConfigurationError(FFEBadRequestError):
    """Invalid configuration."""
    pass

# Server-side errors (5xx equivalent)
class FFEInternalError(FFEBaseError):
    """Internal system error."""
    pass

class DataProviderError(FFEInternalError):
    """Data provider unavailable."""
    pass

class ModelDownloadError(FFEInternalError):
    """ML model download failed."""
    pass

class InsufficientDiskSpaceError(FFEInternalError):
    """Not enough disk space."""
    pass

# Trading platform errors
class TradingPlatformError(FFEInternalError):
    """Trading platform communication error."""
    pass

class InsufficientBalanceError(TradingPlatformError):
    """Account balance too low."""
    pass

class OrderRejectedError(TradingPlatformError):
    """Order rejected by platform."""
    pass

# Decision engine errors
class DecisionEngineError(FFEInternalError):
    """Decision engine failure."""
    pass

class EnsembleQuorumNotMetError(DecisionEngineError):
    """Insufficient providers for ensemble decision."""
    pass

class AIProviderTimeoutError(DecisionEngineError):
    """AI provider did not respond in time."""
    pass
```

**Refactoring priority** (130 instances):
1. **core.py** (8 instances) - Week 1
2. **ensemble_manager.py** (8 instances) - Week 1
3. **trading_platforms/coinbase_platform.py** (18 instances) - Week 2
4. **monitoring/trade_monitor.py** (10 instances) - Week 2
5. **Other files** (86 instances) - Week 3-4

**Validation**:
```bash
# Before: 130 bare exceptions
grep -r "except Exception" --include="*.py" | wc -l

# Target: <50 bare exceptions
```

**Effort**: 16-24 hours (distributed across files)

**Priority**: 🔴 High (critical for debugging)

---

### 2.2 Improve Error Messages

**Problem**: Generic error messages don't provide actionable context

**Examples to fix**:
```python
# Bad
raise ValueError("Invalid input")

# Good
raise AssetPairValidationError(
    f"Invalid asset pair '{asset_pair}': must be 6 characters (e.g., BTCUSD). "
    f"Got {len(asset_pair)} characters."
)
```

**Files to review**: All files with `raise ValueError`, `raise Exception`

**Effort**: 4-6 hours

**Priority**: 🟡 Medium

---

## Phase 3: Type Safety (Week 2-3) 🟠 MEDIUM

### 3.1 Reduce Type: Ignore Comments

**Problem**: 325 type: ignore comments indicate incomplete type annotations

**Target**: <100 (69% reduction)

**Strategy**:
1. **Add return type hints**: Functions missing `-> Type`
2. **Add parameter types**: Untyped parameters
3. **Use Union/Optional**: Instead of `type: ignore` on None checks
4. **Use TypedDict**: For complex dict structures

**Example fixes**:
```python
# Before (type: ignore)
def process_data(data):  # type: ignore
    return data['key']

# After (proper typing)
from typing import TypedDict, Optional

class MarketData(TypedDict):
    timestamp: str
    close: float
    volume: Optional[float]

def process_data(data: MarketData) -> float:
    return data['close']
```

**Priority files** (most type: ignore comments):
1. `decision_engine/engine.py`
2. `data_providers/alpha_vantage_provider.py`
3. `ensemble_manager.py`

**Validation**:
```bash
# Run mypy with strict mode
mypy finance_feedback_engine/ --strict --ignore-missing-imports
```

**Effort**: 12-16 hours

**Priority**: 🟠 Medium

---

### 3.2 Add Type Hints to Pipeline Modules

**Problem**: New pipeline code missing type annotations

**Files**:
- `finance_feedback_engine/pipelines/batch/batch_ingestion.py`
- `finance_feedback_engine/pipelines/storage/delta_lake_manager.py`

**Example**:
```python
# Add proper typing
from typing import Dict, Any, List, Optional
from pandas import DataFrame

async def ingest_historical_data(
    self,
    asset_pair: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    provider: str = 'alpha_vantage'
) -> Dict[str, Any]:
    """Type-annotated method."""
    ...
```

**Effort**: 2-3 hours

**Priority**: 🟡 Medium

---

## Phase 4: Code Quality (Week 3-4) 🟡 MEDIUM

### 4.1 Review and Resolve TODO Comments

**Problem**: 254 TODO comments indicate incomplete work

**Strategy**:
1. **Categorize**: Feature TODOs vs. technical debt TODOs
2. **Delete stale**: TODOs for features already implemented
3. **Create issues**: Convert valid TODOs to GitHub issues
4. **Fix quick wins**: Simple TODOs that can be done immediately

**Search and categorize**:
```bash
# Extract all TODOs with context
grep -rn "# TODO" --include="*.py" > todos.txt

# Common patterns to look for:
# TODO: Add tests
# TODO: Optimize this
# TODO: Remove this after...
# TODO: Handle edge case
```

**Target**: <50 TODO comments (80% reduction)

**Effort**: 6-8 hours (review + triage)

**Priority**: 🟡 Medium

---

### 4.2 Review and Resolve FIXME Comments

**Problem**: 31 FIXME comments indicate bugs or issues

**Strategy**: FIXME = higher priority than TODO

```bash
# Extract all FIXMEs
grep -rn "# FIXME" --include="*.py"

# Common patterns:
# FIXME: Race condition here
# FIXME: Memory leak
# FIXME: Hardcoded value
```

**Target**: 0 FIXME comments (all resolved)

**Effort**: 4-6 hours

**Priority**: 🟠 Medium-High

---

### 4.3 Reduce Linter Suppressions

**Problem**: 259 noqa comments bypass code quality checks

**Strategy**:
1. **Fix underlying issue**: Don't suppress, fix the problem
2. **Use specific codes**: `# noqa: E501` (too generic: `# noqa`)
3. **Document why**: Add reason for suppression

**Example**:
```python
# Bad
some_long_line_that_violates_pep8_because_reasons()  # noqa

# Good (fix the issue)
some_long_line_that_violates_pep8_because_reasons(
    parameter1=value1,
    parameter2=value2
)

# Acceptable (with justification)
url = "https://example.com/very/long/api/endpoint"  # noqa: E501 - URL cannot be split
```

**Target**: <100 noqa comments (61% reduction)

**Effort**: 8-10 hours

**Priority**: 🟡 Medium

---

## Phase 5: Testing & Coverage (Week 3-4) 🔴 HIGH

### 5.1 Add Integration Tests for Data Pipeline

**Problem**: New pipeline modules lack integration tests

**Tests needed**:
```python
# tests/integration/test_pipeline_integration.py

@pytest.mark.integration
async def test_end_to_end_backfill():
    """Test: Alpha Vantage → Bronze Layer → Query."""
    # 1. Ingest 7 days of BTCUSD data
    # 2. Verify records in Delta Lake
    # 3. Query and validate data quality
    pass

@pytest.mark.integration
def test_delta_lake_time_travel():
    """Test: Write → Optimize → Time travel query."""
    pass

@pytest.mark.integration
def test_watermark_persistence():
    """Test: Watermark survives process restart."""
    pass
```

**Effort**: 6-8 hours

**Priority**: 🔴 High

---

### 5.2 Review Coverage Exclusions

**Problem**: 144 `# pragma: no cover` exclusions may hide untested code

**Strategy**:
1. **Justify or remove**: Each exclusion needs a reason
2. **Add tests**: For code that can be tested
3. **Document**: Why code is untestable (defensive error paths)

**Valid exclusions**:
```python
# OK: Defensive programming
if platform_name not in VALID_PLATFORMS:  # pragma: no cover
    raise ValueError(f"Invalid platform: {platform_name}")

# NOT OK: Lazy testing
def complex_business_logic():  # pragma: no cover
    # This should be tested!
    pass
```

**Target**: <80 exclusions (44% reduction)

**Effort**: 4-6 hours

**Priority**: 🟢 Low

---

### 5.3 Add CLI Smoke Tests

**Problem**: No automated tests for CLI commands

**Solution**: Test each command executes without error

```python
# tests/test_cli_smoke.py

def test_analyze_command_smoke(cli_runner):
    """Smoke test: analyze command doesn't crash."""
    result = cli_runner.invoke(main, ['analyze', 'BTCUSD', '--dry-run'])
    assert result.exit_code == 0

def test_backtest_command_smoke(cli_runner):
    """Smoke test: backtest command doesn't crash."""
    result = cli_runner.invoke(main, ['backtest', 'BTCUSD', '--dry-run'])
    assert result.exit_code == 0
```

**Commands to test**: analyze, backtest, execute, balance, history, monitor, run-agent

**Effort**: 2-3 hours

**Priority**: 🟡 Medium

---

## Phase 6: Documentation & Configuration (Week 4) 🟢 LOW

### 6.1 Add Docstring Validation

**Problem**: Inconsistent docstrings across codebase

**Solution**: Use pydocstyle to enforce standards

```bash
# Install pydocstyle
pip install pydocstyle

# Check docstrings
pydocstyle finance_feedback_engine/

# Add to pre-commit hooks
```

**Standard**: Google-style docstrings

**Effort**: 2-3 hours (setup + fix critical files)

**Priority**: 🟢 Low

---

### 6.2 Add Configuration Schema Validation

**Problem**: No validation of config.yaml structure

**Solution**: Use Pydantic for config validation

```python
# finance_feedback_engine/config_schema.py

from pydantic import BaseModel, Field, validator
from typing import List, Optional

class AlphaVantageConfig(BaseModel):
    api_key: str = Field(..., min_length=16)
    timeout: int = Field(10, ge=5, le=60)

class AgentConfig(BaseModel):
    asset_pairs: List[str] = Field(..., min_items=1)
    take_profit_percentage: float = Field(0.05, ge=0.01, le=1.0)
    stop_loss_percentage: float = Field(0.02, ge=0.01, le=1.0)

    @validator('asset_pairs')
    def validate_asset_pairs(cls, v):
        from finance_feedback_engine.utils.validation import standardize_asset_pair
        return [standardize_asset_pair(pair) for pair in v]

class FFEConfig(BaseModel):
    alpha_vantage: AlphaVantageConfig
    agent: AgentConfig
    # ... other sections

# Usage
def load_config(path: str) -> FFEConfig:
    with open(path) as f:
        raw_config = yaml.safe_load(f)
    return FFEConfig(**raw_config)  # Validates on load!
```

**Effort**: 4-6 hours

**Priority**: 🟡 Medium

---

### 6.3 Remove or Document Utility Scripts

**Problem**: `check_circular_imports.py` in root, unclear purpose

**Options**:
1. **Move to scripts/**: If useful for development
2. **Delete**: If obsolete (circular imports already fixed per TECHNICAL_DEBT_ANALYSIS.md)
3. **Document**: Add README explaining purpose

**Effort**: 15 minutes

**Priority**: 🟢 Low

---

## Phase 7: Performance & Integration (Week 5-6) 🟡 MEDIUM

### 7.1 Integrate Delta Lake with FinanceFeedbackEngine

**Problem**: New pipeline isolated from main engine

**Solution**: Add methods to query Delta Lake from core.py

```python
# finance_feedback_engine/core.py

class FinanceFeedbackEngine:
    def __init__(self, config: dict):
        # ... existing init

        # Add Delta Lake integration
        if config.get('delta_lake', {}).get('enabled', False):
            from finance_feedback_engine.pipelines.storage import DeltaLakeManager
            self.delta_lake = DeltaLakeManager(
                storage_path=config['delta_lake']['storage_path']
            )
        else:
            self.delta_lake = None

    def get_historical_data_from_lake(
        self,
        asset_pair: str,
        timeframe: str,
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """Query historical data from Delta Lake (if enabled)."""
        if not self.delta_lake:
            raise ConfigurationError("Delta Lake not enabled")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        # Query Delta Lake
        df = self.delta_lake.read_table(
            table_name=f'raw_market_data_{timeframe}',
            filters=[
                f'asset_pair = "{asset_pair}"',
                f'timestamp >= "{start_date.isoformat()}"'
            ]
        )

        return df
```

**Effort**: 3-4 hours

**Priority**: 🟡 Medium

---

### 7.2 Add Logging Configuration Validation

**Problem**: Logs may go to console in production

**Solution**: Validate logging config on startup

```python
# finance_feedback_engine/utils/logging_config.py

def validate_logging_config(config: dict, environment: str):
    """Ensure production doesn't log to console."""
    if environment == 'production':
        handlers = config.get('logging', {}).get('handlers', {})
        if 'console' in handlers:
            raise ConfigurationError(
                "Production environment cannot use console logging. "
                "Use file or syslog handlers."
            )
```

**Effort**: 1-2 hours

**Priority**: 🟢 Low

---

### 7.3 Improve Test Isolation

**Problem**: Tests may create files in project root

**Solution**: Use tmp_path fixture consistently

```python
# tests/conftest.py

@pytest.fixture
def isolated_data_dir(tmp_path):
    """Provide isolated data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir

# Usage in tests
def test_decision_store(isolated_data_dir):
    store = DecisionStore(config={'storage_path': isolated_data_dir})
    # Test creates files in tmp_path, not project root
```

**Effort**: 2-3 hours

**Priority**: 🟡 Medium

---

### 7.4 Update Technical Debt Metrics

**Problem**: TECHNICAL_DEBT_ANALYSIS.md needs update post-cleanup

**Solution**: Re-run analysis and update document

```bash
# Re-count metrics
grep -r "except Exception" --include="*.py" | wc -l
grep -r "# TODO" --include="*.py" | wc -l
grep -r "# type: ignore" --include="*.py" | wc -l

# Update TECHNICAL_DEBT_ANALYSIS.md with new numbers
```

**Effort**: 1-2 hours

**Priority**: 🟢 Low

---

## Success Metrics

### Before Cleanup
- ✅ Bare exceptions: 130
- ✅ TODO comments: 254
- ✅ FIXME comments: 31
- ✅ Type: ignore: 325
- ✅ Noqa suppressions: 259
- ✅ Test coverage: Unknown
- ✅ Technical debt score: 210/1000

### After Cleanup (Target)
- 🎯 Bare exceptions: <50 (62% reduction)
- 🎯 TODO comments: <50 (80% reduction)
- 🎯 FIXME comments: 0 (100% resolution)
- 🎯 Type: ignore: <100 (69% reduction)
- 🎯 Noqa suppressions: <100 (61% reduction)
- 🎯 Test coverage: ≥70%
- 🎯 Technical debt score: <100/1000

---

## Timeline & Effort Estimate

| Phase | Duration | Effort (hours) | Priority |
|-------|----------|----------------|----------|
| Phase 1: Build Hygiene | Week 1 | 4-6 | 🔴 High |
| Phase 2: Error Handling | Week 1-2 | 20-30 | 🔴 High |
| Phase 3: Type Safety | Week 2-3 | 14-19 | 🟠 Medium |
| Phase 4: Code Quality | Week 3-4 | 18-24 | 🟡 Medium |
| Phase 5: Testing | Week 3-4 | 12-17 | 🔴 High |
| Phase 6: Documentation | Week 4 | 6-9 | 🟢 Low |
| Phase 7: Integration | Week 5-6 | 6-10 | 🟡 Medium |
| **Total** | **4-6 weeks** | **80-115 hours** | - |

**Parallelization**: Phases 3-6 can run in parallel (different files)

---

## Quick Wins (Do These First!)

1. ✅ Clean cache files from git (15 min)
2. ✅ Fix .gitignore (10 min)
3. ✅ Add pre-commit hooks (1 hour)
4. ✅ Remove/document check_circular_imports.py (15 min)
5. ✅ Delete stale TODO comments (2 hours)

**Total quick wins**: 4 hours → Immediate visible improvement

---

## Tracking Progress

Use the todo list in Claude Code:
```bash
# View current todos
/tasks

# Mark task complete
# (done via TodoWrite tool during work)
```

Or track in GitHub issues with labels:
- `tech-debt`: Technical debt cleanup
- `phase-1`, `phase-2`, etc.: Phase tags
- `quick-win`: Low-hanging fruit

---

## Next Steps

1. **Review this plan** with team
2. **Prioritize phases** based on business needs
3. **Assign owners** for each phase
4. **Start with Phase 1** (build hygiene - quick wins)
5. **Track progress** using todo list
6. **Celebrate wins** as metrics improve!

---

**Questions?** See individual phase sections or consult TECHNICAL_DEBT_ANALYSIS.md for detailed analysis.
