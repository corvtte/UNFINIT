from datetime import datetime, date, timezone, timedelta
from typing import Union, Tuple

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]

def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """
    Standard astronomical conversion from Gregorian (gy, gm, gd)
    to Iranian Solar Hijri / Jalali (jy, jm, jd).
    """
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy if gm > 2 else (gy - 1)
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd

def get_shamsi_now_string() -> str:
    now = datetime.now(TEHRAN_TZ)
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d} {now.hour:02d}:{now.minute:02d}"

def format_to_jalali(dt_val: Union[str, datetime, date, None], include_time: bool = True) -> str:
    """
    Formats a datetime or ISO date string into official Iranian Solar Hijri date string.
    Example: '19 شهریور 1405 - 20:03'
    """
    if not dt_val:
        return "-"

    hour, minute = 0, 0
    if isinstance(dt_val, str):
        s = str(dt_val).strip().replace("T", " ")
        try:
            parts = s.split(" ")
            ymd = [int(x) for x in parts[0].split("-")]
            gy, gm, gd = ymd[0], ymd[1], ymd[2]
            if len(parts) > 1 and ":" in parts[1]:
                hms = parts[1].split(":")
                hour = int(hms[0])
                minute = int(hms[1])
        except Exception:
            return str(dt_val)
    elif hasattr(dt_val, "year"):
        gy, gm, gd = dt_val.year, dt_val.month, dt_val.day
        if hasattr(dt_val, "hour"):
            hour, minute = dt_val.hour, dt_val.minute
    else:
        return str(dt_val)

    jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    month_name = PERSIAN_MONTHS[jm - 1] if 1 <= jm <= 12 else str(jm)
    if include_time:
        return f"{jd} {month_name} {jy} - {hour:02d}:{minute:02d}"
    return f"{jd} {month_name} {jy}"
