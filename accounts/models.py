from django.conf import settings
from django.db import models


class Profile(models.Model):
    """
    اطلاعات تکمیلی هر کاربر. خود کاربر (نام کاربری، رمز، ایمیل) در جدول User جنگو است.
    سطح دسترسی:
      - مهمان: کاربر لاگین‌نکرده
      - عضو: هر کاربر ثبت‌نام‌کرده
      - مدیر: کاربری که is_staff=True دارد
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile",
                                verbose_name="کاربر")
    bio = models.TextField("درباره‌ی من", blank=True, max_length=500)
    avatar = models.ImageField("تصویر پروفایل", upload_to="avatars/", blank=True)
    yearly_goal = models.PositiveSmallIntegerField("هدف سالانه (تعداد کتاب)", default=12)
    daily_goal_minutes = models.PositiveSmallIntegerField("هدف روزانه (دقیقه)", default=30)
    is_public = models.BooleanField("پروفایل عمومی باشد", default=True,
                                    help_text="اگر عمومی باشد، دیگران قفسه، نقدها و نقل‌قول‌های شما را می‌بینند.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "پروفایل"
        verbose_name_plural = "پروفایل‌ها"

    def __str__(self):
        return f"پروفایل {self.user.username}"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def initial(self):
        return (self.display_name or "?")[0]
