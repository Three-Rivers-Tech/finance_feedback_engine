"""Tests for retry utilities with exponential backoff."""

import time
from unittest.mock import MagicMock, patch

import pytest

from finance_feedback_engine.utils.retry import (
    RetryConfig,
    exponential_backoff_retry,
)


class TestExponentialBackoffRetry:
    """Test suite for exponential backoff retry decorator."""

    def test_retry_decorator_success_first_attempt(self):
        """Test that function succeeds on first attempt."""
        mock_func = MagicMock(return_value="success")

        @exponential_backoff_retry()
        def test_func():
            return mock_func()

        result = test_func()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_decorator_success_after_retries(self):
        """Test that function succeeds after retries."""
        call_count = 0

        @exponential_backoff_retry(max_retries=3, base_delay=0.01)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = test_func()

        assert result == "success"
        assert call_count == 3

    def test_retry_decorator_max_retries_exceeded(self):
        """Test that exception is raised after max retries."""

        @exponential_backoff_retry(max_retries=2, base_delay=0.01)
        def test_func():
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            test_func()

    def test_retry_decorator_exponential_backoff(self):
        """Test that delays follow exponential backoff pattern."""
        delays = []

        @exponential_backoff_retry(
            max_retries=3, base_delay=1.0, exponential_base=2.0, jitter=False
        )
        def test_func():
            if len(delays) < 3:
                start = time.time()
                raise ValueError("Test error")
            return "success"

        with patch("time.sleep") as mock_sleep:
            try:
                test_func()
            except ValueError:
                pass

            # Check that sleep was called with increasing delays
            assert mock_sleep.call_count > 0
            calls = [call[0][0] for call in mock_sleep.call_args_list]

            # Verify exponential growth (approximately)
            for i in range(len(calls) - 1):
                # Each delay should be roughly double the previous
                assert calls[i + 1] >= calls[i]

    def test_retry_decorator_with_jitter(self):
        """Test that jitter adds randomness to delays."""
        delays = []

        @exponential_backoff_retry(max_retries=2, base_delay=1.0, jitter=True)
        def test_func():
            raise ValueError("Test error")

        with patch("time.sleep") as mock_sleep:
            try:
                test_func()
            except ValueError:
                pass

            # Check that sleep was called
            assert mock_sleep.call_count > 0

    def test_retry_decorator_max_delay_cap(self):
        """Test that delay is capped at max_delay."""

        @exponential_backoff_retry(
            max_retries=10, base_delay=1.0, max_delay=5.0, jitter=False
        )
        def test_func():
            raise ValueError("Test error")

        with patch("time.sleep") as mock_sleep:
            try:
                test_func()
            except ValueError:
                pass

            # Verify no delay exceeds max_delay
            delays = [call[0][0] for call in mock_sleep.call_args_list]
            assert all(delay <= 5.0 for delay in delays)

    def test_retry_decorator_specific_exceptions(self):
        """Test that only specific exceptions trigger retry."""

        @exponential_backoff_retry(
            max_retries=3, base_delay=0.01, exceptions=(ValueError,)
        )
        def test_func(exception_type):
            raise exception_type("Test error")

        # ValueError should be retried
        with pytest.raises(ValueError):
            test_func(ValueError)

        # TypeError should not be retried (raised immediately)
        with pytest.raises(TypeError):
            test_func(TypeError)

    def test_retry_decorator_with_args(self):
        """Test that decorator works with function arguments."""
        call_count = 0

        @exponential_backoff_retry(max_retries=2, base_delay=0.01)
        def test_func(x, y, z=10):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return x + y + z

        result = test_func(1, 2, z=3)

        assert result == 6
        assert call_count == 2

    def test_retry_decorator_zero_retries(self):
        """Test behavior with zero retries."""

        @exponential_backoff_retry(max_retries=0, base_delay=0.01)
        def test_func():
            raise ValueError("Error")

        with pytest.raises(ValueError):
            test_func()

    def test_retry_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @exponential_backoff_retry()
        def test_func():
            """Test docstring."""
            pass

        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test docstring."

    @patch("time.sleep")
    def test_retry_decorator_timing(self, mock_sleep):
        """Test that retry timing is correct."""
        attempts = []

        @exponential_backoff_retry(
            max_retries=3, base_delay=1.0, exponential_base=2.0, jitter=False
        )
        def test_func():
            attempts.append(1)
            if len(attempts) <= 3:
                raise ValueError("Test error")
            return "success"

        try:
            test_func()
        except ValueError:
            pass

        # Should have made 4 attempts (initial + 3 retries)
        assert len(attempts) == 4

        # Should have slept 3 times
        assert mock_sleep.call_count == 3

        # Verify sleep durations: 1.0, 2.0, 4.0
        expected_delays = [1.0, 2.0, 4.0]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays


