"""
پنل مدیریت سامانه (فقط برای کاربران is_staff).

شامل: داشبورد، مدیریت کتاب/نویسنده/دسته، نظارت بر کاربران و فعالیت‌ها، مدیریت نقدها،
و گزارش‌گیری کلی و جزئی در بازه‌ی زمانی دلخواه (با خروجی CSV برای اکسل).
"""
import csv
import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, IntegerField, OuterRef, ProtectedError, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, UpdateView

from catalog.models import Author, Book, Category
from core.jalali import format_jalali
from reading import stats
from reading.models import Activity, Favorite, Quote, Rating, ReadingSession, Review, ShelfEntry

from .forms import AuthorForm, BookForm, CategoryForm

User = get_user_model()


def _is_staff(user):
    return user.is_active and user.is_staff


staff_required = user_passes_test(_is_staff, login_url="accounts:login")


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return _is_staff(self.request.user)


def _sum_subquery(model, field, **filters):
    """جمع یک ستون برای هر کاربر به‌صورت زیرکوئری (تا JOINهای چندگانه عددها را چند برابر نکنند)"""
    qs = model.objects.filter(user=OuterRef("pk"), **filters).order_by().values("user")
    return Coalesce(Subquery(qs.annotate(v=Sum(field)).values("v"), output_field=IntegerField()), 0)


def _count_subquery(model, **filters):
    qs = model.objects.filter(user=OuterRef("pk"), **filters).order_by().values("user")
    return Coalesce(Subquery(qs.annotate(v=Count("pk")).values("v"), output_field=IntegerField()), 0)


# ---------------------------------------------------------------- داشبورد

@staff_required
def dashboard(request):
    today = datetime.date.today()
    rng = stats.DateRange(today - datetime.timedelta(days=29), today, "30", "۳۰ روز اخیر")
    sessions = ReadingSession.objects.all()
    since = today - datetime.timedelta(days=6)
    return render(request, "panel/dashboard.html", {
        "rng": rng,
        "totals": {
            "users": User.objects.count(),
            "books": Book.objects.count(),
            "authors": Author.objects.count(),
            "sessions": sessions.count(),
            "hours": round((sessions.aggregate(m=Sum("minutes"))["m"] or 0) / 60),
            "reviews": Review.objects.count(),
            "quotes": Quote.objects.count(),
            "ratings": Rating.objects.count(),
        },
        "new_users": User.objects.filter(date_joined__date__gte=rng.start).count(),
        "active_week": sessions.filter(date__gte=since).values("user").distinct().count(),
        "active_today": sessions.filter(date=today).values("user").distinct().count(),
        "hidden_reviews": Review.objects.filter(is_hidden=True).count(),
        "s": stats.summary(sessions, rng),
        "series": stats.timeseries(sessions, rng),
        "top_books": stats.top_books(sessions, rng),
        "top_readers": stats.top_readers(sessions, rng),
        "activities": Activity.objects.select_related("user", "book")[:10],
    })


# ---------------------------------------------------------------- کتاب‌ها

@staff_required
def book_list(request):
    q = request.GET.get("q", "").strip()
    books = Book.objects.with_stats().select_related("author", "category").annotate(
        session_count=Count("sessions", distinct=True))
    if q:
        books = books.filter(Q(title__icontains=q) | Q(author__name__icontains=q) | Q(isbn__icontains=q))
    if request.GET.get("category"):
        books = books.filter(category__slug=request.GET["category"])
    page = Paginator(books.order_by("-created_at"), 20).get_page(request.GET.get("page"))
    return render(request, "panel/book_list.html", {
        "page_obj": page, "q": q, "categories": Category.objects.all(),
        "selected_category": request.GET.get("category", ""),
    })


class _PanelFormMixin(StaffRequiredMixin):
    template_name = "panel/form.html"
    title = ""
    back_url = ""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = self.title if not self.object else f"ویرایش «{self.object}»"
        ctx["back_url"] = self.back_url
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "با موفقیت ذخیره شد.")
        return super().form_valid(form)


