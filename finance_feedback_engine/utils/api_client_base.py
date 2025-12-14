from abc import ABC, abstractmethod
import requests
import logging
import json
from typing import Dict, Any, Optional
from requests.exceptions import RequestException, HTTPError, Timeout


from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .rate_limiter import RateLimiter


logger = logging.getLogger(__name__)

def log_before_retry(retry_state):
    """Log before retrying."""
    logger.info(f"Retrying {retry_state.fn.__name__} in {retry_state.next_action.sleep:.2f} seconds...")

class APIClientBase(ABC):
    """
    Abstract Base Class (ABC) for API clients, providing common functionalities
    like request handling, retry mechanisms, and rate limiting.

    This class serves as a foundation for building robust and resilient API
    integrations, particularly important for interacting with external financial
    data providers or trading platforms.


    Implementation Notes:
    - **Abstracted HTTP Operations:** Defines abstract methods for HTTP verbs
      (`_get`, `_post`, etc.) to be implemented by concrete client classes,
      allowing for flexible underlying HTTP libraries (e.g., `requests`, `aiohttp`).
    - **Authentication:** Includes a placeholder for authentication, emphasizing
      the need for secure handling of API keys/secrets.
    - **Retry Mechanism:** Implements a basic exponential backoff retry strategy
      for transient network errors, improving resilience.
    - **Rate Limiting:** Provides a framework for respecting API rate limits,
      preventing temporary bans or service interruptions.
    - **Centralized Error Handling:** All API interactions go through this base
      class, allowing for consistent error logging and handling.

    TODO:
    - **Implement Specific Authentication:** Concrete client implementations should
      handle their specific authentication flows (e.g., OAuth, HMAC, JWT).
    - **Advanced Rate Limiting:** Implement token bucket or leaky bucket algorithms
      for more sophisticated rate limiting, potentially across multiple clients.
    - **Circuit Breaker Pattern:** Integrate a circuit breaker (e.g., `pybreaker` library)
      to prevent cascading failures when an external API is experiencing issues.
    - **Structured Logging:** Ensure detailed logging of requests, responses, and errors
      for debugging and auditing purposes.
    - **Configuration Injection:** Allow API endpoint, keys, and other parameters
      to be injected via configuration (e.g., using the `config_loader`).
    """

    DEFAULT_RETRIES = 3
    DEFAULT_BACKOFF_FACTOR = 0.5
    DEFAULT_TIMEOUT = 10 # seconds
    DEFAULT_TOKENS_PER_SECOND = 5 # Default for rate limiting
    DEFAULT_MAX_TOKENS = 5 # Default max tokens for burst

    def __init__(self, base_url: str, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 tokens_per_second: float = DEFAULT_TOKENS_PER_SECOND, max_tokens: int = DEFAULT_MAX_TOKENS):
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret # For HMAC or other two-part auth
        # Initialize rate limiter with configurable parameters
        self.rate_limiter = RateLimiter(
            tokens_per_second=tokens_per_second,
            max_tokens=max_tokens
        )

    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Abstract method to generate authentication headers for API requests.
        Concrete classes must implement this based on their API's auth scheme.
        """
        pass

    @abstractmethod
    async def _send_request_async(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retries: int = DEFAULT_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Abstract method for sending an asynchronous HTTP request to the API with
        retry logic and error handling. Concrete classes must implement this.
        """
        pass

    def _send_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retries: int = DEFAULT_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        timeout: int = DEFAULT_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Sends an HTTP request to the API with retry logic and error handling.
        """
        url = f"{self.base_url}{endpoint}"

        # Merge provided headers with auth headers
        request_headers = self._get_auth_headers()
        if headers:
            request_headers.update(headers)

        @retry(
            stop=stop_after_attempt(retries),
            wait=wait_exponential(multiplier=backoff_factor),
            retry=retry_if_exception_type((RequestException, HTTPError, Timeout)),
            before_sleep=log_before_retry
        )
        def _send():
            try:
                # Integrate with rate limiter before sending request
                self.rate_limiter.wait_for_token()

                logger.debug(f"Sending {method} request to {url} with params={params}, data={data}, json={json_data}")

                response = requests.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers,
                    timeout=timeout
                )
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                return response.json()

            except HTTPError as e:
                # Distinguish between client errors (4xx) and server errors (5xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Client error ({e.response.status_code}) for {url}: {e.response.text}")
                    raise
                else: # 5xx server errors, retry
                    logger.warning(f"Server error ({e.response.status_code}) for {url}: {e.response.text}")
                    raise
            except (RequestException, Timeout) as e:
                logger.warning(f"Network or request error for {url}: {e}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON response from {url}. Response: {e.doc}")
                raise

        return _send()

    # Concrete API clients will implement methods like get_market_data, place_order, etc.
    # using this _send_request method.
    # Example:
    # def get_market_data(self, symbol: str) -> Dict[str, Any]:
    #     endpoint = f"/market/{symbol}/ticker"
    #     return self._send_request("GET", endpoint)





