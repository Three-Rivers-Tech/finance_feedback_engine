"""Circuit breaker pattern implementation for fault tolerance."""

import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps
import asyncio


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
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.circuit_open_count = 0
        
        logger.info(
            f"{self.name} initialized: threshold={failure_threshold}, "
            f"timeout={recovery_timeout}s"
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Original exception from func (if circuit closed)
        """
        self.total_calls += 1
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(
                    f"{self.name} entering HALF_OPEN state "
                    f"(testing recovery)"
                )
                self.state = CircuitState.HALF_OPEN
            else:
                logger.warning(
                    f"{self.name} is OPEN, rejecting call (fail fast). "
                    f"Failures: {self.failure_count}/{self.failure_threshold}"
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable, please try again later."
                )
        
        # Attempt the call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception:
            self._on_failure()
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
            logger.info(
                f"{self.name} recovery successful, closing circuit"
            )
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
            f"{self.name} failure {self.failure_count}/{self.failure_threshold} "
            f"(state: {self.state.value})"
        )
    
    def _open_circuit(self):
        """Open the circuit breaker."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.circuit_open_count += 1
            logger.error(
                f"{self.name} OPENING circuit after {self.failure_count} failures. "
                f"Will retry after {self.recovery_timeout}s"
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
        logger.info(f"{self.name} manually reset")
        self._reset()


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


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
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        
        # Attach breaker instance for external access
        wrapper.circuit_breaker = breaker
        return wrapper
    
    return decorator
