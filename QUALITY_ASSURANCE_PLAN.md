# Quality Assurance & Testing Plan for Finance Feedback Engine 2.0

## Executive Summary

This document provides an **incremental, execution-ready plan** to assess project completeness and stability, with `run-agent` as the absolutely core and critical component. The plan focuses on making `run-agent` bug-free, reliably runnable from clean environments, and validated by automated tests, while establishing robust commit gates to prevent regressions.

**Status**: Project has 1050+ tests, comprehensive CI/CD pipeline, but needs systematic triage and strengthening around `run-agent`.

---

## Current State Assessment

### ✅ What's Working
- **Test Infrastructure**: pytest 9.0.1 installed, 1050+ tests collected
- **CI/CD Pipeline**: Comprehensive `.github/workflows/ci-enhanced.yml` with:
  - Code quality checks (Black, isort, Flake8, Ruff, mypy)
  - Security scanning (Bandit, Safety, pip-audit)
  - Multi-version testing (Python 3.10-3.13)
  - Coverage reporting (70% threshold)
  - Docker image builds
  - Documentation validation
- **Pre-commit Hooks**: Testing gate configured in `.pre-commit-config.yaml`
- **Project Structure**: Well-organized with modular CLI commands
- **Documentation**: Extensive docs including TESTING_GATE.md

### ⚠️ Areas Needing Attention
- **Test Results**: Need to run full test suite and triage failures
- **run-agent Coverage**: Need to verify comprehensive test coverage for run-agent
- **Flaky Tests**: Need to identify and fix non-deterministic tests
- **Environment Setup**: Need to document clean environment setup process
- **Local Workflow**: Need VS Code integration documentation

---

## Phase 1: Assessment & Triage (Week 1)

### Milestone 1.1: Run Full Test Suite & Analyze Results
**Goal**: Get complete picture of test health

**Steps**:
1. Run full test suite with detailed output:
   ```bash
   pytest -v --tb=short --maxfail=0 > test_results.txt 2>&1
   ```

2. Generate test report with statistics:
   ```bash
   pytest --collect-only -q > test_inventory.txt
   pytest -v --tb=line --junit-xml=test-results.xml
   ```

3. Analyze failures by category:
   - Import errors (missing dependencies)
   - Configuration errors (missing config files)
   - Assertion failures (logic bugs)
   - Timeout errors (slow/hanging tests)
   - Flaky tests (non-deterministic)

**Acceptance Criteria**:
- [ ] Complete test results documented
- [ ] Failures categorized by root cause
- [ ] Priority list created (P0: blocks run-agent, P1: critical, P2: important, P3: nice-to-have)

**Verification**: `test_results.txt` and `test_analysis.md` created

---

### Milestone 1.2: Identify run-agent Execution Paths
**Goal**: Map all ways run-agent can be invoked and verify they work

**Steps**:
1. Document all run-agent entry points:
   - `python main.py run-agent` (standard)
   - `python main.py run-agent --autonomous` (autonomous mode)
   - `python main.py run-agent --asset-pairs "BTCUSD,ETHUSD"` (with overrides)
   - `python main.py run-agent --setup` (with config setup)
   - `python main.py run-agent --yes` (skip confirmation)

2. Test each path from clean environment:
   ```bash
   # Create clean venv
   python -m venv test_env
   source test_env/bin/activate
   pip install -e .
   
   # Test each path
   python main.py run-agent --help
   # ... test other paths
   ```

3. Document dependencies for each path:
   - Required config files
   - Required environment variables
   - Required external services (optional vs required)

**Acceptance Criteria**:
- [ ] All run-agent invocation paths documented
- [ ] Clean environment setup script created
- [ ] Dependency matrix documented

**Verification**: `docs/RUN_AGENT_EXECUTION_PATHS.md` created

---

### Milestone 1.3: Assess Test Coverage for run-agent
**Goal**: Ensure run-agent has comprehensive test coverage

