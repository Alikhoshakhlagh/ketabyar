import datetime

from django.conf import settings

from core.jalali import format_jalali


def site(request):
    """متغیرهایی که در همه‌ی قالب‌ها در دسترس‌اند."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "TODAY_JALALI": format_jalali(datetime.date.today()),
    }
