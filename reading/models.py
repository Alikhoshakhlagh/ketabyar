"""
داده‌های «تجربه‌ی مطالعه»: قفسه، امتیاز، نقد، علاقه‌مندی، نقل‌قول، جلسه‌ی مطالعه و لاگ فعالیت.
"""
import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import Book

User = settings.AUTH_USER_MODEL


class ShelfEntry(models.Model):
    """وضعیت یک کتاب در قفسه‌ی یک کاربر."""

    class Status(models.TextChoices):
        TO_READ = "to_read", "برنامه‌ریزی برای مطالعه"
        READING = "reading", "در حال مطالعه"
        READ = "read", "مطالعه‌شده"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shelf_entries", verbose_name="کاربر")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="shelf_entries", verbose_name="کتاب")
    status = models.CharField("وضعیت", max_length=10, choices=Status.choices, default=Status.TO_READ)
    current_page = models.PositiveIntegerField("صفحه‌ی فعلی", default=0)
    started_on = models.DateField("تاریخ شروع", null=True, blank=True)
    finished_on = models.DateField("تاریخ پایان", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "کتاب در قفسه"
        verbose_name_plural = "قفسه‌ی کاربران"
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user", "book"], name="unique_shelf_entry")]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"{self.user} — {self.book} ({self.get_status_display()})"

    @property
    def progress(self):
        if self.status == self.Status.READ:
            return 100
        if not self.book.pages:
            return 0
        return min(100, round(self.current_page * 100 / self.book.pages))

    def apply_status(self, status, on_date=None):
        """تغییر وضعیت به همراه پر کردن خودکار تاریخ‌ها."""
        on_date = on_date or datetime.date.today()
        self.status = status
        if status == self.Status.READING and not self.started_on:
            self.started_on = on_date
        if status == self.Status.READ:
            self.started_on = self.started_on or on_date
            self.finished_on = self.finished_on or on_date
            if self.book.pages:
                self.current_page = self.book.pages
        if status != self.Status.READ:
            self.finished_on = None


class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings", verbose_name="کاربر")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="ratings", verbose_name="کتاب")
    score = models.PositiveSmallIntegerField("امتیاز", validators=[MinValueValidator(1), MaxValueValidator(5)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "امتیاز"
        verbose_name_plural = "امتیازها"
        constraints = [
            models.UniqueConstraint(fields=["user", "book"], name="unique_rating"),
            models.CheckConstraint(condition=models.Q(score__gte=1, score__lte=5), name="rating_score_1_5"),
        ]

    def __str__(self):
        return f"{self.user} → {self.book}: {self.score}"


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews", verbose_name="کاربر")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews", verbose_name="کتاب")
    title = models.CharField("عنوان نقد", max_length=150, blank=True)
    body = models.TextField("متن نقد و بررسی")
    has_spoiler = models.BooleanField("داستان را لو می‌دهد", default=False)
    is_hidden = models.BooleanField("پنهان‌شده توسط مدیر", default=False)
    likes = models.ManyToManyField(User, through="ReviewLike", related_name="liked_reviews", blank=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "نقد و بررسی"
        verbose_name_plural = "نقدها و بررسی‌ها"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "book"], name="unique_review")]

    def __str__(self):
        return f"نقد {self.user} بر {self.book}"


class ReviewLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    review = models.ForeignKey(Review, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "پسند نقد"
        verbose_name_plural = "پسندهای نقد"
        constraints = [models.UniqueConstraint(fields=["user", "review"], name="unique_review_like")]


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites", verbose_name="کاربر")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="favorited_by", verbose_name="کتاب")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "علاقه‌مندی"
        verbose_name_plural = "علاقه‌مندی‌ها"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "book"], name="unique_favorite")]

    def __str__(self):
        return f"{self.user} ♥ {self.book}"


class Quote(models.Model):
    class Kind(models.TextChoices):
        QUOTE = "quote", "نقل‌قول"
        HIGHLIGHT = "highlight", "هایلایت"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quotes", verbose_name="کاربر")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="quotes", verbose_name="کتاب")
    kind = models.CharField("نوع", max_length=10, choices=Kind.choices, default=Kind.QUOTE)
    text = models.TextField("متن")
    page = models.PositiveIntegerField("صفحه", null=True, blank=True)
    note = models.TextField("یادداشت شخصی", blank=True)
    is_public = models.BooleanField("نمایش عمومی", default=True)
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)

    class Meta:
        verbose_name = "نقل‌قول / هایلایت"
        verbose_name_plural = "نقل‌قول‌ها و هایلایت‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return self.text[:60]


class ReadingSession(models.Model):
    """یک نوبت مطالعه: چه روزی، چند دقیقه، از کدام صفحه تا کدام صفحه."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions", verbose_name="کاربر")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="sessions", verbose_name="کتاب")
    date = models.DateField("تاریخ", default=datetime.date.today, db_index=True)
    minutes = models.PositiveIntegerField("مدت (دقیقه)", validators=[MinValueValidator(1), MaxValueValidator(1440)])
    start_page = models.PositiveIntegerField("از صفحه", null=True, blank=True)
    end_page = models.PositiveIntegerField("تا صفحه", null=True, blank=True)
    pages_read = models.PositiveIntegerField("تعداد صفحات خوانده‌شده", default=0)
    note = models.CharField("یادداشت", max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "جلسه‌ی مطالعه"
        verbose_name_plural = "جلسه‌های مطالعه"
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.user} — {self.book} — {self.minutes} دقیقه"

    def save(self, *args, **kwargs):
        # اگر صفحه‌ی شروع و پایان داده شده، تعداد صفحات خودکار حساب می‌شود
        if self.start_page is not None and self.end_page is not None and self.end_page >= self.start_page:
            self.pages_read = self.end_page - self.start_page
        super().save(*args, **kwargs)

    @property
    def pages_per_hour(self):
        if not self.minutes:
            return 0
        return round(self.pages_read * 60 / self.minutes)


class Activity(models.Model):
    """لاگ فعالیت کاربران؛ مدیر از روی همین جدول بر فعالیت‌ها نظارت می‌کند."""

    class Verb(models.TextChoices):
        JOINED = "joined", "عضو شد"
        SHELF = "shelf", "وضعیت مطالعه را تغییر داد"
        RATED = "rated", "امتیاز داد"
        REVIEWED = "reviewed", "نقد نوشت"
        QUOTED = "quoted", "نقل‌قول ثبت کرد"
        FAVORITED = "favorited", "به علاقه‌مندی‌ها افزود"
        SESSION = "session", "جلسه‌ی مطالعه ثبت کرد"
        FINISHED = "finished", "کتاب را تمام کرد"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities", verbose_name="کاربر")
    verb = models.CharField("نوع فعالیت", max_length=12, choices=Verb.choices)
    book = models.ForeignKey(Book, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
                             verbose_name="کتاب")
    detail = models.CharField("جزئیات", max_length=200, blank=True)
    created_at = models.DateTimeField("زمان", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "فعالیت"
        verbose_name_plural = "لاگ فعالیت‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} {self.get_verb_display()}"