**Steps**:
1. Generate coverage report for run-agent module:
   ```bash
   pytest --cov=finance_feedback_engine.cli.commands.agent \
          --cov=finance_feedback_engine.agent \
          --cov-report=html \
          --cov-report=term-missing \
          tests/test_agent.py tests/test_trading_loop_agent.py tests/cli/
   ```

2. Identify untested code paths:
   - Error handling branches
   - Edge cases (empty config, invalid inputs)
   - Signal-only mode vs autonomous mode
   - Notification channel validation

3. Review existing tests:
   - `tests/test_agent.py` - agent state transitions
   - `tests/test_trading_loop_agent.py` - trading loop logic
   - `tests/cli/test_agent_signal_only_validation.py` - signal-only mode
   - `tests/test_cli_smoke.py` - smoke tests (currently skipped)

**Acceptance Criteria**:
- [ ] Coverage report generated for run-agent
- [ ] Gaps identified and prioritized
- [ ] Target coverage: 85%+ for run-agent critical paths

**Verification**: `htmlcov/index.html` shows run-agent coverage

---

## Phase 2: Quick Wins & Stabilization (Week 2)

### Milestone 2.1: Fix P0 Failures (Blocking run-agent)
**Goal**: Make run-agent reliably executable

**Steps**:
1. Triage P0 failures from Phase 1.1
2. Fix in order of impact:
   - Import errors (missing dependencies)
   - Configuration validation errors
   - Critical path assertion failures

3. For each fix:
   - Write/update test to prevent regression
   - Verify fix doesn't break other tests
   - Document in CHANGELOG.md

**Acceptance Criteria**:
- [ ] All P0 tests passing
- [ ] run-agent executable from clean environment
- [ ] No regressions introduced

**Verification**: `pytest -k "run_agent" -v` passes 100%

---

### Milestone 2.2: Fix Flaky Tests
**Goal**: Make tests deterministic and reliable

**Steps**:
1. Identify flaky tests:
   ```bash
   # Run tests multiple times to find flakes
   pytest --count=10 -x tests/
   ```

2. Common flaky test patterns to fix:
   - **Timing issues**: Use `freezegun` for time-dependent tests
   - **Random data**: Use fixed seeds or deterministic fixtures
   - **External dependencies**: Mock API calls, use fixtures
   - **File system state**: Use `tmp_path` fixture, clean up properly
   - **Async issues**: Proper async/await, use `pytest-asyncio`

3. Example fixes:
   ```python
   # Before (flaky)
   def test_timeout():
       time.sleep(1)
       assert check_condition()
   
   # After (deterministic)
   @pytest.mark.freeze_time("2024-01-01 12:00:00")
   def test_timeout(freezer):
       freezer.tick(delta=timedelta(seconds=1))
       assert check_condition()
   ```

**Acceptance Criteria**:
- [ ] All tests pass 10 consecutive runs
- [ ] No timing-dependent failures
- [ ] All external dependencies mocked

**Verification**: `pytest --count=10 tests/` passes 100%

---

### Milestone 2.3: Pin Environment Dependencies
**Goal**: Ensure reproducible test environment

**Steps**:
1. Generate locked requirements:
   ```bash
   pip-compile requirements.in -o requirements.txt
   pip-compile requirements-dev.in -o requirements-dev.txt
   ```

2. Document Python version requirements:
   - Update `.python-version` file
   - Update CI matrix in `.github/workflows/ci-enhanced.yml`
   - Document in README.md

3. Create environment setup script:
   ```bash
   # scripts/setup_dev_env.sh
   #!/bin/bash
   python -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   pre-commit install
   ```

**Acceptance Criteria**:
- [ ] requirements.txt pinned with hashes
- [ ] Setup script works on clean system
- [ ] CI uses same pinned versions

**Verification**: Fresh clone + setup script = passing tests

---

## Phase 3: Strengthen run-agent Tests (Week 3)

### Milestone 3.1: Add Unit Tests for run-agent Components
**Goal**: Test individual run-agent functions in isolation