class BookCreate(_PanelFormMixin, CreateView):
    model, form_class, title = Book, BookForm, "افزودن کتاب جدید"
    back_url = success_url = reverse_lazy("panel:book_list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class BookUpdate(_PanelFormMixin, UpdateView):
    model, form_class = Book, BookForm
    back_url = success_url = reverse_lazy("panel:book_list")


class AuthorCreate(_PanelFormMixin, CreateView):
    model, form_class, title = Author, AuthorForm, "افزودن نویسنده"
    back_url = success_url = reverse_lazy("panel:author_list")


class AuthorUpdate(_PanelFormMixin, UpdateView):
    model, form_class = Author, AuthorForm
    back_url = success_url = reverse_lazy("panel:author_list")


class CategoryCreate(_PanelFormMixin, CreateView):
    model, form_class, title = Category, CategoryForm, "افزودن دسته‌بندی"
    back_url = success_url = reverse_lazy("panel:category_list")


class CategoryUpdate(_PanelFormMixin, UpdateView):
    model, form_class = Category, CategoryForm
    back_url = success_url = reverse_lazy("panel:category_list")


class _PanelDelete(StaffRequiredMixin, DeleteView):
    template_name = "panel/confirm_delete.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["back_url"] = self.success_url
        return ctx

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, f"«{self.object}» قابل حذف نیست چون کتاب‌هایی به آن وابسته‌اند.")
            return redirect(self.success_url)
        messages.info(self.request, f"«{self.object}» حذف شد.")
        return response


class BookDelete(_PanelDelete):
    model, success_url = Book, reverse_lazy("panel:book_list")


class AuthorDelete(_PanelDelete):
    model, success_url = Author, reverse_lazy("panel:author_list")


class CategoryDelete(_PanelDelete):
    model, success_url = Category, reverse_lazy("panel:category_list")


@staff_required
def author_list(request):
    q = request.GET.get("q", "").strip()
    authors = Author.objects.annotate(n=Count("books"))
    if q:
        authors = authors.filter(name__icontains=q)
    page = Paginator(authors, 25).get_page(request.GET.get("page"))
    return render(request, "panel/author_list.html", {"page_obj": page, "q": q})


@staff_required
def category_list(request):
    categories = Category.objects.annotate(n=Count("books"))
    return render(request, "panel/category_list.html", {"categories": categories})


# ---------------------------------------------------------------- کاربران

USER_SORTS = {
    "minutes": ("بیشترین زمان مطالعه", "-total_minutes"),
    "recent": ("آخرین فعالیت", "-last_activity"),
    "joined": ("جدیدترین عضو", "-date_joined"),
    "read": ("بیشترین کتاب خوانده‌شده", "-read_count"),
}


@staff_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    sort = request.GET.get("sort", "minutes")
    users = User.objects.select_related("profile").annotate(
        total_minutes=_sum_subquery(ReadingSession, "minutes"),
        session_count=_count_subquery(ReadingSession),
        read_count=_count_subquery(ShelfEntry, status=ShelfEntry.Status.READ),
        review_count=_count_subquery(Review),
        last_activity=Subquery(Activity.objects.filter(user=OuterRef("pk")).order_by("-created_at")
                               .values("created_at")[:1]),
    )
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                             | Q(email__icontains=q))
    if role == "staff":
        users = users.filter(is_staff=True)
    elif role == "member":
        users = users.filter(is_staff=False)
    elif role == "inactive":
        users = users.filter(is_active=False)
    order = USER_SORTS.get(sort, USER_SORTS["minutes"])[1]
    users = users.order_by(F(order.lstrip("-")).desc(nulls_last=True), "username")
    page = Paginator(users, 25).get_page(request.GET.get("page"))
    return render(request, "panel/user_list.html", {
        "page_obj": page, "q": q, "role": role, "sort": sort, "sorts": USER_SORTS,
    })


