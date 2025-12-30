"""Tests for data freshness validation."""

import datetime as dt
from datetime import timezone

import pytest
from freezegun import freeze_time

from finance_feedback_engine.utils.validation import validate_data_freshness


class TestValidateDataFreshness:
    """Test suite for validate_data_freshness function."""

    @freeze_time("2024-01-15 12:00:00")
    def test_fresh_crypto_data_no_warning(self):
        """Crypto data within 5 minutes should have no warning."""
        fresh_ts = "2024-01-15T11:58:00Z"  # 2 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(fresh_ts, "crypto")
        assert is_fresh is True
        assert warning == ""
        assert "2" in age_str and "minute" in age_str

    @freeze_time("2024-01-15 12:00:00")
    def test_crypto_warning_threshold_5_minutes(self):
        """Crypto data > 5 mins but ≤ 15 mins should warn but remain usable."""
        stale_ts = "2024-01-15T11:53:00Z"  # 7 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(stale_ts, "crypto")
        assert is_fresh is True  # Still usable
        assert "WARNING" in warning
        assert "7" in age_str

    @freeze_time("2024-01-15 12:00:00")
    def test_crypto_critical_threshold_15_minutes(self):
        """Crypto data > 15 mins should be critical (not fresh)."""
        very_stale_ts = "2024-01-15T11:40:00Z"  # 20 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(very_stale_ts, "crypto")
        assert is_fresh is False
        assert "CRITICAL" in warning
        assert "20" in age_str

    @freeze_time("2024-01-15 12:00:00")
    def test_forex_warning_threshold_5_minutes(self):
        """Forex data follows same thresholds as crypto."""
        stale_ts = "2024-01-15T11:54:00Z"  # 6 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(stale_ts, "forex")
        assert is_fresh is True  # Still usable
        assert "WARNING" in warning
        assert "Forex" in warning

    @freeze_time("2024-01-15 12:00:00")
    def test_forex_critical_threshold_15_minutes(self):
        """Forex data > 15 mins should be critical."""
        very_stale_ts = "2024-01-15T11:44:00Z"  # 16 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(very_stale_ts, "forex")
        assert is_fresh is False
        assert "CRITICAL" in warning

    @freeze_time("2024-01-15 12:00:00")
    def test_stock_intraday_warning_threshold_5_minutes(self):
        """Stock intraday data >= 15 mins should warn during market hours."""
        stale_ts = "2024-01-15T11:40:00Z"  # 20 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(
            stale_ts, "stocks", timeframe="intraday"
        )
        assert is_fresh is True  # Still usable (< 60 min critical threshold)
        assert "WARNING" in warning
        assert "intraday" in warning.lower() or "15 minutes" in warning

    @freeze_time("2024-01-15 12:00:00")
    def test_stock_intraday_critical_threshold_15_minutes(self):
        """Stock intraday data > 60 mins should be critical during market hours."""
        very_stale_ts = "2024-01-15T10:50:00Z"  # 70 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(
            very_stale_ts, "stocks", timeframe="intraday"
        )
        assert is_fresh is False
        assert "CRITICAL" in warning

    @freeze_time("2024-01-15 12:00:00")
    def test_stock_daily_warning_threshold_24_hours(self):
        """Stock daily data > 24 hours should be critical during market hours."""
        old_ts = "2024-01-14T10:00:00Z"  # 26 hours ago

        is_fresh, age_str, warning = validate_data_freshness(
            old_ts, "stocks", timeframe="daily"
        )
        assert is_fresh is False  # Not fresh (> 24 hour threshold during market hours)
        assert "CRITICAL" in warning
        assert "daily" in warning.lower()
        assert "24" in warning  # Should mention 24 hour threshold

    @freeze_time("2024-01-15 12:00:00")
    def test_stock_daily_fresh_within_24_hours(self):
        """Stock daily data within 24 hours should have no critical warning."""
        fresh_ts = "2024-01-15T00:00:00Z"  # 12 hours ago

        is_fresh, age_str, warning = validate_data_freshness(
            fresh_ts, "stocks", timeframe="daily"
        )
        assert is_fresh is True
        # Warns when > 4 hours old but remains usable
        assert "WARNING" in warning
        assert "Stock daily data is" in warning
        assert "4 hours" in warning

    @freeze_time("2024-01-15 12:00:00")
    def test_stock_daily_no_warning_under_4_hours(self):
        """Stock daily data under 4 hours should have no warning."""
        ts = "2024-01-15T09:00:00Z"  # 3 hours ago

        is_fresh, age_str, warning = validate_data_freshness(
            ts, "stocks", timeframe="daily"
        )
        assert is_fresh is True
        assert warning == ""

    def test_timestamp_with_z_suffix(self):
        """Should handle ISO 8601 with 'Z' UTC indicator."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=1)).isoformat(timespec="seconds").replace(
            "+00:00", ""
        ) + "Z"

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        assert is_fresh is True
        assert "1." in age_str

    def test_timestamp_with_timezone_offset(self):
        """Should handle ISO 8601 with +00:00 timezone offset."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=3)).isoformat()

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        assert is_fresh is True
        assert "3." in age_str

    def test_age_string_seconds_format(self):
        """Age string should format as seconds when < 1 minute."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(seconds=45)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        assert "45" in age_str
        assert "seconds" in age_str

    def test_age_string_minutes_format(self):
        """Age string should format as minutes when between 1 and 60 minutes."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=12)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        assert "12" in age_str
        assert "minutes" in age_str
        assert "hours" not in age_str

    def test_age_string_hours_format(self):
        """Age string should format as hours when >= 60 minutes."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(hours=2)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(
            ts, "stocks", timeframe="daily"
        )
        assert "2.00" in age_str
        assert "hours" in age_str

    def test_case_insensitive_asset_type(self):
        """Asset type should be case-insensitive."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=2)).isoformat().replace("+00:00", "Z")

        result_lower = validate_data_freshness(ts, "crypto")
        result_upper = validate_data_freshness(ts, "CRYPTO")
        result_mixed = validate_data_freshness(ts, "CrYpTo")

        assert result_lower[0] == result_upper[0] == result_mixed[0] is True
        assert result_lower[2] == result_upper[2] == result_mixed[2] == ""

    @freeze_time("2024-01-15 12:00:00")
    def test_case_insensitive_timeframe(self):
        """Timeframe should be case-insensitive."""
        ts = "2024-01-14T10:00:00Z"  # 26 hours ago

        result_lower = validate_data_freshness(ts, "stocks", "daily")
        result_upper = validate_data_freshness(ts, "stocks", "DAILY")
        result_mixed = validate_data_freshness(ts, "stocks", "DaIly")

        # All should have same freshness status (not fresh for >24 hour data)
        assert result_lower[0] == result_upper[0] == result_mixed[0] is False

    def test_unknown_asset_type_defaults_to_crypto_thresholds(self):
        """Unknown asset types should default to crypto thresholds."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=8)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts, "unknown_asset")
        assert is_fresh is True  # Within 15 mins
        assert "WARNING" in warning  # But warns (> 5 mins)

    def test_invalid_timestamp_format_raises_error(self):
        """Invalid timestamp format should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_data_freshness("not-a-timestamp", "crypto")
        assert "Invalid data_timestamp" in str(exc_info.value)
        assert "ISO 8601" in str(exc_info.value)

    def test_empty_timestamp_raises_error(self):
        """Empty timestamp should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_data_freshness("", "crypto")
        assert "non-empty" in str(exc_info.value)

    def test_none_timestamp_raises_error(self):
        """None timestamp should raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_data_freshness(None, "crypto")
        assert "non-empty" in str(exc_info.value)

    def test_default_asset_type_is_crypto(self):
        """When asset_type is None, should default to crypto thresholds."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=7)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts)  # No asset_type
        assert is_fresh is True
        assert "WARNING" in warning

    @freeze_time("2024-01-15 12:00:00")
    def test_default_timeframe_is_intraday(self):
        """When timeframe is None, stocks should default to intraday."""
        ts = "2024-01-15T11:40:00Z"  # 20 minutes ago

        is_fresh, age_str, warning = validate_data_freshness(
            ts, "stocks"
        )  # No timeframe
        assert is_fresh is True
        assert "WARNING" in warning  # Should warn for >= 15 min old intraday

    def test_edge_case_exactly_5_minutes_old_crypto(self):
        """Data exactly 5 minutes old should be at warning threshold for crypto."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=5)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        # Exactly at threshold - may or may not warn depending on precision
        assert is_fresh is True  # Still usable

    def test_edge_case_exactly_15_minutes_old_crypto(self):
        """Data exactly 15 minutes old should warn but remain usable for crypto (critical is > 15)."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(minutes=15)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        # Exactly at threshold but not over it (> 15): warn, still usable
        assert is_fresh is True
        assert "WARNING" in warning

    def test_fractional_minute_age_string(self):
        """Age should show fractional minutes."""
        now = dt.datetime.now(timezone.utc)
        ts = (now - dt.timedelta(seconds=150)).isoformat().replace("+00:00", "Z")

        is_fresh, age_str, warning = validate_data_freshness(ts, "crypto")
        assert "2.5" in age_str or "2.4" in age_str  # ~2.5 minutes
        assert "minutes" in age_str
