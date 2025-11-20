# Finance Feedback Engine 2.0 - Examples

This directory contains example scripts demonstrating various features and extension patterns for the Finance Feedback Engine.

## Available Examples

### 1. `custom_platform.py` - Adding a Custom Trading Platform

Demonstrates how to extend the engine with a new trading platform integration.

**Run:**
```bash
python examples/custom_platform.py
```

**What it shows:**
- Creating a new platform class
- Implementing required methods
- Registering the platform with the factory
- Using the platform in your application

**Use case:** Add support for platforms like Binance, Kraken, or any other exchange.

---

### 2. `oanda_forex_example.py` - Oanda Forex Trading with Portfolio Context

Demonstrates Oanda integration for forex trading with comprehensive portfolio tracking.

**Run:**
```bash
python examples/oanda_forex_example.py
```

**What it shows:**
- Setting up Oanda platform connection
- Viewing forex portfolio breakdown (positions, P&L, margin)
- Analyzing forex pairs with AI
- Context-aware trading decisions with portfolio exposure

**Requirements:**
- Oanda account (practice or live)
- `pip install oandapyV20`
- Valid API credentials in config

**Use case:** Professional forex trading with real-time portfolio tracking and AI-powered analysis.

---

### 3. `ensemble_example.py` - Multi-Provider AI Ensemble

Demonstrates ensemble decision making with multiple AI providers.

**Run:**
```bash
python examples/ensemble_example.py
```

**What it shows:**
- Combining multiple AI providers (Local LLM, Copilot CLI, Codex CLI, Qwen)
- Weighted voting strategies
- Agreement scoring and confidence variance
- Adaptive learning with provider weight updates

**Use case:** Increase decision confidence by aggregating multiple AI opinions.

---

### 4. `position_sizing_example.py` - Advanced Position Sizing

Demonstrates position sizing calculations for long/short trades.

**Run:**
```bash
python examples/position_sizing_example.py
```

**What it shows:**
- Risk-based position sizing (1% risk default)
- Stop loss placement (2% default)
- Long vs short position calculations
- Entry price and margin requirements

**Use case:** Proper risk management for trading strategies.

---

### 5. `sentiment_macro_example.py` - Market Sentiment and Macro Analysis

Demonstrates enriched market data with sentiment and macroeconomic indicators.

**Run:**
```bash
python examples/sentiment_macro_example.py
```

**What it shows:**
- News sentiment analysis (bullish/bearish/neutral)
- Macroeconomic indicators (GDP, inflation, Fed funds, unemployment)
- Technical indicators (RSI, candlestick patterns)
- Comprehensive market context for AI decisions

**Use case:** Fundamentals-driven trading with sentiment and macro context.

---

## Creating Your Own Examples

When creating examples:

1. **Import the package correctly:**
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent))
   from finance_feedback_engine import FinanceFeedbackEngine
   ```

2. **Make them self-contained:** Include all necessary configuration in the script

3. **Add clear documentation:** Explain what the example demonstrates

4. **Make them executable:**
   ```bash
   chmod +x examples/your_example.py
   ```

## Example Ideas

Here are some ideas for additional examples:

- **Custom AI Provider**: Integrate OpenAI, Anthropic, or local LLM
- **Backtesting**: Test strategies against historical data
- **Multi-Asset Portfolio**: Analyze and balance multiple assets
- **Risk Management**: Implement stop-loss and take-profit strategies
- **Automated Trading Bot**: Run continuous analysis and execution
- **Custom Data Provider**: Add support for different market data sources
- **Notification System**: Send alerts via email, SMS, or messaging apps

## Running Examples

All examples can be run directly:

```bash
python examples/custom_platform.py
```

Or make them executable and run:

```bash
chmod +x examples/*.py
./examples/custom_platform.py
```

## Need Help?

- Check the main [README.md](../README.md)
- Read the [USAGE.md](../USAGE.md) guide
- Review the source code documentation
- Open an issue on GitHub
