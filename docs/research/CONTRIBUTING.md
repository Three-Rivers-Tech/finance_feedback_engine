# Contributing to Finance Feedback Engine 2.0

Thank you for your interest in contributing to Finance Feedback Engine 2.0! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the bug
- Steps to reproduce
- Expected behavior
- Actual behavior
- System information (OS, Python version, etc.)

### Suggesting Features

Feature suggestions are welcome! Please:
- Check if the feature has already been requested
- Provide a clear use case
- Explain how it would benefit users
- Consider implementation complexity

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow the existing code style
   - Add tests for new features
   - Update documentation as needed
   - Ensure all tests pass
   - **Pre-commit hooks will run automatically** - don't bypass them unless absolutely necessary

4. **Commit your changes**
   ```bash
   git commit -m "Add feature: your feature description"
   ```
   
   **Note:** Pre-commit hooks will run automatically:
   - Code formatting (black, isort)
   - Linting (flake8, mypy)
   - Security checks (bandit, secret detection)
   - Test coverage (≥70%)
   
   If hooks fail, fix the issues before committing. Only bypass with `--no-verify` in emergencies.

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**
   - Provide a clear description
   - Reference any related issues
   - Include screenshots for UI changes

## Development Setup

### Prerequisites
- Python 3.8 or higher
- pip or poetry for package management
- Git

### Installation
```bash
# Clone the repository
git clone https://github.com/Three-Rivers-Tech/finance_feedback_engine-2.0.git
cd finance_feedback_engine-2.0

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up git hooks (IMPORTANT for contributors)
./scripts/setup-hooks.sh
```

This will install pre-commit hooks that automatically:
- Format code (black, isort)
- Run linting (flake8, mypy)
- Check for security issues (bandit)
- Prevent committing secrets
- Enforce test coverage (≥70%)

For more details, see [Pre-commit Configuration Guide](../PRE_COMMIT_GUIDE.md).

### Running Tests
```bash
# Run test script
python test_api.py

# Test CLI commands
python main.py -c config/examples/test.yaml status
python main.py -c config/examples/test.yaml analyze BTCUSD
```

## Code Style

### Python
- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and single-purpose
- Use type hints where appropriate

**Automated Formatting:**
The project uses automated code formatting tools that run via pre-commit hooks:
- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **bandit**: Security scanning

These run automatically on commit. To run manually:
```bash
# Format all code
black finance_feedback_engine/
isort finance_feedback_engine/

# Run linting
flake8 finance_feedback_engine/
mypy finance_feedback_engine/

# Or use pre-commit
pre-commit run --all-files
```

### Example
```python
def get_market_data(self, asset_pair: str) -> Dict[str, Any]:
    """
    Fetch market data for a given asset pair.

    Args:
        asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')

    Returns:
        Dictionary containing market data
    """
    # Implementation
    pass
```

## Project Structure

```
finance_feedback_engine/
├── core.py                    # Main engine
├── data_providers/            # Market data providers
├── trading_platforms/         # Platform integrations
├── decision_engine/           # AI decision making
├── persistence/               # Data storage
└── cli/                       # Command-line interface
```

## Adding New Features

### Adding a New Trading Platform

1. Create a new file in `trading_platforms/`
2. Inherit from `BaseTradingPlatform`
3. Implement required methods
4. Register in `platform_factory.py`

```python
from .base_platform import BaseTradingPlatform

class MyPlatform(BaseTradingPlatform):
    def get_balance(self):
        # Implementation
        pass

    def execute_trade(self, decision):
        # Implementation
        pass

    def get_account_info(self):
        # Implementation
        pass
```

### Adding a New Data Provider

1. Create a new file in `data_providers/`
2. Implement market data fetching
3. Follow the Alpha Vantage provider pattern

### Adding a New AI Provider

1. Modify `decision_engine/engine.py`
2. Add a new method for your provider
3. Update `_query_ai()` to use your provider

## Documentation

- Update README.md for major features
- Update USAGE.md for new commands or API changes
- Add docstrings to all new code
- Include examples in documentation

## Testing

- Test your changes thoroughly
- Include both success and error cases
- Test with different configurations
- Verify backward compatibility

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=finance_feedback_engine --cov-report=term-missing

# Run specific test types
pytest -m "not slow and not external_service"  # Fast tests only
pytest -m integration  # Integration tests only
```

### Test Coverage Requirements
- Minimum 70% test coverage required (enforced by pre-commit hooks)
- Add tests for all new features and bug fixes
- Test both success and error paths

## Security

### Preventing Secrets in Commits

The project includes automatic secret detection that runs before every commit. This prevents:
- API keys
- Passwords and tokens
- Private keys
- Database credentials
- Other sensitive information

**Safe patterns:**
- Use environment variables: `${ALPHA_VANTAGE_API_KEY}`
- Use placeholders: `YOUR_API_KEY`, `your_secret_here`
- Store secrets in `config/config.local.yaml` (git-ignored)
- Use `.env` files (git-ignored)

**If you get a secret detection warning:**
1. Remove the hardcoded secret
2. Use environment variables or config.local.yaml
3. Rotate the exposed credential if it was real

For more details, see `.pre-commit-hooks/README.md`.

## Questions?

If you have questions:
- Open an issue for discussion
- Check existing issues and PRs
- Review the documentation

Thank you for contributing!
