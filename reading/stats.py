"""
تحلیل روند مطالعه.

همه‌ی توابع یک QuerySet از ReadingSession می‌گیرند؛ پس هم برای «آمار من» (جلسه‌های یک کاربر)
و هم برای «گزارش مدیر» (جلسه‌های همه‌ی کاربران) قابل استفاده‌اند.
"""
import datetime
from collections import OrderedDict, defaultdict
from dataclasses import dataclass

from django import forms
from django.db.models import Count, Max, Sum

from core.forms import JalaliDateField
from core.jalali import (IRAN_WEEK_ORDER, MONTH_NAMES, WEEKDAY_NAMES, format_jalali, from_jalali,
                         jalali_year_start, to_fa_digits, to_jalali)

from .models import ShelfEntry

PRESETS = OrderedDict([
    ("7", "۷ روز اخیر"),
    ("30", "۳۰ روز اخیر"),
    ("90", "۳ ماه اخیر"),
    ("365", "یک سال اخیر"),
    ("year", "امسال (شمسی)"),
    ("custom", "بازه‌ی دلخواه"),
])


@dataclass
class DateRange:
    start: datetime.date
    end: datetime.date
    key: str
    label: str

    @property
    def days(self):
        return (self.end - self.start).days + 1

    def previous(self):
        """بازه‌ی هم‌اندازه‌ی قبلی، برای مقایسه"""
        end = self.start - datetime.timedelta(days=1)
        start = end - datetime.timedelta(days=self.days - 1)
        return DateRange(start, end, "prev", "بازه‌ی قبل")

    @property
    def title(self):
        return f"{format_jalali(self.start)} تا {format_jalali(self.end)}"


class RangeForm(forms.Form):
    range = forms.ChoiceField(choices=list(PRESETS.items()), required=False)
    start = JalaliDateField(label="از تاریخ", required=False)
    end = JalaliDateField(label="تا تاریخ", required=False)

    def clean(self):
        data = super().clean()
        if data.get("range") == "custom":
            start, end = data.get("start"), data.get("end")
            if not start or not end:
                raise forms.ValidationError("برای بازه‌ی دلخواه، هر دو تاریخ را وارد کنید.")
            if start > end:
                raise forms.ValidationError("تاریخ شروع باید قبل از تاریخ پایان باشد.")
            if (end - start).days > 366 * 3:
                raise forms.ValidationError("بازه‌ی گزارش حداکثر ۳ سال است.")
        return data


def parse_range(params, default="30"):
    """از پارامترهای GET یک DateRange می‌سازد. خروجی: (DateRange, RangeForm)"""
    today = datetime.date.today()
    form = RangeForm(params or None)
    key = default
    if form.is_bound and form.is_valid() and form.cleaned_data.get("range"):
        key = form.cleaned_data["range"]
    if key == "custom" and form.is_bound and form.is_valid():
        return DateRange(form.cleaned_data["start"], form.cleaned_data["end"], "custom", "بازه‌ی دلخواه"), form
    if key == "year":
        return DateRange(jalali_year_start(today), today, key, PRESETS[key]), form
    if key not in PRESETS or key == "custom":
        key = default
    days = int(key)
    return DateRange(today - datetime.timedelta(days=days - 1), today, key, PRESETS[key]), form


def in_range(sessions, rng):
    # order_by() خالی: مرتب‌سازی پیش‌فرض مدل نباید وارد GROUP BY / DISTINCT شود
    return sessions.filter(date__gte=rng.start, date__lte=rng.end).order_by()


def summary(sessions, rng, entries=None):
    """خلاصه‌ی عددی یک بازه"""
    qs = in_range(sessions, rng)
    agg = qs.aggregate(total=Sum("minutes"), pages=Sum("pages_read"), count=Count("id"), longest=Max("minutes"))
    minutes = agg["total"] or 0
    pages = agg["pages"] or 0
    active_days = qs.values("date").distinct().count()
    data = {
        "minutes": minutes,
        "pages": pages,
        "sessions": agg["count"] or 0,
        "longest": agg["longest"] or 0,
        "active_days": active_days,
        "books": qs.values("book").distinct().count(),
        "readers": qs.values("user").distinct().count(),
        "avg_per_day": round(minutes / rng.days) if rng.days else 0,
        "avg_per_active_day": round(minutes / active_days) if active_days else 0,
        "pages_per_hour": round(pages * 60 / minutes) if minutes else 0,
        "consistency": round(active_days * 100 / rng.days) if rng.days else 0,
    }
    if entries is not None:
        data["finished"] = entries.filter(status=ShelfEntry.Status.READ, finished_on__gte=rng.start,
                                          finished_on__lte=rng.end).count()
    return data


def _daily_totals(qs):
    rows = qs.order_by().values("date").annotate(m=Sum("minutes"), p=Sum("pages_read"))
    return {row["date"]: (row["m"] or 0, row["p"] or 0) for row in rows}