**Steps**:
1. Create unit tests for `_initialize_agent()`:
   ```python
   # tests/cli/test_agent_initialization.py
   def test_initialize_agent_with_valid_config():
       """Test agent initialization with valid configuration."""
       config = {...}
       engine = Mock()
       agent = _initialize_agent(config, engine, 0.05, 0.02, False)
       assert agent is not None
       assert agent.config.autonomous.enabled == False
   
   def test_initialize_agent_validates_notification_channels():
       """Test that signal-only mode requires notification channels."""
       config = {"agent": {"autonomous": {"enabled": False}}, "telegram": {"enabled": False}}
       with pytest.raises(click.ClickException, match="notification channels"):
           _initialize_agent(config, Mock(), 0.05, 0.02, False)
   ```

2. Create unit tests for configuration validation:
   ```python
   def test_run_agent_validates_take_profit_range():
       """Test that take-profit is validated."""
       runner = CliRunner()
       result = runner.invoke(run_agent, ["--take-profit", "150"])
       assert result.exit_code != 0
       assert "Invalid take-profit" in result.output
   ```

3. Create unit tests for asset pair parsing:
   ```python
   def test_run_agent_parses_asset_pairs():
       """Test asset pair parsing and standardization."""
       # Test various formats: BTCUSD, btc-usd, BTC_USD, etc.
   ```

**Acceptance Criteria**:
- [ ] 20+ unit tests for run-agent components
- [ ] All edge cases covered
- [ ] Tests run in <1 second each

**Verification**: `pytest tests/cli/test_agent_*.py -v` passes

---

### Milestone 3.2: Add Integration Tests for run-agent
**Goal**: Test run-agent with real components (but mocked external services)

**Steps**:
1. Create integration test for full run-agent startup:
   ```python
   # tests/integration/test_run_agent_integration.py
   @pytest.mark.integration
   def test_run_agent_starts_successfully(mock_config, mock_platform):
       """Test that run-agent starts and initializes all components."""
       runner = CliRunner()
       with patch('finance_feedback_engine.cli.commands.agent.FinanceFeedbackEngine') as mock_ffe:
           mock_ffe.return_value.trading_platform = mock_platform
           result = runner.invoke(run_agent, ['--yes', '--autonomous'], 
                                  obj={'config': mock_config})
           assert result.exit_code == 0
           # Verify components initialized
           assert mock_ffe.called
   ```

2. Create integration test for signal-only mode:
   ```python
   @pytest.mark.integration
   def test_run_agent_signal_only_mode_sends_telegram(mock_config, mock_telegram):
       """Test that signal-only mode sends signals via Telegram."""
       # Configure signal-only mode
       # Run agent
       # Verify Telegram notification sent
   ```

3. Create integration test for autonomous mode:
   ```python
   @pytest.mark.integration
   def test_run_agent_autonomous_mode_executes_trades(mock_config, mock_platform):
       """Test that autonomous mode executes trades without approval."""
       # Configure autonomous mode
       # Run agent
       # Verify trade executed on platform
   ```

**Acceptance Criteria**:
- [ ] 10+ integration tests for run-agent
- [ ] All major workflows covered
- [ ] Tests use realistic mocks

**Verification**: `pytest -m integration tests/integration/test_run_agent_*.py -v` passes

---

### Milestone 3.3: Add Smoke Tests for run-agent
**Goal**: Quick sanity checks that run-agent doesn't crash

**Steps**:
1. Un-skip existing smoke test in `tests/test_cli_smoke.py`:
   ```python
   def test_run_agent_command_smoke(self):
       """Smoke test: run-agent command doesn't crash."""
       result = self.runner.invoke(
           run_agent,
           ['--help'],
           catch_exceptions=True,
       )
       assert result.exit_code == 0
       assert 'run-agent' in result.output.lower()
   ```

2. Add smoke tests for each run-agent flag:
   ```python
   def test_run_agent_with_autonomous_flag():
       """Smoke test: --autonomous flag accepted."""
       result = runner.invoke(run_agent, ['--autonomous', '--help'])
       assert result.exit_code == 0
   
   def test_run_agent_with_asset_pairs_flag():
       """Smoke test: --asset-pairs flag accepted."""
       result = runner.invoke(run_agent, ['--asset-pairs', 'BTCUSD', '--help'])
       assert result.exit_code == 0
   ```

