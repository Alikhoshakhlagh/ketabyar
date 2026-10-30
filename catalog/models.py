from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, ExpressionWrapper, FloatField, Q, Value
from django.db.models.functions import Cast, Coalesce
from django.urls import reverse

# «میانگین وزنی»: هر کتاب انگار از قبل ۳ رأی با میانگین ۳.۵ دارد (برای رتبه‌بندی منصفانه)
BAYES_PRIOR_VOTES = 3
BAYES_PRIOR_MEAN = 3.5


class Category(models.Model):
    name = models.CharField("نام", max_length=80, unique=True)
    slug = models.SlugField("نامک (برای آدرس)", max_length=80, unique=True, allow_unicode=True)
    description = models.TextField("توضیحات", blank=True)
    color = models.CharField("رنگ", max_length=7, default="#2F6F5E",
                             help_text="کد رنگ هگز؛ جلد و نمودارهای این دسته با این رنگ نمایش داده می‌شوند.")

    class Meta:
        ordering = ["name"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:book_list") + f"?category={self.slug}"


class Author(models.Model):
    name = models.CharField("نام", max_length=150, unique=True)
    country = models.CharField("کشور", max_length=60, blank=True)
    birth_year = models.PositiveSmallIntegerField("سال تولد", null=True, blank=True)
    bio = models.TextField("زندگی‌نامه", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "نویسنده"
        verbose_name_plural = "نویسندگان"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:author_detail", args=[self.pk])


class BookQuerySet(models.QuerySet):
    def with_stats(self):
        """
        میانگین امتیاز، تعداد امتیاز، تعداد خواننده و «امتیاز وزنی» را به هر کتاب اضافه می‌کند.
        امتیاز وزنی = (۳×۳.۵ + میانگین×تعداد) ÷ (۳ + تعداد)
        """
        return self.annotate(
            avg_rating=Avg("ratings__score"),
            rating_count=Count("ratings", distinct=True),
            reader_count=Count("shelf_entries", filter=Q(shelf_entries__status="read"), distinct=True),
        ).annotate(
            weighted=ExpressionWrapper(
                (Value(BAYES_PRIOR_VOTES * BAYES_PRIOR_MEAN)
                 + Coalesce(Cast("avg_rating", FloatField()), Value(0.0)) * Cast("rating_count", FloatField()))
                / (Value(float(BAYES_PRIOR_VOTES)) + Cast("rating_count", FloatField())),
                output_field=FloatField(),
            )
        )

    def top_rated(self):
        return self.with_stats().order_by("-weighted", "-rating_count", "title")


class Book(models.Model):
    title = models.CharField("عنوان", max_length=200, db_index=True)
    subtitle = models.CharField("زیرعنوان", max_length=200, blank=True)
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="books", verbose_name="نویسنده")
    translator = models.CharField("مترجم", max_length=150, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="books", verbose_name="دسته‌بندی")
    publisher = models.CharField("ناشر", max_length=120, blank=True)
    publish_year = models.PositiveSmallIntegerField("سال انتشار", null=True, blank=True)
    pages = models.PositiveIntegerField("تعداد صفحات", default=0)
    isbn = models.CharField("شابک", max_length=20, blank=True)
    description = models.TextField("معرفی کتاب", blank=True)
    cover = models.ImageField("تصویر جلد", upload_to="covers/", blank=True,
                              help_text="اختیاری؛ اگر خالی باشد یک جلد رنگی خودکار ساخته می‌شود.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="+", verbose_name="ثبت‌کننده")
    created_at = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین ویرایش", auto_now=True)

    objects = BookQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "کتاب"
        verbose_name_plural = "کتاب‌ها"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("catalog:book_detail", args=[self.pk])

    @property
    def cover_color(self):
        return self.category.color if self.category else "#6B5B4B"

    @property
    def cover_variant(self):
        """یکی از ۴ طرح جلد خودکار، بر اساس شناسه‌ی کتاب"""
        return (self.pk or 0) % 4


def weighted_rating(avg, count):
    """
    میانگین وزنی (بیزی): کتابی که یک رأی ۵ دارد از کتابی با صد رأی ۴.۸ جلو نمی‌زند.
    """
    avg = avg or 0
    count = count or 0
    return (BAYES_PRIOR_VOTES * BAYES_PRIOR_MEAN + avg * count) / (BAYES_PRIOR_VOTES + count)
