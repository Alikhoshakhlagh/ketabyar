from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from catalog.models import Book

from . import services, stats
from .forms import ProgressForm, QuoteForm, ReviewForm, SessionForm
from .models import Activity, Favorite, Quote, ReadingSession, Review, ShelfEntry


def _back(request, fallback):
    """بعد از یک عمل POST به همان صفحه‌ای که کاربر بود برمی‌گردیم."""
    target = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect(fallback)


# ---------------------------------------------------------------- قفسه

@login_required
def shelf(request):
    tab = request.GET.get("tab", "reading")
    entries = ShelfEntry.objects.filter(user=request.user).select_related("book__author", "book__category")
    counts = dict(entries.order_by().values_list("status").annotate(c=Count("id")))
    fav_count = Favorite.objects.filter(user=request.user).count()

    if tab == "favorites":
        items = [f.book for f in Favorite.objects.filter(user=request.user).select_related("book__author", "book__category")]
        rows = None
    else:
        if tab not in ShelfEntry.Status.values:
            tab = "reading"
        rows = entries.filter(status=tab)
        items = None

    my_ratings = dict(request.user.ratings.values_list("book_id", "score"))
    pace = stats.pace_pages_per_day(request.user.sessions.all())
    if rows is not None:
        rows = list(rows)
        for entry in rows:
            entry.my_rating = my_ratings.get(entry.book_id)
            if entry.status == ShelfEntry.Status.READING:
                entry.eta = stats.finish_eta(entry, pace)

    tabs = [
        ("reading", "در حال مطالعه", counts.get("reading", 0)),
        ("to_read", "برنامه‌ریزی برای مطالعه", counts.get("to_read", 0)),
        ("read", "مطالعه‌شده", counts.get("read", 0)),
        ("favorites", "علاقه‌مندی‌ها", fav_count),
    ]
    return render(request, "reading/shelf.html", {
        "tab": tab, "tabs": tabs, "rows": rows, "favorite_books": items,
    })


@login_required
@require_POST
def set_status(request, pk):
    book = get_object_or_404(Book, pk=pk)
    status = request.POST.get("status")
    if status == "remove":
        services.remove_from_shelf(request.user, book)
        messages.info(request, f"«{book.title}» از قفسه‌ی شما حذف شد.")
    elif status in ShelfEntry.Status.values:
        entry = services.set_shelf_status(request.user, book, status)
        messages.success(request, f"وضعیت «{book.title}»: {entry.get_status_display()}")
    return _back(request, book.get_absolute_url())


@login_required
@require_POST
def update_progress(request, pk):
    book = get_object_or_404(Book, pk=pk)
    form = ProgressForm(request.POST)
    if form.is_valid():
        entry = services.update_progress(request.user, book, form.cleaned_data["current_page"])
        if entry.status == ShelfEntry.Status.READ:
            messages.success(request, f"تبریک! «{book.title}» را تمام کردید. 🎉")
        else:
            messages.success(request, "پیشرفت مطالعه ذخیره شد.")
    else:
        messages.error(request, "شماره‌ی صفحه معتبر نیست.")
    return _back(request, book.get_absolute_url())


@login_required
@require_POST
def rate_book(request, pk):
    book = get_object_or_404(Book, pk=pk)
    score = request.POST.get("score", "")
    if score == "0":
        services.remove_rating(request.user, book)
        messages.info(request, "امتیاز شما حذف شد.")
    elif score.isdigit() and 1 <= int(score) <= 5:
        services.rate(request.user, book, int(score))
        messages.success(request, f"امتیاز {score} از ۵ برای «{book.title}» ثبت شد.")
    return _back(request, book.get_absolute_url())


@login_required
@require_POST
def toggle_favorite(request, pk):
    book = get_object_or_404(Book, pk=pk)
    if services.toggle_favorite(request.user, book):
        messages.success(request, f"«{book.title}» به علاقه‌مندی‌ها اضافه شد.")
    else:
        messages.info(request, f"«{book.title}» از علاقه‌مندی‌ها حذف شد.")
    return _back(request, book.get_absolute_url())


# ---------------------------------------------------------------- نقد و بررسی

@login_required
def review_edit(request, pk):
    book = get_object_or_404(Book, pk=pk)
    review = Review.objects.filter(user=request.user, book=book).first()
    form = ReviewForm(request.POST or None, instance=review)
    if request.method == "POST" and form.is_valid():
        is_new = review is None
        review = form.save(commit=False)
        review.user, review.book = request.user, book
        review.save()
        if is_new:
            services.log(request.user, Activity.Verb.REVIEWED, book, review.title)
        messages.success(request, "نقد شما ذخیره شد.")
        return redirect(f"{book.get_absolute_url()}#reviews")
    return render(request, "reading/review_form.html", {"form": form, "book": book, "review": review})


@login_required
@require_POST
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk, user=request.user)
    book = review.book
    review.delete()
    messages.info(request, "نقد شما حذف شد.")
    return redirect(book.get_absolute_url())


@login_required
@require_POST
def review_like(request, pk):
    review = get_object_or_404(Review, pk=pk, is_hidden=False)
    if review.user_id != request.user.pk:
        services.toggle_review_like(request.user, review)
    return _back(request, f"{review.book.get_absolute_url()}#review-{review.pk}")


# ---------------------------------------------------------------- جلسه‌های مطالعه

