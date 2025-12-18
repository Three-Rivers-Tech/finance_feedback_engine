# TODO: Quality Assurance Implementation Checklist

This file tracks the implementation of the Quality Assurance Plan for Finance Feedback Engine 2.0, with focus on making `run-agent` bug-free and reliably runnable.

## 🚀 Immediate Actions (This Week)

### Phase 1: Assessment & Triage

- [ ] **Run Full Test Suite**
  ```bash
  pytest -v --tb=short --maxfail=0 -x > test_results_full.txt 2>&1
  pytest --junit-xml=test-results.xml --html=test-report.html
  ```
  - [ ] Analyze test_results_full.txt
  - [ ] Categorize failures by type (import, config, assertion, timeout, flaky)
  - [ ] Create test_analysis.md with findings

- [ ] **Test run-agent from Clean Environment**
  ```bash
  # Create clean venv
  python -m venv /tmp/test_ffe_clean
  source /tmp/test_ffe_clean/bin/activate
  pip install -e .
  
  # Test basic invocation
  python main.py run-agent --help
  
  # Test with config
  cp config/config.yaml.example config/config.test.yaml
  python main.py run-agent --yes --autonomous
  ```
  - [ ] Document any failures
  - [ ] Identify missing dependencies
  - [ ] Create docs/RUN_AGENT_EXECUTION_PATHS.md

- [ ] **Generate Coverage Report for run-agent**
  ```bash
  pytest --cov=finance_feedback_engine.cli.commands.agent \
         --cov=finance_feedback_engine.agent \
         --cov-report=html \
         --cov-report=term-missing \
         tests/test_agent.py tests/test_trading_loop_agent.py tests/cli/
  ```
  - [ ] Review htmlcov/index.html
  - [ ] Identify untested code paths
  - [ ] Document coverage gaps

## 📋 Priority Fixes (P0 - Blocking run-agent)

Based on test results, prioritize these:

- [ ] **Fix Import Errors**
  - [ ] Verify all dependencies in requirements.txt
  - [ ] Check for missing optional dependencies
  - [ ] Update imports to use correct module paths

- [ ] **Fix Configuration Errors**
  - [ ] Ensure config/config.yaml has all required fields
  - [ ] Add validation for required config sections
  - [ ] Provide clear error messages for missing config

- [ ] **Fix run-agent Critical Path Failures**
  - [ ] Test autonomous mode
  - [ ] Test signal-only mode
  - [ ] Test asset-pairs override
  - [ ] Test configuration validation

## 🧪 Test Improvements

### Unit Tests to Add

- [ ] **tests/cli/test_agent_initialization.py**
  - [ ] test_initialize_agent_with_valid_config
  - [ ] test_initialize_agent_validates_notification_channels
  - [ ] test_initialize_agent_autonomous_mode
  - [ ] test_initialize_agent_signal_only_mode
  - [ ] test_initialize_agent_with_asset_pairs_override

- [ ] **tests/cli/test_agent_validation.py**
  - [ ] test_run_agent_validates_take_profit_range
  - [ ] test_run_agent_validates_stop_loss_range
  - [ ] test_run_agent_validates_asset_pairs_format
  - [ ] test_run_agent_requires_config

- [ ] **tests/cli/test_agent_configuration.py**
  - [ ] test_display_agent_configuration_summary
  - [ ] test_confirm_agent_startup_with_yes_flag
  - [ ] test_confirm_agent_startup_user_cancels

### Integration Tests to Add

- [ ] **tests/integration/test_run_agent_integration.py**
  - [ ] test_run_agent_starts_successfully
  - [ ] test_run_agent_signal_only_mode_sends_telegram
  - [ ] test_run_agent_autonomous_mode_executes_trades
  - [ ] test_run_agent_with_multiple_asset_pairs
  - [ ] test_run_agent_handles_platform_errors

### Smoke Tests to Fix

- [ ] **tests/test_cli_smoke.py**
  - [ ] Un-skip test_run_agent_command_smoke
  - [ ] Add test_run_agent_with_help_flag
  - [ ] Add test_run_agent_with_autonomous_flag
  - [ ] Add test_run_agent_with_asset_pairs_flag
  - [ ] Add test_run_agent_validates_config

## 🔧 Infrastructure Improvements

### Environment Setup

- [ ] **Create scripts/setup_dev_env.sh**
  ```bash
  #!/bin/bash
  set -e
  python -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  pip install -e .
  pre-commit install
  echo "✅ Development environment ready!"
  ```

- [ ] **Pin Dependencies**
  - [ ] Generate requirements.txt with pinned versions
  - [ ] Generate requirements-dev.txt with pinned versions
  - [ ] Test installation from pinned requirements

- [ ] **Create Clean Environment Test Script**
  ```bash
  # scripts/test_clean_install.sh
  #!/bin/bash
  set -e
  TEMP_DIR=$(mktemp -d)
  cd $TEMP_DIR
  git clone <repo-url> .
  ./scripts/setup_dev_env.sh
  pytest -m "not slow" -v
  echo "✅ Clean install test passed!"
  ```

### VS Code Integration

- [ ] **Create .vscode/settings.json**
  - [ ] Configure pytest
  - [ ] Configure linting
  - [ ] Configure formatting
  - [ ] Enable auto-test discovery

- [ ] **Create .vscode/launch.json**
  - [ ] Add "Python: Current Test File" configuration
  - [ ] Add "Python: run-agent" configuration
  - [ ] Add "Python: Debug Test" configuration

