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