3. Add smoke test for config validation:
   ```python
   def test_run_agent_validates_config():
       """Smoke test: Invalid config is rejected."""
       result = runner.invoke(run_agent, ['--yes'], obj={'config': {}})
       assert result.exit_code != 0
   ```

**Acceptance Criteria**:
- [ ] 5+ smoke tests for run-agent
- [ ] All tests run in <5 seconds total
- [ ] Tests catch basic regressions

**Verification**: `pytest tests/test_cli_smoke.py::TestCLISmoke::test_run_agent* -v` passes

---

## Phase 4: Establish Commit Gates (Week 4)

### Milestone 4.1: Define Required Checks
**Goal**: Establish what must pass before code can be merged

**Required Checks**:
1. **Tests**: All tests must pass (except marked as `xfail`)
   - Unit tests: `pytest -m "unit and not slow"`
   - Integration tests: `pytest -m "integration and not slow"`
   - run-agent tests: `pytest -k "run_agent"`

2. **Coverage**: Minimum 70% overall, 85% for run-agent
   - `pytest --cov=finance_feedback_engine --cov-report=term-missing --cov-fail-under=70`

3. **Linting**: No linting errors
   - Black: `black --check .`
   - isort: `isort --check-only .`
   - Flake8: `flake8 .`
   - Ruff: `ruff check .`

4. **Type Checking**: No critical type errors (advisory for now)
   - mypy: `mypy finance_feedback_engine/ --show-error-codes`

5. **Security**: No high-severity vulnerabilities
   - Bandit: `bandit -r finance_feedback_engine/`
   - Safety: `safety check`

**Acceptance Criteria**:
- [ ] All checks documented in CONTRIBUTING.md
- [ ] CI enforces all checks
- [ ] Pre-commit hooks run subset of checks

**Verification**: CI pipeline passes on main branch

---

### Milestone 4.2: Configure Pre-commit Hooks
**Goal**: Catch issues before commit

**Steps**:
1. Update `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: local
       hooks:
         # Fast checks (run on every commit)
         - id: run-fast-tests
           name: Run fast tests
           entry: bash -c 'pytest -m "not slow" -x --tb=short'
           language: system
           pass_filenames: false
           verbose: true
         
         # Format checks
         - id: black
           name: Black formatting
           entry: black --check
           language: system
           types: [python]
         
         - id: isort
           name: isort import sorting
           entry: isort --check-only
           language: system
           types: [python]
         
         # Linting
         - id: flake8
           name: Flake8 linting
           entry: flake8
           language: system
           types: [python]
         
         # Security
         - id: bandit
           name: Bandit security check
           entry: bandit -r finance_feedback_engine/
           language: system
           pass_filenames: false
   ```

2. Document bypass procedure in CONTRIBUTING.md:
   ```markdown
   ## Bypassing Pre-commit Hooks
   
   Only bypass hooks for documentation-only changes:
   ```bash
   git commit --no-verify -m "docs: update README"
   ```
   
   **Never bypass hooks for code changes.**
   ```

3. Test pre-commit hooks:
   ```bash
   pre-commit run --all-files
   ```

**Acceptance Criteria**:
- [ ] Pre-commit hooks configured
- [ ] Hooks run in <30 seconds
- [ ] Bypass procedure documented

**Verification**: `pre-commit run --all-files` passes

---

### Milestone 4.3: Update CI Pipeline
**Goal**: Ensure CI catches all issues before merge

**Steps**:
1. Review `.github/workflows/ci-enhanced.yml` and ensure:
   - All required checks are enforced
   - run-agent tests are explicitly run
   - Coverage threshold is enforced
   - Branch protection requires all checks to pass

