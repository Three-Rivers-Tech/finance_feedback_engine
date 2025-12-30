"""
Discovery Filters for Pair Universe.

Implements safeguards to prevent low-liquidity, manipulated, and new pairs
from entering the trading universe. Enforces filters for:
- Minimum 24h volume
- Minimum listing age
- Maximum bid-ask spread
- Minimum order book depth
- Suspicious pattern detection
- Minimum venue count
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryFilterConfig:
    """Configuration for pair discovery filters."""

    # Enable/disable filter enforcement
    enabled: bool = True

    # Minimum 24-hour volume threshold (in USD)
    volume_threshold_usd: float = 50_000_000  # 50M USD

    # Minimum listing age (in days)
    min_listing_age_days: int = 365

    # Maximum bid-ask spread threshold (as percentage, e.g. 0.001 = 0.1%)
    max_spread_pct: float = 0.001

    # Minimum order book depth (in USD)
    min_depth_usd: float = 10_000_000  # 10M USD

    # Exclude pairs with suspicious patterns
    exclude_suspicious_patterns: bool = True

    # Minimum number of venues required
    min_venue_count: int = 2

    # Auto-add discovered pairs to whitelist
    auto_add_to_whitelist: bool = False


@dataclass
class WhitelistConfig:
    """Configuration for whitelist-based pair selection."""

    # Enable whitelist mode (takes precedence over discovery)
    enabled: bool = True

    # List of whitelisted pairs
    whitelist_entries: List[str] = None

    def __post_init__(self):
        """Initialize whitelist entries if None."""
        if self.whitelist_entries is None:
            self.whitelist_entries = [
                "BTCUSD",
                "ETHUSD",
                "EURUSD",
                "GBPUSD",
                "USDJPY",
            ]


@dataclass
class PairMetrics:
    """Metrics for a trading pair (used during discovery filtering)."""

    pair: str
    volume_24h_usd: float
    listing_age_days: int
    bid_ask_spread_pct: float
    order_book_depth_usd: float
    venue_count: int
    suspicious_pattern_score: float  # 0.0-1.0, higher = more suspicious


class PairDiscoveryFilter:
    """
    Filters discovered pairs based on quality safeguards.

    Prevents selection of:
    - Low-liquidity pairs (volume < threshold)
    - New pairs (listing age < threshold)
    - Pairs with wide spreads
    - Shallow order books
    - Pairs with manipulation indicators
    - Pairs listed on too few venues
    """

    def __init__(
        self,
        discovery_filter_config: DiscoveryFilterConfig,
        whitelist_config: WhitelistConfig,
    ):
        """
        Initialize Discovery Filter.

        Args:
            discovery_filter_config: Discovery filter configuration
            whitelist_config: Whitelist configuration
        """
        self.discovery_config = discovery_filter_config
        self.whitelist_config = whitelist_config

        logger.info(
            f"PairDiscoveryFilter initialized "
            f"(whitelist_enabled={whitelist_config.enabled}, "
            f"discovery_filters_enabled={discovery_filter_config.enabled})"
        )

        if whitelist_config.enabled:
            logger.info(
                f"Whitelist mode: {len(whitelist_config.whitelist_entries)} "
                f"trusted pairs configured"
            )

        if discovery_filter_config.enabled:
            logger.info(
                f"Discovery filters enabled: "
                f"volume>={discovery_filter_config.volume_threshold_usd:,.0f} USD, "
                f"age>={discovery_filter_config.min_listing_age_days} days, "
                f"spread<={discovery_filter_config.max_spread_pct*100:.2f}%, "
                f"depth>={discovery_filter_config.min_depth_usd:,.0f} USD, "
                f"venues>={discovery_filter_config.min_venue_count}"
            )

    def filter_pairs(
        self,
        discovered_pairs: List[str],
        pair_metrics: Optional[Dict[str, PairMetrics]] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Filter discovered pairs based on configured safeguards.

        If whitelist is enabled, returns whitelisted pairs only.
        Otherwise, applies discovery filters to discovered pairs.

        Args:
            discovered_pairs: List of pairs discovered from exchanges
            pair_metrics: Optional metrics for each pair (for detailed filtering)

        Returns:
            Tuple of (filtered_pairs, rejection_reasons)
            - filtered_pairs: List of pairs passing filters
            - rejection_reasons: Dict[pair] -> reason for rejection
        """
        rejection_reasons: Dict[str, str] = {}

        # Phase 1: Whitelist takes precedence
        if self.whitelist_config.enabled:
            logger.info(
                f"Whitelist mode enabled: returning {len(self.whitelist_config.whitelist_entries)} "
                f"whitelisted pairs"
            )
            filtered = self.whitelist_config.whitelist_entries.copy()

            # Mark non-whitelisted discovered pairs as rejected
            for pair in discovered_pairs:
                if pair not in filtered:
                    rejection_reasons[pair] = "NOT_IN_WHITELIST"

            return filtered, rejection_reasons

        # Phase 2: Discovery filters (if whitelist disabled)
        if not self.discovery_config.enabled:
            logger.info("Discovery filters disabled: accepting all discovered pairs")
            return discovered_pairs, rejection_reasons

        logger.info(
            f"Applying discovery filters to {len(discovered_pairs)} discovered pairs"
        )
        filtered = []

        for pair in discovered_pairs:
            reason = self._should_reject_pair(pair, pair_metrics)
            if reason:
                rejection_reasons[pair] = reason
                logger.debug(f"  ✗ {pair}: {reason}")
            else:
                filtered.append(pair)
                logger.debug(f"  ✓ {pair}: passed filters")

        logger.info(
            f"Discovery filters result: {len(filtered)} accepted, "
            f"{len(rejection_reasons)} rejected"
        )

        return filtered, rejection_reasons

    def _should_reject_pair(
        self, pair: str, pair_metrics: Optional[Dict[str, PairMetrics]] = None
    ) -> Optional[str]:
        """
        Determine if a pair should be rejected by filters.

        Args:
            pair: Pair to evaluate (e.g., 'BTCUSD')
            pair_metrics: Optional metrics for detailed filtering

        Returns:
            Rejection reason if pair fails filters, None if accepted
        """
        # If metrics not available, use basic blacklist/whitelist only
        if pair_metrics is None or pair not in pair_metrics:
            # No metrics available - accept pair if discovery filters allow
            return None

        metrics = pair_metrics[pair]

        # Check volume threshold
        if metrics.volume_24h_usd < self.discovery_config.volume_threshold_usd:
            return (
                f"LOW_VOLUME ({metrics.volume_24h_usd:,.0f} USD < "
                f"{self.discovery_config.volume_threshold_usd:,.0f} USD)"
            )

        # Check listing age
        if metrics.listing_age_days < self.discovery_config.min_listing_age_days:
            return (
                f"TOO_NEW ({metrics.listing_age_days} days < "
                f"{self.discovery_config.min_listing_age_days} days)"
            )

        # Check bid-ask spread
        if metrics.bid_ask_spread_pct > self.discovery_config.max_spread_pct:
            return (
                f"WIDE_SPREAD ({metrics.bid_ask_spread_pct*100:.2f}% > "
                f"{self.discovery_config.max_spread_pct*100:.2f}%)"
            )

        # Check order book depth
        if metrics.order_book_depth_usd < self.discovery_config.min_depth_usd:
            return (
                f"SHALLOW_DEPTH ({metrics.order_book_depth_usd:,.0f} USD < "
                f"{self.discovery_config.min_depth_usd:,.0f} USD)"
            )

        # Check venue count
        if metrics.venue_count < self.discovery_config.min_venue_count:
            return (
                f"INSUFFICIENT_VENUES ({metrics.venue_count} < "
                f"{self.discovery_config.min_venue_count})"
            )

        # Check for suspicious patterns
        if (
            self.discovery_config.exclude_suspicious_patterns
            and metrics.suspicious_pattern_score > 0.7
        ):
            return (
                f"SUSPICIOUS_PATTERN "
                f"(score: {metrics.suspicious_pattern_score:.2f} > 0.7)"
            )

        return None

    def add_to_whitelist(self, pair: str) -> bool:
        """
        Conditionally add discovered pair to whitelist.

        Only allowed if auto_add_to_whitelist is enabled and
        whitelist mode is active.

        Args:
            pair: Pair to add (e.g., 'BTCUSD')

        Returns:
            True if added, False otherwise
        """
        if not self.discovery_config.auto_add_to_whitelist:
            logger.debug(
                f"auto_add_to_whitelist disabled: {pair} not added to whitelist"
            )
            return False

        if not self.whitelist_config.enabled:
            logger.debug(
                f"whitelist_enabled disabled: {pair} not added to whitelist"
            )
            return False

        if pair in self.whitelist_config.whitelist_entries:
            logger.debug(f"{pair} already in whitelist")
            return False

        self.whitelist_config.whitelist_entries.append(pair)
        logger.info(f"Added {pair} to whitelist (auto_add_to_whitelist=true)")
        return True

    def get_filter_summary(self) -> Dict[str, any]:
        """
        Get summary of active filters.

        Returns:
            Dictionary with filter configuration summary
        """
        return {
            "whitelist_enabled": self.whitelist_config.enabled,
            "whitelist_count": (
                len(self.whitelist_config.whitelist_entries)
                if self.whitelist_config.enabled
                else 0
            ),
            "discovery_filters_enabled": self.discovery_config.enabled,
            "volume_threshold_usd": self.discovery_config.volume_threshold_usd,
            "min_listing_age_days": self.discovery_config.min_listing_age_days,
            "max_spread_pct": self.discovery_config.max_spread_pct,
            "min_depth_usd": self.discovery_config.min_depth_usd,
            "exclude_suspicious_patterns": self.discovery_config.exclude_suspicious_patterns,
            "min_venue_count": self.discovery_config.min_venue_count,
            "auto_add_to_whitelist": self.discovery_config.auto_add_to_whitelist,
        }
