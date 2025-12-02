"""Circuit breaker pattern implementation for fault tolerance.

Thread/async safety added: protects shared mutable state with
`threading.Lock` for synchronous paths and `asyncio.Lock` for async paths.
This ensures atomic counters and correct HALF_OPEN single-request probing
under concurrent load.
"""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
import asyncio
import threading


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation, requests pass through
    OPEN = "OPEN"          # Circuit is open, requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service has recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    
    Implements the circuit breaker pattern to fail fast and prevent
    overwhelming a failing service. After a threshold of failures,
    the circuit "opens" and rejects requests immediately for a timeout
    period. After the timeout, it enters "half-open" state to test
    if the service has recovered.
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Too many failures, reject all requests immediately
    - HALF_OPEN: Testing recovery, allow one request through
    
    Industry pattern from Hugging Face docs:
    "Try to return a 503 or 504 error when the server is overloaded
    instead of forcing a user to wait indefinitely"
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        name: Optional[str] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type that counts as failure
            name: Optional name for logging/identification
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name or "CircuitBreaker"
        
        # State tracking
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._half_open_in_progress = False  # Track HALF_OPEN probe reservation
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.circuit_open_count = 0

        # Concurrency locks (sync + async)
        self._sync_lock = threading.Lock()
        # Lazy init: create async lock on first async use to bind to correct event loop
        self._async_lock = None
        
        logger.info(
            "%s initialized: threshold=%d, timeout=%.1fs",
            self.name, failure_threshold, recovery_timeout
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection (async version).
        """
        if asyncio.iscoroutinefunction(func):
            async def async_runner():
                return await func(*args, **kwargs)
            return await self._execute_with_circuit_async(
                async_runner, is_async=True
            )
        else:
            def sync_runner():
                return func(*args, **kwargs)
            # Directly use the sync logic, no event loop
            return self._execute_with_circuit(sync_runner)

    def call_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection in a synchronous
        context.
        """
        def runner():
            return func(*args, **kwargs)
        return self._execute_with_circuit(runner)

    def _execute_with_circuit(self, runner: Callable[[], Any]) -> Any:
        """Core circuit breaker logic for synchronous execution."""
        # Acquire lock only for state checks and updates
        with self._sync_lock:
            self.total_calls += 1
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        "%s entering HALF_OPEN state (testing recovery)",
                        self.name
                    )
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_in_progress = True
                else:
                    logger.warning(
                        "%s is OPEN, rejecting call (fail fast). Failures: %d/%d",
                        self.name, self.failure_count, self.failure_threshold
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        "Service unavailable, please try again later."
                    )
            elif self.state == CircuitState.HALF_OPEN:
                # Reject concurrent calls during HALF_OPEN probe
                if self._half_open_in_progress:
                    logger.warning(
                        "%s is HALF_OPEN with probe in progress, rejecting call",
                        self.name
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is testing recovery. "
                        "Please try again shortly."
                    )
                self._half_open_in_progress = True
        
        # Execute runner WITHOUT holding lock to avoid serialization
        try:
            result = runner()
            # Re-acquire lock for success handling
            with self._sync_lock:
                was_half_open = self.state == CircuitState.HALF_OPEN
                self._on_success()
                if was_half_open:
                    self._half_open_in_progress = False
            return result
        except Exception as exc:
            # Re-acquire lock for failure handling
            with self._sync_lock:
                if isinstance(exc, self.expected_exception):
                    self._on_failure()
                if self.state == CircuitState.HALF_OPEN:
                    self._half_open_in_progress = False
            raise

    async def _execute_with_circuit_async(
        self, runner: Callable[[], Any], is_async: bool
    ) -> Any:
        """Core circuit breaker logic for async execution."""
        # Lazy init: create lock in the correct event loop on first use
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        
        # Acquire lock only for state checks and updates
        async with self._async_lock:
            self.total_calls += 1
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        "%s entering HALF_OPEN state (testing recovery)",
                        self.name
                    )
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_in_progress = True
                else:
                    logger.warning(
                        "%s is OPEN, rejecting call (fail fast). Failures: %d/%d",
                        self.name, self.failure_count, self.failure_threshold
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        "Service unavailable, please try again later."
                    )
            elif self.state == CircuitState.HALF_OPEN:
                # Reject concurrent calls during HALF_OPEN probe
                if self._half_open_in_progress:
                    logger.warning(
                        "%s is HALF_OPEN with probe in progress, rejecting call",
                        self.name
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is testing recovery. "
                        "Please try again shortly."
                    )
                self._half_open_in_progress = True
        
        # Execute runner WITHOUT holding lock to avoid serialization
        try:
            if is_async:
                result = await runner()
            else:
                result = runner()
            # Re-acquire lock for success handling
            async with self._async_lock:
                was_half_open = self.state == CircuitState.HALF_OPEN
                self._on_success()
                if was_half_open:
                    self._half_open_in_progress = False
            return result
        except Exception as exc:
            # Re-acquire lock for failure handling
            async with self._async_lock:
                if isinstance(exc, self.expected_exception):
                    self._on_failure()
                if self.state == CircuitState.HALF_OPEN:
                    self._half_open_in_progress = False
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.total_successes += 1
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            logger.info("%s recovery successful, closing circuit", self.name)
            self._reset()
        
        # Reset failure count on success in CLOSED state
        if self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.total_failures += 1
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self._open_circuit()
        
        logger.warning(
            "%s failure %d/%d (state: %s)",
            self.name,
            self.failure_count,
            self.failure_threshold,
            self.state.value
        )
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.circuit_open_count += 1
            logger.error(
                "%s OPENING circuit after %d failures. Will retry after %.1fs",
                self.name, self.failure_count, self.recovery_timeout
            )
    
    def _reset(self):
        """Reset circuit breaker to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'total_calls': self.total_calls,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'circuit_open_count': self.circuit_open_count,
            'failure_rate': self.total_failures / max(self.total_calls, 1),
            'last_failure_time': self.last_failure_time
        }
    
    def reset_manually(self):
        """Manually reset circuit breaker (for testing/admin)."""
        logger.info("%s manually reset", self.name)
        self._reset()


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: type = Exception,
    name: Optional[str] = None
):
    """
    Decorator to apply circuit breaker to a function.
    
    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type that counts as failure
        name: Optional name for circuit breaker
        
    Example:
        @circuit_breaker(failure_threshold=3, recovery_timeout=30)
        async def call_external_api():
            return await aiohttp.get(url)
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
        name=name
    )

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await breaker.call(func, *args, **kwargs)
            async_wrapper.circuit_breaker = breaker
            return async_wrapper
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return breaker.call_sync(func, *args, **kwargs)
        sync_wrapper.circuit_breaker = breaker
        return sync_wrapper
    return decorator
