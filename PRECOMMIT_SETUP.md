# Pre-Commit Hook Setup Guide

This project enforces **70% test coverage** before commits are allowed. This prevents accidentally committing untested code.

## Installation (One-time Setup)

### Option 1: Using Git Config (Recommended - Simpler)

```bash
# Configure git to use our custom hooks directory
git config core.hooksPath .githooks

# Verify it's set
git config core.hooksPath
# Should output: .githooks
```

That's it! The hook will run automatically on every `git commit`.

### Option 2: Using Pre-Commit Framework (Advanced)

If you want to use the full pre-commit framework with all linting hooks:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run all hooks manually (optional)
pre-commit run --all-files
```

This method also runs Black, isort, Flake8, and Bandit alongside the test coverage check.

## How It Works

When you run `git commit`, the hook automatically:

1. **Runs pytest** with coverage collection (`--cov=finance_feedback_engine`)
2. **Checks coverage threshold** (must be ≥ 70%)
3. **Blocks commit** if tests fail or coverage is below 70%
4. **Allows commit** only if all tests pass and coverage meets threshold

## Example

### ✅ Commit Succeeds (Coverage ≥ 70%)
```
$ git commit -m "Add new feature"
🧪 Running tests with coverage check...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ All tests passed! Coverage: 75%

[main a1b2c3d] Add new feature
 1 file changed, 10 insertions(+)
```

### ❌ Commit Fails (Coverage < 70%)
```
$ git commit -m "Add new feature"
🧪 Running tests with coverage check...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Tests failed or coverage below 70%

To skip this check (NOT RECOMMENDED), use:
  git commit --no-verify
```

## Skipping the Check (Emergency Only)

If you absolutely must commit without passing tests:

```bash
git commit --no-verify
```

⚠️ **Use sparingly!** This bypasses safety checks and should only be used for hotfixes or documentation changes.

## Coverage Threshold

- **Current threshold**: 70% (enforced in `pyproject.toml`)
- **Rationale**: See `.github/copilot-instructions.md`
- **To increase coverage**: Add tests rather than lowering the threshold

## Troubleshooting

### Hook not running?
```bash
# Verify git hooks path is set
git config core.hooksPath

# If empty, set it:
git config core.hooksPath .githooks

# Verify hook is executable
ls -la .githooks/pre-commit
# Should have 'x' permissions: -rwxr-xr-x
```

### Hook runs but seems to hang?
- Pytest may be running full test suite, which can take time
- Check test output at `/tmp/pytest_output.txt`
- Run manually: `pytest --cov=finance_feedback_engine --cov-fail-under=70`

### "Permission denied" when running hook?
```bash
chmod +x .githooks/pre-commit
```

### Disabling the hook temporarily?
```bash
# Temporarily disable
git config --local core.hooksPath /dev/null

# Re-enable when done
git config core.hooksPath .githooks
```

## Configuration

To adjust the coverage threshold, edit `.githooks/pre-commit`:

```bash
COVERAGE_THRESHOLD=70  # Change this value
```

Then rebuild coverage in `pyproject.toml` if needed (currently set to 70%).

## CI/CD Integration

The same 70% threshold is enforced in CI pipelines. Both local and remote checks must pass:

1. **Local** (pre-commit hook) ← You are here
2. **Remote** (GitHub Actions) ← Checked on push
3. **PR checks** ← Must pass before merge

## See Also

- [Pre-Commit Framework Docs](https://pre-commit.com/)
- `pyproject.toml` — Pytest configuration with coverage settings
- `.pre-commit-config.yaml` — All hooks configuration
- `.github/copilot-instructions.md` — Project standards and philosophy
