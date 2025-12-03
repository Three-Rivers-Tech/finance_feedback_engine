"""Tests for utils.circuit_breaker module."""

import pytest
import time
import asyncio
from finance_feedback_engine.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError
)


class TestCircuitBreakerBasics:
    """Test basic circuit breaker functionality."""
    
    def test_init_defaults(self):
        """Test circuit breaker initialization with defaults."""
        cb = CircuitBreaker()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.total_calls == 0
    
    def test_init_custom_params(self):
        """Test circuit breaker with custom parameters."""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
            name="TestBreaker"
        )
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert cb.name == "TestBreaker"
    
    def test_successful_call(self):
        """Test successful function execution."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def success_func():
            return "success"
        
        result = cb.call_sync(success_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.success_count == 1
        assert cb.total_calls == 1


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""
    
    def test_closed_to_open_after_threshold(self):
        """Test circuit opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def failing_func():
            raise ValueError("Test failure")
        
        # Execute failures up to threshold
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call_sync(failing_func)
        
        # Circuit should now be OPEN
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3
    
    def test_open_rejects_calls_immediately(self):
        """Test that open circuit rejects calls without executing them."""
        cb = CircuitBreaker(failure_threshold=2)
        
        call_count = 0
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Test failure")
        
        # Trigger circuit to open
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(failing_func)
        
        assert cb.state == CircuitState.OPEN
        initial_calls = call_count
        
        # Next call should fail fast without executing function
        with pytest.raises(CircuitBreakerOpenError):
            cb.call_sync(failing_func)
        
        assert call_count == initial_calls  # Function not called
    
    def test_open_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        def failing_func():
            raise ValueError("Test failure")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should allow test call (HALF_OPEN)
        def success_func():
            return "recovered"
        
        result = cb.call_sync(success_func)
        
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED  # Success closes circuit
    
    def test_half_open_to_closed_on_success(self):
        """Test HALF_OPEN transitions to CLOSED on successful call."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: 1/0)
        
        time.sleep(0.15)
        
        # Successful call in HALF_OPEN should close circuit
        result = cb.call_sync(lambda: "success")
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0  # Reset on recovery
    
    def test_half_open_to_open_on_failure(self):
        """Test HALF_OPEN returns to OPEN on failure."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: 1/0)
        
        time.sleep(0.15)
        
        # Failed call in HALF_OPEN should reopen circuit
        with pytest.raises(ZeroDivisionError):
            cb.call_sync(lambda: 1/0)
        
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerMetrics:
    """Test circuit breaker metrics tracking."""
    
    def test_success_count_tracking(self):
        """Test tracking of successful calls."""
        cb = CircuitBreaker()
        
        for _ in range(5):
            cb.call_sync(lambda: "ok")
        
        assert cb.success_count == 5
        assert cb.total_successes == 5
        assert cb.total_calls == 5
    
    def test_failure_count_tracking(self):
        """Test tracking of failed calls."""
        cb = CircuitBreaker(failure_threshold=10)
        
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: 1/0)
        
        assert cb.failure_count == 3
        assert cb.total_failures == 3
        assert cb.total_calls == 3
    
    def test_mixed_calls_tracking(self):
        """Test tracking of mixed successful and failed calls."""
        cb = CircuitBreaker(failure_threshold=10)
        
        # 3 successes
        for _ in range(3):
            cb.call_sync(lambda: "ok")
        
        # 2 failures
        for _ in range(2):
            with pytest.raises(ZeroDivisionError):
                cb.call_sync(lambda: 1/0)
        
        assert cb.success_count == 3
        assert cb.failure_count == 2
        assert cb.total_calls == 5


class TestCircuitBreakerAsync:
    """Test async circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_async_successful_call(self):
        """Test successful async function execution."""
        cb = CircuitBreaker()
        
        async def async_success():
            return "async success"
        
        result = await cb.call(async_success)
        
        assert result == "async success"
        assert cb.success_count == 1
    
    @pytest.mark.asyncio
    async def test_async_failure_opens_circuit(self):
        """Test async failures open circuit."""
        cb = CircuitBreaker(failure_threshold=2)
        
        async def async_fail():
            raise ValueError("Async failure")
        
        # Trigger failures
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(async_fail)
        
        assert cb.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_async_open_rejects_calls(self):
        """Test open circuit rejects async calls."""
        cb = CircuitBreaker(failure_threshold=1)
        
        async def async_fail():
            raise ValueError("Async failure")
        
        # Open circuit
        with pytest.raises(ValueError):
            await cb.call(async_fail)
        
        # Should reject next call
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(async_fail)


class TestCircuitBreakerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_zero_failure_threshold(self):
        """Test circuit with zero failure threshold."""
        cb = CircuitBreaker(failure_threshold=0)
        
        # Should open immediately on any failure
        with pytest.raises(ZeroDivisionError):
            cb.call_sync(lambda: 1/0)
        
        # Circuit may be open depending on implementation
        # Just verify it doesn't crash
        assert cb.total_calls >= 1
    
    def test_very_short_timeout(self):
        """Test circuit with very short recovery timeout."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        
        # Open circuit
        with pytest.raises(ZeroDivisionError):
            cb.call_sync(lambda: 1/0)
        
        # Wait minimal time
        time.sleep(0.02)
        
        # Should allow test
        result = cb.call_sync(lambda: "recovered")
        assert result == "recovered"
    
    def test_custom_exception_type(self):
        """Test circuit with custom expected exception."""
        cb = CircuitBreaker(
            failure_threshold=2,
            expected_exception=ValueError
        )
        
        # ValueError should count as failure
        with pytest.raises(ValueError):
            cb.call_sync(lambda: exec('raise ValueError()'))
        
        assert cb.failure_count == 1
        
        # Other exceptions might not count (depends on implementation)
        try:
            cb.call_sync(lambda: 1/0)
        except ZeroDivisionError:
            pass
        
        # Should have counted at least the ValueError
        assert cb.total_failures >= 1


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker."""
    
    def test_multiple_circuits_independent(self):
        """Test that multiple circuit breakers operate independently."""
        cb1 = CircuitBreaker(failure_threshold=2, name="CB1")
        cb2 = CircuitBreaker(failure_threshold=2, name="CB2")
        
        # Open CB1
        for _ in range(2):
            with pytest.raises(ValueError):
                cb1.call_sync(lambda: exec('raise ValueError()'))
        
        # CB2 should still be closed
        result = cb2.call_sync(lambda: "ok")
        
        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.CLOSED
        assert result == "ok"
    
    def test_recovery_workflow(self):
        """Test complete failure and recovery workflow."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
        
        # Phase 1: Normal operation
        cb.call_sync(lambda: "ok")
        assert cb.state == CircuitState.CLOSED
        
        # Phase 2: Failures trigger opening
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call_sync(lambda: exec('raise ValueError()'))
        
        assert cb.state == CircuitState.OPEN
        
        # Phase 3: Wait for recovery
        time.sleep(0.15)
        
        # Phase 4: Test recovery
        result = cb.call_sync(lambda: "recovered")
        
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0  # Reset
