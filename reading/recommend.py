"""
پیشنهاد هوشمند کتاب (بدون یادگیری ماشین، قابل توضیح در ارائه):

۱) محتوا‌محور: از روی علاقه‌مندی‌ها، امتیازها و قفسه‌ی کاربر، به هر «دسته» و هر «نویسنده» وزن می‌دهیم.
۲) مشارکتی: کاربرانی که همان کتاب‌های محبوب شما را پسندیده‌اند، چه کتاب‌های دیگری را پسندیده‌اند؟
۳) کیفیت عمومی: امتیاز وزنی (بیزی) کتاب.
امتیاز نهایی = وزن دسته + وزن نویسنده + امتیاز مشارکتی + کیفیت عمومی
"""
import math
from collections import Counter, defaultdict

from catalog.models import Book

from .models import Favorite, Rating, ShelfEntry

LIKED_SCORE = 4  # امتیاز ۴ و ۵ یعنی «پسندیده»


def _liked_book_ids(user):
    liked = set(Rating.objects.filter(user=user, score__gte=LIKED_SCORE).values_list("book_id", flat=True))
    liked |= set(Favorite.objects.filter(user=user).values_list("book_id", flat=True))
    return liked


def _co_liked(book_ids, exclude_user=None):
    """کتاب‌هایی که پسندکنندگانِ book_ids هم پسندیده‌اند، با تعداد تکرار"""
    if not book_ids:
        return Counter()
    fans = set(Rating.objects.filter(book_id__in=book_ids, score__gte=LIKED_SCORE).values_list("user_id", flat=True))
    fans |= set(Favorite.objects.filter(book_id__in=book_ids).values_list("user_id", flat=True))
    fans.discard(getattr(exclude_user, "pk", None))
    if not fans:
        return Counter()
    counter = Counter(Rating.objects.filter(user_id__in=fans, score__gte=LIKED_SCORE)
                      .exclude(book_id__in=book_ids).values_list("book_id", flat=True))
    counter.update(Favorite.objects.filter(user_id__in=fans).exclude(book_id__in=book_ids)
                   .values_list("book_id", flat=True))
    return counter


def recommend_for(user, limit=6):
    """فهرست [(کتاب، دلیل پیشنهاد)]"""
    if not user.is_authenticated:
        return [(b, "از پرامتیازترین‌ها") for b in Book.objects.top_rated().select_related("author", "category")[:limit]]

    cat_w, author_w = defaultdict(float), defaultdict(float)
    known = set()

    def add(book_id, cat_id, author_id, weight):
        known.add(book_id)
        if cat_id:
            cat_w[cat_id] += weight
        author_w[author_id] += weight * 1.2

    for f in Favorite.objects.filter(user=user).values("book_id", "book__category_id", "book__author_id"):
        add(f["book_id"], f["book__category_id"], f["book__author_id"], 3)
    for r in Rating.objects.filter(user=user).values("book_id", "score", "book__category_id", "book__author_id"):
        add(r["book_id"], r["book__category_id"], r["book__author_id"], (r["score"] - 3) * 1.5)
    shelf_weights = {"read": 1.0, "reading": 1.0, "to_read": 0.5}
    for e in ShelfEntry.objects.filter(user=user).values("book_id", "status", "book__category_id", "book__author_id"):
        add(e["book_id"], e["book__category_id"], e["book__author_id"], shelf_weights[e["status"]])

    if not known:
        return [(b, "از پرامتیازترین‌ها") for b in Book.objects.top_rated().select_related("author", "category")[:limit]]

    co_liked = _co_liked(_liked_book_ids(user), exclude_user=user)

    candidates = Book.objects.with_stats().exclude(pk__in=known).select_related("author", "category")
    scored = []
    for book in candidates:
        parts = {
            "category": cat_w.get(book.category_id, 0),
            "author": author_w.get(book.author_id, 0),
            "similar": co_liked.get(book.pk, 0) * 1.5,
        }
        quality = (book.weighted - 3) * 2 + math.log1p(book.reader_count) * 0.3
        total = sum(parts.values()) + quality
        if total <= 0:
            continue
        best = max(parts, key=parts.get)
        if parts[best] <= 0:
            reason = "از کتاب‌های پرامتیاز"
        elif best == "author":
            reason = f"چون آثار {book.author.name} را دوست دارید"
        elif best == "category":
            reason = f"بر اساس علاقه‌ی شما به «{book.category.name}»"
        else:
            reason = "خوانندگانی با سلیقه‌ی شما پسندیده‌اند"
        scored.append((total, book, reason))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [(book, reason) for _, book, reason in scored[:limit]]


def similar_books(book, limit=4):
    """«کسانی که این کتاب را پسندیدند، این‌ها را هم پسندیدند» + در صورت کمبود، هم‌نویسنده/هم‌دسته"""
    co = _co_liked({book.pk})
    ids = [book_id for book_id, _ in co.most_common(limit)]
    result = list(Book.objects.filter(pk__in=ids).select_related("author", "category"))
    result.sort(key=lambda b: ids.index(b.pk))
    if len(result) < limit:
        fallback = (Book.objects.top_rated().filter(category=book.category)
                    .exclude(pk__in=[book.pk, *ids]).select_related("author", "category"))
        same_author = (Book.objects.top_rated().filter(author=book.author)
                       .exclude(pk__in=[book.pk, *ids]).select_related("author", "category"))
        for candidate in list(same_author[:limit]) + list(fallback[:limit]):
            if len(result) >= limit:
                break
            if candidate not in result:
                result.append(candidate)
    return result