2. Add run-agent specific CI job:
   ```yaml
   run-agent-tests:
     name: run-agent Critical Tests
     runs-on: ubuntu-latest
     steps:
       - name: Checkout code
         uses: actions/checkout@v4
       
       - name: Set up Python
         uses: actions/setup-python@v5
         with:
           python-version: '3.11'
       
       - name: Install dependencies
         run: |
           pip install -r requirements.txt
           pip install -r requirements-dev.txt
           pip install -e .
       
       - name: Run run-agent tests
         run: |
           pytest -k "run_agent" -v --tb=short
           pytest tests/test_agent.py -v --tb=short
           pytest tests/test_trading_loop_agent.py -v --tb=short
           pytest tests/cli/test_agent_*.py -v --tb=short
       
       - name: Verify run-agent coverage
         run: |
           pytest --cov=finance_feedback_engine.cli.commands.agent \
                  --cov=finance_feedback_engine.agent \
                  --cov-report=term-missing \
                  --cov-fail-under=85 \
                  -k "run_agent or agent"
   ```

3. Configure branch protection rules:
   - Require status checks to pass before merging
   - Require branches to be up to date before merging
   - Require review from code owners

**Acceptance Criteria**:
- [ ] CI runs all required checks
- [ ] run-agent tests explicitly verified
- [ ] Branch protection configured

**Verification**: PR cannot be merged without passing checks

---

## Phase 5: Documentation & Developer Experience (Week 5)

### Milestone 5.1: Document Local Development Workflow
**Goal**: Make it easy for developers to run tests locally

**Steps**:
1. Create `docs/DEVELOPMENT.md`:
   ```markdown
   # Development Guide
   
   ## Setup
   
   1. Clone repository:
      ```bash
      git clone https://github.com/your-org/finance_feedback_engine-2.0.git
      cd finance_feedback_engine-2.0
      ```
   
   2. Run setup script:
      ```bash
      ./scripts/setup_dev_env.sh
      ```
   
   3. Verify setup:
      ```bash
      pytest --version
      python main.py --help
      ```
   
   ## Running Tests
   
   ### All Tests
   ```bash
   pytest
   ```
   
   ### Fast Tests Only
   ```bash
   pytest -m "not slow"
   ```
   
   ### Specific Module
   ```bash
   pytest tests/test_agent.py -v
   ```
   
   ### With Coverage
   ```bash
   pytest --cov=finance_feedback_engine --cov-report=html
   open htmlcov/index.html
   ```
   
   ### run-agent Tests
   ```bash
   pytest -k "run_agent" -v
   ```
   
   ## VS Code Integration
   
   ### Test Explorer
   1. Install Python extension
   2. Open Command Palette (Cmd+Shift+P)
   3. Select "Python: Configure Tests"
   4. Choose "pytest"
   5. Tests appear in Test Explorer sidebar
   
   ### Running Tests in VS Code
   - Click play button next to test in Test Explorer
   - Right-click test file → "Run Python Tests"
   - Use keyboard shortcut: Cmd+; Cmd+A (run all)
   
   ### Debugging Tests
   1. Set breakpoint in test
   2. Right-click test → "Debug Test"
   3. Use Debug Console to inspect variables
   
   ### Coverage in VS Code
   1. Install "Coverage Gutters" extension
   2. Run tests with coverage: `pytest --cov`
   3. Click "Watch" in status bar
   4. Coverage indicators appear in gutter
   
   ## Reproducing CI Failures Locally
   
   ### Run Same Commands as CI
   ```bash
   # Linting (same as CI)
   black --check .
   isort --check-only .
   flake8 .
   ruff check .
   
   # Tests (same as CI)
   pytest -m "not slow" -v
   
   # Coverage (same as CI)
   pytest --cov=finance_feedback_engine --cov-report=term-missing --cov-fail-under=70
   ```
   
   ### Use Docker (exact CI environment)
   ```bash
   docker build -f Dockerfile.ci -t ffe-ci .
   docker run -it ffe-ci pytest
   ```
   
   ## Common Issues
   
   ### Tests Fail with Import Errors
   - Ensure you installed in editable mode: `pip install -e .`
   - Check PYTHONPATH: `echo $PYTHONPATH`
   
   ### Tests Fail with Config Errors
   - Copy example config: `cp config/config.yaml.example config/config.yaml`
   - Set required env vars: `export ALPHA_VANTAGE_API_KEY=test`
   
   ### Tests Hang
   - Use timeout: `pytest --timeout=30`
   - Check for infinite loops or missing mocks
   ```

