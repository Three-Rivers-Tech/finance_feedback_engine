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
            "time_to_open": 0,
            "warning": warning,
        }

    @classmethod
    def _forex_status(cls, now_utc: _dt.datetime) -> Dict[str, object]:
        now_ny = now_utc.astimezone(cls.NY_TZ)
        now_london = now_utc.astimezone(cls.LONDON_TZ)

        weekday = now_ny.weekday()  # Monday=0, Sunday=6
        ny_hour = now_ny.hour
        weekend_window = (
            (weekday == 4 and ny_hour >= 17)  # Friday after 5 PM NY
            or weekday == 5  # Saturday
            or (weekday == 6 and ny_hour < 17)  # Sunday before 5 PM NY
        )

        if weekend_window:
            # Calculate time until Sunday 5 PM NY reopening
            if weekday == 6 and ny_hour < 17:
                # Already Sunday before 5 PM
                reopen_dt = now_ny.replace(hour=17, minute=0, second=0, microsecond=0)
            else:
                # Friday evening or Saturday - calculate days until Sunday
                days_until_sunday = (6 - weekday) % 7
                reopen_date = now_ny.date() + _dt.timedelta(days=days_until_sunday)
                reopen_dt = cls.NY_TZ.localize(
                    _dt.datetime.combine(reopen_date, _dt.time(hour=17, minute=0))
                )
            time_to_open = int(max(0, (reopen_dt - now_ny).total_seconds() // 60))

            return {
                "is_open": False,
                "session": "Closed",
                "time_to_close": 0,
                "time_to_open": time_to_open,
                "warning": "Forex market closed for weekend",
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
            "time_to_open": 0,
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
            # Next open at 9:30 AM NY on the next business day (or later today before open)
            if is_weekday and now_ny.time() < open_time:
                next_open_date = now_ny.date()
            else:
                next_open_date = now_ny.date()
                while True:
                    next_open_date += _dt.timedelta(days=1)
                    if next_open_date.weekday() <= 4:
                        break

            open_dt = cls.NY_TZ.localize(
                _dt.datetime.combine(next_open_date, open_time)
            )
            time_to_open = int(max(0, (open_dt - now_ny).total_seconds() // 60))

            return {
                "is_open": False,
                "session": "Closed",
                "time_to_close": 0,
                "time_to_open": time_to_open,
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
            "time_to_open": 0,
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
            Dictionary with:
            - is_open: bool
            - session: str
            - time_to_close: minutes until current session closes (0 when closed)
            - time_to_open: minutes until next session opens (0 when already open)
            - warning: str
        """
        now_utc = _dt.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.UTC)
        return cls.get_market_status(asset_pair, asset_type, now_utc=now_utc)