def timeseries(sessions, rng):
    """
    سری زمانی برای نمودار میله‌ای.
    تا ۳۱ روز: روزانه | تا ۱۲۰ روز: هفتگی | بیشتر: ماهانه (ماه شمسی)
    """
    daily = _daily_totals(in_range(sessions, rng))
    buckets = []  # [label, minutes, pages, tooltip]
    if rng.days <= 31:
        unit = "روز"
        day = rng.start
        while day <= rng.end:
            m, p = daily.get(day, (0, 0))
            jy, jm, jd = to_jalali(day)
            buckets.append([to_fa_digits(jd), m, p, format_jalali(day)])
            day += datetime.timedelta(days=1)
    elif rng.days <= 120:
        unit = "هفته"
        day = rng.start
        while day <= rng.end:
            week_end = min(day + datetime.timedelta(days=6), rng.end)
            m = p = 0
            d = day
            while d <= week_end:
                dm, dp = daily.get(d, (0, 0))
                m, p = m + dm, p + dp
                d += datetime.timedelta(days=1)
            buckets.append([format_jalali(day, "day"), m, p, f"{format_jalali(day)} تا {format_jalali(week_end)}"])
            day = week_end + datetime.timedelta(days=1)
    else:
        unit = "ماه"
        months = OrderedDict()
        day = rng.start
        while day <= rng.end:
            jy, jm, _ = to_jalali(day)
            months.setdefault((jy, jm), [0, 0])
            dm, dp = daily.get(day, (0, 0))
            months[(jy, jm)][0] += dm
            months[(jy, jm)][1] += dp
            day += datetime.timedelta(days=1)
        for (jy, jm), (m, p) in months.items():
            buckets.append([MONTH_NAMES[jm - 1], m, p, to_fa_digits(f"{MONTH_NAMES[jm - 1]} {jy}")])

    peak = max((b[1] for b in buckets), default=0)
    return {
        "unit": unit,
        "peak": peak,
        "bars": [
            {"label": label, "minutes": m, "pages": p, "tooltip": tip,
             "height": round(m * 100 / peak) if peak else 0}
            for label, m, p, tip in buckets
        ],
        # برای نمودارهای خیلی پرتعداد فقط بعضی برچسب‌ها نمایش داده می‌شوند
        "label_every": 1 if len(buckets) <= 14 else (2 if len(buckets) <= 31 else 3),
    }


def weekday_distribution(sessions, rng):
    """جمع دقیقه‌ها به تفکیک روز هفته (شنبه تا جمعه)"""
    totals = defaultdict(int)
    for day, (m, _) in _daily_totals(in_range(sessions, rng)).items():
        totals[day.weekday()] += m
    peak = max(totals.values(), default=0)
    return [
        {"label": WEEKDAY_NAMES[wd], "minutes": totals[wd], "pct": round(totals[wd] * 100 / peak) if peak else 0}
        for wd in IRAN_WEEK_ORDER
    ]


def category_breakdown(sessions, rng):
    rows = (in_range(sessions, rng)
            .values("book__category__name", "book__category__color")
            .annotate(total=Sum("minutes"))
            .order_by("-total"))
    total = sum(r["total"] or 0 for r in rows)
    return [
        {"name": r["book__category__name"] or "بدون دسته", "color": r["book__category__color"] or "#8A7F72",
         "minutes": r["total"], "pct": round(r["total"] * 100 / total) if total else 0}
        for r in rows
    ]


def top_books(sessions, rng, limit=5):
    from catalog.models import Book

    rows = list(in_range(sessions, rng).values("book")
                .annotate(total=Sum("minutes"), pages=Sum("pages_read"), count=Count("id"))
                .order_by("-total")[:limit])
    books = Book.objects.select_related("author", "category").in_bulk([r["book"] for r in rows])
    peak = rows[0]["total"] if rows else 0
    return [dict(r, book=books[r["book"]], minutes=r["total"], pct=round(r["total"] * 100 / peak) if peak else 0)
            for r in rows]


def top_readers(sessions, rng, limit=5):
    from django.contrib.auth import get_user_model

    rows = list(in_range(sessions, rng).values("user")
                .annotate(total=Sum("minutes"), pages=Sum("pages_read"), count=Count("id"),
                          books=Count("book", distinct=True))
                .order_by("-total")[:limit])
    users = get_user_model().objects.select_related("profile").in_bulk([r["user"] for r in rows])
    peak = rows[0]["total"] if rows else 0
    return [dict(r, reader=users[r["user"]], minutes=r["total"], pct=round(r["total"] * 100 / peak) if peak else 0)
            for r in rows]


