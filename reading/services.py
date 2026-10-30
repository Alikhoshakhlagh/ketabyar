"""
منطق کسب‌وکار (business logic) بخش مطالعه.
ویوها فقط این توابع را صدا می‌زنند تا منطق در یک جا باشد و هر عمل در لاگ فعالیت ثبت شود.
"""
from django.db import transaction

from .models import Activity, Favorite, Rating, ReadingSession, ReviewLike, ShelfEntry

Status = ShelfEntry.Status


def log(user, verb, book=None, detail=""):
    Activity.objects.create(user=user, verb=verb, book=book, detail=detail[:200])


@transaction.atomic
def set_shelf_status(user, book, status, on_date=None):
    entry, created = ShelfEntry.objects.get_or_create(user=user, book=book)
    old_status = None if created else entry.status
    entry.apply_status(status, on_date)
    entry.save()
    if status == Status.READ and old_status != Status.READ:
        log(user, Activity.Verb.FINISHED, book)
    elif old_status != status:
        log(user, Activity.Verb.SHELF, book, entry.get_status_display())
    return entry


def remove_from_shelf(user, book):
    ShelfEntry.objects.filter(user=user, book=book).delete()


def update_progress(user, book, page):
    """صفحه‌ی فعلی را به‌روز می‌کند؛ اگر به آخر کتاب رسید، کتاب «مطالعه‌شده» می‌شود."""
    entry, _ = ShelfEntry.objects.get_or_create(user=user, book=book)
    if book.pages:
        page = min(page, book.pages)
    entry.current_page = page
    if entry.status == Status.TO_READ and page > 0:
        entry.apply_status(Status.READING)
    entry.save()
    if book.pages and page >= book.pages and entry.status != Status.READ:
        set_shelf_status(user, book, Status.READ)
    return entry


def rate(user, book, score):
    rating, created = Rating.objects.update_or_create(user=user, book=book, defaults={"score": score})
    log(user, Activity.Verb.RATED, book, f"{score} از ۵")
    return rating


def remove_rating(user, book):
    Rating.objects.filter(user=user, book=book).delete()


def toggle_favorite(user, book):
    """True یعنی الان در علاقه‌مندی‌هاست."""
    deleted, _ = Favorite.objects.filter(user=user, book=book).delete()
    if deleted:
        return False
    Favorite.objects.create(user=user, book=book)
    log(user, Activity.Verb.FAVORITED, book)
    return True


def toggle_review_like(user, review):
    deleted, _ = ReviewLike.objects.filter(user=user, review=review).delete()
    if deleted:
        return False
    ReviewLike.objects.create(user=user, review=review)
    return True


@transaction.atomic
def session_saved(session: ReadingSession, created: bool):
    """
    بعد از ثبت جلسه‌ی مطالعه، قفسه‌ی کاربر را هوشمندانه به‌روز می‌کند:
    - اگر کتاب در قفسه نیست یا «برای مطالعه» است → «در حال مطالعه»
    - صفحه‌ی فعلی جلو می‌رود
    - اگر به صفحه‌ی آخر رسید → «مطالعه‌شده» با تاریخ همان جلسه
    """
    user, book = session.user, session.book
    entry, _ = ShelfEntry.objects.get_or_create(user=user, book=book)
    if entry.status == Status.TO_READ:
        entry.apply_status(Status.READING, session.date)
    if entry.status == Status.READING and (not entry.started_on or entry.started_on > session.date):
        entry.started_on = session.date

    if session.end_page:
        entry.current_page = max(entry.current_page, session.end_page)
    elif created and session.pages_read:
        entry.current_page += session.pages_read
    if book.pages:
        entry.current_page = min(entry.current_page, book.pages)
    entry.save()

    if created:
        log(user, Activity.Verb.SESSION, book, f"{session.minutes} دقیقه")
    if book.pages and entry.current_page >= book.pages and entry.status != Status.READ:
        set_shelf_status(user, book, Status.READ, on_date=session.date)
