"""Helpers for the UTC timestamps stored in the cache."""

from datetime import datetime, timedelta, timezone


def utc_now() -> str:
    """Returns the current UTC time as an ISO 8601 string.

    Returns:
        timestamp (str): The current time, for example
            2026-10-10T12:00:00+00:00.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")

    return timestamp


def utc_cutoff(max_age_hours: int) -> str:
    """Returns the UTC time that is max_age_hours before now, as ISO 8601.

    Args:
        max_age_hours (int): How many hours back the cutoff is.

    Returns:
        cutoff (str): The cutoff time, in the same format as utc_now().
    """
    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=max_age_hours)
    cutoff = cutoff_time.isoformat(timespec="seconds")

    return cutoff
