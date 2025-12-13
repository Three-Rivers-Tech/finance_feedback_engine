# Next Steps - Prioritized Roadmap

This document outlines the next high-value refactoring tasks, ordered by ROI.

---

## 🎯 Immediate Wins (Next Session, 4-8 hours)

### 1. Extract CLI Commands (HIGH PRIORITY)
**Effort:** 6 hours | **Savings:** $72K/year | **ROI:** 1,200%

Create these command modules:

```bash
# Create files
touch finance_feedback_engine/cli/commands/analysis.py
touch finance_feedback_engine/cli/commands/trading.py
touch finance_feedback_engine/cli/commands/agent.py
touch finance_feedback_engine/cli/commands/backtest.py
touch finance_feedback_engine/cli/commands/memory.py
touch finance_feedback_engine/cli/commands/infrastructure.py
```

**Template for each module:**
```python
# finance_feedback_engine/cli/commands/analysis.py
import click
from rich.console import Console

console = Console()

@click.command()
@click.argument('asset_pair')
@click.pass_context
def analyze(ctx, asset_pair: str):
    """Analyze asset pair."""
    # Move logic from main.py here
    pass

# Export for main.py
# Export for main.py
commands = [analyze]
```

**Update main.py:**
```python
# Reduce to ~100 lines
from finance_feedback_engine.cli.commands import (
    analyze, history,           # analysis
    execute, balance,           # trading
    run_agent, monitor,         # agent
    backtest, walk_forward,     # backtest
    # ... etc
)

@click.group()
def cli():
    """Entry point."""
    pass

# Register all commands
for cmd in [analyze, history, execute, ...]:
    cli.add_command(cmd)
```

**Testing:**
```bash
# After refactoring, verify all commands work:
python main.py analyze BTCUSD
python main.py balance
python main.py backtest BTCUSD --start-date 2024-01-01
```

---

### 2. Migrate Remaining Data Providers (MEDIUM PRIORITY)
**Effort:** 4 hours | **Savings:** $54K/year | **ROI:** 1,350%

Update these providers to use `BaseDataProvider`:

**Step-by-step:**
```python
# 1. AlphaVantageProvider
# finance_feedback_engine/data_providers/alpha_vantage_refactored.py

from .base_provider import BaseDataProvider

class AlphaVantageProviderRefactored(BaseDataProvider):
    @property
    def provider_name(self) -> str:
        return "AlphaVantage"

    @property
    def base_url(self) -> str:
        return "https://www.alphavantage.co/query"

    # Only implement provider-specific logic
    def normalize_asset_pair(self, pair: str) -> str:
        # AlphaVantage uses "BTC", "ETH" format
        return pair.upper().replace('USD', '').replace('-', '')

    async def fetch_market_data(self, pair: str) -> dict:
        normalized = self.normalize_asset_pair(pair)
        params = {
            'function': 'DIGITAL_CURRENCY_DAILY',
            'symbol': normalized,
            'market': 'USD',
            'apikey': self.api_key
        }
        # Use inherited _make_http_request() - automatic rate limiting!
        return await self._make_http_request(self.base_url, params=params)
```

**Repeat for:**
- OandaDataProvider
- RealtimeDataProvider
- HistoricalDataProvider

**Test each:**
```bash
pytest tests/data_providers/ -v
```

---

### 3. Fix Remaining Bare Exceptions (QUICK WIN)
**Effort:** 2 hours | **Savings:** $14K/year | **ROI:** 700%

**Find all bare exceptions:**
```bash
python scripts/check_code_quality.py --check-bare-except
```

**Fix pattern:**
```python
# BEFORE:
try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")
    return None

# AFTER:
from finance_feedback_engine.exceptions import (
    DataProviderError, TradingPlatformError
)

try:
    result = risky_operation()
except DataProviderError as e:
    logger.error(
        "Data provider failed",
        extra={"provider": provider_name, "asset": asset_pair},
        exc_info=True
    )
    raise  # Re-raise for higher-level handling
except TradingPlatformError as e:
    logger.error(f"Platform error: {e}", exc_info=True)
    return None  # Only swallow if truly safe
```

**Priority files:**
1. `finance_feedback_engine/core.py`
2. `finance_feedback_engine/decision_engine/engine.py`
3. `finance_feedback_engine/cli/main.py`

---

## 📅 Short-Term (Week 2, 8-12 hours)

### 4. Implement Prometheus Metrics
**File:** `finance_feedback_engine/monitoring/prometheus.py`

Currently 100% stubbed! Need production observability.

**Implementation:**
```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
decision_latency = Histogram(
    'decision_latency_seconds',
    'Time to make trading decision',
    ['provider', 'asset_pair']
)

provider_requests = Counter(
    'provider_requests_total',
    'Total AI provider requests',
    ['provider', 'status']
)

# Instrument code
def record_decision_latency(provider, asset_pair, duration):
    decision_latency.labels(provider, asset_pair).observe(duration)

def record_provider_request(provider, status):
    provider_requests.labels(provider, status).inc()
```

