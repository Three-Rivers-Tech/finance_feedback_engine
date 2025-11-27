import asyncio
import time
import threading

class RateLimiter:
    """
    Implements a token bucket algorithm for rate limiting API requests.

    Tokens are refilled at a specified rate (tokens_per_second). Each request
    consumes one token. If no tokens are available, the caller waits until
    a token becomes available.

    Supports both synchronous and asynchronous usage. The shared state is
    protected by a single threading.Lock to prevent race conditions between
    sync and async methods.
    """
    def __init__(self, tokens_per_second: float, max_tokens: int):
        if tokens_per_second <= 0 or max_tokens <= 0:
            raise ValueError(
                "Both tokens_per_second and max_tokens must be positive."
            )

        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_refill_time = time.monotonic()
        self._lock = threading.Lock()  # Single lock for shared state

    def _refill_tokens(self):
        """Refills tokens based on the elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill_time
        if elapsed > 0:
            new_tokens = elapsed * self.tokens_per_second
            self.tokens = min(self.max_tokens, self.tokens + new_tokens)
            self.last_refill_time = now

    def _wait_for_token_sync(self):
        """
        Internal synchronous method to wait for and consume a token.
        Must be called with the lock held.
        """
        self._refill_tokens()
        while self.tokens < 1:
            sleep_time = (1 - self.tokens) / self.tokens_per_second
            time.sleep(sleep_time)
            self._refill_tokens()
        self.tokens -= 1

    def wait_for_token(self):
        """
        Blocks until a token is available, then consumes one.
        Suitable for synchronous operations.
        """
        with self._lock:
            self._wait_for_token_sync()

    async def wait_for_token_async(self):
        """
        Asynchronously waits until a token is available, then consumes one.
        Suitable for asynchronous operations.
        """
        await asyncio.to_thread(self._wait_for_token_sync)


if __name__ == "__main__":
    # Example Synchronous Usage
    print("--- Synchronous Rate Limiter Test (1 token/sec, max 1) ---")
    limiter_sync = RateLimiter(tokens_per_second=1, max_tokens=1)
    for i in range(5):
        start_time = time.monotonic()
        limiter_sync.wait_for_token()
        end_time = time.monotonic()
        print(f"Sync Request {i+1}: waited for {end_time - start_time:.2f}s")
        if i == 0:
            assert (end_time - start_time) < 0.1  # First fast
        else:
            assert (end_time - start_time) > 0.9  # Subsequent should wait ~1s

    # Example Asynchronous Usage
    print("\n--- Asynchronous Rate Limiter Test (2 tokens/sec, max 2) ---")
    limiter_async = RateLimiter(tokens_per_second=2, max_tokens=2)

    async def make_async_requests():
        tasks = []
        for i in range(5):
            async def request_func(req_num):
                start_time = time.monotonic()
                await limiter_async.wait_for_token_async()
                end_time = time.monotonic()
                print(f"Async {req_num+1}: {end_time - start_time:.2f}s")

            tasks.append(asyncio.create_task(request_func(i)))
        await asyncio.gather(*tasks)

    asyncio.run(make_async_requests())
