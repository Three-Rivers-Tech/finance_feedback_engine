# Workflow Automation Guide

This guide provides comprehensive documentation for all automated workflows in the Finance Feedback Engine project.

## Table of Contents

1. [Overview](#overview)
2. [CI/CD Pipelines](#cicd-pipelines)
3. [Release Automation](#release-automation)
4. [Performance Testing](#performance-testing)
5. [Backup & Disaster Recovery](#backup--disaster-recovery)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Development Environment Setup](#development-environment-setup)
8. [Workflow Orchestration](#workflow-orchestration)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Finance Feedback Engine implements comprehensive workflow automation to ensure:

- **Quality Assurance**: Automated testing, linting, and security scanning
- **Continuous Delivery**: Automated builds, deployments, and releases
- **System Reliability**: Automated backups, monitoring, and health checks
- **Developer Experience**: Automated environment setup and development tools

### Automation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflows                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   CI/CD      │  │   Release    │  │  Performance │      │
│  │   Pipeline   │  │  Automation  │  │   Testing    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Backup &   │  │  Monitoring  │  │   Security   │      │
│  │   Recovery   │  │  & Alerting  │  │   Scanning   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
          ┌──────────────────────────────────┐
          │   Workflow Orchestrator Tool     │
          │   (scripts/workflow-orchestrator)│
          └──────────────────────────────────┘
```

---

## CI/CD Pipelines

### Overview

Multiple CI/CD workflows ensure code quality and enable continuous delivery:

1. **ci.yml**: Fast CI checks using Docker containers
2. **ci-enhanced.yml**: Comprehensive multi-platform testing
3. **deploy.yml**: Automated deployment to staging and production

### CI Pipeline (ci.yml)

**Trigger**: Push to `main`, Pull Requests
**Duration**: ~5-10 minutes
**Docker-based**: Uses pre-built CI container

#### Jobs

1. **Lint**: Code quality checks
   - Black (formatting)
   - Flake8 (linting)
   - isort (import sorting)

2. **Test**: Fast test suite
   - Excludes external services
   - Coverage threshold: 70%
   - Uploads coverage to Codecov

3. **Coverage**: Coverage reporting
   - Downloads test results
   - Uploads to Codecov
   - Generates HTML reports

**Usage:**
```bash
# Runs automatically on push/PR
# View results: GitHub Actions tab
```

### Enhanced CI Pipeline (ci-enhanced.yml)

**Trigger**: Push to `main`/`develop`, Pull Requests, Manual dispatch
**Duration**: ~15-30 minutes
**Multi-platform**: Ubuntu, macOS, Windows

#### Jobs

1. **Quality**: Code quality and static analysis
2. **Security**: Security scanning (Bandit, Safety, pip-audit)
3. **Test**: Matrix testing (Python 3.10, 3.11, 3.12, 3.13)
4. **Coverage**: Comprehensive coverage analysis
5. **Build**: Distribution packaging
6. **Docker**: Container image building
7. **Docs**: Documentation validation
8. **Config Validation**: YAML and configuration checks
9. **Benchmark**: Performance benchmarks (main branch only)

**Configuration:**
```yaml
env:
  PYTHON_VERSION: '3.11'
  CACHE_KEY_PREFIX: v1
```

### Deployment Pipeline (deploy.yml)

**Trigger**: Push to `main`, Manual workflow dispatch
**Environments**: Staging (automatic), Production (manual approval)

#### Staging Deployment

**Automatic**: Triggers on push to `main`

```bash
# SSH-based deployment
cd /opt/finance-feedback-engine
git pull origin main
./scripts/deploy.sh staging restart
```

**Health Check**: 30-second wait + HTTP health check

#### Production Deployment

**Manual**: Requires workflow dispatch with environment selection

**Safety Features:**
- Pre-deployment backup
- Health checks
- Deployment tags
- Manual approval gates

```bash
# Manual trigger
# 1. Go to Actions tab
# 2. Select "Deploy to Environments"
# 3. Click "Run workflow"
# 4. Choose "production"
# 5. Approve environment deployment
```

---

## Release Automation

### Overview

**File**: `.github/workflows/release-automation.yml`
**Trigger**: Push to `main`, Manual dispatch
**Convention**: Follows conventional commits

### Release Process

1. **Check Release Needed**
   - Analyzes commits since last tag
   - Detects `feat:`, `fix:`, `BREAKING CHANGE`
   - Calculates semantic version

2. **Pre-Release Tests**
   - Full test suite
   - Coverage validation
   - Integration tests

3. **Build Artifacts**
   - Python distribution packages
   - Docker images (tagged with version)
   - Multi-architecture support

4. **Create GitHub Release**
   - Automated release notes
   - Changelog generation
   - Asset uploads
   - Git tagging

5. **Notify Release**
   - Workflow summary
   - Deployment tracking

### Semantic Versioning

```
feat:     → MINOR version bump (0.1.0 → 0.2.0)
fix:      → PATCH version bump (0.1.0 → 0.1.1)
BREAKING: → MAJOR version bump (0.1.0 → 1.0.0)
```

### Release Checklist

```markdown
- [ ] All tests passing
- [ ] Coverage >= 70%
- [ ] Conventional commit messages
- [ ] CHANGELOG updated (automatic)
- [ ] Documentation current
- [ ] Security scan clean
```

### Manual Release

```bash
# Force a release type
# 1. Go to Actions → Release Automation
# 2. Run workflow
# 3. Select release type: patch/minor/major
```

---

## Performance Testing

### Overview

**File**: `.github/workflows/performance-testing.yml`
**Trigger**: Push to `main`, PRs, Weekly schedule (Sunday 3 AM)
**Duration**: ~30 minutes

### Test Suites

#### 1. Benchmark Tests

**Pytest-benchmark** based performance tests

```python
@pytest.mark.benchmark
def test_indicator_calculation(benchmark):
    result = benchmark(calculate_sma, data, period=20)
    assert result is not None
```

**Features:**
- Historical comparison
- Regression detection
- JSON result storage

#### 2. Memory Profiling

**Memory_profiler** tracks memory usage

```bash
mprof run --include-children python -m finance_feedback_engine
mprof plot -o memory-profile.png
```

**Outputs:**
- Memory usage graphs
- Peak memory detection
- Memory leak identification

#### 3. Load Testing

**Locust** for API load testing

```python
class FinanceFeedbackUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health_check(self):
        self.client.get("/health")
```

**Configuration:**
- 50 concurrent users
- 5 users/second spawn rate
- 2-minute duration

#### 4. API Performance

**Response time analysis** (100 requests per endpoint)

**Metrics:**
- Mean response time
- Median response time
- P95 latency
- Min/Max times

### Performance Thresholds

```yaml
Response Time:
  Health Endpoint: < 100ms
  API Endpoints: < 500ms

Memory:
  Peak Usage: < 1GB
  Memory Leaks: None

Throughput:
  Minimum RPS: 100
  Target RPS: 500
```

### Viewing Results

```bash
# Download artifacts from GitHub Actions
# - benchmark-results.json
# - memory-profile.png
# - load-test-report.html
```

---

## Backup & Disaster Recovery

### Overview

**File**: `.github/workflows/backup-automation.yml`
**Trigger**: Daily 2 AM UTC, Weekly Sunday 3 AM UTC, Manual dispatch

### Backup Types

#### Incremental Backup

**Schedule**: Daily (Monday-Saturday)
**Retention**: 30 days

**Includes:**
- Configuration changes
- Application data
- Recent logs

#### Full Backup

**Schedule**: Weekly (Sunday)
**Retention**: 90 days

**Includes:**
- Complete configuration
- All application data
- Historical logs
- Database state

### Backup Process

1. **Create Backup**
   - Collect configuration files
   - Compress application data
   - Generate manifest
   - Calculate checksums

2. **Verify Integrity**
   - Checksum validation
   - Test extraction
   - Manifest verification

3. **Upload to Cloud**
   - AWS S3 storage
   - Encrypted transfer
   - Lifecycle policies

4. **Cleanup Old Backups**
   - Remove backups older than retention
   - Free up storage space

5. **Test Recovery**
   - Simulate restore procedure
   - Verify critical files
   - Validate configuration

### Backup Structure

```
s3://finance-feedback-engine-backups/
├── production/
│   ├── finance-feedback-engine-full-20250129_020000.tar.gz
│   ├── finance-feedback-engine-full-20250129_020000.tar.gz.sha256
│   ├── finance-feedback-engine-incremental-20250130_020000.tar.gz
│   └── ...
└── staging/
    └── ...
```

### Manual Backup

```bash
# Trigger manual backup
# 1. Go to Actions → Backup Automation
# 2. Run workflow
# 3. Select backup type: incremental/full
# 4. Select environment: staging/production
```

### Disaster Recovery

**RTO (Recovery Time Objective)**: < 4 hours
**RPO (Recovery Point Objective)**: < 24 hours

#### Recovery Steps

```bash
# 1. Download latest backup from S3
aws s3 cp s3://bucket/latest-backup.tar.gz .

# 2. Verify checksum
sha256sum -c latest-backup.tar.gz.sha256

# 3. Extract backup
tar -xzf latest-backup.tar.gz

# 4. Restore configuration
cp -r backups/*/config ./

# 5. Restore data
cp -r backups/*/data ./

# 6. Restart services
./scripts/deploy.sh production restart

# 7. Verify recovery
./scripts/verify-deployment.sh
```

---

## Monitoring & Alerting

### Overview

**File**: `.github/workflows/monitoring-alerts.yml`
**Trigger**: Every 15 minutes, Manual dispatch

### Monitoring Checks

#### 1. Health Checks

**Frequency**: Every 15 minutes
**Endpoints**:
- Production: `/health`
- Staging: `/health`

**Alerts**:
- HTTP status != 200
- Response timeout (> 10s)
- Service unavailable

#### 2. Performance Monitoring

**Metrics**:
- API response times
- Resource utilization
- Throughput rates

**Thresholds**:
- Response time > 2s → Warning
- Response time > 5s → Alert

#### 3. Security Monitoring

**Checks**:
- Security advisories
- SSL certificate expiration
- Exposed secrets

**Alerts**:
- Certificate expires < 30 days
- New security advisory

#### 4. Dependency Monitoring

**Checks**:
- Outdated dependencies
- Stale update PRs

**Alerts**:
- Dependency PR > 7 days old
- High-severity vulnerabilities

### Alert Levels

```
🟢 INFO     - Informational, no action needed
🟡 WARNING  - Attention required, not urgent
🔴 CRITICAL - Immediate action required
```

### Alert Channels

1. **GitHub Issues**
   - Automated issue creation
   - Labels: `alert`, `production`, `critical`
   - Assigned to repository owner

2. **Workflow Summaries**
   - Real-time status updates
   - Historical tracking
   - Metrics visualization

### Incident Response

#### Production Health Check Failed

**Severity**: 🔴 CRITICAL

**Actions:**
1. Check production logs
2. Verify service status
3. Review recent deployments
4. Escalate if necessary

**SLA**: Response within 15 minutes

---

## Development Environment Setup

### Overview

**File**: `scripts/setup-dev-environment.sh`
**Purpose**: Automated local development setup

### Features

- ✅ Prerequisite checking
- ✅ Virtual environment creation
- ✅ Dependency installation
- ✅ Environment configuration
- ✅ Git hooks setup
- ✅ Docker services startup
- ✅ Database initialization
- ✅ Initial testing
- ✅ IDE configuration

### Usage

```bash
# Full setup
./scripts/setup-dev-environment.sh

# Skip Docker services
./scripts/setup-dev-environment.sh --skip-docker

# Skip Git hooks
./scripts/setup-dev-environment.sh --skip-git-hooks

# Minimal setup (essentials only)
./scripts/setup-dev-environment.sh --minimal
```

### What Gets Installed

#### Python Packages
- Production dependencies (requirements.txt)
- Development dependencies (requirements-dev.txt)
- Package in editable mode

#### Git Hooks
- Pre-commit hooks
- Commit message validation
- Auto-formatting on commit

#### Docker Services
- Redis
- PostgreSQL (if configured)
- Other development services

#### IDE Configuration
- VSCode settings
- Launch configurations
- Debug configurations

### Post-Setup Checklist

```markdown
1. ✅ Virtual environment activated
2. ✅ Dependencies installed
3. ✅ .env configured
4. ✅ Git hooks active
5. ✅ Docker services running
6. ✅ Tests passing
```

---

## Workflow Orchestration

### Overview

**File**: `scripts/workflow-orchestrator.py`
**Purpose**: Complex multi-step workflow execution

### Features

- ✅ Sequential and parallel execution
- ✅ Automatic retries with exponential backoff
- ✅ Timeout handling
- ✅ Conditional execution
- ✅ Error handling strategies
- ✅ Result tracking and reporting

### Architecture

```python
WorkflowStep
├── name: str
├── type: Sequential | Parallel
├── action: Callable
├── steps: List[WorkflowStep]
├── retries: int
├── timeout: int
├── condition: Callable
└── on_error: Fail | Continue | Retry
```

### Usage

```bash
# Run deployment workflow
python scripts/workflow-orchestrator.py --workflow deployment

# Load from config file
python scripts/workflow-orchestrator.py --config workflows/custom.yaml

# Adjust logging
python scripts/workflow-orchestrator.py --log-level DEBUG
```

### Example: Deployment Workflow

```python
deployment_workflow = WorkflowStep(
    name="deployment",
    type=StepType.SEQUENTIAL,
    steps=[
        WorkflowStep(
            name="pre-deployment",
            type=StepType.PARALLEL,
            steps=[
                WorkflowStep(
                    name="backup",
                    action=backup_database,
                    timeout=300,
                    retries=2
                ),
                WorkflowStep(
                    name="health-check",
                    action=health_check,
                    retries=3
                )
            ]
        ),
        WorkflowStep(
            name="deploy",
            action=deploy_app,
            on_error=ErrorAction.FAIL
        ),
        WorkflowStep(
            name="post-deployment",
            type=StepType.PARALLEL,
            steps=[
                WorkflowStep(
                    name="notify",
                    action=notify_team,
                    on_error=ErrorAction.CONTINUE
                ),
                WorkflowStep(
                    name="monitoring",
                    action=update_monitoring
                )
            ]
        )
    ]
)
```

### Error Handling

```python
ErrorAction.FAIL     # Stop workflow on error
ErrorAction.CONTINUE # Continue despite error
ErrorAction.RETRY    # Retry with exponential backoff
```

### Result Tracking

Results saved to: `logs/workflow_{name}_{timestamp}.json`

```json
{
  "workflow_name": "deployment",
  "success": true,
  "duration": 45.2,
  "steps": [
    {
      "name": "backup",
      "status": "completed",
      "duration": 12.3,
      "output": "Database backup created"
    }
  ]
}
```

---

## Best Practices

### 1. Conventional Commits

Use conventional commit messages for automatic release management:

```bash
feat: add new trading indicator
fix: resolve API timeout issue
docs: update deployment guide
chore: upgrade dependencies
BREAKING CHANGE: change API response format
```

### 2. Pull Request Guidelines

- ✅ All CI checks must pass
- ✅ Code review required
- ✅ Coverage must not decrease
- ✅ No security vulnerabilities
- ✅ Documentation updated

### 3. Deployment Safety

**Pre-deployment:**
- [ ] All tests passing
- [ ] Security scan clean
- [ ] Backup created
- [ ] Rollback plan ready

**Post-deployment:**
- [ ] Health check passed
- [ ] Smoke tests passed
- [ ] Monitoring updated
- [ ] Team notified

### 4. Monitoring

**Key Metrics:**
- Response time
- Error rate
- CPU/Memory usage
- API throughput

**Alerting Rules:**
- Error rate > 1% → Warning
- Response time > 2s → Warning
- Service down → Critical

### 5. Security

**Continuous:**
- Daily security scans
- Automated dependency updates
- Secret scanning
- Certificate monitoring

### 6. Performance

**Regular Testing:**
- Weekly performance tests
- Benchmark comparison
- Load testing
- Memory profiling

---

## Troubleshooting

### CI/CD Issues

#### Tests Failing

```bash
# Run tests locally first
pytest -v

# Check specific test
pytest tests/test_specific.py -v

# View coverage
pytest --cov=finance_feedback_engine --cov-report=html
open htmlcov/index.html
```

#### Docker Build Failing

```bash
# Build locally
docker build -f Dockerfile.ci -t test .

# Check build logs
docker build --no-cache -f Dockerfile.ci -t test .

# Test container
docker run -it test /bin/bash
```

### Deployment Issues

#### Deployment Failed

```bash
# Check deployment logs
ssh user@host "cd /opt/finance-feedback-engine && tail -100 logs/deploy.log"

# Verify service status
ssh user@host "cd /opt/finance-feedback-engine && ./scripts/deploy.sh production status"

# Rollback if needed
ssh user@host "cd /opt/finance-feedback-engine && git checkout previous-tag"
ssh user@host "cd /opt/finance-feedback-engine && ./scripts/deploy.sh production restart"
```

#### Health Check Failing

```bash
# Check service logs
ssh user@host "cd /opt/finance-feedback-engine && tail -100 logs/app.log"

# Test health endpoint
curl -v http://host:8000/health

# Check Docker services
ssh user@host "cd /opt/finance-feedback-engine && docker-compose ps"
```

### Performance Issues

#### Slow Response Times

```bash
# Profile application
python -m cProfile -o profile.stats main.py

# Analyze profile
python -m pstats profile.stats

# Memory profiling
mprof run python main.py
mprof plot
```

### Backup Issues

#### Backup Failed

```bash
# Check S3 access
aws s3 ls s3://bucket-name

# Verify credentials
aws sts get-caller-identity

# Manual backup
./scripts/backup.sh
```

#### Restore Failed

```bash
# Download backup manually
aws s3 cp s3://bucket/backup.tar.gz .

# Verify integrity
sha256sum -c backup.tar.gz.sha256

# Extract and inspect
tar -tzf backup.tar.gz | head
```

### Monitoring Issues

#### Alerts Not Triggering

```bash
# Check workflow runs
# Go to Actions → Monitoring & Alerting

# Verify endpoints
curl http://production-url/health

# Check secrets configuration
# Settings → Secrets and variables → Actions
```

---

## Additional Resources

### Documentation

- [Contributing Guide](CONTRIBUTING.md)
- [Development Guide](DEVELOPMENT.md)
- [API Documentation](API.md)
- [Deployment Guide](DEPLOYMENT.md)

### External Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

### Support

- **Issues**: [GitHub Issues](https://github.com/Grovex-Tech-Solutions/finance_feedback_engine/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Grovex-Tech-Solutions/finance_feedback_engine/discussions)
- **Security**: security@example.com

---

**Last Updated**: 2025-12-29
**Version**: 1.0.0
