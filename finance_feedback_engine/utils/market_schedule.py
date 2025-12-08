"""Market schedule and session awareness utilities.

All internal logic uses UTC for calculations but converts to local market
zones (New York or London) for open/close boundaries and session labels.
"""
import datetime as _dt
from typing import Dict

import pytz


class MarketSchedule:
    """Provide market open/close checks and session labels."""

    NY_TZ = pytz.timezone("America/New_York")
    LONDON_TZ = pytz.timezone("Europe/London")

    @classmethod
    def get_market_status(
        cls,
        asset_pair: str,
        asset_type: str,
        now_utc: _dt.datetime | None = None,
    ) -> Dict[str, object]:
        """Return current market status for the given asset type.

        Args:
            asset_pair: Symbol pair; currently used only for crypto weekend warnings.
            asset_type: One of "crypto", "forex", or "stocks" (case-insensitive).
            now_utc: Optional timezone-aware UTC datetime for testing/overrides.
        """
        now_utc = now_utc or _dt.datetime.utcnow().replace(tzinfo=pytz.UTC)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=pytz.UTC)
        asset_kind = (asset_type or "crypto").lower()

        if asset_kind == "forex":
            return cls._forex_status(now_utc)
        if asset_kind == "stocks":
            return cls._stock_status(now_utc)

        return cls._crypto_status(now_utc)

    @classmethod
    def _crypto_status(cls, now_utc: _dt.datetime) -> Dict[str, object]:
        warning = "Weekend Low Liquidity" if now_utc.weekday() >= 5 else ""
        return {
            "is_open": True,
            "session": "Open",
            "time_to_close": 0,
            "warning": warning,
        }

    @classmethod
    def _forex_status(cls, now_utc: _dt.datetime) -> Dict[str, object]:
        now_ny = now_utc.astimezone(cls.NY_TZ)
        now_london = now_utc.astimezone(cls.LONDON_TZ)

        weekday = now_ny.weekday()  # Monday=0, Sunday=6
        ny_hour = now_ny.hour

        closed = False
        if weekday == 4 and ny_hour >= 17:
            closed = True  # Friday after 5 PM NY
        elif weekday == 5:
            closed = True  # Saturday
        elif weekday == 6 and ny_hour < 17:
            closed = True  # Sunday before 5 PM NY

        if closed:
            return {
                "is_open": False,
                "session": "Closed",
                "time_to_close": 0,
                "warning": "",
            }

        # Determine session based on major center hours.
        london_open = 8 <= now_london.hour < 17
        ny_open = 8 <= now_ny.hour < 17
        if london_open and ny_open:
            session = "Overlap"
        elif london_open:
            session = "London"
        elif ny_open:
            session = "New York"
        else:
            session = "Asian"

        # Compute minutes until the next market close (Friday 5 PM NY).
        if weekday == 4 and ny_hour < 17:
            close_dt = now_ny.replace(hour=17, minute=0, second=0, microsecond=0)
        else:
            days_until_friday = (4 - weekday) % 7
            close_date = now_ny.date() + _dt.timedelta(days=days_until_friday)
            close_dt = cls.NY_TZ.localize(
                _dt.datetime.combine(close_date, _dt.time(hour=17, minute=0))
            )

        time_to_close = int(max(0, (close_dt - now_ny).total_seconds() // 60))

        return {
            "is_open": True,
            "session": session,
            "time_to_close": time_to_close,
            "warning": "",
        }

    @classmethod
    def _stock_status(cls, now_utc: _dt.datetime) -> Dict[str, object]:
        now_ny = now_utc.astimezone(cls.NY_TZ)
        weekday = now_ny.weekday()
        open_time = _dt.time(hour=9, minute=30)
        close_time = _dt.time(hour=16, minute=0)

        is_weekday = 0 <= weekday <= 4
        within_hours = open_time <= now_ny.time() < close_time
        is_open = is_weekday and within_hours

        if not is_open:
            return {
                "is_open": False,
                "session": "Closed",
                "time_to_close": 0,
                "warning": "",
            }

        close_dt = now_ny.replace(
            hour=close_time.hour,
            minute=close_time.minute,
            second=0,
            microsecond=0,
        )
        time_to_close = int(max(0, (close_dt - now_ny).total_seconds() // 60))

        return {
            "is_open": True,
            "session": "New York",
            "time_to_close": time_to_close,
            "warning": "",
        }

    @classmethod
    def get_market_status_at_timestamp(
        cls, asset_pair: str, asset_type: str, timestamp: int
    ) -> Dict[str, object]:
        """Return market status at a given Unix timestamp (for backtesting).

        Args:
            asset_pair: Symbol pair.
            asset_type: One of "crypto", "forex", or "stocks".
            timestamp: Unix timestamp (seconds since epoch).

        Returns:
            Dictionary with is_open, session, time_to_close, warning keys.
        """
        now_utc = _dt.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC)
        return cls.get_market_status(asset_pair, asset_type, now_utc=now_utc)
