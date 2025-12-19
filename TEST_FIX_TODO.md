# Test Fix TODO Tracker

## Status: Starting Careful Test Analysis
**Date**: 2025-01-XX
**Approach**: Run tests individually to avoid IDE crashes

## Phase 1: Identify Crash-Causing Tests

### Step 1: Test Collection Analysis
- [ ] Collect all test files safely
- [ ] Identify test modules that might cause crashes
- [ ] Create isolated test runner script

### Step 2: Resource Leak Detection
- [ ] Check for unclosed sessions
- [ ] Check for file handle leaks
- [ ] Check for memory leaks

## Tests to Analyze (One by One)

### Critical Resource Tests
- [ ] tests/conftest.py - Check fixtures
- [ ] tests/test_data_providers_comprehensive.py
- [ ] tests/test_core_integration.py
- [ ] tests/test_api.py

## Progress Log

### 2024-12-19 Update

#### ✅ Good News
- **No IDE crashes detected** in priority tests
- **No resource leaks detected** in priority tests  
- **No timeout issues** in priority tests
- Tests complete quickly (~0.8s each)

#### ❌ Issues Found
- All 6 priority tests are failing (but not crashing)
- Tests affected:
  - tests/conftest.py
  - tests/test_data_providers_comprehensive.py
  - tests/test_core_integration.py
  - tests/test_api.py
  - tests/test_ensemble_error_propagation.py
  - tests/test_critical_fixes_integration.py

#### 🔍 Next Steps
1. Running verbose test output to identify failure reasons
2. Focus on fixing test failures (not crashes)
3. Once tests pass, run full suite analysis

## Safe Test Commands
```bash
# Run single test file with resource warnings
python -m pytest tests/conftest.py -v -W error::ResourceWarning --tb=short

# Run with memory profiling
python -m pytest tests/test_api.py -v --tb=short --capture=no

# Run with timeout to prevent hangs
python -m pytest tests/test_data_providers_comprehensive.py -v --timeout=10