@staff_required
def user_detail(request, pk):
    member = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    rng, range_form = stats.parse_range(request.GET, default="30")
    sessions = member.sessions.all()
    shelf_counts = dict(member.shelf_entries.order_by().values_list("status").annotate(c=Count("id")))
    streak_now, streak_best = stats.streaks(sessions)
    activities = Paginator(member.activities.select_related("book"), 15).get_page(request.GET.get("page"))
    return render(request, "panel/user_detail.html", {
        "member": member, "rng": rng, "range_form": range_form, "presets": stats.PRESETS,
        "s": stats.summary(sessions, rng, entries=member.shelf_entries.all()),
        "series": stats.timeseries(sessions, rng),
        "categories": stats.category_breakdown(sessions, rng),
        "top_books": stats.top_books(sessions, rng),
        "shelf_counts": shelf_counts,
        "counts": {
            "reviews": member.reviews.count(), "quotes": member.quotes.count(),
            "ratings": member.ratings.count(), "favorites": member.favorites.count(),
            "avg_rating": member.ratings.aggregate(a=Avg("score"))["a"],
        },
        "streak_now": streak_now, "streak_best": streak_best,
        "activities": activities,
        "goal": stats.yearly_goal(member),
    })


@staff_required
@require_POST
def user_toggle(request, pk):
    member = get_object_or_404(User, pk=pk)
    field = request.POST.get("field")
    if member == request.user:
        messages.error(request, "نمی‌توانید دسترسی خودتان را تغییر دهید.")
    elif field == "is_active":
        member.is_active = not member.is_active
        member.save(update_fields=["is_active"])
        messages.success(request, f"حساب {member.username} {'فعال' if member.is_active else 'غیرفعال'} شد.")
    elif field == "is_staff" and request.user.is_superuser:
        member.is_staff = not member.is_staff
        member.save(update_fields=["is_staff"])
        messages.success(request, f"{member.username} {'مدیر شد' if member.is_staff else 'دیگر مدیر نیست'}.")
    return redirect("panel:user_detail", pk=pk)


# ---------------------------------------------------------------- نقدها و فعالیت‌ها

@staff_required
def review_list(request):
    reviews = Review.objects.select_related("book", "user").annotate(like_count=Count("reviewlike"))
    state = request.GET.get("state", "")
    q = request.GET.get("q", "").strip()
    if state == "hidden":
        reviews = reviews.filter(is_hidden=True)
    elif state == "spoiler":
        reviews = reviews.filter(has_spoiler=True)
    if q:
        reviews = reviews.filter(Q(body__icontains=q) | Q(title__icontains=q) | Q(book__title__icontains=q)
                                 | Q(user__username__icontains=q))
    page = Paginator(reviews, 15).get_page(request.GET.get("page"))
    return render(request, "panel/review_list.html", {"page_obj": page, "state": state, "q": q})


@staff_required
@require_POST
def review_moderate(request, pk):
    review = get_object_or_404(Review, pk=pk)
    action = request.POST.get("action")
    if action == "toggle":
        review.is_hidden = not review.is_hidden
        review.save(update_fields=["is_hidden"])
        messages.success(request, "نقد پنهان شد." if review.is_hidden else "نقد دوباره نمایش داده می‌شود.")
    elif action == "delete":
        review.delete()
        messages.info(request, "نقد حذف شد.")
    return redirect(request.POST.get("next") or "panel:review_list")


@staff_required
def activity_list(request):
    rng, range_form = stats.parse_range(request.GET, default="30")
    activities = Activity.objects.select_related("user", "book").filter(
        created_at__date__gte=rng.start, created_at__date__lte=rng.end)
    q = request.GET.get("q", "").strip()
    verb = request.GET.get("verb", "")
    if q:
        activities = activities.filter(Q(user__username__icontains=q) | Q(book__title__icontains=q))
    if verb in Activity.Verb.values:
        activities = activities.filter(verb=verb)
    verb_counts = dict(activities.order_by().values_list("verb").annotate(c=Count("id")))
    page = Paginator(activities, 30).get_page(request.GET.get("page"))
    return render(request, "panel/activity_list.html", {
        "page_obj": page, "rng": rng, "range_form": range_form, "presets": stats.PRESETS,
        "q": q, "verb": verb, "verbs": [(v, label, verb_counts.get(v, 0)) for v, label in Activity.Verb.choices],
    })


# ---------------------------------------------------------------- گزارش‌ها

