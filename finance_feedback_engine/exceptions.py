"""
Custom exception hierarchy for Finance Feedback Engine 2.0.

This module defines a comprehensive exception hierarchy that allows for more specific
error handling instead of broad try/except Exception blocks.
"""


class FFEError(Exception):
    """
    Base exception for all Finance Feedback Engine errors.

    All custom exceptions in the system inherit from this class,
    allowing for broad exception catching when needed while still
    maintaining a clear exception hierarchy.
    """


class ConfigurationError(FFEError):
    """
    Raised when configuration validation fails or required configuration is missing.

    Examples: missing API keys, invalid config values, incompatible settings.
    """


class APIError(FFEError):
    """
    Base class for all API-related errors.

    Parent class for connection errors, response errors, and rate limit errors
    when interacting with external APIs (Alpha Vantage, trading platforms, etc.).
    """


class APIConnectionError(APIError):
    """
    Raised when unable to establish connection to external API.

    Examples: network timeout, DNS resolution failure, refused connection.
    """


class APIResponseError(APIError):
    """
    Raised when API returns malformed or unexpected response.

    Examples: invalid JSON, missing required fields, HTTP 500 errors.
    """


class APIRateLimitError(APIError):
    """
    Raised when API rate limits are exceeded.

    Indicates the API request quota has been exhausted and retry should
    be attempted after a backoff period.
    """


class ValidationError(FFEError):
    """
    Base class for all validation errors.

    Parent class for errors that occur when validating user input,
    configuration values, or data integrity checks.
    """


class RiskValidationError(ValidationError):
    """
    Raised when risk checks fail in RiskGatekeeper.

    Examples: position exceeds max concentration, VaR limit exceeded,
    correlation threshold breached.
    """


class AssetPairValidationError(ValidationError):
    """
    Raised when asset pair format or existence validation fails.

    Examples: invalid asset pair format, unsupported trading pair,
    pair not available on selected platform.
    """


class DecisionEngineError(FFEError):
    """
    Base class for all decision engine errors.

    Parent class for errors occurring in AI decision-making pipeline,
    including model installation, LLM provider communication, and ensemble voting.
    """


class ModelInstallationError(DecisionEngineError):
    """
    Raised when local AI model installation fails.

    Examples: Ollama service unavailable, insufficient disk space,
    model download timeout, corrupted model files.
    """


class AIClientError(DecisionEngineError):
    """
    Raised when AI provider client operations fail.

    Examples: API authentication failure, malformed response from LLM,
    prompt execution timeout, provider service unavailable.
    """


class TradingError(FFEError):
    """
    Base class for all trading platform errors.

    Parent class for errors occurring during trade execution, balance queries,
    and position management across Coinbase, Oanda, and other platforms.
    """


class BalanceRetrievalError(TradingError):
    """
    Raised when unable to retrieve account balance from trading platform.

    Examples: API endpoint unavailable, authentication expired,
    platform-specific balance query failure.
    """


class OrderExecutionError(TradingError):
    """
    Raised when trade order execution fails on platform.

    Examples: insufficient funds, invalid order size, market closed,
    platform rejected order due to risk limits.
    """


class PositionError(TradingError):
    """
    Raised when position queries or updates fail.

    Examples: position not found, failed to close position,
    unable to retrieve open positions from platform.
    """


class DataProviderError(FFEError):
    """
    Base class for all data provider errors.

    Parent class for errors when fetching market data from Alpha Vantage
    or other data sources (OHLCV, sentiment, news).
    """


class DataRetrievalError(DataProviderError):
    """
    Raised when unable to retrieve market data from provider.

    Examples: API key invalid, symbol not found, data request timeout,
    provider rate limit exceeded.
    """


class BacktestingError(FFEError):
    """
    Base class for all backtesting errors.

    Parent class for errors during historical strategy simulation,
    data replay, and performance calculation.
    """


class BacktestValidationError(BacktestingError):
    """
    Raised when backtest configuration or data validation fails.

    Examples: insufficient historical data, invalid date range,
    missing required indicators, incompatible strategy parameters.
    """


class FFEMemoryError(FFEError):
    """
    Base class for all memory and caching errors.

    Parent class for errors in portfolio memory, decision caching,
    and vector store operations.
    """


class VectorStoreError(FFEMemoryError):
    """
    Raised when vector store read/write operations fail.

    Examples: corrupted cache file, disk I/O error, serialization failure,
    unable to load decision history.
    """


class PersistenceError(FFEError):
    """
    Base class for all data persistence errors.

    Parent class for errors when saving or loading decisions,
    configurations, and other persistent state.
    """


class StorageError(PersistenceError):
    """
    Raised when file system storage operations fail.

    Examples: disk full, permission denied, directory not found,
    file already exists when uniqueness required.
    """


class CircuitBreakerError(FFEError):
    """
    Raised when circuit breaker prevents operation due to repeated failures.

    Circuit breaker opens after threshold of consecutive failures to prevent
    cascading errors. Automatically resets after cooldown period.
    """


class FFESystemError(FFEError):
    """
    Raised when system-level or infrastructure issues occur.

    Examples: out of memory, file descriptor limit reached,
    system signal received, unexpected shutdown.
    """


class InsufficientProvidersError(FFEError):
    """
    Raised when ensemble cannot reach quorum due to provider failures.

    Indicates too many AI providers are unavailable to make a reliable
    ensemble decision. Requires minimum number of successful responses.
    """


# Import all exceptions to make them available from the module
__all__ = [
    "FFEError",
    "ConfigurationError",
    "APIError",
    "APIConnectionError",
    "APIResponseError",
    "APIRateLimitError",
    "ValidationError",
    "AssetPairValidationError",
    "RiskValidationError",
    "DecisionEngineError",
    "ModelInstallationError",
    "AIClientError",
    "TradingError",
    "BalanceRetrievalError",
    "OrderExecutionError",
    "PositionError",
    "DataProviderError",
    "DataRetrievalError",
    "BacktestingError",
    "BacktestValidationError",
    "FFEMemoryError",
    "VectorStoreError",
    "PersistenceError",
    "StorageError",
    "CircuitBreakerError",
    "FFESystemError",
    "InsufficientProvidersError",
]
