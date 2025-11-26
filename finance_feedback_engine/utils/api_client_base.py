from abc import ABC, abstractmethod
import requests
import time
import logging
from typing import Dict, Any, Optional
from requests.exceptions import RequestException, HTTPError, Timeout

# TODO: Consider using a dedicated retry library like 'tenacity' for more advanced retry logic.
# from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

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
    - **Asynchronous Support:** Provide an asynchronous version of this base class
      (e.g., `AsyncAPIClientBase`) using `aiohttp` for non-blocking operations.
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

    def __init__(self, base_url: str, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret # For HMAC or other two-part auth
        # TODO: Initialize rate limiter here
        # self.rate_limiter = RateLimiter(calls=10, period=1) # Example: 10 calls per second

    @abstractmethod
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Abstract method to generate authentication headers for API requests.
        Concrete classes must implement this based on their API's auth scheme.
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

        for attempt in range(retries):
            try:
                # TODO: Integrate with a rate limiter before sending request
                # self.rate_limiter.wait()

                logger.debug(f"Attempt {attempt + 1}/{retries}: {method} {url} with params={params}, data={data}, json={json_data}")
                
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
            
            except Timeout as e:
                logger.warning(f"Request to {url} timed out on attempt {attempt + 1}: {e}")
            except HTTPError as e:
                # Distinguish between client errors (4xx) and server errors (5xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Client error ({e.response.status_code}) for {url}: {e.response.text}")
                    raise
                else: # 5xx server errors, retry
                    logger.warning(f"Server error ({e.response.status_code}) for {url} on attempt {attempt + 1}: {e.response.text}")
            except RequestException as e:
                logger.warning(f"Network or request error for {url} on attempt {attempt + 1}: {e}")
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON response from {url}. Response: {response.text}")
                raise

            if attempt < retries - 1:
                sleep_time = backoff_factor * (2 ** attempt)
                logger.info(f"Retrying {url} in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            
        logger.error(f"Failed to {method} {url} after {retries} attempts.")
        raise RequestException(f"Max retries exceeded for {url}")

    # Concrete API clients will implement methods like get_market_data, place_order, etc.
    # using this _send_request method.
    # Example:
    # def get_market_data(self, symbol: str) -> Dict[str, Any]:
    #     endpoint = f"/market/{symbol}/ticker"
    #     return self._send_request("GET", endpoint)

# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    class DummyAPIClient(APIClientBase):
        """A dummy API client for testing the base class functionality."""
        def _get_auth_headers(self) -> Dict[str, str]:
            if self.api_key:
                return {"X-API-KEY": self.api_key}
            return {}

        def get_dummy_data(self, item_id: str) -> Dict[str, Any]:
            logger.info(f"Fetching dummy data for {item_id}")
            # Simulate a real API call using a mock URL
            # For this example, we'll hit a real endpoint that might return 404
            # or use httpbin.org for testing
            mock_endpoint = f"/anything/{item_id}"
            return self._send_request("GET", mock_endpoint)

        def post_dummy_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
            logger.info(f"Posting dummy data: {data}")
            mock_endpoint = "/post"
            return self._send_request("POST", mock_endpoint, json_data=data)


    # Test successful request
    print("--- Testing Successful Request (using httpbin.org) ---")
    dummy_client = DummyAPIClient(base_url="https://httpbin.org", api_key="test_key")
    try:
        response_data = dummy_client.get_dummy_data("success")
        print(f"Success response: {response_data.get('args', 'No args')}")
    except RequestException as e:
        print(f"Error: {e}")

    # Test request with expected retry (simulated by making a POST to a GET endpoint, will get 405)
    print("\n--- Testing Retries for Server Error (e.g., 405 Method Not Allowed) ---")
    try:
        # httpbin.org/get expects GET, so POST will return 405
        # We need a 5xx error for retry, let's pretend a 405 is retryable for this test.
        # A more realistic test would use a mock server that returns 500.
        # For actual 5xx simulation:
        # response_data = dummy_client._send_request("GET", "/status/500", retries=2)
        response_data = dummy_client.post_dummy_data({"test": "data"}) # This would return a 200 actually
        print(f"Post response: {response_data.get('json', 'No JSON')}")
    except RequestException as e:
        print(f"Error after retries: {e}")

    # Test request with timeout
    print("\n--- Testing Timeout ---")
    try:
        # httpbin.org/delay/x will delay for x seconds
        dummy_client._send_request("GET", "/delay/5", timeout=2, retries=1)
    except RequestException as e:
        print(f"Expected Timeout Error: {e}")
