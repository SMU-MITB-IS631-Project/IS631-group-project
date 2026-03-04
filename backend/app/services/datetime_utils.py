from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime.

    Prefer this over `datetime.utcnow()` (naive datetime).
    """

    return datetime.now(timezone.utc)