2. Create VS Code settings:
   ```json
   // .vscode/settings.json
   {
     "python.testing.pytestEnabled": true,
     "python.testing.unittestEnabled": false,
     "python.testing.pytestArgs": [
       "tests",
       "-v",
       "--tb=short"
     ],
     "python.linting.enabled": true,
     "python.linting.flake8Enabled": true,
     "python.formatting.provider": "black",
     "editor.formatOnSave": true,
     "python.testing.autoTestDiscoverOnSaveEnabled": true
   }
   ```

3. Create launch configurations:
   ```json
   // .vscode/launch.json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "Python: Current Test File",
         "type": "python",
         "request": "launch",
         "module": "pytest",
         "args": [
           "${file}",
           "-v",
           "--tb=short"
         ],
         "console": "integratedTerminal"
       },
       {
         "name": "Python: run-agent",
         "type": "python",
         "request": "launch",
         "program": "${workspaceFolder}/main.py",
         "args": [
           "run-agent",
           "--help"
         ],
         "console": "integratedTerminal"
       }
     ]
   }
   ```

**Acceptance Criteria**:
- [ ] DEVELOPMENT.md created
- [ ] VS Code settings configured
- [ ] Launch configurations created
- [ ] Common issues documented

**Verification**: New developer can set up and run tests in <10 minutes

---

### Milestone 5.2: Create Test Writing Guide
**Goal**: Help developers write good tests

**Steps**:
1. Create `docs/TESTING_GUIDE.md`:
   ```markdown
   # Testing Guide
   
   ## Test Structure
   
   ### Naming Conventions
   - Test files: `test_<module>.py`
   - Test functions: `test_<what_it_tests>()`
   - Test classes: `Test<Feature>`
   
   ### Organization
   ```
   tests/
     ├── unit/              # Fast, isolated tests
     ├── integration/       # Tests with multiple components
     ├── cli/              # CLI command tests
     └── conftest.py       # Shared fixtures
   ```
   
   ## Writing Good Tests
   
   ### Unit Tests
   ```python
   def test_function_with_valid_input():
       """Test that function works with valid input."""
       result = my_function("valid")
       assert result == expected
   
   def test_function_with_invalid_input():
       """Test that function raises error with invalid input."""
       with pytest.raises(ValueError, match="invalid"):
           my_function("invalid")
   ```
   
   ### Integration Tests
   ```python
   @pytest.mark.integration
   def test_end_to_end_workflow(mock_platform):
       """Test complete workflow from input to output."""
       # Setup
       engine = FinanceFeedbackEngine(config)
       
       # Execute
       result = engine.run_analysis("BTCUSD")
       
       # Verify
       assert result.success
       assert mock_platform.get_price.called
   ```
   
   ### Async Tests
   ```python
   @pytest.mark.asyncio
   async def test_async_function():
       """Test async function."""
       result = await async_function()
       assert result is not None
   ```
   
   ## Fixtures
   
   ### Using Fixtures
   ```python
   @pytest.fixture
   def mock_config():
       """Provide mock configuration."""
       return {
           "trading_platform": "mock",
           "agent": {"autonomous": {"enabled": True}}
       }
   
   def test_with_fixture(mock_config):
       """Test using fixture."""
       engine = FinanceFeedbackEngine(mock_config)
       assert engine.config == mock_config
   ```
   
   ### Fixture Scopes
   - `function`: New instance per test (default)
   - `class`: Shared within test class
   - `module`: Shared within test file
   - `session`: Shared across all tests
   
   ## Mocking
   
   ### Mock External Services
   ```python
   @patch('finance_feedback_engine.data_providers.alpha_vantage.AlphaVantageProvider')
   def test_with_mocked_api(mock_provider):
       """Test with mocked API."""
       mock_provider.return_value.get_price.return_value = 50000
       result = get_current_price("BTCUSD")
       assert result == 50000
   ```
   
   ### Mock Time
   ```python
   @pytest.mark.freeze_time("2024-01-01 12:00:00")
   def test_time_dependent(freezer):
       """Test time-dependent logic."""
       assert datetime.now() == datetime(2024, 1, 1, 12, 0, 0)
       freezer.tick(delta=timedelta(hours=1))
       assert datetime.now() == datetime(2024, 1, 1, 13, 0, 0)
   ```
   
   ## Test Markers
   
   ### Using Markers
   ```python
   @pytest.mark.slow
   def test_slow_operation():
       """Test that takes >1 second."""
       time.sleep(2)
       assert True
   
   @pytest.mark.integration
   def test_integration():
       """Integration test."""
       pass
   
   @pytest.mark.skip(reason="Not implemented yet")
   def test_future_feature():
       """Test for future feature."""
       pass
   ```
   
   ### Running Specific Markers
   ```bash
   pytest -m "not slow"        # Skip slow tests
   pytest -m "integration"     # Only integration tests
   pytest -m "unit and not slow"  # Fast unit tests
   ```
   
   ## Coverage
   
   ### Measuring Coverage
   ```bash
   pytest --cov=finance_feedback_engine --cov-report=html
   ```
   
   ### Improving Coverage
   1. Identify uncovered lines in `htmlcov/index.html`
   2. Write tests for uncovered code
   3. Focus on critical paths first
   
   ### Coverage Goals
   - Overall: 70%+
   - run-agent: 85%+
   - New code: 80%+
   
   ## Best Practices
   
   1. **Test One Thing**: Each test should verify one behavior
   2. **Use Descriptive Names**: Test name should describe what it tests
   3. **Arrange-Act-Assert**: Structure tests clearly
   4. **Don't Test Implementation**: Test behavior, not internals
   5. **Keep Tests Fast**: Use mocks, avoid I/O
   6. **Make Tests Deterministic**: No random data, no timing dependencies
   7. **Clean Up**: Use fixtures, context managers, tmp_path
   8. **Document Complex Tests**: Add docstrings explaining why
   ```

