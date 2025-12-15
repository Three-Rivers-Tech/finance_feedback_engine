# Workflow Automation Guide

This guide describes the comprehensive workflow automation system for the Finance Feedback Engine 2.0 project.

## Table of Contents

- [Overview](#overview)
- [CI/CD Pipeline](#cicd-pipeline)
- [Pre-commit Hooks](#pre-commit-hooks)
- [Release Automation](#release-automation)
- [Security Automation](#security-automation)
- [Dependency Management](#dependency-management)
- [Monitoring](#monitoring)
- [Setup Instructions](#setup-instructions)
- [Troubleshooting](#troubleshooting)

## Overview

The Finance Feedback Engine uses a multi-layered automation strategy to ensure:

- **Code Quality**: Consistent formatting, linting, and type checking
- **Security**: Automated vulnerability scanning and secrets detection
- **Testing**: Comprehensive test coverage across multiple Python versions
- **Deployment**: Automated releases with semantic versioning
- **Monitoring**: Continuous health checks and performance tracking

### Automation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Workstation                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Pre-commit   │  │ Local Tests  │  │ Git Hooks    │      │
│  │ Hooks        │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────┬──────────────────────────────────┘
                           │ git push
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      GitHub Actions                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ CI Pipeline  │  │ Security     │  │ Dependency   │      │
│  │ (Enhanced)   │  │ Scanning     │  │ Updates      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Release      │  │ Monitoring   │  │ Docs Gen     │      │
│  │ Automation   │  │ & Alerts     │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## CI/CD Pipeline

### Enhanced CI Pipeline (`.github/workflows/ci-enhanced.yml`)

The enhanced CI pipeline provides comprehensive quality gates:

#### Jobs Overview

1. **quality**: Code formatting, linting, type checking
2. **security**: Security scanning with Bandit, Safety, pip-audit
3. **test**: Multi-version testing (Python 3.10, 3.11, 3.12, 3.13)
4. **coverage**: Code coverage analysis (70% minimum)
5. **build**: Package distribution validation
6. **docker**: Container image build and push
7. **docs**: Documentation validation
8. **config-validation**: Configuration file checks
9. **benchmark**: Performance benchmarking (main branch only)

#### Triggers

- **Push**: `main`, `develop` branches
- **Pull Request**: All PRs to `main`
- **Manual**: `workflow_dispatch`

#### Key Features

```yaml
# Multi-version testing
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ['3.10', '3.11', '3.12', '3.13']

# Caching for faster builds
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}

# Coverage threshold enforcement
- name: Check coverage threshold
  run: coverage report --fail-under=70
```

### Running CI Locally

```bash
# Install act (GitHub Actions local runner)
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI locally
act -j quality
act -j test
act -j coverage

# Run all jobs
act
```

## Pre-commit Hooks

### Setup

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Install commit-msg hook for conventional commits
pre-commit install --hook-type commit-msg
```

### Enhanced Configuration (`.pre-commit-config-enhanced.yaml`)

The enhanced pre-commit configuration includes:

#### Code Formatting

- **Black**: Python code formatter (line length: 88)
- **isort**: Import sorting (Black profile)
- **Ruff**: Fast linting and formatting
- **Prettier**: Markdown, YAML, JSON formatting

#### Linting

- **Flake8**: Python linting with plugins
  - flake8-docstrings
  - flake8-bugbear
  - flake8-comprehensions
  - flake8-simplify
- **Ruff**: Modern, fast linting
- **mypy**: Type checking

#### Security

- **Bandit**: Security issue detection
- **detect-secrets**: Secret scanning

#### Documentation

- **pydocstyle**: Docstring validation
- **interrogate**: Docstring coverage (60% minimum)
- **mdformat**: Markdown formatting

#### Custom Hooks

- Check for print statements in production code
- Verify test files exist for modules
- Validate configuration files
- Check TODO comments

### Running Pre-commit

```bash
# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run bandit --all-files

# Update hooks to latest versions
pre-commit autoupdate

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

### Troubleshooting Pre-commit

```bash
# Clear cache if hooks fail
pre-commit clean

# Reinstall hooks
pre-commit uninstall
pre-commit install

# Debug specific hook
pre-commit run --verbose black
```

## Release Automation

### Semantic Versioning

The project uses semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Creating a Release

#### Method 1: Git Tag (Automatic)

```bash
# Create and push a version tag
git tag v2.1.0
git push origin v2.1.0

# For pre-releases
git tag v2.1.0-beta.1
git push origin v2.1.0-beta.1
```

#### Method 2: Manual Workflow Dispatch

1. Go to Actions → Release Automation
2. Click "Run workflow"
3. Enter version (e.g., `2.1.0`)
4. Select if pre-release
5. Click "Run workflow"

### Release Process

The release workflow automatically:

1. **Validates**: Runs full test suite
2. **Builds**: Creates distribution packages (wheel, sdist)
3. **Dockerizes**: Builds multi-platform Docker images
4. **Generates**: Creates changelog from commits
5. **Publishes**: Creates GitHub release with artifacts
6. **Updates**: Opens PR with CHANGELOG.md updates

### Release Artifacts

Each release includes:

- Source distribution (`.tar.gz`)
- Wheel distribution (`.whl`)
- Docker images (AMD64, ARM64)
- Changelog
- Installation instructions

### Changelog Format

```markdown
## Finance Feedback Engine v2.1.0

### What's New

### ✨ New Features

- feat: Add real-time monitoring dashboard (#123)
- feature: Implement multi-asset portfolio tracking (#124)

### 🚀 Improvements

- improve: Optimize timeframe aggregation performance (#125)
- enhance: Better error handling in trading platforms (#126)

### 🐛 Bug Fixes

- fix: Resolve asset pair standardization edge case (#127)
- bug: Fix memory leak in decision cache (#128)
```

## Security Automation

### Daily Security Scans (`.github/workflows/security-scan.yml`)

Runs comprehensive security checks:

#### 1. Dependency Vulnerabilities

- **Safety**: Known vulnerability database
- **pip-audit**: OSV database scanning
- Auto-creates issues for critical vulnerabilities

#### 2. Code Security

- **Bandit**: Python security linter
- **CodeQL**: GitHub's semantic analysis
- **Semgrep**: Pattern-based security scanning

#### 3. Container Security

- **Trivy**: Container vulnerability scanner
- **Grype**: Anchore vulnerability scanner
- SARIF reports uploaded to GitHub Security

#### 4. Secrets Detection

- **GitLeaks**: Secret scanning
- **TruffleHog**: Entropy-based detection
- **detect-secrets**: Pattern matching

#### 5. License Compliance

- **pip-licenses**: License inventory
- Validation against allowed licenses
- Auto-generates license reports

#### 6. OpenSSF Scorecard

- Repository security best practices
- Automated security posture assessment

### Viewing Security Results

```bash
# View security tab in GitHub
https://github.com/[org]/finance_feedback_engine-2.0/security

# Download reports from workflow artifacts
gh run download --name security-reports
```

### Security Issue Response

When vulnerabilities are detected:

1. **Automatic**: Issue created with details
2. **Review**: Security team reviews severity
3. **Fix**: Update dependencies or patch code
4. **Verify**: Re-run security scan
5. **Close**: Issue closed when resolved

## Dependency Management

### Renovate Bot (`.github/renovate.json`)

Automated dependency updates with intelligent grouping:

#### Update Strategy

- **Security**: Immediate updates, auto-merge patches
- **Testing**: Auto-merge minor/patch updates
- **Development Tools**: Auto-merge all updates
- **Core Libraries**: Manual review required
- **Major Updates**: Separate PRs, monthly schedule

#### Dependency Groups

```json
{
  "testing dependencies": ["pytest", "pytest-cov", "pytest-asyncio"],
  "development tools": ["black", "flake8", "isort", "mypy"],
  "data processing": ["pandas", "numpy", "pandas-ta"],
  "API clients": ["alpha-vantage", "coinbase-advanced-py", "oandapyV20"],
  "web services": ["fastapi", "uvicorn", "redis"],
  "AI/ML": ["scikit-learn", "optuna", "ollama"]
}
```

#### Configuration Highlights

- **Schedule**: After 10pm weekdays, weekends
- **Concurrent PRs**: Max 5
- **Auto-merge**: Enabled for non-breaking updates
- **Vulnerability Alerts**: Immediate, high priority
- **Pin Digests**: Enabled for Docker images

#### Dependency Dashboard

View all pending updates:

```
https://github.com/[org]/finance_feedback_engine-2.0/issues?q=is%3Aissue+is%3Aopen+label%3Adependencies
```

### Manual Dependency Updates

```bash
# Check for outdated packages
pip list --outdated

# Update specific package
pip install --upgrade pandas

# Update all development dependencies
pip install -U -r requirements-dev.txt

# Freeze current versions
pip freeze > requirements.lock
```

## Monitoring

### Continuous Monitoring (`.github/workflows/monitoring.yml`)

#### Health Checks (Every 6 hours)

- CLI command validation
- Configuration file syntax
- Redis connectivity
- Import health

#### Performance Monitoring

- Import time profiling
- Memory usage baseline
- Operation benchmarking
- Performance trend tracking

#### Coverage Trend Analysis

- Daily coverage tracking
- Historical trend storage
- Threshold validation (70%)
- Automatic alerts on decline

#### Alert Validation

- Configuration syntax checking
- Threshold logic validation
- Alert rule testing

#### Dependency Freshness

- Weekly outdated package checks
- Auto-creates tracking issues
- Notifies maintainers

### Monitoring Metrics

```bash
# View monitoring results
gh workflow view monitoring

# Download metrics
gh run download --name system-metrics
gh run download --name performance-report

# View coverage trends
cat .coverage-history/trend.csv
```

### Custom Monitoring

Add custom health checks in `.github/workflows/monitoring.yml`:

```yaml
- name: Custom Health Check
  run: |
    python -c "
    from finance_feedback_engine.core import FinanceFeedbackEngine
    engine = FinanceFeedbackEngine()
    # Add custom checks
    "
```

## Setup Instructions

### Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/[org]/finance_feedback_engine-2.0.git
cd finance_feedback_engine-2.0

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .

# 3. Install pre-commit hooks
pip install pre-commit
pre-commit install
pre-commit install --hook-type commit-msg

# 4. Run initial checks
pre-commit run --all-files
pytest --cov=finance_feedback_engine

# 5. Verify workflows (requires act)
act -j quality --dry-run
```

### GitHub Actions Setup

Required secrets (Settings → Secrets → Actions):

```bash
# Optional: For private packages
GITHUB_TOKEN  # Auto-provided by GitHub

# Optional: For external services
CODECOV_TOKEN  # Code coverage reporting
SNYK_TOKEN     # Snyk security scanning
GITLEAKS_LICENSE  # GitLeaks Pro (optional)
```

### Renovate Setup

1. Install Renovate GitHub App
2. Configuration automatically loaded from `.github/renovate.json`
3. Review dependency dashboard issue

### Docker Registry Setup

GitHub Container Registry is used by default:

```bash
# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Pull image
docker pull ghcr.io/[org]/finance_feedback_engine-2.0:latest

# Run container
docker run -it ghcr.io/[org]/finance_feedback_engine-2.0:latest
```

## Troubleshooting

### Common Issues

#### 1. Pre-commit Hook Failures

```bash
# Problem: Hook fails on specific files
# Solution: Run with verbose flag
pre-commit run --verbose --all-files

# Problem: Hook installation fails
# Solution: Reinstall
pre-commit clean
pre-commit install --install-hooks
```

#### 2. CI Pipeline Failures

```bash
# Problem: Tests fail in CI but pass locally
# Solution: Match CI environment
docker run -it python:3.11 bash
pip install -r requirements.txt
pytest

# Problem: Cache corruption
# Solution: Clear cache in GitHub Actions
# Go to Actions → Caches → Delete cache
```

#### 3. Coverage Below Threshold

```bash
# Problem: Coverage drops below 70%
# Solution: Identify uncovered code
pytest --cov=finance_feedback_engine --cov-report=html
open htmlcov/index.html

# Add tests for uncovered modules
```

#### 4. Dependency Conflicts

```bash
# Problem: Renovate creates conflicting updates
# Solution: Group dependencies
# Edit .github/renovate.json to add package to group

# Problem: pip install fails
# Solution: Use constraint file
pip install -r requirements.txt -c constraints.txt
```

#### 5. Release Failures

```bash
# Problem: Release workflow fails
# Solution: Check version format
git tag -d v2.1.0  # Delete bad tag
git tag v2.1.0     # Create correct tag
git push origin v2.1.0

# Problem: Build artifacts missing
# Solution: Check build step logs
gh run view --log | grep "Build distribution"
```

### Debug Mode

Enable debug logging in workflows:

```yaml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

### Getting Help

1. **Documentation**: Check `/docs` directory
2. **Issues**: Search existing issues on GitHub
3. **Discussions**: GitHub Discussions for questions
4. **CI Logs**: Review workflow logs for details

## Best Practices

### Commit Messages

Use conventional commits for automatic changelog generation:

```bash
feat: Add new feature
fix: Resolve bug
docs: Update documentation
test: Add tests
refactor: Refactor code
chore: Maintenance tasks
ci: CI/CD changes
perf: Performance improvements
```

### Pull Request Workflow

1. Create feature branch: `git checkout -b feature/description`
2. Make changes with conventional commits
3. Run pre-commit: `pre-commit run --all-files`
4. Run tests: `pytest`
5. Push: `git push origin feature/description`
6. Create PR with template
7. Address CI feedback
8. Wait for review
9. Merge when approved

### Version Bumping

Follow semantic versioning guidelines:

- Breaking changes: Bump MAJOR
- New features: Bump MINOR
- Bug fixes: Bump PATCH
- Pre-releases: Add suffix (`-alpha.1`, `-beta.1`, `-rc.1`)

### Security

- Never commit secrets or API keys
- Use environment variables for sensitive data
- Review Renovate security updates promptly
- Monitor security scan results
- Rotate credentials regularly

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Renovate Documentation](https://docs.renovatebot.com/)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**Maintained by**: Three Rivers Tech
**Last Updated**: December 2024
**Version**: 2.0
