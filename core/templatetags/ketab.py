"""
فیلترها و تگ‌های قالب که در همه‌ی صفحه‌ها استفاده می‌شوند.

در قالب:  {% load ketab %}
"""
import datetime

from django import template
from django.utils import timezone

from core.jalali import format_jalali, to_fa_digits

register = template.Library()


@register.filter
def fa(value):
    """اعداد انگلیسی را به فارسی تبدیل می‌کند: 12 → ۱۲"""
    if value is None:
        return ""
    return to_fa_digits(value)


@register.filter
def num(value):
    """عدد با جداکننده‌ی هزارگان و ارقام فارسی: 12500 → ۱۲٬۵۰۰"""
    if value in (None, ""):
        return to_fa_digits(0)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return to_fa_digits(value)
    if number.is_integer():
        text = f"{int(number):,}"
    else:
        text = f"{number:,.1f}"
    return to_fa_digits(text.replace(",", "٬").replace(".", "٫"))


@register.filter
def jdate(value, style="long"):
    """تاریخ شمسی: {{ obj.created_at|jdate }} یا {{ d|jdate:'short' }}"""
    if not value:
        return ""
    if isinstance(value, datetime.datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    return format_jalali(value, style)


@register.filter
def ago(value):
    """زمان نسبی فارسی: «۳ ساعت پیش»"""
    if not value:
        return ""
    now = timezone.now()
    seconds = int((now - value).total_seconds())
    if seconds < 60:
        return "همین الان"
    if seconds < 3600:
        return f"{to_fa_digits(seconds // 60)} دقیقه پیش"
    if seconds < 86400:
        return f"{to_fa_digits(seconds // 3600)} ساعت پیش"
    if seconds < 86400 * 7:
        return f"{to_fa_digits(seconds // 86400)} روز پیش"
    return jdate(value)


@register.filter
def duration(minutes):
    """دقیقه را خوانا می‌کند: 135 → «۲ ساعت و ۱۵ دقیقه»"""
    minutes = int(minutes or 0)
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{to_fa_digits(hours)} ساعت و {to_fa_digits(mins)} دقیقه"
    if hours:
        return f"{to_fa_digits(hours)} ساعت"
    return f"{to_fa_digits(mins)} دقیقه"


@register.filter
def hours(minutes):
    """دقیقه → ساعت با یک رقم اعشار"""
    return num(round((minutes or 0) / 60, 1))


@register.filter
def percent_of(value, total):
    """درصد value نسبت به total (حداکثر ۱۰۰) برای عرض نوارها"""
    try:
        value, total = float(value or 0), float(total or 0)
    except (TypeError, ValueError):
        return 0
    if total <= 0:
        return 0
    return min(100, round(value * 100 / total))


@register.filter
def get_item(mapping, key):
    return mapping.get(key) if mapping else None


@register.inclusion_tag("partials/_stars.html")
def stars(score, size="md"):
    """نمایش ۵ ستاره با پر شدن جزئی؛ score می‌تواند اعشاری باشد."""
    score = float(score or 0)
    items = []
    for i in range(1, 6):
        fill = max(0.0, min(1.0, score - (i - 1)))
        items.append(round(fill * 100))
    return {"items": items, "score": score, "size": size}


@register.inclusion_tag("partials/_cover.html")
def cover(book, size="md"):
    return {"book": book, "size": size}


@register.simple_tag(takes_context=True)
def url_with(context, **kwargs):
    """کوئری‌استرینگ فعلی را نگه می‌دارد و فقط پارامترهای داده‌شده را عوض می‌کند (برای صفحه‌بندی و فیلترها)."""
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    encoded = query.urlencode()
    return f"?{encoded}" if encoded else "?"
