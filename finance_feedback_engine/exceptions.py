"""
Custom exception hierarchy for Finance Feedback Engine 2.0.

This module defines a comprehensive exception hierarchy that allows for more specific
error handling instead of broad try/except Exception blocks.
"""

class FFEError(Exception):
    """Base exception for all Finance Feedback Engine errors."""
    pass


class ConfigurationError(FFEError):
    """Raised when there are configuration issues."""
    pass


class APIError(FFEError):
    """Base class for API-related errors."""
    pass


class APIConnectionError(APIError):
    """Raised when there are connection issues with APIs."""
    pass


class APIResponseError(APIError):
    """Raised when API returns unexpected response."""
    pass


class APIRateLimitError(APIError):
    """Raised when rate limits are exceeded."""
    pass


class ValidationError(FFEError):
    """Raised when validation fails."""
    pass


class AssetPairValidationError(ValidationError):
    """Raised when asset pair validation fails."""
    pass


class RiskValidationError(FFEError):
    """Raised when risk validation fails."""
    pass


class DecisionEngineError(FFEError):
    """Base class for decision engine related errors."""
    pass


class ModelInstallationError(DecisionEngineError):
    """Raised when model installation fails."""
    pass


class AIClientError(DecisionEngineError):
    """Raised when AI client operations fail."""
    pass


class TradingError(FFEError):
    """Base class for trading related errors."""
    pass


class BalanceRetrievalError(TradingError):
    """Raised when balance retrieval fails."""
    pass


class OrderExecutionError(TradingError):
    """Raised when order execution fails."""
    pass


class PositionError(TradingError):
    """Raised when position operations fail."""
    pass


class DataProviderError(FFEError):
    """Base class for data provider related errors."""
    pass


class DataRetrievalError(DataProviderError):
    """Raised when data retrieval fails."""
    pass


class BacktestingError(FFEError):
    """Base class for backtesting related errors."""
    pass


class BacktestValidationError(BacktestingError):
    """Raised when backtesting validation fails."""
    pass


class MemoryError(FFEError):
    """Base class for memory related errors."""
    pass


class VectorStoreError(MemoryError):
    """Raised when vector store operations fail."""
    pass


class PersistenceError(FFEError):
    """Base class for persistence related errors."""
    pass


class StorageError(PersistenceError):
    """Raised when storage operations fail."""
    pass


class CircuitBreakerError(FFEError):
    """Raised when circuit breaker is open."""
    pass


class SystemError(FFEError):
    """Raised when system-level issues occur."""
    pass


class InsufficientProvidersError(FFEError):
    """Raised when insufficient providers are available for ensemble decisions."""
    pass


# Import all exceptions to make them available from the module
__all__ = [
    'FFEError',
    'ConfigurationError',
    'APIError',
    'APIConnectionError',
    'APIResponseError',
    'APIRateLimitError',
    'ValidationError',
    'AssetPairValidationError',
    'RiskValidationError',
    'DecisionEngineError',
    'ModelInstallationError',
    'AIClientError',
    'TradingError',
    'BalanceRetrievalError',
    'OrderExecutionError',
    'PositionError',
    'DataProviderError',
    'DataRetrievalError',
    'BacktestingError',
    'BacktestValidationError',
    'MemoryError',
    'VectorStoreError',
    'PersistenceError',
    'StorageError',
    'CircuitBreakerError',
    'SystemError',
    'InsufficientProvidersError',
]