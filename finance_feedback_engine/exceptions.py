"""
Custom exception hierarchy for Finance Feedback Engine.

Replaces bare 'except Exception' handlers with specific, meaningful exceptions.
Improves debugging by providing context and allowing targeted error handling.
"""


class FinanceFeedbackEngineError(Exception):
    """Base exception for all Finance Feedback Engine errors."""
    pass


# Data Provider Errors
class DataProviderError(FinanceFeedbackEngineError):
    """Base exception for data provider errors."""
    pass


class DataFetchError(DataProviderError):
    """Raised when data cannot be fetched from provider."""
    pass


class DataValidationError(DataProviderError):
    """Raised when fetched data fails validation."""
    pass


class RateLimitExceededError(DataProviderError):
    """Raised when API rate limit is exceeded."""
    pass


class InvalidAssetPairError(DataProviderError):
    """Raised when asset pair format is invalid."""
    pass


# Decision Engine Errors
class DecisionEngineError(FinanceFeedbackEngineError):
    """Base exception for decision engine errors."""
    pass


class AIProviderError(DecisionEngineError):
    """Raised when AI provider fails to respond."""
    pass


class PromptGenerationError(DecisionEngineError):
    """Raised when prompt cannot be generated."""
    pass


class DecisionValidationError(DecisionEngineError):
    """Raised when AI decision fails validation."""
    pass


class InsufficientProvidersError(DecisionEngineError):
    """Raised when ensemble doesn't have minimum providers (Phase 1 quorum)."""
    def __init__(self, message: str, providers_failed=None, providers_succeeded=None):
        super().__init__(message)
        self.providers_failed = providers_failed or []
        self.providers_succeeded = providers_succeeded or []


# Trading Platform Errors
class TradingPlatformError(FinanceFeedbackEngineError):
    """Base exception for trading platform errors."""
    pass


class PlatformConnectionError(TradingPlatformError):
    """Raised when cannot connect to trading platform."""
    pass


class BalanceRetrievalError(TradingPlatformError):
    """Raised when cannot retrieve account balance."""
    pass


class OrderExecutionError(TradingPlatformError):
    """Raised when order execution fails."""
    pass


class InsufficientBalanceError(TradingPlatformError):
    """Raised when account has insufficient balance for trade."""
    pass


# Risk Management Errors
class RiskManagementError(FinanceFeedbackEngineError):
    """Base exception for risk management errors."""
    pass


class RiskLimitExceededError(RiskManagementError):
    """Raised when trade exceeds risk limits."""
    pass


class DrawdownLimitExceededError(RiskManagementError):
    """Raised when drawdown exceeds configured limit."""
    pass


class ConcentrationLimitExceededError(RiskManagementError):
    """Raised when position concentration exceeds limit."""
    pass


# Configuration Errors
class ConfigurationError(FinanceFeedbackEngineError):
    """Base exception for configuration errors."""
    pass


class InvalidConfigError(ConfigurationError):
    """Raised when configuration is invalid or incomplete."""
    pass


class MissingCredentialsError(ConfigurationError):
    """Raised when required credentials are missing."""
    pass


# Agent Errors
class AgentError(FinanceFeedbackEngineError):
    """Base exception for trading agent errors."""
    pass


class AgentStateError(AgentError):
    """Raised when agent is in invalid state for requested operation."""
    pass


class KillSwitchTriggeredError(AgentError):
    """Raised when agent kill-switch is triggered (P&L limits exceeded)."""
    pass


# Memory/Persistence Errors
class PersistenceError(FinanceFeedbackEngineError):
    """Base exception for persistence/storage errors."""
    pass


class DecisionStoreError(PersistenceError):
    """Raised when decision cannot be stored or retrieved."""
    pass


class MemoryCorruptionError(PersistenceError):
    """Raised when portfolio memory data is corrupted."""
    pass


# Monitoring Errors
class MonitoringError(FinanceFeedbackEngineError):
    """Base exception for monitoring/tracking errors."""
    pass


class TradeTrackingError(MonitoringError):
    """Raised when trade cannot be tracked."""
    pass


class MetricsCollectionError(MonitoringError):
    """Raised when metrics collection fails."""
    pass
