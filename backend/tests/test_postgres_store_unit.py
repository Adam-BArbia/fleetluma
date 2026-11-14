"""FL-15 non-network PostgreSQL adapter unit tests."""
from datetime import datetime, timedelta, timezone

from fleetluma_backend.postgres_store import host_state, iso, WINDOWS


def test_host_state_missing_fresh_and_stale():
    now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    assert host_state(None, now) == "PENDING"
    assert host_state(now - timedelta(seconds=5), now) == "CONNECTED"
    assert host_state(now - timedelta(seconds=50), now) == "STALE"


def test_utc_timestamp_iso_and_windows():
    now = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
    assert iso(now) == "2026-11-14T12:00:00Z"
    assert set(WINDOWS) == {"15m", "1h", "24h"}
