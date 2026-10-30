from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = "پروفایل"


admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = ["username", "first_name", "last_name", "email", "is_staff", "is_active", "date_joined"]

    def get_inline_instances(self, request, obj=None):
        # هنگام ساخت کاربر جدید، پروفایل را سیگنال می‌سازد؛ پس فرم پروفایل فقط در ویرایش نمایش داده می‌شود
        return super().get_inline_instances(request, obj) if obj else []
