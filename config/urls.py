from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "مدیریت فنی کتاب‌یار"
admin.site.site_title = "کتاب‌یار"
admin.site.index_title = "جداول پایگاه داده"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("books/", include("catalog.urls")),
    path("me/", include("reading.urls")),
    path("panel/", include("panel.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
