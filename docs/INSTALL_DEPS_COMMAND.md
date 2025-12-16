# Install Dependencies Command - Quick Reference

## Overview
The `install-deps` command helps manage project dependencies by comparing installed packages against `requirements.txt` and offering to install missing ones.

## Usage

### 1. Check Status (Interactive)
```bash
python main.py install-deps
```
Shows a summary table of installed vs missing dependencies and prompts to install.

### 2. Auto-Install (Non-Interactive)
```bash
python main.py install-deps -y
# or
python main.py install-deps --auto-install
```
Automatically installs missing dependencies without prompting.

### 3. Interactive Mode
```bash
python main.py --interactive
finance-cli> install-deps
```

## What It Does

✓ **Checks:** Compares currently installed packages with `requirements.txt`
✓ **Reports:** Shows clear table of installed vs missing packages
✓ **Installs:** Offers to install missing packages via pip
✓ **Safe:** Only handles core project dependencies

## What It Doesn't Do

✗ **No AI Providers:** Does not install Ollama, Copilot CLI, Qwen CLI
✗ **No Credentials:** Does not configure API keys or platform credentials
✗ **No Platform SDKs:** Just shows status, user must configure manually

## Scope

### Handles These Dependencies:
- `requests` - HTTP library
- `pandas` - Data processing
- `numpy` - Numerical computing
- `click` - CLI framework
- `rich` - Terminal formatting
- `pyyaml` - Configuration parsing
- `python-dotenv` - Environment variables
- `python-dateutil` - Date utilities
- `alpha-vantage` - Market data API
- `coinbase-advanced-py` - Coinbase platform SDK
- `oandapyV20` - Oanda platform SDK

### Skips These:
- API keys (Alpha Vantage, Coinbase, Oanda)
- AI provider binaries (Ollama, Copilot CLI, Qwen CLI)
- Platform credentials configuration

## Example Output

```
Checking project dependencies...

                 Dependency Status
┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Status      ┃ Count ┃ Packages                  ┃
┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ✓ Installed │     8 │ requests, pandas, numpy,  │
│             │       │ click ... (+4 more)       │
│ ✗ Missing   │     3 │ alpha-vantage,            │
│             │       │ coinbase-advanced-py,     │
│             │       │ oandapyV20                │
└─────────────┴───────┴───────────────────────────┘

Missing dependencies:
  • alpha-vantage
  • coinbase-advanced-py
  • oandapyV20

Install missing dependencies? [y/N]:
```

## Implementation Details

### Functions
- `_parse_requirements_file()` - Parses requirements.txt
- `_get_installed_packages()` - Gets currently installed packages via `pip list`
- `_check_dependencies()` - Compares required vs installed

### Error Handling
- Missing `requirements.txt` → shows warning
- Pip command fails → shows error with helpful message
- Individual package install fails → shows which package failed

## Use Cases

### 1. Fresh Clone
After cloning the repo, check what needs to be installed:
```bash
git clone <repo>
cd finance_feedback_engine-2.0
python main.py install-deps -y
```

### 2. After Updating requirements.txt
After adding new dependencies to requirements.txt:
```bash
python main.py install-deps
```

### 3. Environment Validation
Check if environment has all required packages:
```bash
python main.py install-deps
# If all installed: "✓ All dependencies are installed!"
```

### 4. CI/CD Integration
In CI pipelines:
```bash
python main.py install-deps -y
```

## Notes

- Uses `pip list --format=json` for reliable package detection
- Installs via `python -m pip install` to ensure correct environment
- Package names are normalized to lowercase for comparison
- Handles version specifiers (>=, ==) by extracting base package name
- Interactive mode prompts work in both standalone and interactive shell modes
