from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def _now(tz_name: str | None = None) -> datetime:
    return datetime.now(ZoneInfo(tz_name or get_settings().timezone))


def get_current_date(tz_name: str | None = None) -> dict:
    now = _now(tz_name)
    return {
        "date": now.date().isoformat(),
        "day_of_week": now.strftime("%A"),
        "timezone": str(now.tzinfo),
    }


def get_current_time(tz_name: str | None = None) -> dict:
    now = _now(tz_name)
    return {
        "time": now.strftime("%H:%M:%S"),
        "iso_datetime": now.isoformat(timespec="seconds"),
        "timezone": str(now.tzinfo),
    }
