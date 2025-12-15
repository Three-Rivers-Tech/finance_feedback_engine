# Testing Gate Implementation

## Overview

This document outlines the testing gate implementation to prevent regressions in the Finance Feedback Engine repository. The testing gate ensures that all tests pass before allowing commits or merging code to the main branch.

## Components

### 1. Pre-commit Hook

The testing gate is enforced through a pre-commit hook that runs all tests before allowing a commit to proceed. This prevents faulty code from entering the repository history.

#### Configuration

The pre-commit hook is configured in `.pre-commit-config.yaml` with the following test execution hook:

```yaml
- repo: local
  hooks:
    - id: run-tests
      name: Run all tests
      entry: bash -c 'python -m pytest -m "not slow"'
      language: system
      pass_filenames: false
      verbose: true
```

#### Installation

To install the pre-commit hooks with the testing gate:

```bash
# Install all pre-commit hooks including the test runner
pip install pre-commit
pre-commit install
```

### 2. CI Pipeline

The CI pipeline is configured in `.github/workflows/ci.yml` to ensure that tests pass before code can be merged to the main branch.

The pipeline includes:
- Build checks
- Linting
- Security scanning
- Test execution
- Coverage reporting

## How It Works

### Before Committing

1. When you run `git commit`, the pre-commit hooks execute automatically
2. The testing gate hook runs `python -m pytest -m "not slow"`
3. If tests fail, the commit is blocked and you must fix the issues first
4. If tests pass, the commit proceeds normally

### During Pull Request

1. When a pull request is opened or updated, the CI pipeline executes
2. All tests are run in the CI environment
3. If tests fail, the CI check fails and the PR cannot be merged
4. Maintainers can only merge PRs when all checks pass

## Bypassing the Testing Gate

### Temporary Bypass (Use with Caution)

If you need to bypass the pre-commit hook temporarily (e.g., for a documentation-only change), you can use:

```bash
# Bypass all pre-commit hooks
git commit --no-verify -m "Your commit message"

# Or bypass just for this commit
SKIP=run-tests git commit -m "Your commit message"
```

⚠️ **Warning**: Bypassing the testing gate should be done only when absolutely necessary and with extreme caution.

## Requirements

### For Local Development

1. All tests must pass before committing
2. Install pre-commit hooks to enforce testing gate locally
3. Run tests manually with `pytest -m "not slow"` before committing

### For CI/CD

1. All pull requests must pass all tests in CI
2. Branch protection rules prevent merging without passing status checks
3. Code coverage must meet minimum threshold (currently 70%)

## Troubleshooting

### Tests Failing Locally

If tests fail during commit:

1. Run tests manually to see detailed output:
   ```bash
   python -m pytest -m "not slow" -v
   ```

2. Fix the failing tests before committing

3. If you need to run a specific test file:
   ```bash
   python -m pytest tests/test_specific_file.py -v
   ```

### Pre-commit Hook Issues

If the pre-commit hook fails to run properly:

1. Update pre-commit hooks:
   ```bash
   pre-commit autoupdate
   ```

2. Run all hooks manually:
   ```bash
   pre-commit run --all-files
   ```

## Best Practices

1. **Run tests frequently**: Execute tests before making commits to catch issues early
2. **Write tests for new code**: All new features and bug fixes must include appropriate tests
3. **Maintain test quality**: Ensure tests are meaningful and provide value
4. **Keep tests fast**: Use pytest markers to categorize slow tests appropriately
5. **Review test failures carefully**: Understand why tests fail before attempting fixes

## Adding New Tests

When adding new functionality, ensure appropriate tests are added:

1. Place tests in the appropriate directory under `/tests/`
2. Follow existing test patterns and naming conventions
3. Use appropriate pytest markers (e.g., `slow`, `integration`, `unit`)
4. Ensure new tests pass before committing

## Maintenance

The testing gate system requires minimal maintenance, but remember:

1. Keep test execution time reasonable by using the `not slow` marker appropriately
2. Update tests when changing functionality
3. Periodically review test coverage and quality

## Contact

If you have questions about the testing gate implementation, contact the development team or raise an issue in the repository.