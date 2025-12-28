# Pre-commit Hooks Scripts

This directory contains custom Python scripts used by the pre-commit framework.

## Scripts

### `prevent-secrets.py`

**Purpose**: Scans staged files for potential secrets, API keys, tokens, and credentials before allowing commits.

**Features**:
- Detects various secret patterns (API keys, tokens, passwords, private keys, etc.)
- Allows safe placeholders (e.g., `YOUR_API_KEY`, `${ENV_VAR}`)
- Special check for `config.local.yaml` (should never be committed)
- Configurable ignore lists for files and directories

**Usage**: Integrated into `.pre-commit-config.yaml` as the `prevent-secrets` hook.

**Patterns Detected**:
- API keys (generic, AWS, GitHub, etc.)
- Secrets and passwords
- Tokens (Bearer, OAuth, Slack, Telegram, etc.)
- Private keys (RSA, EC, SSH, etc.)
- Database URLs with credentials
- Basic auth headers

**Safe Placeholders**:
- `YOUR_*` format (e.g., `YOUR_ALPHA_VANTAGE_API_KEY`)
- `${ENV_VAR}` or `$ENV` references
- Common test values: `test`, `demo`, `example`, `sample`

**Ignored Files**:
- `.env.example`, `.env.template`
- `config.yaml` (base config with placeholders only)
- `config.test.mock.yaml`, `config.backtest.yaml`
- Virtual environments, node_modules, caches

## Adding New Hooks

To add a new custom hook:

1. Create a Python script in this directory
2. Make it executable: `chmod +x .pre-commit-hooks/your_script.py`
3. Add it to `.pre-commit-config.yaml` under the `local` repo:

```yaml
- repo: local
  hooks:
    - id: your-hook-id
      name: Your Hook Name
      entry: python .pre-commit-hooks/your_script.py
      language: system
      pass_filenames: false
      always_run: true
      stages: [pre-commit]
```

## Testing Hooks

Test individual hooks:

```bash
# Run prevent-secrets manually
python .pre-commit-hooks/prevent-secrets.py

# Run via pre-commit
pre-commit run prevent-secrets --all-files
```

## Maintenance

- Keep scripts focused on a single responsibility
- Add comprehensive docstrings
- Use type hints for better IDE support
- Include ANSI color codes for terminal output
- Handle errors gracefully with clear messages
