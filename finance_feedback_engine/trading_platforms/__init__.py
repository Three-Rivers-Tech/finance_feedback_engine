"""Trading platforms module initialization."""

from .base_platform import BaseTradingPlatform
from .coinbase_platform import CoinbaseAdvancedPlatform
from .coinbase_portfolio_retriever import CoinbasePortfolioRetriever
from .mock_platform import MockTradingPlatform
from .mock_portfolio_retriever import MockPortfolioRetriever
from .oanda_platform import OandaPlatform
from .oanda_portfolio_retriever import OandaPortfolioRetriever
from .platform_factory import PlatformFactory
from .portfolio_retriever import PortfolioRetrieverFactory
from .unified_platform import UnifiedTradingPlatform

# Register portfolio retrievers
PortfolioRetrieverFactory.register("coinbase", CoinbasePortfolioRetriever)
PortfolioRetrieverFactory.register("oanda", OandaPortfolioRetriever)
PortfolioRetrieverFactory.register("mock", MockPortfolioRetriever)

__all__ = [
    "BaseTradingPlatform",
    "CoinbaseAdvancedPlatform",
    "OandaPlatform",
    "UnifiedTradingPlatform",
    "MockTradingPlatform",
    "PlatformFactory",
    "PortfolioRetrieverFactory",
    "CoinbasePortfolioRetriever",
    "OandaPortfolioRetriever",
    "MockPortfolioRetriever",
]