def streaks(sessions):
    """(رکورد فعلی، بلندترین رکورد) روزهای پشت سر هم با مطالعه"""
    dates = sorted(set(sessions.order_by().values_list("date", flat=True)))
    if not dates:
        return 0, 0
    longest = run = 1
    for prev, cur in zip(dates, dates[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)
    today = datetime.date.today()
    date_set = set(dates)
    # اگر امروز هنوز نخوانده، رکورد از دیروز حساب می‌شود
    day = today if today in date_set else today - datetime.timedelta(days=1)
    current = 0
    while day in date_set:
        current += 1
        day -= datetime.timedelta(days=1)
    return current, longest


def heatmap(sessions, weeks=17):
    """
    تقویم حرارتی شبیه گیت‌هاب: ستون‌ها هفته‌ها، ردیف‌ها شنبه تا جمعه.
    سطح رنگ ۰ تا ۴ بر اساس دقیقه‌ی مطالعه.
    """
    today = datetime.date.today()
    # شنبه‌ی هفته‌ی جاری (weekday شنبه = 5)
    this_saturday = today - datetime.timedelta(days=(today.weekday() - 5) % 7)
    start = this_saturday - datetime.timedelta(weeks=weeks - 1)
    daily = _daily_totals(sessions.filter(date__gte=start, date__lte=today))
    columns = []
    for w in range(weeks):
        cells = []
        for d in range(7):
            day = start + datetime.timedelta(days=w * 7 + d)
            minutes = daily.get(day, (0, 0))[0]
            if day > today:
                level = -1
            elif minutes == 0:
                level = 0
            elif minutes < 20:
                level = 1
            elif minutes < 45:
                level = 2
            elif minutes < 90:
                level = 3
            else:
                level = 4
            cells.append({"date": day, "minutes": minutes, "level": level})
        jy, jm, jd = to_jalali(cells[0]["date"])
        month_label = MONTH_NAMES[jm - 1] if jd <= 7 else ""
        columns.append({"cells": cells, "month": month_label})
    return columns


def pace_pages_per_day(sessions, days=30):
    """میانگین صفحه در روز در ۳۰ روز اخیر (برای پیش‌بینی زمان تمام شدن کتاب)"""
    since = datetime.date.today() - datetime.timedelta(days=days - 1)
    pages = sessions.filter(date__gte=since).aggregate(p=Sum("pages_read"))["p"] or 0
    return pages / days


def finish_eta(entry, pace):
    """تخمین تعداد روز باقی‌مانده تا تمام شدن یک کتاب"""
    remaining = max(0, (entry.book.pages or 0) - entry.current_page)
    if not remaining or pace <= 0:
        return None
    days = max(1, round(remaining / pace))
    return {"days": days, "date": datetime.date.today() + datetime.timedelta(days=days)}


def yearly_goal(user):
    """پیشرفت هدف سالانه در سال شمسی جاری"""
    today = datetime.date.today()
    start = jalali_year_start(today)
    jy = to_jalali(today)[0]
    next_start = from_jalali(jy + 1, 1, 1)
    goal = user.profile.yearly_goal or 0
    done = user.shelf_entries.filter(status=ShelfEntry.Status.READ, finished_on__gte=start).count()
    year_fraction = (today - start).days / (next_start - start).days
    expected = goal * year_fraction
    return {
        "year": jy, "goal": goal, "done": done,
        "pct": min(100, round(done * 100 / goal)) if goal else 0,
        "expected": round(expected),
        "ahead": done - round(expected),
    }


def change_pct(current, previous):
    if not previous:
        return None
    return round((current - previous) * 100 / previous)


def insights(sessions, rng, current, previous, weekdays, categories):
    """جمله‌های تحلیلی «هوشمند» درباره‌ی رفتار مطالعه‌ی کاربر"""
    notes = []
    if not current["sessions"]:
        return ["در این بازه جلسه‌ی مطالعه‌ای ثبت نشده است. با ثبت اولین جلسه، تحلیل‌ها اینجا ظاهر می‌شوند."]

    diff = change_pct(current["minutes"], previous["minutes"])
    if diff is not None:
        if diff > 0:
            notes.append(f"نسبت به بازه‌ی قبل {to_fa_digits(diff)}٪ بیشتر مطالعه کرده‌اید. عالی است!")
        elif diff < 0:
            notes.append(f"زمان مطالعه‌ی شما نسبت به بازه‌ی قبل {to_fa_digits(abs(diff))}٪ کمتر شده است.")
        else:
            notes.append("زمان مطالعه‌ی شما دقیقاً هم‌اندازه‌ی بازه‌ی قبل است.")

    best_day = max(weekdays, key=lambda w: w["minutes"])
    if best_day["minutes"]:
        notes.append(f"بیشترین مطالعه‌ی شما در روزهای «{best_day['label']}» است.")

    if current["pages_per_hour"]:
        notes.append(f"سرعت مطالعه‌ی شما به‌طور میانگین {to_fa_digits(current['pages_per_hour'])} صفحه در ساعت است.")

    if categories:
        top = categories[0]
        notes.append(f"{to_fa_digits(top['pct'])}٪ از زمان مطالعه‌ی شما به دسته‌ی «{top['name']}» گذشته است.")

    if current["consistency"] >= 70:
        notes.append("نظم شما فوق‌العاده است؛ در بیشتر روزهای این بازه مطالعه کرده‌اید.")
    elif current["consistency"] < 30:
        notes.append("مطالعه‌ی پراکنده دارید؛ جلسه‌های کوتاه ولی هر روزه بیشتر کمک می‌کنند.")

    avg_session = round(current["minutes"] / current["sessions"])
    notes.append(f"هر جلسه‌ی مطالعه‌ی شما به‌طور میانگین {to_fa_digits(avg_session)} دقیقه طول می‌کشد.")
    return notes
