# Pre-commit Configuration Guide

This project uses [pre-commit](https://pre-commit.com/) for automated code quality checks. We provide three configuration variants to suit different needs.

## Quick Start

```bash
# Install and set up hooks (uses default config)
./scripts/setup-hooks.sh

# Or manually:
pip install pre-commit
pre-commit install
```

## Configuration Variants

### 1. Default Configuration (`.pre-commit-config.yaml`)

**Recommended for:** Most developers, everyday development

**Features:**
- Black code formatting
- isort import sorting
- flake8 linting
- mypy type checking
- Bandit security scanning
- **Secret detection** (prevent-secrets hook)
- **Fast pytest** (unit tests only, 70% coverage requirement)

**Performance:** ⚡ Fast (~30-60 seconds for full check)

**When to use:**
- Daily development work
- Quick commits
- CI/CD pipelines

**Setup:**
```bash
./scripts/setup-hooks.sh --config default
# or
pre-commit install
```

---

### 2. Enhanced Configuration (`.pre-commit-config-enhanced.yaml`)

**Recommended for:** Release branches, thorough code reviews, security audits

**Features:** All default checks PLUS:
- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON/TOML/XML syntax validation
- Large file detection (2MB limit)
- Merge conflict detection
- Private key detection
- Mixed line ending fixes
- Debug statement detection
- Test naming validation
- Documentation checks (docstrings, comments)
- Advanced security scanning
- Import cycle detection
- Additional Python best practices

**Performance:** 🐢 Slower (~2-5 minutes for full check)

**When to use:**
- Before creating pull requests
- Release preparation
- Security audits
- Code quality gates

**Setup:**
```bash
./scripts/setup-hooks.sh --config enhanced
```

---

### 3. Progressive Configuration (`.pre-commit-config-progressive.yaml`)

**Recommended for:** Legacy codebases, gradual adoption, learning

**Features:** Subset of default checks with relaxed rules:
- Basic formatting (black, isort)
- Limited linting (only critical issues)
- No type checking
- No test requirements
- Warnings instead of errors

**Performance:** ⚡⚡ Very fast (~10-20 seconds)

**When to use:**
- Introducing pre-commit to an existing project
- Learning the tools
- Quick fixes without full compliance
- Temporary bypass during refactoring

**Setup:**
```bash
./scripts/setup-hooks.sh --config progressive
```

---

## Comparison Table

| Feature | Default | Enhanced | Progressive |
|---------|---------|----------|-------------|
| Code Formatting | ✓ | ✓ | ✓ |
| Linting | ✓ | ✓✓ | ~ |
| Type Checking | ✓ | ✓ | ✗ |
| Security Scanning | ✓ | ✓✓ | ~ |
| Secret Detection | ✓ | ✓ | ✗ |
| Test Coverage | ✓ (70%) | ✓ (70%) | ✗ |
| File Checks | ~ | ✓✓ | ✗ |
| Documentation | ~ | ✓✓ | ✗ |
| Performance | Fast | Slow | Very Fast |
| Strictness | Medium | High | Low |

Legend: ✓ = Included, ✓✓ = Enhanced, ~ = Basic, ✗ = Not included

---

## Usage Examples

### Run All Hooks

```bash
# On all files
pre-commit run --all-files

# On staged files only (automatic before commit)
pre-commit run
```

### Run Specific Hooks

```bash
# Run only formatting
pre-commit run black
pre-commit run isort

# Run only security checks
pre-commit run prevent-secrets
pre-commit run bandit

# Run only tests
pre-commit run pytest-fast
```

### Update Hook Versions

```bash
pre-commit autoupdate
```

### Bypass Hooks (Emergency Only)

```bash
git commit --no-verify
```

⚠️ **Warning:** Only bypass hooks if absolutely necessary. This skips all quality checks!

---

## Switching Configurations

To switch between configurations:

```bash
# Method 1: Use setup script
./scripts/setup-hooks.sh --config enhanced

# Method 2: Manual symlink
ln -sf .pre-commit-config-enhanced.yaml .pre-commit-config.yaml
pre-commit install

# Method 3: Specify directly
pre-commit run --config .pre-commit-config-enhanced.yaml --all-files
```

---

## Custom Hooks

Our custom hooks are located in `.pre-commit-hooks/`:

### `prevent-secrets`
Prevents committing secrets, API keys, and credentials.

**Allowed placeholders:**
- `YOUR_*` format (e.g., `YOUR_API_KEY`)
- `${ENV_VAR}` references
- Test values: `test`, `demo`, `example`

**Ignored files:**
- `.env.example`, `.env.template`
- `config.yaml` (base config only)
- Test/mock configs

---

## CI/CD Integration

Add to your CI pipeline:

```yaml
# GitHub Actions
- name: Run pre-commit
  run: |
    pip install pre-commit
    pre-commit run --all-files

# Or use the pre-commit action
- uses: pre-commit/action@v3.0.0
```

---

## Troubleshooting

### Hooks are slow
- Use **default** config instead of enhanced
- Run specific hooks: `pre-commit run black isort`
- Skip slow hooks: `SKIP=pytest-fast git commit`

### Hook failures
- Read the error message carefully
- Run manually to see details: `pre-commit run --all-files --verbose`
- Fix the issues or bypass with `--no-verify` (not recommended)

### Coverage failures
- Run tests locally: `pytest --cov=finance_feedback_engine`
- Check which files lack coverage: `pytest --cov=finance_feedback_engine --cov-report=html`
- Add tests or adjust threshold in config

### Secret detection false positives
- Ensure placeholders match allowed patterns
- Use `${ENV_VAR}` format for environment variables
- Add exceptions to `.pre-commit-hooks/prevent-secrets.py`

---

## Migration from `.githooks/`

The old `.githooks/` directory is **deprecated**. All functionality has been migrated to pre-commit:

| Old Hook | New Hook | Location |
|----------|----------|----------|
| `.githooks/pre-commit` (coverage) | `pytest-fast` | `.pre-commit-config.yaml` |
| `.pre-commit-hooks/prevent-secrets.py` | `prevent-secrets` | `.pre-commit-config.yaml` |

See `.githooks/README.md` for full migration details.

---

## Support

- **Pre-commit documentation**: https://pre-commit.com/
- **Project issues**: GitHub Issues
- **Questions**: See `docs/` or open a discussion

---

## Best Practices

1. **Run before committing**: Let pre-commit catch issues early
2. **Keep hooks fast**: Use default config for daily work
3. **Update regularly**: Run `pre-commit autoupdate` monthly
4. **Don't bypass unnecessarily**: Hooks are there to help you
5. **Use enhanced for PRs**: Extra checks before code review
6. **CI should match local**: Use same config in CI/CD

---

**Last Updated:** December 2025  
**Version:** 2.0  
**Maintainers:** See CODEOWNERS