@login_required
def session_list(request):
    rng, range_form = stats.parse_range(request.GET, default="30")
    sessions = request.user.sessions.select_related("book__author", "book__category")
    qs = stats.in_range(sessions, rng).order_by("-date", "-created_at")
    book_id = request.GET.get("book")
    if book_id and book_id.isdigit():
        qs = qs.filter(book_id=book_id)
    totals = qs.aggregate(total=Sum("minutes"), pages=Sum("pages_read"))
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    my_books = Book.objects.filter(sessions__user=request.user).distinct().order_by("title")
    return render(request, "reading/session_list.html", {
        "page_obj": page, "rng": rng, "range_form": range_form, "presets": stats.PRESETS,
        "totals": totals, "my_books": my_books, "selected_book": book_id,
    })


@login_required
def session_form(request, pk=None):
    session = get_object_or_404(ReadingSession, pk=pk, user=request.user) if pk else None
    initial = {}
    if not session and request.GET.get("book", "").isdigit():
        initial["book"] = request.GET["book"]
        entry = ShelfEntry.objects.filter(user=request.user, book_id=request.GET["book"]).first()
        if entry and entry.current_page:
            initial["start_page"] = entry.current_page
    form = SessionForm(request.POST or None, instance=session, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.save()
        services.session_saved(obj, created=session is None)
        messages.success(request, "جلسه‌ی مطالعه ذخیره شد.")
        if request.POST.get("again"):
            return redirect(f"{request.path}?book={obj.book_id}")
        return redirect("reading:session_list")
    return render(request, "reading/session_form.html", {"form": form, "session": session})


@login_required
def session_delete(request, pk):
    session = get_object_or_404(ReadingSession, pk=pk, user=request.user)
    if request.method == "POST":
        session.delete()
        messages.info(request, "جلسه‌ی مطالعه حذف شد.")
        return redirect("reading:session_list")
    return render(request, "reading/confirm_delete.html", {
        "object_label": f"جلسه‌ی مطالعه‌ی «{session.book.title}» ({session.minutes} دقیقه)",
        "cancel_url": "reading:session_list",
    })


# ---------------------------------------------------------------- نقل‌قول و هایلایت

@login_required
def quote_list(request):
    quotes = Quote.objects.filter(user=request.user).select_related("book__author", "book__category")
    q = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")
    if q:
        quotes = quotes.filter(Q(text__icontains=q) | Q(note__icontains=q) | Q(book__title__icontains=q))
    if kind in Quote.Kind.values:
        quotes = quotes.filter(kind=kind)
    page = Paginator(quotes, 12).get_page(request.GET.get("page"))
    return render(request, "reading/quote_list.html", {"page_obj": page, "q": q, "kind": kind})


@login_required
def quote_form(request, pk=None):
    quote = get_object_or_404(Quote, pk=pk, user=request.user) if pk else None
    initial = {}
    if not quote and request.GET.get("book", "").isdigit():
        initial["book"] = request.GET["book"]
    form = QuoteForm(request.POST or None, instance=quote, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.save()
        if quote is None:
            services.log(request.user, Activity.Verb.QUOTED, obj.book, obj.text[:80])
        messages.success(request, f"{obj.get_kind_display()} ذخیره شد.")
        return redirect("reading:quote_list")
    return render(request, "reading/quote_form.html", {"form": form, "quote": quote})


@login_required
def quote_delete(request, pk):
    quote = get_object_or_404(Quote, pk=pk, user=request.user)
    if request.method == "POST":
        quote.delete()
        messages.info(request, "حذف شد.")
        return redirect("reading:quote_list")
    return render(request, "reading/confirm_delete.html", {
        "object_label": f"{quote.get_kind_display()}: «{quote.text[:80]}»",
        "cancel_url": "reading:quote_list",
    })


def quote_feed(request):
    """نقل‌قول‌های عمومی همه‌ی کاربران (اشتراک‌گذاری)"""
    quotes = (Quote.objects.filter(is_public=True, user__profile__is_public=True, user__is_active=True)
              .select_related("book__author", "book__category", "user__profile"))
    q = request.GET.get("q", "").strip()
    if q:
        quotes = quotes.filter(Q(text__icontains=q) | Q(book__title__icontains=q) | Q(book__author__name__icontains=q))
    page = Paginator(quotes, 12).get_page(request.GET.get("page"))
    return render(request, "reading/quote_feed.html", {"page_obj": page, "q": q})


# ---------------------------------------------------------------- تحلیل روند مطالعه

@login_required
def my_stats(request):
    user = request.user
    rng, range_form = stats.parse_range(request.GET, default="30")
    sessions = user.sessions.all()
    current = stats.summary(sessions, rng, entries=user.shelf_entries.all())
    previous = stats.summary(sessions, rng.previous(), entries=user.shelf_entries.all())
    weekdays = stats.weekday_distribution(sessions, rng)
    categories = stats.category_breakdown(sessions, rng)
    streak_now, streak_best = stats.streaks(sessions)
    return render(request, "reading/stats.html", {
        "rng": rng, "range_form": range_form, "presets": stats.PRESETS,
        "s": current, "prev": previous,
        "minutes_change": stats.change_pct(current["minutes"], previous["minutes"]),
        "pages_change": stats.change_pct(current["pages"], previous["pages"]),
        "series": stats.timeseries(sessions, rng),
        "weekdays": weekdays,
        "categories": categories,
        "top_books": stats.top_books(sessions, rng),
        "insights": stats.insights(sessions, rng, current, previous, weekdays, categories),
        "streak_now": streak_now, "streak_best": streak_best,
        "heatmap": stats.heatmap(sessions),
        "goal": stats.yearly_goal(user),
    })
