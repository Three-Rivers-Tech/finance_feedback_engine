# Finance Feedback Engine 2.0 - Demo Summary

## Demos Successfully Run

### 1. **New Features Demo** (`demo_features.py`)
Showcased the latest additions to the engine:

#### News Sentiment Analysis 📰
- Real-time sentiment from Alpha Vantage NEWS_SENTIMENT API
- Sentiment scores (-1.0 to +1.0 range)
- Article counts and topic analysis
- Example: BTCUSD sentiment score: -0.027 (neutral)

#### Macroeconomic Indicators 📊
- Real GDP, inflation, Fed rates, unemployment
- Provides broader market context
- Helps AI understand economic environment

#### Dynamic Weight Adjustment 🔄
- Automatic handling of AI provider failures
- Weight renormalization (0.67 + 0.33 = 1.00)
- Maintains decision quality with partial provider availability
- All failures tracked in metadata

#### Comprehensive Market Analysis 📈
- Combined price + technical + sentiment data
- Live BTC price: $92,392.63
- RSI, candlestick patterns, volatility

#### Position Sizing 💰
- Risk-based position calculation
- 1% risk / 2% stop-loss formula
- Example: 0.0526 BTC position on $10k account

---

### 2. **Oanda Forex Demo** (`demo_oanda_features.py`)
Comprehensive forex trading capabilities:

#### Forex Market Data
- Major pairs: EUR_USD, GBP_USD, USD_JPY
- Cross pairs: EUR_GBP, AUD_JPY, GBP_JPY
- Exotic pairs: USD_MXN, EUR_TRY, USD_ZAR
- Example: EUR/USD @ 1.08450 (+0.12%)

#### Portfolio Breakdown
- Total NAV: $50,000
- Unrealized P&L: $1,500
- Margin used: $5,000 (10% leverage)
- Open positions tracking:
  - EUR_USD LONG 100,000 units (+$850)
  - GBP_USD SHORT -50,000 units (+$320)
  - USD_JPY LONG 75,000 units (+$330)

#### Currency Exposure Tracking
- USD: 48.5%
- EUR: 30.0%
- GBP: 15.0%
- JPY: 6.5%

#### Context-Aware AI Decisions
- AI receives full portfolio context
- Considers current positions
- Evaluates currency exposure
- Monitors margin usage
- Assesses correlation risk

#### Forex Position Sizing
- Account: $50,000
- Risk: 1.0% per trade
- Stop: 50 pips
- Result: 100,000 units (1 standard lot)
- Margin: $2,169 (2% margin requirement)

---

## Key Features Summary

### Data Enrichment
✓ News sentiment analysis
✓ Macroeconomic indicators
✓ Technical indicators (RSI, trends)
✓ Candlestick pattern analysis

### AI Ensemble System
✓ Multi-provider support (local, CLI, Codex, Qwen)
✓ Dynamic weight adjustment
✓ Automatic failure handling
✓ Weighted/majority/stacking strategies

### Trading Platforms
✓ Coinbase Advanced (crypto)
✓ Oanda (forex)
✓ Extensible platform factory
✓ Portfolio breakdown support

### Risk Management
✓ Position sizing calculations
✓ Risk percentage controls (1%)
✓ Stop-loss settings (2%)
✓ Margin monitoring

---

## Available Demo Scripts

| Script | Purpose |
|--------|---------|
| `demo_features.py` | New features showcase |
| `demo_oanda_features.py` | Oanda forex capabilities |
| `demo_new_features.sh` | Interactive bash demo |
| `demo.sh` | Basic CLI demo |
| `examples/sentiment_macro_example.py` | Sentiment & macro data |
| `examples/dynamic_weight_adjustment_example.py` | Ensemble resilience |
| `examples/oanda_forex_example.py` | Oanda integration |
| `examples/position_sizing_example.py` | Risk management |

---

## How to Run Demos

### Quick Start
```bash
# New features demo
python demo_features.py

# Oanda forex demo
python demo_oanda_features.py

# Interactive bash demo
bash demo_new_features.sh
```

### Individual Examples
```bash
# Sentiment analysis
python examples/sentiment_macro_example.py

# Dynamic weights
python examples/dynamic_weight_adjustment_example.py

# Oanda forex
python examples/oanda_forex_example.py
```

### CLI Commands
```bash
# Analyze asset
python main.py analyze BTCUSD

# Check balance
python main.py balance

# View portfolio
python main.py dashboard

# Decision history
python main.py history --limit 10

# Engine status
python main.py status
```

---

## Documentation

- **SENTIMENT_MACRO_FEATURES.md** - News & macro data integration
- **DYNAMIC_WEIGHT_ADJUSTMENT_QUICKREF.md** - Ensemble failure handling
- **docs/ENSEMBLE_SYSTEM.md** - Multi-provider AI system
- **docs/OANDA_INTEGRATION.md** - Forex trading setup
- **docs/PORTFOLIO_TRACKING.md** - Portfolio management
- **POSITION_SIZING_CHANGES.md** - Risk management details

---

## Setup for Live Trading

### Oanda Forex Trading
1. Create account: https://www.oanda.com/
2. Install library: `pip install oandapyV20`
3. Configure `config/config.local.yaml`:
   ```yaml
   trading_platform: 'oanda'
   platform_credentials:
     api_key: 'YOUR_API_KEY'
     account_id: 'YOUR_ACCOUNT_ID'
     environment: 'practice'
   ```

### Alpha Vantage API
Get free API key: https://www.alphavantage.co/support/#api-key

---

**Demo Date:** November 20, 2025
**Engine Version:** 2.0.0
**Status:** ✅ All demos successful
