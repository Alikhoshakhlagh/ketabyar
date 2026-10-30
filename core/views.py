import datetime

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import render

from catalog.models import Book
from reading import stats
from reading.models import Activity, Quote, ReadingSession, Review, ShelfEntry
from reading.recommend import recommend_for


def _public_quotes():
    return (Quote.objects.filter(is_public=True, user__profile__is_public=True, user__is_active=True)
            .select_related("book__author", "user__profile"))


def home(request):
    if request.user.is_authenticated:
        return dashboard(request)

    return render(request, "core/landing.html", {
        "counts": {
            "books": Book.objects.count(),
            "members": get_user_model().objects.filter(is_active=True).count(),
            "hours": round((ReadingSession.objects.aggregate(m=Sum("minutes"))["m"] or 0) / 60),
            "reviews": Review.objects.filter(is_hidden=False).count(),
        },
        "top_books": Book.objects.top_rated().select_related("author", "category")[:6],
        "new_books": Book.objects.with_stats().select_related("author", "category").order_by("-created_at")[:6],
        "quotes": _public_quotes()[:3],
        "reviews": Review.objects.filter(is_hidden=False).select_related("book__author", "book__category",
                                                                         "user__profile")[:3],
    })


def dashboard(request):
    """داشبورد کاربر عضو"""
    user = request.user
    sessions = user.sessions.all()
    today = datetime.date.today()

    pace = stats.pace_pages_per_day(sessions)
    reading = list(user.shelf_entries.filter(status=ShelfEntry.Status.READING)
                   .select_related("book__author", "book__category")[:4])
    for entry in reading:
        entry.eta = stats.finish_eta(entry, pace)

    today_minutes = sessions.filter(date=today).aggregate(m=Sum("minutes"))["m"] or 0
    daily_goal = user.profile.daily_goal_minutes or 0
    week = stats.DateRange(today - datetime.timedelta(days=6), today, "7", "۷ روز اخیر")
    streak_now, streak_best = stats.streaks(sessions)

    # نقل‌قول روز: هر روز یکی از نقل‌قول‌های عمومی (ثابت در طول روز)
    quotes = _public_quotes()
    quote_count = quotes.count()
    quote_of_day = quotes[today.toordinal() % quote_count] if quote_count else None

    community = (Activity.objects.filter(user__profile__is_public=True, user__is_active=True)
                 .exclude(user=user).exclude(verb=Activity.Verb.JOINED)
                 .select_related("user__profile", "book")[:6])

    return render(request, "core/dashboard.html", {
        "reading": reading,
        "today_minutes": today_minutes,
        "daily_goal": daily_goal,
        "week": stats.timeseries(sessions, week),
        "week_summary": stats.summary(sessions, week),
        "streak_now": streak_now, "streak_best": streak_best,
        "goal": stats.yearly_goal(user),
        "recommendations": recommend_for(user, limit=6),
        "quote_of_day": quote_of_day,
        "community": community,
        "to_read_count": user.shelf_entries.filter(status=ShelfEntry.Status.TO_READ).count(),
    })
