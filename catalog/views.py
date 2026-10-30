from django import forms
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, render

from reading.models import Favorite, Quote, Rating, Review, ReviewLike, ShelfEntry
from reading.recommend import similar_books

from .models import Author, Book, Category

SORTS = {
    "top": ("بیشترین امتیاز", ["-weighted", "-rating_count"]),
    "popular": ("پرخواننده‌ترین", ["-reader_count", "-weighted"]),
    "newest": ("جدیدترین", ["-created_at"]),
    "title": ("عنوان (الفبایی)", ["title"]),
    "year": ("سال انتشار", ["-publish_year"]),
}


class BookFilterForm(forms.Form):
    """فرم جستجو و فیلتر پیشرفته (با متد GET، بدون نیاز به جاوااسکریپت)"""

    q = forms.CharField(label="جستجو", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "نام کتاب، نویسنده یا مترجم…", "type": "search"}))
    category = forms.ModelChoiceField(label="دسته‌بندی", queryset=Category.objects.all(), required=False,
                                      to_field_name="slug", empty_label="همه‌ی دسته‌ها")
    author = forms.ModelChoiceField(label="نویسنده", queryset=Author.objects.all(), required=False,
                                    empty_label="همه‌ی نویسندگان")
    year_from = forms.IntegerField(label="سال انتشار از", required=False,
                                   widget=forms.NumberInput(attrs={"placeholder": "مثلاً ۱۳۵۰"}))
    year_to = forms.IntegerField(label="تا", required=False,
                                 widget=forms.NumberInput(attrs={"placeholder": "مثلاً ۱۴۰۴"}))
    min_rating = forms.TypedChoiceField(label="حداقل امتیاز", required=False, coerce=int, empty_value=None,
                                        choices=[("", "فرقی نمی‌کند"), (4, "۴ ستاره به بالا"), (3, "۳ ستاره به بالا"),
                                                 (2, "۲ ستاره به بالا")])
    max_pages = forms.TypedChoiceField(label="حجم کتاب", required=False, coerce=int, empty_value=None,
                                       choices=[("", "همه"), (200, "کم‌حجم (تا ۲۰۰ صفحه)"),
                                                (400, "متوسط (تا ۴۰۰ صفحه)")])
    sort = forms.ChoiceField(label="مرتب‌سازی", required=False,
                             choices=[(k, v[0]) for k, v in SORTS.items()])


def book_list(request):
    form = BookFilterForm(request.GET or None)
    books = Book.objects.with_stats().select_related("author", "category")
    sort = "top"
    active_filters = 0
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            words = data["q"].split()
            for word in words:  # هر کلمه باید در عنوان یا نویسنده یا مترجم باشد
                books = books.filter(Q(title__icontains=word) | Q(subtitle__icontains=word)
                                     | Q(author__name__icontains=word) | Q(translator__icontains=word))
        if data["category"]:
            books = books.filter(category=data["category"])
        if data["author"]:
            books = books.filter(author=data["author"])
        if data["year_from"]:
            books = books.filter(publish_year__gte=data["year_from"])
        if data["year_to"]:
            books = books.filter(publish_year__lte=data["year_to"])
        if data["min_rating"]:
            books = books.filter(avg_rating__gte=data["min_rating"])
        if data["max_pages"]:
            books = books.filter(pages__lte=data["max_pages"])
        sort = data["sort"] or "top"
        active_filters = sum(1 for k in ("category", "author", "year_from", "year_to", "min_rating", "max_pages")
                             if data[k])
    books = books.order_by(*SORTS[sort][1], "pk")

    page = Paginator(books, 12).get_page(request.GET.get("page"))
    my_status = {}
    if request.user.is_authenticated:
        my_status = dict(ShelfEntry.objects.filter(user=request.user, book__in=page.object_list)
                         .values_list("book_id", "status"))
    for book in page.object_list:
        book.my_status = my_status.get(book.pk)

    return render(request, "catalog/book_list.html", {
        "form": form, "page_obj": page, "total": page.paginator.count,
        "categories": Category.objects.annotate(n=Count("books")),
        "active_filters": active_filters,
    })


def book_detail(request, pk):
    book = get_object_or_404(Book.objects.with_stats().select_related("author", "category"), pk=pk)
    user = request.user

    reviews = (Review.objects.filter(book=book, is_hidden=False)
               .select_related("user__profile")
               .annotate(like_count=Count("reviewlike")))
    if user.is_authenticated:
        reviews = reviews.annotate(liked=Exists(ReviewLike.objects.filter(review=OuterRef("pk"), user=user)))
    reviews = list(reviews.order_by("-like_count", "-created_at"))
    user_scores = dict(Rating.objects.filter(book=book, user__in=[r.user_id for r in reviews])
                       .values_list("user_id", "score"))
    for review in reviews:
        review.score = user_scores.get(review.user_id)

    distribution_raw = dict(Rating.objects.filter(book=book).order_by().values_list("score")
                            .annotate(c=Count("id")))
    total_ratings = sum(distribution_raw.values())
    distribution = [
        {"score": s, "count": distribution_raw.get(s, 0),
         "pct": round(distribution_raw.get(s, 0) * 100 / total_ratings) if total_ratings else 0}
        for s in range(5, 0, -1)
    ]

    status_counts = dict(ShelfEntry.objects.filter(book=book).order_by().values_list("status")
                         .annotate(c=Count("id")))

    context = {
        "book": book,
        "reviews": reviews,
        "distribution": distribution,
        "status_counts": status_counts,
        "fav_count": Favorite.objects.filter(book=book).count(),
        "quotes": (Quote.objects.filter(book=book, is_public=True, user__profile__is_public=True)
                   .select_related("user__profile")[:6]),
        "similar": similar_books(book),
        # برچسب کوتاه برای دکمه‌های وضعیت در ستون باریک کنار جلد
        "statuses": [("to_read", "می‌خواهم بخوانم"), ("reading", "در حال مطالعه"), ("read", "خوانده‌ام")],
    }
    if user.is_authenticated:
        context.update({
            "entry": ShelfEntry.objects.filter(user=user, book=book).first(),
            "my_rating": Rating.objects.filter(user=user, book=book).values_list("score", flat=True).first(),
            "is_favorite": Favorite.objects.filter(user=user, book=book).exists(),
            "my_review": next((r for r in reviews if r.user_id == user.pk), None)
                         or Review.objects.filter(user=user, book=book).first(),
            "my_quotes": Quote.objects.filter(user=user, book=book)[:5],
            "my_minutes": sum(user.sessions.filter(book=book).values_list("minutes", flat=True)),
        })
    return render(request, "catalog/book_detail.html", context)


def author_list(request):
    q = request.GET.get("q", "").strip()
    authors = Author.objects.annotate(n=Count("books"))
    if q:
        authors = authors.filter(name__icontains=q)
    return render(request, "catalog/author_list.html", {"authors": authors, "q": q})


def author_detail(request, pk):
    author = get_object_or_404(Author, pk=pk)
    books = Book.objects.top_rated().filter(author=author).select_related("author", "category")
    return render(request, "catalog/author_detail.html", {"author": author, "books": books})


def category_list(request):
    categories = Category.objects.annotate(n=Count("books")).order_by("-n", "name")
    for category in categories:
        category.samples = Book.objects.top_rated().filter(category=category).select_related("author", "category")[:3]
    return render(request, "catalog/category_list.html", {"categories": categories})
