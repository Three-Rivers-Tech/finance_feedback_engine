# Config Precedence

The engine loads configuration using a tiered precedence (highest first):

1. Environment variables
2. `config/config.local.yaml` (gitignored local overrides)
3. `config/config.yaml` (base defaults)

Notes:
- Environment variables override keys from YAML files (e.g., `ALPHA_VANTAGE_API_KEY`).
- Tests should use `config/config.test.mock.yaml` to ensure deterministic behavior.
- CLI and core components deep-merge local config over base config.