**Acceptance Criteria**:
- [ ] TESTING_GUIDE.md created
- [ ] Examples for all test types
- [ ] Best practices documented

**Verification**: New developer can write good tests following guide

---

### Milestone 5.3: Document CI Failure Reproduction
**Goal**: Make it easy to reproduce CI failures locally

**Steps**:
1. Add section to DEVELOPMENT.md:
   ```markdown
   ## Reproducing CI Failures
   
   ### Step 1: Identify Failing Job
   1. Go to GitHub Actions tab
   2. Click on failed workflow run
   3. Click on failed job (e.g., "Test (Python 3.11)")
   4. Note the failing command
   
   ### Step 2: Run Same Command Locally
   ```bash
   # Example: If CI failed on "pytest -m 'not slow' -v"
   pytest -m "not slow" -v
   ```
   
   ### Step 3: Use Same Python Version
   ```bash
   # If CI uses Python 3.11
   pyenv install 3.11
   pyenv local 3.11
   python --version  # Should show 3.11.x
   ```
   
   ### Step 4: Use Same Dependencies
   ```bash
   # CI uses pinned requirements
   pip install -r requirements.txt -r requirements-dev.txt
   pip list  # Compare with CI logs
   ```
   
   ### Step 5: Use Docker (Exact CI Environment)
   ```bash
   # Build CI image
   docker build -f Dockerfile.ci -t ffe-ci .
   
   # Run tests in container
   docker run -it ffe-ci pytest -m "not slow" -v
   
   # Interactive debugging
   docker run -it ffe-ci bash
   # Inside container:
   pytest tests/test_specific.py -v
   ```
   
   ### Common CI-Only Failures
   
   #### Timing Issues
   - CI may be slower than local machine
   - Solution: Increase timeouts, use freezegun
   
   #### Missing Environment Variables
   - CI may have different env vars
   - Solution: Check workflow YAML for env vars
   
   #### File System Differences
   - CI uses Linux, you may use macOS/Windows
   - Solution