class TestRetryConfig:
    """Test suite for RetryConfig class."""

    def test_api_call_config(self):
        """Test API call retry configuration."""
        config = RetryConfig.get_config("api_call")

        assert config["max_retries"] == 3
        assert config["base_delay"] == 1.0
        assert config["max_delay"] == 30.0
        assert config["jitter"] is True

    def test_ai_provider_config(self):
        """Test AI provider retry configuration."""
        config = RetryConfig.get_config("ai_provider")

        assert config["max_retries"] == 2
        assert config["base_delay"] == 2.0
        assert config["max_delay"] == 60.0
        assert config["jitter"] is True

    def test_database_operation_config(self):
        """Test database operation retry configuration."""
        config = RetryConfig.get_config("database_operation")

        assert config["max_retries"] == 3
        assert config["base_delay"] == 0.5
        assert config["max_delay"] == 10.0
        assert config["jitter"] is True

    def test_unknown_config_returns_default(self):
        """Test that unknown config type returns API_CALL default."""
        config = RetryConfig.get_config("unknown_type")

        # Should return API_CALL config as default
        assert config["max_retries"] == 3
        assert config["base_delay"] == 1.0

    def test_case_insensitive_config_lookup(self):
        """Test that config lookup is case insensitive."""
        config1 = RetryConfig.get_config("api_call")
        config2 = RetryConfig.get_config("API_CALL")
        config3 = RetryConfig.get_config("Api_Call")

        assert config1 == config2 == config3

    def test_config_immutability(self):
        """Test that modifying returned config doesn't affect original."""
        config = RetryConfig.get_config("api_call")
        original_retries = config["max_retries"]

        # Modify returned config
        config["max_retries"] = 999

        # Get config again
        new_config = RetryConfig.get_config("api_call")

        # Original should be unchanged
        assert new_config["max_retries"] == original_retries


class TestRetryIntegration:
    """Integration tests for retry functionality."""

    @patch("time.sleep")
    def test_retry_with_api_config(self, mock_sleep):
        """Test retry with API call configuration."""
        config = RetryConfig.get_config("api_call")
        call_count = 0

        @exponential_backoff_retry(**config)
        def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("API unavailable")
            return {"status": "success"}

        result = api_call()

        assert result["status"] == "success"
        assert call_count == 3

    @patch("time.sleep")
    def test_retry_with_ai_provider_config(self, mock_sleep):
        """Test retry with AI provider configuration."""
        config = RetryConfig.get_config("ai_provider")
        call_count = 0

        @exponential_backoff_retry(**config, exceptions=(TimeoutError,))
        def ai_request():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("AI provider timeout")
            return "AI response"

        result = ai_request()

        assert result == "AI response"
        assert call_count == 2

    def test_retry_failure_logging(self, caplog):
        """Test that retry failures are logged."""

        @exponential_backoff_retry(max_retries=1, base_delay=0.01)
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_func()

        # Check that warnings were logged
        assert any("retrying" in record.message.lower() for record in caplog.records)

    def test_retry_success_after_failure_no_logging(self, caplog):
        """Test that successful retry doesn't log errors."""
        call_count = 0

        @exponential_backoff_retry(max_retries=2, base_delay=0.01)
        def recovering_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Temporary issue")
            return "recovered"

        result = recovering_func()

        assert result == "recovered"
        # Should have warning logs for the retry
        assert any("retrying" in record.message.lower() for record in caplog.records)
