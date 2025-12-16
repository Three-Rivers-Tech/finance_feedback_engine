# Finance Feedback Engine 2.0 - Usage Guide

## Table of Contents
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [CLI Commands](#cli-commands)
- [Python API](#python-api)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up configuration:**
   ```bash
   cp config/config.yaml config/config.local.yaml
   ```

3. **Edit configuration with your credentials:**
   ```bash
   nano config/config.local.yaml
   ```

### First Run

Test your configuration:

```bash
python main.py status
```

This will verify that your configuration is valid and the engine can initialize.

## Configuration

### Using YAML Configuration

The default configuration file is `config/config.yaml`. Create a local version:

```yaml
alpha_vantage_api_key: "YOUR_KEY"
trading_platform: "coinbase"
platform_credentials:
  api_key: "YOUR_API_KEY"
  api_secret: "YOUR_SECRET"
decision_engine:
  ai_provider: "local"
  decision_threshold: 0.7
persistence:
  storage_path: "data/decisions"
```

### Using Environment Variables

You can also use environment variables (recommended for production):

```bash
export ALPHA_VANTAGE_API_KEY="your_key"
export COINBASE_API_KEY="your_key"
export COINBASE_API_SECRET="your_secret"
```

Then reference them in your config:

```yaml
alpha_vantage_api_key: ${ALPHA_VANTAGE_API_KEY}
```

## CLI Commands

### 1. Analyze an Asset

Analyze a cryptocurrency or forex pair and generate a trading decision.

**Flexible Input Formats** - The engine automatically standardizes asset pairs to uppercase without separators:

```bash
# Analyze Bitcoin (all formats work!)
python main.py analyze BTCUSD       # Standard format
python main.py analyze btc-usd      # Lowercase with dash
python main.py analyze BTC_USD      # Underscore separator
python main.py analyze "BTC/USD"    # Slash separator (quotes needed)

# Analyze Ethereum (any format)
python main.py analyze ETHUSD
python main.py analyze eth-usd
python main.py analyze ETH_USD

# Analyze EUR/USD forex pair (various formats)
python main.py analyze EURUSD
python main.py analyze eur_usd      # Common forex format
python main.py analyze EUR-USD
python main.py analyze "EUR/USD"
```

> **Note**: All formats are automatically converted to uppercase without separators (e.g., `btc-usd` → `BTCUSD`).
> See [docs/ASSET_PAIR_VALIDATION.md](docs/ASSET_PAIR_VALIDATION.md) for complete details.

**Output:**
```
Analyzing BTCUSD...

Trading Decision Generated
Decision ID: 550e8400-e29b-41d4-a716-446655440000
Asset: BTCUSD
Action: BUY
Confidence: 75%
Reasoning: Price dropped, good buying opportunity.
Suggested Amount: 0.1

Market Data:
  Close: $45000.00
  High: $46000.00
  Low: $44500.00
  Price Change: -2.50%
  Volatility: 3.25%
```

### 2. Check Account Balance

View your current trading account balances:

```bash
python main.py balance
```

**Output:**
```
┌─────────┬──────────────┐
│ Asset   │      Balance │
├─────────┼──────────────┤
│ USD     │   10,000.00 │
│ BTC     │        0.50 │
│ ETH     │        2.00 │
└─────────┴──────────────┘
```

### 3. View Decision History

See your past trading decisions:

```bash
# View last 10 decisions
python main.py history

# View last 20 decisions
python main.py history --limit 20

# Filter by specific asset
python main.py history --asset BTCUSD --limit 5
```

**Output:**
```
┌──────────┬─────────┬────────┬────────────┬──────────┐
│ Time     │ Asset   │ Action │ Confidence │ Executed │
├──────────┼─────────┼────────┼────────────┼──────────┤
│ 14:30:00 │ BTCUSD  │ BUY    │       75% │ ✗        │
│ 13:15:00 │ ETHUSD  │ HOLD   │       60% │ ✗        │
│ 12:00:00 │ EURUSD  │ SELL   │       80% │ ✓        │
└──────────┴─────────┴────────┴────────────┴──────────┘
```

### 4. Execute a Decision

Execute a previously generated trading decision:

```bash
python main.py execute 550e8400-e29b-41d4-a716-446655440000
```

**Output:**
```
Executing decision 550e8400-e29b-41d4-a716-446655440000...
✓ Trade executed successfully
Platform: coinbase_advanced
Message: Trade execution simulation (not implemented)
```

### 5. Check Engine Status

Verify your configuration and engine status:

```bash
python main.py status
```

**Output:**
```
Finance Feedback Engine Status

Trading Platform: coinbase
AI Provider: local
Storage Path: data/decisions

✓ Engine initialized successfully
```

### 6. Verbose Mode

Enable detailed logging for any command:

```bash
python main.py -v analyze BTCUSD
python main.py --verbose balance
```

### 7. Custom Configuration File

Use a different configuration file:

```bash
python main.py -c config/config.oanda.example.yaml status
python main.py --config config/my_custom_config.yaml analyze EURUSD
```

## Safety & Execution Modes

The engine provides safeguards to prevent unsafe automated executions. Operators should understand two key features:

- **`signal_only` mode**: When enabled on a decision (`signal_only: true`) the engine will not execute orders and will treat the output as a signal only. This is useful for dry-run, simulation, or when the platform credentials are unavailable.

- **Circuit Breaker (execution safety)**: The engine wraps platform `execute_trade` calls with a process-local circuit breaker that tracks recent failures and will temporarily open if repeated errors occur. This prevents cascading failures during noisy platform outages or repeated execution errors.

Example conservative config snippets (in `config/config.local.yaml`):

```yaml
# Prevent live execution by default in development
signal_only_default: true

# Safety thresholds used during pre-execution monitoring checks
safety:
    max_leverage: 5.0           # block execution above this leverage estimate
    max_position_pct: 25.0      # block execution if largest position > this percent

# Circuit breaker tuning (process-local)
circuit_breaker:
    failure_threshold: 3        # number of consecutive failures to open the breaker
    recovery_timeout_seconds: 300
    half_open_retry: 1
```

Operational notes:

- If the monitoring provider is temporarily unavailable (network timeout or connection error), the engine will log a warning and proceed cautiously using conservative defaults, rather than failing hard. Unexpected monitoring errors or critical configuration problems will raise and block execution so operators can address them.
- To run the engine in purely signal-only mode use `signal_only_default: true` in your local config or pass `--signal-only` if the CLI supports it.
- Circuit breaker state is process-local; restarting the engine resets the breaker. For long-lived deployments consider external health checks and operator alerts.

## Python API

### Basic Usage

```python
from finance_feedback_engine import FinanceFeedbackEngine

# Load configuration
config = {
    'alpha_vantage_api_key': 'YOUR_KEY',
    'trading_platform': 'coinbase',
    'platform_credentials': {
        'api_key': 'YOUR_API_KEY',
        'api_secret': 'YOUR_SECRET'
    },
    'decision_engine': {
        'ai_provider': 'local'
    },
    'persistence': {
        'storage_path': 'data/decisions'
    }
}

# Initialize engine
engine = FinanceFeedbackEngine(config)

# Analyze an asset
decision = engine.analyze_asset('BTCUSD')
print(f"Action: {decision['action']}")
print(f"Confidence: {decision['confidence']}%")

# Get balance
balance = engine.get_balance()
print(f"USD Balance: ${balance['USD']}")

# View history
history = engine.get_decision_history(limit=5)
for d in history:
    print(f"{d['asset_pair']}: {d['action']} ({d['confidence']}%)")
```

### Advanced Usage

```python
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.trading_platforms import PlatformFactory

# Create custom configuration
config = {
    'alpha_vantage_api_key': 'YOUR_KEY',
    'trading_platform': 'oanda',
    'platform_credentials': {
        'api_key': 'YOUR_KEY',
        'account_id': 'YOUR_ACCOUNT',
        'environment': 'practice'
    },
    'decision_engine': {
        'ai_provider': 'cli',
        'decision_threshold': 0.8
    },
    'persistence': {
        'storage_path': 'data/forex_decisions'
    }
}

engine = FinanceFeedbackEngine(config)

# Analyze multiple assets
assets = ['EURUSD', 'GBPUSD', 'USDJPY']
for asset in assets:
    decision = engine.analyze_asset(asset)
    if decision['confidence'] > 75:
        print(f"High confidence decision: {asset} - {decision['action']}")
```

## Advanced Usage

### Custom AI Provider

Implement your own AI provider:

```python
from finance_feedback_engine.decision_engine import DecisionEngine

class CustomDecisionEngine(DecisionEngine):
    def _query_ai(self, prompt):
        # Your custom AI logic here
        # Could integrate with OpenAI, Anthropic, etc.
        response = your_ai_model.query(prompt)
        return {
            'action': response.action,
            'confidence': response.confidence,
            'reasoning': response.reasoning,
            'amount': response.amount
        }
```

### Custom Trading Platform

Add support for a new trading platform:

```python
from finance_feedback_engine.trading_platforms import BaseTradingPlatform, PlatformFactory

class KrakenPlatform(BaseTradingPlatform):
    def __init__(self, credentials):
        super().__init__(credentials)
        # Initialize Kraken API client

    def get_balance(self):
        # Implement Kraken balance fetching
        pass

    def execute_trade(self, decision):
        # Implement Kraken trade execution
        pass

    def get_account_info(self):
        # Implement Kraken account info
        pass

# Register the new platform
PlatformFactory.register_platform('kraken', KrakenPlatform)
```

### Automated Trading Loop

Create an automated trading bot:

```python
import time
from finance_feedback_engine import FinanceFeedbackEngine

engine = FinanceFeedbackEngine(config)

assets = ['BTCUSD', 'ETHUSD']

while True:
    for asset in assets:
        try:
            decision = engine.analyze_asset(asset)

            # Only execute high-confidence decisions
            if decision['confidence'] > 80:
                print(f"Executing: {asset} - {decision['action']}")
                engine.execute_decision(decision['id'])
            else:
                print(f"Low confidence, skipping: {asset}")

        except Exception as e:
            print(f"Error analyzing {asset}: {e}")

    # Wait 5 minutes before next analysis
    time.sleep(300)
```

## Troubleshooting

### Issue: "Alpha Vantage API key is required"

**Solution:** Make sure you've set your API key in the configuration file:
```yaml
alpha_vantage_api_key: "YOUR_KEY"
```

### Issue: "Platform 'xyz' not supported"

**Solution:** Check available platforms:
```python
from finance_feedback_engine.trading_platforms import PlatformFactory
print(PlatformFactory.list_platforms())
```

Supported platforms: `coinbase`, `coinbase_advanced`, `oanda`

### Issue: Configuration file not found

**Solution:** Specify the full path:
```bash
python main.py -c /full/path/to/config.yaml status
```

### Issue: Mock data being returned

If you see `"mock": True` in market data, it means:
- Alpha Vantage API returned unexpected format
- API rate limit exceeded
- Invalid API key

**Solution:**
- Verify your API key
- Check Alpha Vantage dashboard for rate limits
- Use premium API key for higher limits

### Issue: Trade execution not working

The current implementation uses mock execution. To enable real trading:
1. Implement actual API calls in platform classes
2. Add proper authentication
3. Test thoroughly with sandbox/practice accounts

### Debug Mode

Enable verbose logging to debug issues:

```bash
python main.py -v analyze BTCUSD
```

Or in Python:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Best Practices

1. **Start with practice accounts** - Always test with sandbox/practice environments
2. **Monitor API rate limits** - Alpha Vantage free tier has limits
3. **Review decisions before executing** - Check decision history regularly
4. **Set confidence thresholds** - Only execute high-confidence decisions
5. **Keep credentials secure** - Use environment variables, never commit secrets
6. **Regular backups** - Backup your decision history periodically
7. **Test thoroughly** - Test all changes in a safe environment

## Getting Help

- Check the [README.md](README.md) for general information
- Review example configurations in `config/` directory
- Open an issue on GitHub for bugs or feature requests
- Read the source code documentation for detailed API information
