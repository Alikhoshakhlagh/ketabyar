"""
تبدیل تاریخ میلادی ↔ شمسی بدون نیاز به کتابخانه‌ی جانبی.

الگوریتم همان الگوریتم شناخته‌شده‌ی jdf است که در بیشتر پروژه‌های فارسی استفاده می‌شود.
"""
import datetime

MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
# datetime.weekday(): دوشنبه=0 ... یکشنبه=6
WEEKDAY_NAMES = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
# ترتیب نمایش هفته‌ی ایرانی: شنبه تا جمعه (بر اساس weekday پایتون)
IRAN_WEEK_ORDER = [5, 6, 0, 1, 2, 3, 4]

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_TO_EN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_fa_digits(value):
    return str(value).translate(_FA_DIGITS)


def to_en_digits(value):
    return str(value).translate(_TO_EN_DIGITS)


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
        + (gy2 + 399) // 400 + gd + g_d_m[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    month_days = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    return gy, gm, gd


def to_jalali(value):
    """یک date یا datetime میلادی می‌گیرد و (سال، ماه، روز) شمسی برمی‌گرداند."""
    if isinstance(value, datetime.datetime):
        value = value.date()
    return gregorian_to_jalali(value.year, value.month, value.day)


def from_jalali(jy, jm, jd):
    """(سال، ماه، روز) شمسی → datetime.date. اگر تاریخ نامعتبر باشد ValueError می‌دهد."""
    if not (1 <= jm <= 12 and 1 <= jd <= 31):
        raise ValueError("تاریخ نامعتبر")
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    result = datetime.date(gy, gm, gd)
    # برگرداندن دوباره برای اطمینان (مثلاً ۳۱ مهر وجود ندارد)
    if to_jalali(result) != (jy, jm, jd):
        raise ValueError("تاریخ نامعتبر")
    return result


def jalali_year_start(today=None):
    """اولین روز سال شمسی جاری (۱ فروردین) را به‌صورت date میلادی برمی‌گرداند."""
    today = today or datetime.date.today()
    jy, _, _ = to_jalali(today)
    return from_jalali(jy, 1, 1)


def format_jalali(value, style="long"):
    if not value:
        return ""
    jy, jm, jd = to_jalali(value)
    if style == "short":
        text = f"{jy}/{jm:02d}/{jd:02d}"
    elif style == "month":
        text = f"{MONTH_NAMES[jm - 1]} {jy}"
    elif style == "day":
        text = f"{jd} {MONTH_NAMES[jm - 1]}"
    else:
        text = f"{jd} {MONTH_NAMES[jm - 1]} {jy}"
    return to_fa_digits(text)
