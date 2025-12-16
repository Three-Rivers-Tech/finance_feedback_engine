# Platform Switching Guide

Quick reference for switching between Coinbase Advanced (crypto) and Oanda (forex) in your local configuration.

## Current Setup

Your configuration files are now unified:
- **`config/config.yaml`** - Master template with all platforms documented
- **`config/config.local.yaml`** - Your active configuration (gitignored)
- **`config/examples/oanda.yaml`** - Standalone Oanda-only example for testing

## Switch to Oanda (Forex Trading)

Edit `config/config.local.yaml`:

```yaml
# Change platform
trading_platform: "oanda"

# Comment out Coinbase credentials
platform_credentials:
  # api_key: "organizations/..."
  # api_secret: "-----BEGIN EC PRIVATE KEY REDACTED-----..."
  # use_sandbox: false

  # Uncomment and configure Oanda
  api_key: "YOUR_OANDA_API_TOKEN"
  account_id: "YOUR_OANDA_ACCOUNT_ID"
  environment: "practice"  # or "live"
```

Then verify:
```bash
python main.py status
python main.py dashboard  # View forex positions & margin
python main.py analyze EUR_USD
```

## Switch to Coinbase Advanced (Crypto)

Edit `config/config.local.yaml`:

```yaml
# Change platform
trading_platform: "coinbase_advanced"

# Comment out Oanda credentials
platform_credentials:
  # api_key: "YOUR_OANDA_API_TOKEN"
  # account_id: "YOUR_OANDA_ACCOUNT_ID"
  # environment: "practice"

  # Uncomment and configure Coinbase
  api_key: "organizations/..."
  api_secret: "-----BEGIN EC PRIVATE KEY REDACTED-----..."
  use_sandbox: false
```

Then verify:
```bash
python main.py status
python main.py dashboard  # View crypto futures positions
python main.py analyze BTCUSD
```

## Platform Differences

### Coinbase Advanced (Crypto Futures)
- **Assets**: BTCUSD, ETHUSD (crypto futures)
- **Portfolio**: Futures positions, margin, P&L
- **Library**: `coinbase-advanced-py`
- **Format**: Asset pairs without underscore

### Oanda (Forex)
- **Assets**: EUR_USD, GBP_USD (forex pairs)
- **Portfolio**: Currency positions, margin, exposure
- **Library**: `oandapyV20`
- **Format**: Asset pairs WITH underscore
- **Environments**: Practice (demo) or Live (real money)

## Testing Standalone Oanda Config

To test Oanda in isolation without modifying your main config:

```bash
python main.py -c config/examples/oanda.yaml status
python main.py -c config/examples/oanda.yaml portfolio
python main.py -c config/examples/oanda.yaml analyze EUR_USD
```

## Configuration Hierarchy

When you run `python main.py`:

1. **Default**: Uses `config/config.yaml`
2. **If exists**: Auto-selects `config/config.local.yaml`
3. **Override**: Use `-c path/to/config.yaml` flag

This means your `config.local.yaml` is automatically used when present!

## Quick Commands

```bash
# Check which platform is active
python main.py status

# View portfolio (both platforms)
python main.py dashboard

# Crypto analysis (Coinbase)
python main.py analyze BTCUSD

# Forex analysis (Oanda)
python main.py analyze EUR_USD

# Use specific config
python main.py -c config/examples/oanda.yaml status
```

## Common Issues

### Wrong Asset Format
- **Crypto**: `BTCUSD` (no underscore)
- **Forex**: `EUR_USD` (with underscore)

### Library Not Installed
```bash
# For Oanda
pip install oandapyV20

# For Coinbase
pip install coinbase-advanced-py
```

### Wrong Credentials Active
Check `config/config.local.yaml`:
- Only one set of credentials should be active (uncommented)
- Others should be commented out with `#`
- Match `trading_platform` to active credentials

## Multi-Platform Setup

To quickly switch between platforms, keep both credentials in `config.local.yaml`:

```yaml
trading_platform: "coinbase_advanced"  # <-- Change this line only

platform_credentials:
  # === ACTIVE: Coinbase ===
  api_key: "organizations/..."
  api_secret: "-----BEGIN..."
  use_sandbox: false

  # === INACTIVE: Oanda (comment when using Coinbase) ===
  # api_key: "YOUR_OANDA_TOKEN"
  # account_id: "001-XXX-XXX"
  # environment: "practice"
```

Then just change the `trading_platform` line and swap which credentials are commented!

## See Also

- `docs/OANDA_INTEGRATION.md` - Comprehensive Oanda guide
- `docs/PORTFOLIO_TRACKING.md` - Coinbase portfolio features
- `README.md` - General setup and usage
- `USAGE.md` - CLI commands reference
