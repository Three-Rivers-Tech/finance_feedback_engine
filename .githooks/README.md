# Git Hooks Directory (DEPRECATED)

⚠️ **This directory is deprecated and will be removed in a future version.**

## Migration Notice

The custom git hooks previously stored here have been **integrated into the pre-commit framework**.

### Why This Change?

1. **Standardization**: Pre-commit is an industry-standard tool with better integration
2. **Maintainability**: Centralized configuration in `.pre-commit-config.yaml`
3. **Extensibility**: Easy to add new hooks from the pre-commit ecosystem
4. **CI/CD Integration**: Pre-commit works seamlessly in pipelines

### What Was Migrated?

- **Coverage enforcement** → Now part of `pytest-fast` hook in `.pre-commit-config.yaml`
- **Secret detection** → Integrated as `prevent-secrets` hook in `.pre-commit-config.yaml`

## How to Use Pre-commit Hooks

### Installation (One-time setup)

```bash
# Install pre-commit tool
pip install pre-commit

# Install the hooks
pre-commit install
```

### Usage

Hooks run automatically on `git commit`. To run manually:

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run specific hook
pre-commit run pytest-fast
pre-commit run prevent-secrets
```

### Bypassing Hooks (Not Recommended)

In emergencies only:
```bash
git commit --no-verify
```

## Configuration Files

- **`.pre-commit-config.yaml`** - Default configuration (recommended)
- **`.pre-commit-config-enhanced.yaml`** - Extended checks for thorough validation
- **`.pre-commit-config-progressive.yaml`** - Gradual adoption for legacy projects

See the root-level `CONTRIBUTING.md` or `docs/DEVELOPMENT.md` for more details.

## Support

For issues or questions, please refer to:
- Pre-commit documentation: https://pre-commit.com/
- Project documentation: `docs/`
- Open an issue on GitHub
