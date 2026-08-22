from __future__ import annotations

import os
from datetime import datetime, timezone, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@lru_cache(maxsize=8)
def _timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def app_timezone() -> tzinfo:
    return _timezone(os.getenv("MMRLOL_TIMEZONE", "Europe/Madrid").strip() or "Europe/Madrid")


def app_now() -> datetime:
    return datetime.now(app_timezone())


def to_app_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=app_timezone())
    return value.astimezone(app_timezone())
