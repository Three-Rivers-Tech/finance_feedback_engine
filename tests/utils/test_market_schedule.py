import datetime as dt

import pytz

from finance_feedback_engine.utils.market_schedule import MarketSchedule


def _to_utc(local_dt: dt.datetime, tz: pytz.BaseTzInfo) -> dt.datetime:
    return tz.localize(local_dt).astimezone(pytz.UTC)


def _to_unix(utc_dt: dt.datetime) -> int:
    """Convert UTC datetime to Unix timestamp."""
    return int(utc_dt.timestamp())


def test_forex_friday_boundary_stays_open():
    open_dt = _to_utc(dt.datetime(2024, 5, 10, 16, 59), MarketSchedule.NY_TZ)
    status_open = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=open_dt)
    assert status_open["is_open"] is True
    assert status_open["session"] == "New York"
    assert status_open["time_to_close"] > 0

    close_dt = _to_utc(dt.datetime(2024, 5, 10, 17, 0), MarketSchedule.NY_TZ)
    status_weekend = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=close_dt)
    assert status_weekend["is_open"] is True
    assert status_weekend["session"] == "Weekend"
    assert status_weekend["warning"] == "Weekend forex trading has reduced liquidity and wider spreads"
    assert status_weekend["time_to_close"] == 0
    assert status_weekend["time_to_open"] == 0


def test_forex_sunday_reopen_window():
    pre_reopen = _to_utc(dt.datetime(2024, 5, 12, 16, 0), MarketSchedule.NY_TZ)
    status_pre = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=pre_reopen)
    assert status_pre["is_open"] is True
    assert status_pre["session"] == "Weekend"
    assert status_pre["warning"] == "Weekend forex trading has reduced liquidity and wider spreads"

    post_reopen = _to_utc(dt.datetime(2024, 5, 12, 17, 0), MarketSchedule.NY_TZ)
    status_open = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=post_reopen)
    assert status_open["is_open"] is True
    assert status_open["session"] != "Closed"
    assert status_open["warning"] == ""


def test_stock_open_and_close_edges():
    pre_open = _to_utc(dt.datetime(2024, 5, 13, 9, 29), MarketSchedule.NY_TZ)
    status_pre = MarketSchedule.get_market_status("AAPL", "stocks", now_utc=pre_open)
    assert status_pre["is_open"] is False

    at_open = _to_utc(dt.datetime(2024, 5, 13, 9, 30), MarketSchedule.NY_TZ)
    status_open = MarketSchedule.get_market_status("AAPL", "stocks", now_utc=at_open)
    assert status_open["is_open"] is True
    assert status_open["time_to_close"] == 390

    at_close = _to_utc(dt.datetime(2024, 5, 13, 16, 0), MarketSchedule.NY_TZ)
    status_close = MarketSchedule.get_market_status("AAPL", "stocks", now_utc=at_close)
    assert status_close["is_open"] is False


# ============================================================================
# CRYPTO TESTS
# ============================================================================