- [ ] **Create .vscode/tasks.json**
  - [ ] Add "Run All Tests" task
  - [ ] Add "Run Fast Tests" task
  - [ ] Add "Run Coverage" task
  - [ ] Add "Lint Code" task

## 📚 Documentation

### Developer Documentation

- [ ] **Create docs/DEVELOPMENT.md**
  - [ ] Setup instructions
  - [ ] Running tests locally
  - [ ] VS Code integration
  - [ ] Reproducing CI failures
  - [ ] Common issues and solutions

- [ ] **Create docs/TESTING_GUIDE.md**
  - [ ] Test structure and naming
  - [ ] Writing unit tests
  - [ ] Writing integration tests
  - [ ] Using fixtures and mocks
  - [ ] Coverage best practices

- [ ] **Create docs/RUN_AGENT_EXECUTION_PATHS.md**
  - [ ] Document all invocation methods
  - [ ] Document required configuration
  - [ ] Document optional parameters
  - [ ] Document error scenarios

### User Documentation

- [ ] **Update README.md**
  - [ ] Add "Running Tests" section
  - [ ] Add "Development Setup" section
  - [ ] Link to DEVELOPMENT.md

- [ ] **Update CONTRIBUTING.md**
  - [ ] Add testing requirements
  - [ ] Add pre-commit hook instructions
  - [ ] Add CI/CD information

## 🔒 Commit Gates

### Pre-commit Hooks

- [ ] **Update .pre-commit-config.yaml**
  - [ ] Add fast test runner
  - [ ] Add Black formatting check
  - [ ] Add isort import sorting check
  - [ ] Add Flake8 linting
  - [ ] Add Bandit security check

- [ ] **Test Pre-commit Hooks**
  ```bash
  pre-commit run --all-files
  ```

### CI Pipeline

- [ ] **Review .github/workflows/ci-enhanced.yml**
  - [ ] Verify all required checks are present
  - [ ] Add run-agent specific job
  - [ ] Ensure coverage threshold is enforced

- [ ] **Add run-agent CI Job**
  - [ ] Create dedicated job for run-agent tests
  - [ ] Verify 85%+ coverage for run-agent
  - [ ] Test all invocation paths

- [ ] **Configure Branch Protection**
  - [ ] Require status checks to pass
  - [ ] Require branches to be up to date
  - [ ] Require review from code owners

## 🐛 Bug Fixes

### Flaky Tests

- [ ] **Identify Flaky Tests**
  ```bash
  pytest --count=10 -x tests/
  ```

- [ ] **Fix Common Flaky Patterns**
  - [ ] Replace time.sleep() with freezegun
  - [ ] Use fixed seeds for random data
  - [ ] Mock external API calls
  - [ ] Use tmp_path for file operations
  - [ ] Fix async/await issues

### Known Issues

- [ ] **Logging Errors**
  - [ ] Fix "I/O operation on closed file" error
  - [ ] Fix unclosed client session warnings
  - [ ] Ensure proper cleanup in tests

- [ ] **Test Isolation**
  - [ ] Ensure tests don't share state
  - [ ] Use fixtures for setup/teardown
  - [ ] Clean up temporary files

## 📊 Metrics & Monitoring

### Coverage Tracking

- [ ] **Set Coverage Targets**
  - [ ] Overall: 70%+
  - [ ] run-agent: 85%+
  - [ ] New code: 80%+

- [ ] **Monitor Coverage Trends**
  - [ ] Upload coverage to Codecov
  - [ ] Add coverage badge to README
  - [ ] Review coverage in PRs

### Test Performance

- [ ] **Measure Test Execution Time**
  ```bash
  pytest --durations=10
  ```

- [ ] **Optimize Slow Tests**
  - [ ] Mark slow tests with @pytest.mark.slow
  - [ ] Use mocks to speed up tests
  - [ ] Parallelize tests with pytest-xdist

## 🎯 Success Criteria

### Phase 1 Complete When:
- [ ] All tests categorized and prioritized
- [ ] run-agent execution paths documented
- [ ] Coverage report generated and analyzed

### Phase 2 Complete When:
- [ ] All P0 tests passing
- [ ] No flaky tests
- [ ] Dependencies pinned
- [ ] Clean environment setup works

### Phase 3 Complete When:
- [ ] 20+ unit tests for run-agent
- [ ] 10+ integration tests for run-agent
- [ ] 5+ smoke tests for run-agent
- [ ] 85%+ coverage for run-agent

### Phase 4 Complete When:
- [ ] Pre-commit hooks configured and working
- [ ] CI pipeline enforces all checks
- [ ] Branch protection configured
- [ ] All checks passing on main branch

### Phase 5 Complete When:
- [ ] DEVELOPMENT.md created
- [ ] TESTING_GUIDE.md created
- [ ] VS Code integration documented
- [ ] New developer can set up in <10 minutes

## 📅 Timeline

- **Week 1**: Phase 1 (Assessment & Triage)
- **Week 2**: Phase 2 (Quick Wins & Stabilization)
- **Week 3**: Phase 3 (Strengthen run-agent Tests)
- **Week 4**: Phase 4 (Establish Commit Gates)
- **Week 5**: Phase 5 (Documentation & Developer Experience)

## 🚦 Current Status

**Last Updated**: [Date]

**Overall Progress**: 0/100+ tasks complete

**Blockers**: 
- Need to run full test suite to identify failures
- Need to test run-agent from clean environment

**Next Steps**:
1. Run full test suite and analyze results
2. Test run-agent from clean environment
3. Generate coverage report for run-agent
4. Create test_analysis.md with findings
