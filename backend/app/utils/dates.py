from datetime import date, datetime
from zoneinfo import ZoneInfo

KENYA_TZ = ZoneInfo("Africa/Nairobi")


def today_ke() -> date:
    return datetime.now(KENYA_TZ).date()