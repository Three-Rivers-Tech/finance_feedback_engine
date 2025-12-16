# Enhanced Market Context: Sentiment & Macroeconomic Data

## Overview

The Finance Feedback Engine now incorporates **news sentiment analysis** and **macroeconomic indicators** from Alpha Vantage, providing AI models with comprehensive market context for better-informed trading decisions.

## New Features

### 1. News Sentiment Analysis

**What it provides:**
- Overall sentiment (Bullish/Bearish/Neutral)
- Sentiment score (-1.0 to +1.0 scale)
- Number of news articles analyzed
- Top topics from news coverage

**Data source:** Alpha Vantage NEWS_SENTIMENT API

**Example output:**
```
NEWS SENTIMENT ANALYSIS:
Overall Sentiment: NEUTRAL
Sentiment Score: +0.037 (range: -1 to +1)
News Articles Analyzed: 50
Top Topics: Financial Markets, Blockchain, Economy - Monetary

Sentiment Interpretation:
- Positive (>0.15): Bullish news momentum
- Negative (<-0.15): Bearish news momentum
- Neutral (-0.15 to 0.15): Mixed or balanced coverage
```

### 2. Macroeconomic Indicators

**What it provides:**
- Real GDP
- Inflation rate
- Federal Funds Rate
- Unemployment rate

**Data source:** Alpha Vantage Economic Indicators API

**Example output:**
```
MACROECONOMIC CONTEXT:
Real GDP: 23358.435 (as of 2024-01-01)
Inflation: 2.95% (as of 2024-01-01)
Federal Funds Rate: 4.09 (as of 2025-10-01)

Macro Impact Considerations:
- High inflation: May favor real assets (crypto/commodities) over fiat
- Rising rates: Typically bearish for risk assets
- Strong GDP: Generally positive for markets
- High unemployment: May signal economic weakness
```

### 3. Enhanced Technical Analysis

**Already included:**
- Candlestick pattern analysis (body size, wicks)
- Price trend direction (bullish/bearish/neutral)
- Price position in daily range
- RSI indicator (14-period)
- Volatility calculations

**New additions:**
- Price range percentage
- Upper/lower wick analysis
- Close position relative to range

## Implementation Details

### Alpha Vantage Provider Methods

**`get_news_sentiment(asset_pair, limit=5)`**
- Fetches recent news articles about the asset
- Calculates average sentiment score
- Extracts top topics from coverage
- Returns structured sentiment data

**`get_macro_indicators(indicators=None)`**
- Fetches key economic indicators
- Default: GDP, Inflation, Fed Funds Rate, Unemployment
- Returns latest values with dates

**`get_comprehensive_market_data(asset_pair, include_sentiment=True, include_macro=False)`**
- One-stop method for all market context
- Combines price + technical + sentiment + macro
- Configurable to control API calls

### Decision Engine Integration

The enhanced AI prompt now includes:

1. **Price Data Section**
   - OHLC with date
   - Price change %
   - Price range analysis

2. **Candlestick Analysis Section**
   - Trend direction
   - Body size and percentage
   - Upper/lower wick sizes
   - Close position in range

3. **Technical Indicators Section** (if available)
   - RSI with signal (overbought/oversold/neutral)

4. **News Sentiment Section** (if available)
   - Overall sentiment classification
   - Numeric score
   - Article count
   - Top topics
   - Interpretation guide

5. **Macroeconomic Context Section** (if available)
   - Key indicators with latest values
   - Impact considerations for trading

6. **Analysis Guidelines**
   - How to integrate all signals
   - Handling conflicting signals
   - Sentiment + technical synthesis

## Usage Examples

### Basic Analysis (with sentiment, default)
```python
from finance_feedback_engine.core import FinanceFeedbackEngine

config = {...}  # Your config
engine = FinanceFeedbackEngine(config)

# Automatically includes sentiment
decision = engine.analyze_asset('BTCUSD')
```

### Analysis with Macro Indicators
```python
# Include macroeconomic context
decision = engine.analyze_asset('BTCUSD', include_macro=True)
```

### CLI Usage
```bash
# Standard analysis (includes sentiment)
python main.py analyze BTCUSD

# Output now shows:
# - Price data
# - Technical analysis
# - News sentiment (if available)
# - Macro indicators (if enabled)
```

