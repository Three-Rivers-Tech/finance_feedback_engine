# Git Hooks Quick Reference

## 🚀 Quick Start

```bash
# One-line setup (recommended)
./scripts/setup-hooks.sh
```

That's it! Hooks will run automatically on `git commit`.

---

## 📋 Common Commands

```bash
# Run all hooks manually
pre-commit run --all-files

# Run specific hook
pre-commit run black
pre-commit run prevent-secrets
pre-commit run pytest-fast

# Update hook versions
pre-commit autoupdate

# Bypass hooks (emergency only!)
git commit --no-verify
```

---

## ⚙️ Configuration Variants

### Default (Recommended)
```bash
./scripts/setup-hooks.sh
```
- ⚡ Fast (~30-60s)
- ✅ All essential checks
- 🎯 Best for daily work

### Enhanced (Thorough)
```bash
./scripts/setup-hooks.sh --config enhanced
```
- 🐢 Slower (~2-5 min)
- ✅✅ All checks + extras
- 🎯 Best for releases

### Progressive (Gradual)
```bash
./scripts/setup-hooks.sh --config progressive
```
- ⚡⚡ Very fast (~10-20s)
- ~ Relaxed rules
- 🎯 Best for learning

---

## 🔍 What Gets Checked?

### Every Commit Checks:
- ✅ **Code Formatting** (black, isort)
- ✅ **Linting** (flake8)
- ✅ **Type Checking** (mypy)
- ✅ **Security** (bandit)
- ✅ **Secret Detection** (prevent-secrets)
- ✅ **Test Coverage** (≥70% required)

---

## 🔐 Secret Detection

### ❌ Blocked Patterns:
- API keys
- Passwords & tokens
- Private keys
- Database credentials

### ✅ Safe Patterns:
- `${ENV_VAR}` references
- `YOUR_API_KEY` placeholders
- `test`, `demo`, `example` values

### If Blocked:
1. Remove hardcoded secret
2. Use environment variable
3. Store in `config/config.local.yaml` (git-ignored)

---

## 🐛 Troubleshooting

### Hooks Running Slow?
```bash
# Use faster config
./scripts/setup-hooks.sh --config progressive

# Or skip slow hooks
SKIP=pytest-fast git commit
```

### Hook Fails?
```bash
# See detailed error
pre-commit run --all-files --verbose

# Fix issues, then retry
git add -u
git commit
```

### Coverage Below 70%?
```bash
# Check coverage
pytest --cov=finance_feedback_engine --cov-report=html

# Add tests or adjust threshold in .pre-commit-config.yaml
```

### False Positive Secret Detection?
See `.pre-commit-hooks/README.md` for patterns and exceptions.

---

## 📚 Full Documentation

- **Detailed Guide**: [docs/PRE_COMMIT_GUIDE.md](PRE_COMMIT_GUIDE.md)
- **Setup Summary**: [docs/GIT_HOOKS_CLEANUP_SUMMARY.md](GIT_HOOKS_CLEANUP_SUMMARY.md)
- **Hook Scripts**: [.pre-commit-hooks/README.md](../.pre-commit-hooks/README.md)
- **Migration**: [.githooks/README.md](../.githooks/README.md)
- **Contributing**: [docs/research/CONTRIBUTING.md](research/CONTRIBUTING.md)

---

## 🆘 Need Help?

1. Check documentation above
2. Run `./scripts/setup-hooks.sh --help`
3. Open an issue on GitHub
4. Ask in team chat

---

**Remember:** Hooks are here to help! They catch issues early before code review. 🎯