def _report_querysets(request):
    """جلسه‌ها و قفسه‌ها با فیلترهای گزارش جزئی (کاربر، دسته‌بندی، کتاب)"""
    sessions = ReadingSession.objects.all()
    entries = ShelfEntry.objects.all()
    filters = {}
    if request.GET.get("user", "").isdigit():
        filters["user"] = get_object_or_404(User, pk=request.GET["user"])
        sessions = sessions.filter(user=filters["user"])
        entries = entries.filter(user=filters["user"])
    if request.GET.get("category"):
        filters["category"] = get_object_or_404(Category, slug=request.GET["category"])
        sessions = sessions.filter(book__category=filters["category"])
        entries = entries.filter(book__category=filters["category"])
    if request.GET.get("book", "").isdigit():
        filters["book"] = get_object_or_404(Book, pk=request.GET["book"])
        sessions = sessions.filter(book=filters["book"])
        entries = entries.filter(book=filters["book"])
    return sessions, entries, filters


@staff_required
def reports(request):
    rng, range_form = stats.parse_range(request.GET, default="30")
    sessions, entries, filters = _report_querysets(request)
    current = stats.summary(sessions, rng, entries=entries)
    previous = stats.summary(sessions, rng.previous(), entries=entries)

    in_rng = {"created_at__date__gte": rng.start, "created_at__date__lte": rng.end}
    community = {
        "new_users": User.objects.filter(date_joined__date__gte=rng.start, date_joined__date__lte=rng.end).count(),
        "reviews": Review.objects.filter(**in_rng).count(),
        "ratings": Rating.objects.filter(**in_rng).count(),
        "quotes": Quote.objects.filter(**in_rng).count(),
        "favorites": Favorite.objects.filter(**in_rng).count(),
    }

    # جدول جزئی: عملکرد هر کاربر در این بازه
    per_user = list(stats.in_range(sessions, rng).values("user__username", "user__first_name", "user__last_name", "user")
                    .annotate(total=Sum("minutes"), pages=Sum("pages_read"), count=Count("id"),
                              days=Count("date", distinct=True), books=Count("book", distinct=True))
                    .order_by("-total")[:50])
    finished_by_user = dict(entries.filter(status=ShelfEntry.Status.READ, finished_on__gte=rng.start,
                                                      finished_on__lte=rng.end)
                            .order_by().values_list("user").annotate(c=Count("id")))
    for row in per_user:
        row["minutes"] = row["total"]
        row["finished"] = finished_by_user.get(row["user"], 0)
        row["avg"] = round(row["minutes"] / row["count"]) if row["count"] else 0

    top_rated = (Book.objects.filter(ratings__created_at__date__gte=rng.start, ratings__created_at__date__lte=rng.end)
                 .annotate(avg=Avg("ratings__score"), n=Count("ratings")).filter(n__gte=1)
                 .select_related("author").order_by("-avg", "-n")[:5])

    weekdays = stats.weekday_distribution(sessions, rng)
    return render(request, "panel/reports.html", {
        "rng": rng, "range_form": range_form, "presets": stats.PRESETS,
        "filters": filters, "s": current, "prev": previous,
        "minutes_change": stats.change_pct(current["minutes"], previous["minutes"]),
        "community": community,
        "series": stats.timeseries(sessions, rng),
        "weekdays": weekdays,
        "categories": stats.category_breakdown(sessions, rng),
        "top_books": stats.top_books(sessions, rng, limit=8),
        "top_readers": stats.top_readers(sessions, rng, limit=8),
        "top_rated": top_rated,
        "per_user": per_user,
        "all_users": User.objects.order_by("username"),
        "all_categories": Category.objects.all(),
    })


@staff_required
def reports_export(request):
    """خروجی CSV جلسه‌های مطالعه در بازه (با BOM تا اکسل فارسی را درست نشان دهد)"""
    rng, _ = stats.parse_range(request.GET, default="30")
    sessions, _, _ = _report_querysets(request)
    rows = stats.in_range(sessions, rng).select_related("user", "book__author", "book__category").order_by("date")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="reading-report-{rng.start}-{rng.end}.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(["تاریخ", "تاریخ میلادی", "کاربر", "کتاب", "نویسنده", "دسته‌بندی", "دقیقه", "صفحات", "یادداشت"])
    for s in rows:
        writer.writerow([format_jalali(s.date, "short"), s.date.isoformat(), s.user.username, s.book.title,
                         s.book.author.name, s.book.category.name if s.book.category else "", s.minutes,
                         s.pages_read, s.note])
    return response