**Instrument in:**
- `decision_engine/engine.py` - decision latency
- `decision_engine/ensemble_manager.py` - provider requests
- `monitoring/trade_monitor.py` - P&L tracking
- `trading_platforms/*.py` - balance checks

**Create Grafana dashboard:**
```yaml
# grafana/dashboards/trading_metrics.json
{
  "dashboard": {
    "title": "Trading Metrics",
    "panels": [
      {
        "title": "Decision Latency by Provider",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, decision_latency_seconds)"
          }
        ]
      }
    ]
  }
}
```

---

### 5. Update CLI main.py to Use New Pulse Formatter
**Effort:** 30 minutes

**Change:**
```python
# cli/main.py

# OLD:
def _display_pulse_data(engine, asset_pair: str):
    # 149 lines of code
    ...

# NEW:
from finance_feedback_engine.cli.formatters.pulse_formatter import display_pulse_data

# In analyze command:
if show_pulse:
    display_pulse_data(engine, asset_pair, console)
```

**Test:**
```bash
python main.py analyze BTCUSD --show-pulse
```

---

## 🏗️ Medium-Term (Month 2, 20-30 hours)

### 6. Refactor Decision Engine
**File:** `finance_feedback_engine/decision_engine/engine.py` (1,612 lines)

**Split into:**
```
decision_engine/
├── engine.py                 # Orchestration only (200 lines)
├── prompt_builder.py         # Prompt generation logic
├── position_sizer.py         # Position sizing calculations
├── market_context.py         # Regime detection integration
└── validation.py             # Data freshness checks
```

**Example:**
```python
# decision_engine/prompt_builder.py
class TradingPromptBuilder:
    """Builds AI prompts for trading decisions."""

    def build_prompt(
        self,
        asset_pair: str,
        market_data: dict,
        portfolio_context: dict
    ) -> str:
        # Extract from engine.py
        ...
```

---

### 7. Comprehensive Test Suite
**Target:** 95%+ coverage

**Create tests for new modules:**
```bash
# tests/cli/formatters/test_pulse_formatter.py
from finance_feedback_engine.cli.formatters.pulse_formatter import (
    RSILevel, TimeframeData, PulseDisplayService
)

def test_rsi_overbought():
    rsi = RSILevel(75.0)
    assert rsi.interpretation == "OVERBOUGHT"
    assert rsi.color == "red"

def test_timeframe_data_creation():
    data = TimeframeData.from_dict('1h', {
        'trend': 'UPTREND',
        'rsi': 65.0,
        # ...
    })
    assert data.timeframe == '1h'
    assert data.rsi.value == 65.0
```

**Run coverage:**
```bash
pytest --cov=finance_feedback_engine --cov-report=html
open htmlcov/index.html
```

---

## 🎯 Long-Term (Quarter 2, 40+ hours)

### 8. Complete Documentation
- API documentation (Sphinx)
- Architecture diagrams (Mermaid)
- Deployment guides
- Troubleshooting runbooks

### 9. Performance Optimization
- Profile hot paths
- Optimize database queries
- Implement caching strategies
- Reduce API calls

### 10. Security Hardening
- Dependency scanning (Snyk)
- Secret management (Vault)
- Rate limiting enforcement
- Audit logging

---

## 📊 Success Metrics

Track these KPIs monthly:

```python
# Monthly metrics to track
metrics = {
    "debt_score": 685,           # Target: <400 by Q2
    "largest_file": 3160,        # Target: <500 lines
    "code_duplication": "20%",   # Target: <5%
    "test_coverage": "50%",      # Target: 95%+
    "bare_exceptions": 30,       # Target: 0
    "features_per_quarter": 5,   # Target: 10+
}
```

**Review quarterly:**
- Code quality dashboard
- Developer satisfaction survey
- Production incident rate
- Feature delivery velocity

---

## 🚀 Getting Started

**Right now:**
```bash
# 1. Run quality checks
python scripts/check_code_quality.py --check-bare-except --check-file-size

# 2. Enable pre-commit hooks
pip install pre-commit
pre-commit install

# 3. Start CLI refactoring
mkdir -p finance_feedback_engine/cli/commands
# Create your first command module
```

**Tomorrow:**
- Extract 2-3 CLI commands
- Migrate 1 data provider
- Fix 5 bare exceptions

**This week:**
- Complete CLI refactoring
- All data providers migrated
- No bare exceptions in main code paths

**This month:**
- Prometheus metrics live
- Decision engine refactored
- 95%+ test coverage

---

## 📞 Need Help?

- **Questions:** See GitHub Issues
- **Technical Debt Analysis:** See REFACTORING_SUMMARY.md
- **Migration Guides:** See docs/migration/
- **Architecture:** See CLAUDE.md

---

**Remember:** Small, incremental improvements compound. Each hour invested in technical debt reduction saves 10+ hours of future maintenance.

_Last updated: 2025-12-13_
