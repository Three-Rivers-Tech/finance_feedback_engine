"""Alpha Vantage data provider module."""

from typing import Dict, Any, Optional
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class AlphaVantageProvider:
    """
    Data provider for Alpha Vantage Premium API.
    
    Supports various asset types including cryptocurrencies and forex.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key (premium recommended)
        """
        if not api_key:
            raise ValueError("Alpha Vantage API key is required")
        self.api_key = api_key
        logger.info("Alpha Vantage provider initialized")

    def get_market_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch market data for a given asset pair.

        Args:
            asset_pair: Asset pair (e.g., 'BTCUSD', 'EURUSD')

        Returns:
            Dictionary containing market data
        """
        logger.info("Fetching market data for %s", asset_pair)
        
        # Determine asset type and fetch appropriate data
        if 'BTC' in asset_pair or 'ETH' in asset_pair:
            market_data = self._get_crypto_data(asset_pair)
        else:
            market_data = self._get_forex_data(asset_pair)
        
        # Enrich with additional context
        market_data = self._enrich_market_data(market_data, asset_pair)
        
        return market_data

    # ------------------------------------------------------------------
    # Historical Batch Data
    # ------------------------------------------------------------------
    def get_historical_data(
        self,
        asset_pair: str,
        start: str,
        end: str,
    ) -> list:
        """Return a list of daily OHLC dictionaries within [start,end].

        Uses a single Alpha Vantage call (DIGITAL_CURRENCY_DAILY or FX_DAILY)
        then slices the requested date range. Falls back to synthetic mock
        candles if API fails. Each candle dict keys: date, open, high, low,
        close.
        """
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end, "%Y-%m-%d").date()
            if end_dt < start_dt:
                raise ValueError("End date precedes start date")

            # Decide endpoint by asset type (reuse logic from get_market_data)
            if 'BTC' in asset_pair or 'ETH' in asset_pair:
                # Crypto
                if asset_pair.endswith('USD'):
                    symbol = asset_pair[:-3]
                    market = 'USD'
                else:
                    symbol = asset_pair[:3]
                    market = asset_pair[3:]
                params = {
                    'function': 'DIGITAL_CURRENCY_DAILY',
                    'symbol': symbol,
                    'market': market,
                    'apikey': self.api_key,
                }
                response = requests.get(
                    self.BASE_URL, params=params, timeout=15
                )
                response.raise_for_status()
                data = response.json()
                series_key = 'Time Series (Digital Currency Daily)'
            else:
                from_currency = asset_pair[:3]
                to_currency = asset_pair[3:]
                params = {
                    'function': 'FX_DAILY',
                    'from_symbol': from_currency,
                    'to_symbol': to_currency,
                    'apikey': self.api_key,
                }
                response = requests.get(
                    self.BASE_URL, params=params, timeout=15
                )
                response.raise_for_status()
                data = response.json()
                series_key = 'Time Series FX (Daily)'

            if series_key not in data:
                logger.warning(
                    "Historical data unexpected format for %s", asset_pair
                )
                return self._generate_mock_series(start_dt, end_dt)

            time_series = data[series_key]
            candles = []
            for date_str, day_data in time_series.items():
                day_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
                if day_dt < start_dt or day_dt > end_dt:
                    continue
                # Field name differences for crypto vs forex
                o_val = (
                    day_data.get('1a. open (USD)')
                    or day_data.get('1. open')
                    or day_data.get('1. open', 0)
                )
                h_val = (
                    day_data.get('2a. high (USD)')
                    or day_data.get('2. high')
                    or day_data.get('2. high', 0)
                )
                low_val = (
                    day_data.get('3a. low (USD)')
                    or day_data.get('3. low')
                    or day_data.get('3. low', 0)
                )
                c_val = (
                    day_data.get('4a. close (USD)')
                    or day_data.get('4. close')
                    or day_data.get('4. close', 0)
                )
                try:
                    candles.append({
                        'date': date_str,
                        'open': float(o_val),
                        'high': float(h_val),
                        'low': float(low_val),
                        'close': float(c_val),
                    })
                except Exception:
                    continue
            # Sort ascending by date
            candles.sort(key=lambda x: x['date'])
            if not candles:
                return self._generate_mock_series(start_dt, end_dt)
            return candles
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Historical data fetch failed for %s: %s", asset_pair, e
            )
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d").date()
                end_dt = datetime.strptime(end, "%Y-%m-%d").date()
                return self._generate_mock_series(start_dt, end_dt)
            except Exception:
                return []

    def _generate_mock_series(self, start_dt, end_dt) -> list:
        """Synthetic daily series fallback (linear drift)."""
        span = (end_dt - start_dt).days + 1
        base = 100.0
        out = []
        for i in range(span):
            from datetime import timedelta
            d = start_dt + timedelta(days=i)
            drift = 1 + (i / span) * 0.02  # +2% over full period
            close = base * drift
            out.append({
                'date': d.isoformat(),
                'open': close * 0.995,
                'high': close * 1.01,
                'low': close * 0.99,
                'close': close,
                'mock': True,
            })
        return out

    def _enrich_market_data(
        self, market_data: Dict[str, Any], asset_pair: str
    ) -> Dict[str, Any]:
        """
        Enrich market data with additional metrics and context.

        Args:
            market_data: Base market data
            asset_pair: Asset pair

        Returns:
            Enriched market data
        """
        try:
            # Calculate additional technical indicators
            open_price = market_data.get('open', 0)
            high_price = market_data.get('high', 0)
            low_price = market_data.get('low', 0)
            close_price = market_data.get('close', 0)
            
            # Price range
            price_range = high_price - low_price
            price_range_pct = (
                (price_range / close_price * 100) if close_price > 0 else 0
            )
            
            # Body vs wick analysis (candlestick)
            body = abs(close_price - open_price)
            body_pct = (body / close_price * 100) if close_price > 0 else 0
            
            # Upper and lower wicks
            upper_wick = high_price - max(open_price, close_price)
            lower_wick = min(open_price, close_price) - low_price
            
            # Trend direction
            is_bullish = close_price > open_price
            trend = (
                "bullish"
                if is_bullish
                else "bearish" if close_price < open_price else "neutral"
            )
            
            # Position in range (where did it close)
            if price_range > 0:
                close_position_in_range = (
                    (close_price - low_price) / price_range
                )
            else:
                close_position_in_range = 0.5
            
            # Add enrichments
            market_data['price_range'] = price_range
            market_data['price_range_pct'] = price_range_pct
            market_data['body_size'] = body
            market_data['body_pct'] = body_pct
            market_data['upper_wick'] = upper_wick
            market_data['lower_wick'] = lower_wick
            market_data['trend'] = trend
            market_data['is_bullish'] = is_bullish
            market_data['close_position_in_range'] = close_position_in_range
            
            # Fetch technical indicators if available
            technical_data = self._get_technical_indicators(asset_pair)
            if technical_data:
                market_data.update(technical_data)
            
        except Exception as e:  # noqa: BLE001
            logger.warning("Error enriching market data: %s", e)
        
        return market_data

    def _get_technical_indicators(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch technical indicators from Alpha Vantage.

        Args:
            asset_pair: Asset pair

        Returns:
            Dictionary with technical indicators
        """
        indicators = {}
        
        try:
            # Determine symbol format
            if 'BTC' in asset_pair or 'ETH' in asset_pair:
                # For crypto, use the base currency
                symbol = asset_pair[:3] if len(asset_pair) > 3 else asset_pair
            else:
                # For forex, we'll skip detailed indicators for now
                return indicators
            
            # Fetch RSI (Relative Strength Index)
            rsi_params = {
                'function': 'RSI',
                'symbol': symbol,
                'interval': 'daily',
                'time_period': 14,
                'series_type': 'close',
                'apikey': self.api_key
            }
            
            rsi_response = requests.get(
                self.BASE_URL, params=rsi_params, timeout=10
            )
            if rsi_response.status_code == 200:
                rsi_data = rsi_response.json()
                if 'Technical Analysis: RSI' in rsi_data:
                    rsi_series = rsi_data['Technical Analysis: RSI']
                    latest_rsi = list(rsi_series.values())[0]
                    indicators['rsi'] = float(latest_rsi.get('RSI', 0))
                    
                    # Interpret RSI
                    if indicators['rsi'] > 70:
                        indicators['rsi_signal'] = 'overbought'
                    elif indicators['rsi'] < 30:
                        indicators['rsi_signal'] = 'oversold'
                    else:
                        indicators['rsi_signal'] = 'neutral'
            
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch technical indicators: %s", e)
        
        return indicators

    def get_news_sentiment(
        self, asset_pair: str, limit: int = 5
    ) -> Dict[str, Any]:
        """
        Fetch news sentiment data from Alpha Vantage.

        Args:
            asset_pair: Asset pair to get news for
            limit: Maximum number of news items

        Returns:
            Dictionary with sentiment analysis
        """
        sentiment_data = {
            'available': False,
            'overall_sentiment': 'neutral',
            'sentiment_score': 0.0,
            'news_count': 0,
            'top_topics': []
        }
        
        try:
            # Extract ticker/symbol
            if 'BTC' in asset_pair:
                tickers = 'CRYPTO:BTC'
            elif 'ETH' in asset_pair:
                tickers = 'CRYPTO:ETH'
            else:
                # For forex, use currency codes
                tickers = asset_pair[:3]
            
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': tickers,
                'apikey': self.api_key,
                'limit': limit
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if 'feed' in data and len(data['feed']) > 0:
                    sentiment_data['available'] = True
                    sentiment_data['news_count'] = len(data['feed'])
                    
                    # Calculate average sentiment
                    sentiment_scores = []
                    topics = []
                    
                    for article in data['feed'][:limit]:
                        # Overall article sentiment
                        overall_score = float(
                            article.get('overall_sentiment_score', 0)
                        )
                        sentiment_scores.append(overall_score)
                        
                        # Extract topics
                        if 'topics' in article:
                            for topic in article['topics']:
                                topics.append(topic.get('topic', ''))
                    
                    # Average sentiment
                    if sentiment_scores:
                        avg_sentiment = (
                            sum(sentiment_scores) / len(sentiment_scores)
                        )
                        sentiment_data['sentiment_score'] = avg_sentiment
                        
                        # Classify sentiment
                        if avg_sentiment > 0.15:
                            sentiment_data['overall_sentiment'] = 'bullish'
                        elif avg_sentiment < -0.15:
                            sentiment_data['overall_sentiment'] = 'bearish'
                        else:
                            sentiment_data['overall_sentiment'] = 'neutral'
                    
                    # Top topics
                    if topics:
                        from collections import Counter
                        topic_counts = Counter(topics)
                        sentiment_data['top_topics'] = [
                            t[0] for t in topic_counts.most_common(3)
                        ]
                
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch news sentiment: %s", e)
        
        return sentiment_data

    def get_macro_indicators(
        self, indicators: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Fetch macroeconomic indicators from Alpha Vantage.

        Args:
            indicators: List of indicators to fetch (default: key indicators)

        Returns:
            Dictionary with macro indicators
        """
        if indicators is None:
            indicators = [
                'REAL_GDP', 'INFLATION', 'FEDERAL_FUNDS_RATE', 'UNEMPLOYMENT'
            ]
        
        macro_data = {
            'available': False,
            'indicators': {}
        }
        
        try:
            for indicator in indicators[:3]:  # Limit to avoid rate limits
                params = {
                    'function': indicator,
                    'apikey': self.api_key
                }
                
                response = requests.get(
                    self.BASE_URL, params=params, timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'data' in data and len(data['data']) > 0:
                        latest = data['data'][0]
                        macro_data['indicators'][indicator] = {
                            'value': latest.get('value', 'N/A'),
                            'date': latest.get('date', 'N/A')
                        }
                        macro_data['available'] = True
                
        except Exception as e:  # noqa: BLE001
            logger.debug("Could not fetch macro indicators: %s", e)
        
        return macro_data

    def get_comprehensive_market_data(
        self,
        asset_pair: str,
        include_sentiment: bool = True,
        include_macro: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch comprehensive market data including price, sentiment, and macro.

        Args:
            asset_pair: Asset pair to analyze
            include_sentiment: Whether to include news sentiment
            include_macro: Whether to include macro indicators

        Returns:
            Comprehensive market data dictionary
        """
        # Get base market data
        market_data = self.get_market_data(asset_pair)
        
        # Add sentiment if requested
        if include_sentiment:
            sentiment = self.get_news_sentiment(asset_pair)
            market_data['sentiment'] = sentiment
        
        # Add macro indicators if requested
        if include_macro:
            macro = self.get_macro_indicators()
            market_data['macro'] = macro
        
        return market_data

    def _get_crypto_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch cryptocurrency data.

        Args:
            asset_pair: Crypto pair (e.g., 'BTCUSD')

        Returns:
            Dictionary containing crypto market data
        """
        # Extract base and quote currencies
        if asset_pair.endswith('USD'):
            symbol = asset_pair[:-3]
            market = 'USD'
        else:
            symbol = asset_pair[:3]
            market = asset_pair[3:]

        params = {
            'function': 'DIGITAL_CURRENCY_DAILY',
            'symbol': symbol,
            'market': market,
            'apikey': self.api_key
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'Time Series (Digital Currency Daily)' in data:
                time_series = data['Time Series (Digital Currency Daily)']
                latest_date = list(time_series.keys())[0]
                latest_data = time_series[latest_date]

                # Try different field name formats (API response varies)
                open_price = float(
                    latest_data.get('1a. open (USD)') or
                    latest_data.get('1. open') or
                    0
                )
                high_price = float(
                    latest_data.get('2a. high (USD)') or
                    latest_data.get('2. high') or
                    0
                )
                low_price = float(
                    latest_data.get('3a. low (USD)') or
                    latest_data.get('3. low') or
                    0
                )
                close_price = float(
                    latest_data.get('4a. close (USD)') or
                    latest_data.get('4. close') or
                    0
                )
                volume = float(latest_data.get('5. volume', 0))
                market_cap = float(
                    latest_data.get('6. market cap (USD)', 0)
                )

                return {
                    'asset_pair': asset_pair,
                    'timestamp': datetime.utcnow().isoformat(),
                    'date': latest_date,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume,
                    'market_cap': market_cap,
                    'type': 'crypto'
                }
            else:
                logger.warning("Unexpected response format: %s", data)
                return self._create_mock_data(asset_pair, 'crypto')

        except Exception as e:  # noqa: BLE001
            logger.error("Error fetching crypto data: %s", e)
            return self._create_mock_data(asset_pair, 'crypto')

    def _get_forex_data(self, asset_pair: str) -> Dict[str, Any]:
        """
        Fetch forex data.

        Args:
            asset_pair: Forex pair (e.g., 'EURUSD')

        Returns:
            Dictionary containing forex market data
        """
        from_currency = asset_pair[:3]
        to_currency = asset_pair[3:]

        params = {
            'function': 'FX_DAILY',
            'from_symbol': from_currency,
            'to_symbol': to_currency,
            'apikey': self.api_key
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'Time Series FX (Daily)' in data:
                time_series = data['Time Series FX (Daily)']
                latest_date = list(time_series.keys())[0]
                latest_data = time_series[latest_date]

                return {
                    'asset_pair': asset_pair,
                    'timestamp': datetime.utcnow().isoformat(),
                    'date': latest_date,
                    'open': float(latest_data.get('1. open', 0)),
                    'high': float(latest_data.get('2. high', 0)),
                    'low': float(latest_data.get('3. low', 0)),
                    'close': float(latest_data.get('4. close', 0)),
                    'type': 'forex'
                }
            else:
                logger.warning("Unexpected response format: %s", data)
                return self._create_mock_data(asset_pair, 'forex')

        except Exception as e:  # noqa: BLE001
            logger.error("Error fetching forex data: %s", e)
            return self._create_mock_data(asset_pair, 'forex')

    def _create_mock_data(
        self, asset_pair: str, asset_type: str
    ) -> Dict[str, Any]:
        """
        Create mock data for testing/demo purposes.

        Args:
            asset_pair: Asset pair
            asset_type: Type of asset (crypto/forex)

        Returns:
            Mock market data
        """
        logger.info("Creating mock data for %s", asset_pair)
        
        base_price = 50000.0 if asset_type == 'crypto' else 1.1
        
        return {
            'asset_pair': asset_pair,
            'timestamp': datetime.utcnow().isoformat(),
            'date': datetime.utcnow().date().isoformat(),
            'open': base_price,
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'close': base_price * 1.01,
            'volume': 1000000.0 if asset_type == 'crypto' else 0,
            'type': asset_type,
            'mock': True
        }