### Direct Provider Access
```python
from finance_feedback_engine.data_providers.alpha_vantage_provider import AlphaVantageProvider

provider = AlphaVantageProvider(api_key='your_key')

# Get sentiment only
sentiment = provider.get_news_sentiment('BTCUSD', limit=10)
print(f"Sentiment: {sentiment['overall_sentiment']}")
print(f"Score: {sentiment['sentiment_score']}")

# Get macro only
macro = provider.get_macro_indicators()
for indicator, data in macro['indicators'].items():
    print(f"{indicator}: {data['value']}")

# Get everything
full_data = provider.get_comprehensive_market_data(
    'BTCUSD',
    include_sentiment=True,
    include_macro=True
)
```

## Decision Synthesis

The AI now considers multiple signal types:

### Strong BUY Signals
- Bullish price trend
- RSI oversold (<30)
- Positive news sentiment (>0.15)
- Favorable macro environment

### Strong SELL Signals
- Bearish price trend
- RSI overbought (>70)
- Negative news sentiment (<-0.15)
- Unfavorable macro conditions

### HOLD Signals
- Mixed technical signals
- Neutral sentiment (-0.15 to 0.15)
- Conflicting indicators
- High uncertainty

## Example Scenario

```
Asset: BTCUSD
Price: $92,183.78 (Bearish trend)
RSI: 33.10 (Neutral, approaching oversold)
Sentiment: Neutral (+0.028)
Macro: Fed Funds Rate 4.09% (elevated)

AI Analysis:
"Bearish price action with RSI approaching oversold territory suggests
potential for a bounce. However, neutral sentiment and elevated interest
rates create uncertainty. Recommend HOLD with close monitoring. If RSI
drops below 30 with improving sentiment, consider small long position."
```

## Performance Considerations

- **API Rate Limits:** Alpha Vantage has rate limits (5 calls/min free tier)
- **Sentiment fetching:** Adds ~1-2 seconds to analysis
- **Macro fetching:** Adds ~2-3 seconds (queries multiple endpoints)
- **Recommendation:** Enable sentiment by default, macro on-demand

## Configuration

Control features via `FinanceFeedbackEngine.analyze_asset()`:

```python
# Sentiment only (default, faster)
decision = engine.analyze_asset('BTCUSD', include_sentiment=True, include_macro=False)

# Full context (slower, more comprehensive)
decision = engine.analyze_asset('BTCUSD', include_sentiment=True, include_macro=True)

# Price + technicals only (fastest)
decision = engine.analyze_asset('BTCUSD', include_sentiment=False, include_macro=False)
```

## Benefits

1. **Holistic View:** Combines price, technicals, sentiment, and macro
2. **Better Decisions:** AI has full context, not just price data
3. **Risk Awareness:** Macro factors highlight systemic risks
4. **Sentiment Edge:** News analysis provides leading indicators
5. **Transparency:** All factors visible in decision reasoning

## Testing

Run the demonstration:
```bash
python examples/sentiment_macro_example.py
```

Shows:
- Live sentiment analysis for BTC/ETH
- Macro indicator retrieval
- Comprehensive data synthesis
- Signal interpretation

## Real-World Application

**Scenario 1: Bullish Setup**
- Price: Strong uptrend
- RSI: 45 (neutral)
- Sentiment: Bullish (+0.28)
- Macro: Inflation rising
→ **BUY SIGNAL** (crypto may benefit from inflation hedge narrative)

**Scenario 2: Bearish Setup**
- Price: Downtrend
- RSI: 75 (overbought)
- Sentiment: Bearish (-0.22)
- Macro: Fed raising rates
→ **SELL SIGNAL** (multiple bearish factors aligned)

**Scenario 3: Mixed Signals**
- Price: Sideways
- RSI: 50 (neutral)
- Sentiment: Neutral (+0.05)
- Macro: Stable
→ **HOLD** (no clear directional bias)

## Future Enhancements

Potential additions:
- Social media sentiment (Twitter, Reddit)
- On-chain metrics (for crypto)
- Correlation analysis across assets
- Sentiment momentum (change over time)
- Macro forecast integration
- Custom sentiment sources

---

The Finance Feedback Engine now provides AI models with the same comprehensive context that professional traders use: price action, technical indicators, news sentiment, and macroeconomic backdrop. This multi-dimensional approach leads to more informed, nuanced trading decisions.
