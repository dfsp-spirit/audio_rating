from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Returns:
        datetime: Current time with ``timezone.utc``.
    """
    return datetime.now(timezone.utc)