def test_crypto_always_open_weekday():
    """Crypto markets are 24/7 on weekdays with no liquidity warning."""
    dt_monday = _to_utc(dt.datetime(2024, 5, 13, 14, 30), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("BTCUSD", "crypto", now_utc=dt_monday)
    assert status["is_open"] is True
    assert status["warning"] == ""
    assert status["session"] == "Open"
    assert status["time_to_close"] == 0


def test_crypto_weekend_low_liquidity_warning():
    """Crypto is open 24/7 but warns of weekend low liquidity."""
    dt_saturday = _to_utc(dt.datetime(2024, 5, 11, 10, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("ETHUSD", "crypto", now_utc=dt_saturday)
    assert status["is_open"] is True
    assert status["warning"] == "Weekend Low Liquidity"
    assert status["session"] == "Open"

    dt_sunday = _to_utc(dt.datetime(2024, 5, 12, 10, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("ETHUSD", "crypto", now_utc=dt_sunday)
    assert status["is_open"] is True
    assert status["warning"] == "Weekend Low Liquidity"


# ============================================================================
# FOREX SESSION DETECTION
# ============================================================================


def test_forex_asian_session():
    """Test Asian session detection (outside London and NY hours)."""
    dt_tokyo = _to_utc(dt.datetime(2024, 5, 13, 2, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("GBPJPY", "forex", now_utc=dt_tokyo)
    assert status["is_open"] is True
    assert status["session"] == "Asian"


def test_forex_london_session():
    """Test London-only session (8-17 London time, outside NY hours)."""
    # London 10 AM, New York 5 AM
    dt_london = _to_utc(dt.datetime(2024, 5, 13, 10, 0), MarketSchedule.LONDON_TZ)
    status = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_london)
    assert status["is_open"] is True
    assert status["session"] == "London"


def test_forex_ny_session():
    """Test New York-only session (8-17 NY time, outside London hours)."""
    # New York 1 PM, London 5 PM (London closed)
    dt_ny = _to_utc(dt.datetime(2024, 5, 13, 13, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_ny)
    assert status["is_open"] is True
    assert status["session"] == "New York"


def test_forex_overlap_session():
    """Test overlap session (both London and NY 8-17)."""
    # New York 9 AM, London 2 PM
    dt_overlap = _to_utc(dt.datetime(2024, 5, 13, 9, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_overlap)
    assert status["is_open"] is True
    assert status["session"] == "Overlap"


def test_forex_saturday_open_with_warning():
    """Forex should stay open on weekends but emit liquidity warning."""
    dt_saturday = _to_utc(dt.datetime(2024, 5, 11, 12, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_saturday)
    assert status["is_open"] is True
    assert status["session"] == "Weekend"
    assert status["warning"] == "Weekend forex trading has reduced liquidity and wider spreads"


def test_forex_time_to_close_friday():
    """Test time_to_close calculation on Friday."""
    # Friday 3 PM NY (2 hours before 5 PM close)
    dt_friday = _to_utc(dt.datetime(2024, 5, 10, 15, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_friday)
    assert status["is_open"] is True
    assert status["time_to_close"] == 120


def test_forex_time_to_close_midweek():
    """Test time_to_close points to next Friday close from midweek."""
    # Monday 10 AM NY
    dt_monday = _to_utc(dt.datetime(2024, 5, 13, 10, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_monday)
    assert status["is_open"] is True
    # Next Friday is May 17, 5 PM = 4 days * 24 hours + 7 hours = 103 hours = 6180 minutes
    assert status["time_to_close"] == 6180


# ============================================================================
# STOCK SESSION TESTS
# ============================================================================


def test_stock_weekend_closed():
    """Test stocks are closed on weekends."""
    dt_saturday = _to_utc(dt.datetime(2024, 5, 11, 10, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("AAPL", "stocks", now_utc=dt_saturday)
    assert status["is_open"] is False
    assert status["session"] == "Closed"

    dt_sunday = _to_utc(dt.datetime(2024, 5, 12, 15, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("AAPL", "stocks", now_utc=dt_sunday)
    assert status["is_open"] is False
    assert status["session"] == "Closed"


def test_stock_time_to_close_midday():
    """Test time_to_close calculation during trading hours."""
    # 2 PM NY (2 hours before 4 PM close)
    dt_midday = _to_utc(dt.datetime(2024, 5, 13, 14, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("AAPL", "stocks", now_utc=dt_midday)
    assert status["is_open"] is True
    assert status["time_to_close"] == 120


def test_stock_session_label():
    """Stocks use 'New York' session label when open."""
    dt_open = _to_utc(dt.datetime(2024, 5, 13, 11, 0), MarketSchedule.NY_TZ)
    status = MarketSchedule.get_market_status("MSFT", "stocks", now_utc=dt_open)
    assert status["session"] == "New York"


# ============================================================================
# BACKTESTING: UNIX TIMESTAMP METHOD
# ============================================================================


def test_backtesting_forex_timestamp():
    """Test get_market_status_at_timestamp with Unix timestamps (backtesting)."""
    dt_friday = _to_utc(dt.datetime(2024, 5, 10, 16, 59), MarketSchedule.NY_TZ)
    timestamp = _to_unix(dt_friday)
    status = MarketSchedule.get_market_status_at_timestamp("EURUSD", "forex", timestamp)
    assert status["is_open"] is True

    # Friday 5 PM NY (previously closed window)
    dt_close = _to_utc(dt.datetime(2024, 5, 10, 17, 0), MarketSchedule.NY_TZ)
    timestamp_close = _to_unix(dt_close)
    status_close = MarketSchedule.get_market_status_at_timestamp("EURUSD", "forex", timestamp_close)
    assert status_close["is_open"] is True
    assert status_close["session"] == "Weekend"
    assert status_close["warning"] == "Weekend forex trading has reduced liquidity and wider spreads"


def test_backtesting_stock_timestamp():
    """Test stock market status via Unix timestamp."""
    dt_open = _to_utc(dt.datetime(2024, 5, 13, 9, 30), MarketSchedule.NY_TZ)
    timestamp = _to_unix(dt_open)
    status = MarketSchedule.get_market_status_at_timestamp("TSLA", "stocks", timestamp)
    assert status["is_open"] is True
    assert status["time_to_close"] == 390


def test_backtesting_crypto_timestamp():
    """Test crypto market status via Unix timestamp (should be open)."""
    dt_any = _to_utc(dt.datetime(2024, 5, 10, 12, 0), MarketSchedule.NY_TZ)  # Friday
    timestamp = _to_unix(dt_any)
    status = MarketSchedule.get_market_status_at_timestamp("BTCUSD", "crypto", timestamp)
    assert status["is_open"] is True
    assert status["warning"] == ""  # Friday is weekday for crypto


def test_backtesting_crypto_weekend_timestamp():
    """Test crypto weekend warning via Unix timestamp."""
    dt_saturday = _to_utc(dt.datetime(2024, 5, 11, 8, 0), MarketSchedule.NY_TZ)
    timestamp = _to_unix(dt_saturday)
    status = MarketSchedule.get_market_status_at_timestamp("ETHUSD", "crypto", timestamp)
    assert status["is_open"] is True
    assert status["warning"] == "Weekend Low Liquidity"


# ============================================================================
# EDGE CASES & DEFAULTS
# ============================================================================


def test_asset_type_case_insensitive():
    """Asset type should be case-insensitive."""
    dt_open = _to_utc(dt.datetime(2024, 5, 13, 10, 0), MarketSchedule.NY_TZ)

    status_lower = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=dt_open)
    status_upper = MarketSchedule.get_market_status("EURUSD", "FOREX", now_utc=dt_open)
    status_mixed = MarketSchedule.get_market_status("EURUSD", "FoReX", now_utc=dt_open)

    assert status_lower["is_open"] == status_upper["is_open"] == status_mixed["is_open"]


def test_default_asset_type_is_crypto():
    """When asset_type is None or unknown, default to crypto."""
    dt_saturday = _to_utc(dt.datetime(2024, 5, 11, 10, 0), MarketSchedule.NY_TZ)

    status_none = MarketSchedule.get_market_status("BTC", None, now_utc=dt_saturday)
    status_unknown = MarketSchedule.get_market_status("BTC", "unknown", now_utc=dt_saturday)

    assert status_none["is_open"] is True
    assert status_unknown["is_open"] is True
    assert status_none["warning"] == "Weekend Low Liquidity"
    assert status_unknown["warning"] == "Weekend Low Liquidity"


def test_timezone_awareness():
    """Verify UTC conversion from different input timezones."""
    # Same instant, different timezone inputs
    ny_dt = _to_utc(dt.datetime(2024, 5, 13, 13, 0), MarketSchedule.NY_TZ)
    london_dt = _to_utc(dt.datetime(2024, 5, 13, 18, 0), MarketSchedule.LONDON_TZ)

    # Should be the same UTC time
    assert ny_dt == london_dt

    status_ny = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=ny_dt)
    status_london = MarketSchedule.get_market_status("EURUSD", "forex", now_utc=london_dt)

    # Should have identical results
    assert status_ny["is_open"] == status_london["is_open"]
    assert status_ny["session"] == status_london["session"]

